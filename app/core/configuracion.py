"""Configuración y preferencias de EntornoLab (archivo JSON portable).

Qué resuelve este módulo y por qué:

- **Valores por defecto en código** (``VALORES_POR_DEFECTO``), agrupados por
  secciones. El archivo solo guarda lo que el usuario tiene; al cargar se
  completa con los valores por defecto, así una preferencia nueva aparece sola
  y un archivo de una versión antigua sigue funcionando.
- **Archivo en ``data/config/config.json``**, junto al programa (portable).
- **Tolerancia a daños.** Un JSON corrupto se aparta como
  ``config.json.corrupto-AAAAMMDD_HHMMSS`` (no se pierde), se intenta la copia
  ``config.json.bak`` y, si tampoco sirve, se arranca con los valores por
  defecto. Todo queda registrado y ``recuperacion`` dice qué pasó para que la
  interfaz se lo cuente al usuario.
- **Escritura atómica**: temporal único en la misma carpeta + ``fsync`` +
  ``os.replace``. Un corte de luz deja el archivo viejo o el nuevo, nunca uno a
  medias. Antes se copia el archivo actual a ``.bak``.
- **Seguro entre hilos** (``RLock`` para los datos, otro candado para el disco:
  la interfaz no espera al ``fsync`` de un guardado de fondo).
- **Claves «seccion.clave»** con ``obtener``/``establecer``.
- **Versión de esquema y migraciones** (claves renombradas, movidas o
  eliminadas) que se aplican una sola vez al cargar.
- **Suscriptores**: las ventanas abiertas se enteran de cada cambio y aplican
  la preferencia al momento (sin reiniciar).
- **Validación** de tipos, rangos y opciones con ``REGLAS``.
- **Guardado inmediato, diferido (agrupa cambios rápidos) o por lotes.**

Cómo se usa::

	from app.core.configuracion import obtener_configuracion

	config = obtener_configuracion()
	motor = config.obtener("sonido.motor")
	config.establecer("sonido.volumen_maestro", 0.8)            # valida, guarda y avisa
	config.establecer_diferido("voz.velocidad", 60)              # agrupa el guardado
	config.establecer_varias({"juego.paso_m": 0.7, "juego.unidad": "pasos"})
	cancelar = config.suscribir(self._al_cambiar, prefijo="sonido.")

Diferencias deliberadas con la plantilla del agente «configuracion», para no
romper lo que el esqueleto y el resto del proyecto ya usaban:

- El archivo se sigue llamando ``config.json``.
- ``obtener(clave, defecto)`` devuelve ``defecto`` (``None`` si no se indica)
  cuando la clave no existe, en vez de lanzar ``KeyError``.
- ``guardar()`` devuelve ``True`` o ``False`` y nunca lanza: se llama al cerrar
  la aplicación y un disco lleno no debe impedir que la ventana se cierre.
- Cargar no escribe nada salvo que haya habido una migración o una
  recuperación: el Estudio y el reproductor leen el mismo archivo y no
  conviene que cada arranque lo reescriba.
- Se admiten claves de más de dos niveles (``teclado.mapa.juego``); solo se
  validan las de dos niveles, que son las que tienen valor por defecto.

Estudio y reproductor son dos procesos con el mismo archivo:

- **Guardar no pisa lo del otro proceso.** Cada instancia apunta qué claves
  ha cambiado ella desde la última vez que leyó o escribió el archivo. Si al
  guardar el archivo ha cambiado en disco (lo guardó el otro proceso), se
  vuelve a leer y se escriben SUS valores más los cambios propios; lo del
  otro queda en memoria y se avisa de ello en la siguiente ``recargar()``.
- **``recargar()``** vuelve a leer el archivo y avisa a los suscriptores de
  cada clave que haya cambiado (así se aplica «en caliente» lo que cambió el
  otro proceso con los mismos manejadores de siempre). ``cargar()`` relee sin
  avisar.

Queda una ventana mínima (entre leer y reemplazar el archivo al guardar) en
la que dos guardados simultáneos pueden cruzarse; no hay bloqueo entre
procesos porque en Windows un candado de archivo mal soltado dejaría la
configuración inservible hasta reiniciar.

Los secretos (contraseñas, tokens) NO van aquí: van cifrados en
``data/config/secretos.dat`` (módulo ``secretos``).
"""

from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import threading
import time
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core import paths

log = logging.getLogger(__name__)

NOMBRE_ARCHIVO = "config.json"

# Clave de la raíz del JSON donde se guarda la versión del esquema.
CLAVE_VERSION = "version_esquema"

# Versión actual del esquema. Súbala cuando añada una migración.
# 2: «voz.salida» pasa de dos valores (lector, sapi) a cuatro (automatica, lector, sapi, ninguna).
VERSION_ESQUEMA = 2

# ── Valores por defecto ──────────────────────────────────────────────────────
# Un diccionario por sección. Cada valor fija también el TIPO esperado: si en el
# archivo aparece otro tipo (una cadena donde va un número), se descarta y se
# usa el valor por defecto. Un entero vale donde se espera un decimal.
VALORES_POR_DEFECTO: dict[str, dict[str, Any]] = {
	"general": {
		# Código de idioma («en», «pt_BR») o «auto» para el de Windows.
		"idioma": "auto",
		# Enseñar las novedades una vez tras actualizar a una versión nueva.
		"comprobar_novedades": True,
		# Colores del Estudio: los de Windows, claro u oscuro.
		"estilo_visual": "sistema",
		# Tamaño del texto del Estudio y del plano, en porcentaje.
		"tamano_texto": 100,
		# Colores de alto contraste en el plano gráfico y en el reproductor.
		"alto_contraste": False,
		# Voz al arrancar (solo si hay lector de pantalla o SAPI disponibles).
		"anunciar_arranque": True,
		# Opciones de bandeja desactivadas de serie: hay usuarios cuya bandeja
		# oculta los iconos y perderían el acceso a la ventana.
		"minimizar_a_bandeja": False,
		"cerrar_a_bandeja": False,
		"iniciar_en_bandeja": False,
	},
	"ventana": {
		# -1 = sin posición guardada: se centra en la pantalla.
		"x": -1,
		"y": -1,
		"ancho": 800,
		"alto": 600,
		"maximizada": False,
		"barra_estado": True,
	},
	"registro": {
		"nivel": "INFO",
	},
	"sonido": {
		# Motor preferido; si falla se cae al siguiente: openal, clasico, estereo, nulo.
		"motor": "openal",
		# Nombre del dispositivo de salida; vacío = el predeterminado de Windows.
		"dispositivo": "",
		# Dispositivo donde el profesional oye lo mismo que el alumno; vacío = ninguno.
		"segunda_salida": "",
		# Perfil de cabeza HRTF de OpenAL Soft; vacío = el predeterminado.
		"perfil_hrtf": "",
		# Con auriculares se usa sonido binaural; con altavoces, paneo.
		"modo_salida": "auriculares",
		# Volumen de cada bus, de 0 a 1.
		"volumen_maestro": 1.0,
		"volumen_efectos": 1.0,
		"volumen_pasos": 1.0,
		"volumen_ambiente": 0.7,
		"volumen_ayudas": 1.0,
		"volumen_interfaz": 0.8,
		"volumen_musica": 0.5,
		"volumen_voz": 1.0,
		# Techo de volumen y subidas graduales (protege el oído con auriculares).
		"proteccion_auditiva": True,
		# Filtro que apaga el sonido que llega por detrás, para distinguirlo.
		"refuerzo_detras": True,
		# Seguimiento de cabeza por OpenTrack (UDP).
		"seguimiento_cabeza": False,
		"seguimiento_cabeza_puerto": 4242,
		# Paquete de sonidos (una carpeta de data/sounds). Se cambia en caliente.
		"paquete": "por_defecto",
		# Llevar los sonidos de los demás paquetes al nivel de los de serie.
		"igualar_paquetes": True,
		# Ajuste de volumen de sonidos concretos: nombre → factor de 0,3 a 2. Vacío = todos como vienen.
		"volumen_sonidos": {},
	},
	"voz": {
		# Quién habla: «automatica» (el lector de pantalla activo y, si no hay, SAPI), «lector» (solo el
		# lector de pantalla; sin él no se habla), «sapi» (siempre la voz de Windows) o «ninguna» (no se
		# habla nunca; el historial y el braille siguen). Ver docs/voz.md.
		"salida": "automatica",
		# Nombre de la voz SAPI; vacío = la predeterminada de Windows.
		"voz_sapi": "",
		# Velocidad y volumen de SAPI, de 0 a 100.
		"velocidad": 50,
		"volumen": 100,
		# Enviar también los mensajes a la línea braille.
		"braille": True,
		# Un mensaje nuevo corta el que se está diciendo.
		"interrumpir": True,
		# Mensajes que se guardan para repasarlos con «anterior» y «siguiente».
		"historial": 50,
		# Cuánto cuenta el juego: 0 mínimo, 3 máximo.
		"detalle": 2,
		# Canales de voz activados.
		"canales": {"juego": True, "ayuda": True, "aviso": True, "profesional": True},
	},
	"juego": {
		"modo_movimiento": "pasos",
		# Longitud de un paso, en metros.
		"paso_m": 0.6,
		# Cuánto gira cada pulsación, en grados.
		"giro_grados": 45.0,
		# Velocidad en el modo continuo, en metros por segundo.
		"velocidad_ms": 1.2,
		"formato_direccion": "reloj",
		"unidad": "metros",
		"estilo": "adulto",
		# Reproductor: dibujar el plano de la planta (baja visión y acompañantes).
		"ver_plano": True,
		# Reproductor: pantalla en negro (no dibuja nada; para quien no la usa o no quiere pistas visuales).
		"pantalla_negra": False,
		# Reproductor: decir la posición en los menús («3 de 9»).
		"posicion_menu": True,
		# Reproductor: último alias con el que se jugó en este equipo (nunca un nombre real).
		"alias": "",
	},
	"teclado": {
		# Contexto → acción → teclas. Vacío = el mapa de serie de app/entrada.
		"mapa": {},
	},
	"mando": {
		# Contexto → acción → botones. Vacío = el mapa de serie de app/entrada.
		"mapa": {},
		# Recorrido de la palanca que se ignora, de 0 a 0,9.
		"zona_muerta": 0.2,
		"vibracion": True,
		# Fuerza de la vibración, de 0 a 1.
		"fuerza_vibracion": 1.0,
	},
	"editor": {
		# Ajustar a la cuadrícula al dibujar y mover.
		"cuadricula": True,
		# Separación de la cuadrícula, en metros.
		"paso_cuadricula": 0.5,
		# Desplazamiento más fino con el teclado, en metros.
		"paso_minimo_m": 0.05,
		"deshacer_niveles": 100,
		# Minutos entre autoguardados; 0 = desactivado.
		"autoguardado_min": 5,
		# Carpeta de los entornos del profesional; vacío = data/entornos.
		"carpeta_entornos": "",
		# Paso libre mínimo, en metros, que debe quedar al colocar un objeto (bastón o perro guía).
		"paso_libre_m": 0.8,
		# Últimos entornos abiertos, del más reciente al más antiguo (rutas).
		"recientes": [],
		# Cuántos entornos recientes se recuerdan.
		"max_recientes": 10,
		# Enseñar el plano gráfico junto al árbol y la lista.
		"plano_visible": True,
	},
	"supervision": {
		# Puerto TCP de la sala del Estudio.
		"puerto": 47900,
		# Decir por voz al profesional lo que le ocurre al alumno.
		"anunciar_eventos": True,
		# Qué sucesos se anuncian, separados por comas (conexion, choque, ayuda, premio, objetivo,
		# cruce_inseguro, entrada_espacio, fin, codigo, voz). Se elige en la ventana de supervisión.
		"eventos_anunciados": "conexion,choque,ayuda,premio,objetivo,cruce_inseguro,fin,codigo",
		# Enviar el sonido del alumno también a sonido.segunda_salida.
		"segunda_salida": False,
		# Reproductor: última sala escrita a mano en «Conectar con mi profesor» (equipo:puerto).
		"ultima_sala": "",
	},
	"privacidad": {
		# Cifrar con la contraseña del profesional los datos personales de las fichas.
		"cifrar_fichas": True,
		# Días que se conservan las sesiones; 0 = sin caducidad.
		"caducidad_dias": 0,
	},
	"accesibilidad": {
		# Qué se lee al moverse por una lista de varias columnas.
		"leer_columnas": "todas",
		# Decir el nombre de la columna antes de su valor.
		"leer_cabeceras": True,
		# Anunciar por voz el avance de las tareas largas.
		"anunciar_progreso": True,
		# Cada cuánto se anuncia, en puntos de porcentaje.
		"progreso_cada": 25,
		# Sonidos breves de la interfaz del Estudio (abrir, guardar, error).
		"sonidos_interfaz": True,
	},
	"actualizaciones": {
		# Comprobar al arrancar si hay versión nueva. Apagado de fábrica: la aplicación
		# no se conecta a Internet sin permiso; la primera vez PREGUNTA (ver «preguntado»).
		"comprobar_al_arrancar": False,
		# De dónde se toman las versiones: «estable» o «pruebas» (versiones preliminares).
		"canal": "estable",
		# Versión que el usuario pidió no volver a ofrecer en la comprobación automática.
		"version_saltada": "",
		# Fecha (ISO, UTC) de la última comprobación correcta; vacía si nunca se hizo.
		"ultima_comprobacion": "",
		# True cuando ya se preguntó si se quiere la comprobación al arrancar.
		"preguntado": False,
	},
	"complementos": {
		# Dirección del índice firmado del catálogo en línea; vacía = la oficial.
		"url_catalogo": "",
		# Mirar el catálogo al comprobar actualizaciones al arrancar (mismo permiso).
		"comprobar_actualizaciones": True,
		# Complementos instalados que el profesional ha desactivado (ids): no salen en el catálogo.
		"desactivados": [],
	},
	"importar": {
		# Servidor Overpass propio para descargar de OpenStreetMap; vacío = los públicos.
		"overpass_url": "",
		# Servidor Nominatim propio para buscar lugares; vacío = el público.
		"nominatim_url": "",
		# Radio de la zona que se propone al importar de OpenStreetMap, en metros.
		"radio_m": 150,
		# True cuando el profesional ya leyó y aceptó el aviso de privacidad de OpenStreetMap.
		"aviso_privacidad_visto": False,
	},
}


@dataclass(frozen=True)
class Regla:
	"""Restricciones opcionales de una clave.

	:param minimo: valor mínimo (números).
	:param maximo: valor máximo (números).
	:param opciones: valores admitidos (listas cerradas: motor, unidad...).
	:param longitud_maxima: longitud máxima (textos).
	"""

	minimo: float | None = None
	maximo: float | None = None
	opciones: tuple[Any, ...] | None = None
	longitud_maxima: int | None = None


_VOLUMEN = Regla(minimo=0.0, maximo=1.0)

# Reglas por clave «seccion.clave». Las claves sin regla solo comprueban el tipo.
REGLAS: dict[str, Regla] = {
	"general.idioma": Regla(longitud_maxima=16),
	"general.estilo_visual": Regla(opciones=("sistema", "claro", "oscuro")),
	"general.tamano_texto": Regla(minimo=75, maximo=300),
	# El mínimo real lo decide la ventana (un valor demasiado pequeño se sustituye por el estándar).
	"ventana.ancho": Regla(minimo=1, maximo=20000),
	"ventana.alto": Regla(minimo=1, maximo=20000),
	"registro.nivel": Regla(opciones=("DEBUG", "INFO", "WARNING", "ERROR")),
	"sonido.motor": Regla(opciones=("openal", "clasico", "estereo", "bass", "nulo")),
	"sonido.dispositivo": Regla(longitud_maxima=255),
	"sonido.segunda_salida": Regla(longitud_maxima=255),
	"sonido.perfil_hrtf": Regla(longitud_maxima=255),
	"sonido.modo_salida": Regla(opciones=("auriculares", "altavoces")),
	"sonido.volumen_maestro": _VOLUMEN,
	"sonido.volumen_efectos": _VOLUMEN,
	"sonido.volumen_pasos": _VOLUMEN,
	"sonido.volumen_ambiente": _VOLUMEN,
	"sonido.volumen_ayudas": _VOLUMEN,
	"sonido.volumen_interfaz": _VOLUMEN,
	"sonido.volumen_musica": _VOLUMEN,
	"sonido.volumen_voz": _VOLUMEN,
	"sonido.seguimiento_cabeza_puerto": Regla(minimo=1024, maximo=65535),
	# El identificador es el nombre de la carpeta; si el paquete no existe, el banco usa el de por defecto.
	"sonido.paquete": Regla(longitud_maxima=64),
	"voz.salida": Regla(opciones=("automatica", "lector", "sapi", "ninguna")),
	"voz.voz_sapi": Regla(longitud_maxima=255),
	"voz.velocidad": Regla(minimo=0, maximo=100),
	"voz.volumen": Regla(minimo=0, maximo=100),
	"voz.historial": Regla(minimo=0, maximo=500),
	"voz.detalle": Regla(minimo=0, maximo=3),
	"juego.modo_movimiento": Regla(opciones=("pasos", "continuo", "brujula", "salas", "aceras")),
	"juego.paso_m": Regla(minimo=0.2, maximo=2.0),
	"juego.giro_grados": Regla(minimo=1.0, maximo=180.0),
	"juego.velocidad_ms": Regla(minimo=0.2, maximo=4.0),
	"juego.formato_direccion": Regla(opciones=("reloj", "lados", "cardinal", "grados")),
	"juego.unidad": Regla(opciones=("metros", "pasos")),
	"juego.estilo": Regla(opciones=("infantil", "juvenil", "adulto")),
	"juego.alias": Regla(longitud_maxima=60),
	"mando.zona_muerta": Regla(minimo=0.0, maximo=0.9),
	"mando.fuerza_vibracion": _VOLUMEN,
	"editor.paso_cuadricula": Regla(minimo=0.05, maximo=10.0),
	"editor.paso_minimo_m": Regla(minimo=0.01, maximo=1.0),
	"editor.deshacer_niveles": Regla(minimo=1, maximo=1000),
	"editor.autoguardado_min": Regla(minimo=0, maximo=120),
	"editor.carpeta_entornos": Regla(longitud_maxima=1024),
	"editor.paso_libre_m": Regla(minimo=0.4, maximo=2.0),
	"editor.max_recientes": Regla(minimo=0, maximo=30),
	"supervision.puerto": Regla(minimo=1024, maximo=65535),
	"supervision.eventos_anunciados": Regla(longitud_maxima=200),
	"supervision.ultima_sala": Regla(longitud_maxima=255),
	"privacidad.caducidad_dias": Regla(minimo=0, maximo=3650),
	"accesibilidad.leer_columnas": Regla(opciones=("todas", "primera")),
	"accesibilidad.progreso_cada": Regla(minimo=5, maximo=50),
	"actualizaciones.canal": Regla(opciones=("estable", "pruebas")),
	"actualizaciones.version_saltada": Regla(longitud_maxima=64),
	"actualizaciones.ultima_comprobacion": Regla(longitud_maxima=64),
	"complementos.url_catalogo": Regla(longitud_maxima=1024),
	"importar.overpass_url": Regla(longitud_maxima=1024),
	"importar.nominatim_url": Regla(longitud_maxima=1024),
	# El máximo coincide con RADIO_MAXIMO_M de app/importar/osm.py.
	"importar.radio_m": Regla(minimo=20, maximo=400),
}


class ErrorConfiguracion(Exception):
	"""Error de configuración que el llamante debe conocer (no se oculta)."""


class ErrorValidacion(ErrorConfiguracion, ValueError):
	"""Valor que no cumple el tipo o la regla de su clave."""


# ── Migraciones ──────────────────────────────────────────────────────────────


def renombrar_clave(datos: dict, antigua: str, nueva: str) -> bool:
	"""Mueve el valor de ``antigua`` a ``nueva`` (ambas «seccion.clave»).

	Si la clave nueva ya existe, gana la nueva (el usuario ya la configuró con
	una versión más reciente) y la antigua se elimina igualmente.

	:return: ``True`` si había algo que mover.
	"""
	sec_antigua, _sep, clave_antigua = antigua.partition(".")
	sec_nueva, _sep, clave_nueva = nueva.partition(".")
	origen = datos.get(sec_antigua)
	if not isinstance(origen, dict) or clave_antigua not in origen:
		return False
	valor = origen.pop(clave_antigua)
	destino = datos.setdefault(sec_nueva, {})
	if isinstance(destino, dict):
		destino.setdefault(clave_nueva, valor)
	if not origen:
		# Sección vacía tras el traslado: se elimina para no dejar restos.
		datos.pop(sec_antigua, None)
	return True


def eliminar_clave(datos: dict, clave: str) -> bool:
	"""Elimina una clave obsoleta. ``True`` si existía."""
	seccion, _sep, nombre = clave.partition(".")
	contenedor = datos.get(seccion)
	if isinstance(contenedor, dict) and nombre in contenedor:
		del contenedor[nombre]
		return True
	return False


# MIGRACIONES[n] lleva los datos de la versión n a la n+1. Cada función recibe
# el diccionario TAL COMO SE LEYÓ del archivo (antes de completar con los
# valores por defecto) y lo modifica en el sitio. Deben ser idempotentes.
# Ejemplo, el día que una clave cambie de nombre (y VERSION_ESQUEMA pase a 2):
#
# 	def _migrar_a_2(datos: dict) -> None:
# 		renombrar_clave(datos, "sonido.volumen", "sonido.volumen_maestro")
#
# 	MIGRACIONES = {1: _migrar_a_2}


def _migrar_a_2(datos: dict) -> None:
	"""«voz.salida» = «lector» de la versión 1 pasa a «automatica».

	En la versión 1, «lector» quería decir «el lector de pantalla y, si no hay,
	la voz de Windows». Desde la 2 ese comportamiento se llama «automatica» y
	«lector» significa «solo el lector de pantalla». Sin esta migración, quien
	tenía guardado «lector» y no usa lector de pantalla se quedaría sin voz al
	actualizar. Es idempotente: un «automatica» o un «sapi» no se tocan.
	"""
	seccion = datos.get("voz")
	if isinstance(seccion, dict) and seccion.get("salida") == "lector":
		seccion["salida"] = "automatica"


MIGRACIONES: dict[int, Callable[[dict], None]] = {1: _migrar_a_2}


# ── Rutas ────────────────────────────────────────────────────────────────────


def ruta_por_defecto() -> Path:
	"""``data/config/config.json`` (no crea la carpeta: se crea al guardar)."""
	return paths.ruta_datos() / "config" / NOMBRE_ARCHIVO


# ── Utilidades internas ──────────────────────────────────────────────────────

_SIN_VALOR = object()


def _fusionar(base: dict, encima: dict) -> None:
	"""Pone ``encima`` sobre ``base`` de forma recursiva.

	Las secciones y claves desconocidas se CONSERVAN: pueden ser de una versión
	más nueva de la aplicación o de un complemento, y descartarlas borraría la
	configuración del usuario al abrir una versión anterior.
	"""
	for clave, valor in encima.items():
		if isinstance(valor, dict) and isinstance(base.get(clave), dict):
			_fusionar(base[clave], valor)
		else:
			base[clave] = copy.deepcopy(valor)


def _diferencias(antes: dict, despues: dict) -> list[tuple[str, Any, Any]]:
	"""Claves «seccion.clave» que difieren entre dos estados, con su valor anterior y el nuevo.

	Se compara a dos niveles, que es lo que avisan los suscriptores: un mapa
	de teclas (``teclado.mapa``) cambia como una sola clave.
	"""
	cambios: list[tuple[str, Any, Any]] = []
	for seccion in list(antes) + [s for s in despues if s not in antes]:
		if seccion == CLAVE_VERSION:
			continue
		previa = antes.get(seccion)
		nueva = despues.get(seccion)
		if not isinstance(previa, dict) or not isinstance(nueva, dict):
			if previa != nueva:
				cambios.append((seccion, copy.deepcopy(previa), copy.deepcopy(nueva)))
			continue
		for nombre in list(previa) + [n for n in nueva if n not in previa]:
			valor_antes = previa.get(nombre)
			valor_despues = nueva.get(nombre)
			if valor_antes != valor_despues or type(valor_antes) is not type(valor_despues):
				cambios.append((f"{seccion}.{nombre}", copy.deepcopy(valor_antes), copy.deepcopy(valor_despues)))
	return cambios


def _tipo_compatible(valor: Any, referencia: Any) -> bool:
	"""Comprueba que ``valor`` tiene el tipo del valor por defecto ``referencia``.

	``bool`` es subclase de ``int`` en Python: se distinguen explícitamente para
	que ``True`` no pase por un número ni ``1`` por un booleano. Un ``int`` sí vale
	donde se espera ``float`` (el JSON escribe ``1.0`` como ``1`` a veces).
	"""
	if referencia is None:
		return True
	if isinstance(referencia, bool):
		return isinstance(valor, bool)
	if isinstance(referencia, int):
		return isinstance(valor, int) and not isinstance(valor, bool)
	if isinstance(referencia, float):
		return isinstance(valor, (int, float)) and not isinstance(valor, bool)
	return isinstance(valor, type(referencia))


def validar_valor(
	clave: str,
	valor: Any,
	reglas: dict[str, Regla] | None = None,
	por_defecto: dict | None = None,
) -> None:
	"""Lanza ``ErrorValidacion`` si ``valor`` no es válido para ``clave``.

	Solo se comprueban las claves de dos niveles («seccion.clave»): son las
	que tienen valor por defecto y, por tanto, un tipo de referencia.
	"""
	reglas = REGLAS if reglas is None else reglas
	por_defecto = VALORES_POR_DEFECTO if por_defecto is None else por_defecto
	seccion, _sep, nombre = clave.partition(".")
	contenedor = por_defecto.get(seccion, {})
	referencia = contenedor.get(nombre, _SIN_VALOR) if isinstance(contenedor, dict) else _SIN_VALOR
	if referencia is not _SIN_VALOR and not _tipo_compatible(valor, referencia):
		raise ErrorValidacion(f"«{clave}» espera {type(referencia).__name__} y recibió {type(valor).__name__}.")
	regla = reglas.get(clave)
	if regla is None:
		return
	if regla.opciones is not None and valor not in regla.opciones:
		raise ErrorValidacion(f"«{clave}» solo admite: {', '.join(map(str, regla.opciones))}.")
	if isinstance(valor, (int, float)) and not isinstance(valor, bool):
		if regla.minimo is not None and valor < regla.minimo:
			raise ErrorValidacion(f"«{clave}» debe ser como mínimo {regla.minimo}.")
		if regla.maximo is not None and valor > regla.maximo:
			raise ErrorValidacion(f"«{clave}» debe ser como máximo {regla.maximo}.")
	if isinstance(valor, str) and regla.longitud_maxima is not None and len(valor) > regla.longitud_maxima:
		raise ErrorValidacion(f"«{clave}» admite como máximo {regla.longitud_maxima} caracteres.")


def _con_tipo_de_fabrica(valor: Any, referencia: Any) -> Any:
	"""Devuelve ``valor`` con el tipo del valor de fábrica cuando son equivalentes.

	Un entero donde se espera un decimal se convierte: así quien lee
	``sonido.volumen_maestro`` recibe siempre un ``float`` (el JSON guarda
	``1.0`` como ``1`` según quién lo escriba) y ``1`` no cuenta como un
	cambio respecto de ``1.0``.
	"""
	if isinstance(referencia, float) and isinstance(valor, int) and not isinstance(valor, bool):
		return float(valor)
	return valor


def _reemplazar(origen: Path, destino: Path, intentos: int = 5) -> None:
	"""``os.replace`` con reintentos.

	En Windows el reemplazo falla con ``PermissionError`` (WinError 5 o 32) si
	un antivirus, el indexador o una copia de seguridad tiene el destino abierto
	un instante. Se reintenta con una espera corta antes de rendirse.
	"""
	espera = 0.05
	for intento in range(1, intentos + 1):
		try:
			os.replace(origen, destino)
			return
		except PermissionError:
			if intento == intentos:
				raise
			log.debug("Reemplazo de %s bloqueado, reintento %d", destino.name, intento, exc_info=True)
			time.sleep(espera)
			espera *= 2


class _Suscriptor:
	"""Función suscrita a los cambios, con referencia débil si es un método.

	Con una referencia normal, una ventana cerrada seguiría viva en memoria (y
	recibiendo avisos sobre controles ya destruidos). Con ``WeakMethod`` se
	borra sola cuando la ventana desaparece.
	"""

	def __init__(self, funcion: Callable[[str, Any, Any], None], prefijo: str) -> None:
		self.prefijo = prefijo
		if hasattr(funcion, "__self__") and hasattr(funcion, "__func__"):
			self._ref: Callable[[], Any] = weakref.WeakMethod(funcion)
		else:
			self._ref = lambda: funcion

	def funcion(self) -> Callable[[str, Any, Any], None] | None:
		"""La función suscrita, o ``None`` si su objeto ya no existe."""
		return self._ref()


# ── Clase principal ──────────────────────────────────────────────────────────


class Configuracion:
	"""Preferencias de la aplicación persistidas en JSON.

	:param ruta: archivo JSON (por defecto ``data/config/config.json``).
	:param por_defecto: valores por defecto (por defecto ``VALORES_POR_DEFECTO``).
	:param reglas: reglas de validación (por defecto ``REGLAS``).
	:param version: versión del esquema actual.
	:param migraciones: funciones de migración por versión de origen.
	"""

	def __init__(
		self,
		ruta: Path | str | None = None,
		por_defecto: dict[str, dict[str, Any]] | None = None,
		reglas: dict[str, Regla] | None = None,
		version: int = VERSION_ESQUEMA,
		migraciones: dict[int, Callable[[dict], None]] | None = None,
	) -> None:
		self.ruta = Path(ruta) if ruta is not None else ruta_por_defecto()
		self._por_defecto = copy.deepcopy(VALORES_POR_DEFECTO if por_defecto is None else por_defecto)
		self._reglas = REGLAS if reglas is None else reglas
		self._version = version
		self._migraciones = MIGRACIONES if migraciones is None else migraciones
		# Datos: RLock porque un suscriptor puede volver a leer la configuración.
		self._candado = threading.RLock()
		# Disco: separado del de datos para que obtener()/establecer() no esperen al fsync.
		self._candado_disco = threading.Lock()
		self._datos: dict[str, Any] = {}
		self._suscriptores: list[_Suscriptor] = []
		self._profundidad_lote = 0
		self._cambios_lote: list[tuple[str, Any, Any]] = []
		self._pendiente_lote = False
		self._temporizador: threading.Timer | None = None
		# No se sobrescribe un archivo que no se pudo LEER (permisos, disco): se
		# perdería la configuración real del usuario.
		self._guardado_bloqueado = False
		#: True si no existía archivo (primer arranque): útil para autodetectar idioma.
		self.primer_arranque = False
		#: Texto con lo que se recuperó al cargar (None si todo fue bien).
		self.recuperacion: str | None = None
		# Huella (fecha en ns, tamaño) del archivo la última vez que se leyó o se escribió desde aquí.
		self._sello: tuple[int, int] | None = None
		# Claves «seccion.clave» cambiadas en este proceso desde la última lectura o escritura.
		self._propias: set[str] = set()
		# Cambios del otro proceso absorbidos al guardar, pendientes de avisar en ``recargar``.
		self._externos: list[tuple[str, Any, Any]] = []
		self.cargar()

	# ── Carga ────────────────────────────────────────────────────────────────

	def _leer_json(self, ruta: Path) -> dict:
		"""Lee y decodifica ``ruta``. Lanza ``ValueError`` si no es un objeto JSON."""
		texto = ruta.read_text(encoding="utf-8")
		datos = json.loads(texto)
		if not isinstance(datos, dict):
			raise ValueError("el archivo no contiene un objeto JSON")
		return datos

	def _apartar_corrupto(self) -> Path | None:
		"""Copia el archivo dañado a ``config.json.corrupto-FECHA`` (se conserva para estudiarlo)."""
		marca = datetime.now().strftime("%Y%m%d_%H%M%S")
		destino = self.ruta.with_name(f"{self.ruta.name}.corrupto-{marca}")
		try:
			shutil.copy2(self.ruta, destino)
			return destino
		except OSError:
			log.exception("No se pudo apartar la configuración dañada %s", self.ruta)
			return None

	def cargar(self) -> None:
		"""Carga el archivo, lo migra, lo completa y lo valida.

		Nunca lanza por un archivo dañado: la aplicación debe poder arrancar.
		Se puede volver a llamar para ver lo que guardó otro proceso (el
		reproductor o el Estudio); no avisa a los suscriptores.
		"""
		with self._candado:
			self.recuperacion = None
			self._guardado_bloqueado = False
			self.primer_arranque = False
			reescribir = False
			try:
				existe = self.ruta.is_file()
			except OSError:
				existe = False
			if not existe:
				log.info("Sin archivo de configuración; se usan los valores por defecto (%s)", self.ruta)
				self.primer_arranque = True
				leidos: dict = {}
			else:
				try:
					leidos = self._leer_json(self.ruta)
				except (ValueError, UnicodeDecodeError) as error:
					apartado = self._apartar_corrupto()
					log.error("Configuración dañada (%s); copia apartada en %s", error, apartado)
					respaldo = self._leer_respaldo()
					if respaldo is not None:
						leidos = respaldo
						self.recuperacion = "La configuración estaba dañada y se ha recuperado la copia anterior."
					else:
						leidos = {}
						self.recuperacion = "La configuración estaba dañada y se han restablecido los valores de fábrica."
					reescribir = True
				except OSError:
					log.exception("No se pudo leer la configuración %s; no se sobrescribirá", self.ruta)
					self._guardado_bloqueado = True
					self.recuperacion = "No se pudo leer la configuración; se usan valores de fábrica sin guardar."
					leidos = {}

			if not self.primer_arranque:
				reescribir |= self._migrar(leidos)
			datos = copy.deepcopy(self._por_defecto)
			_fusionar(datos, leidos)
			saneado = self._sanear(datos)
			try:
				version_leida = int(leidos.get(CLAVE_VERSION, 0) or 0)
			except TypeError, ValueError:
				version_leida = 0
			datos[CLAVE_VERSION] = max(self._version, version_leida)
			self._datos = datos
			self._propias.clear()
			self._sello = self._sello_en_disco()
			# Solo se reescribe si se migró o se recuperó algo: completar las
			# claves que faltan no necesita tocar el disco.
			if reescribir or (saneado and not self.primer_arranque and not self._guardado_bloqueado):
				self.guardar()

	def _sello_en_disco(self) -> tuple[int, int] | None:
		"""(fecha de modificación en ns, tamaño) del archivo, o None si no existe o no se puede mirar."""
		try:
			estado = self.ruta.stat()
		except OSError:
			return None
		return (estado.st_mtime_ns, estado.st_size)

	def _absorber_externos(self) -> None:
		"""Si otro proceso ha guardado el archivo, toma sus valores y conserva solo los cambios propios.

		Se llama con el candado de datos cogido, justo antes de escribir. Los
		cambios ajenos quedan apuntados para avisar de ellos en ``recargar``
		(aquí no se avisa: guardar puede ocurrir en un hilo de temporizador).
		"""
		sello = self._sello_en_disco()
		if sello is None or sello == self._sello:
			return
		try:
			leidos = self._leer_json(self.ruta)
		except OSError, ValueError, UnicodeDecodeError:
			log.warning("La configuración cambió en disco pero no se pudo leer; se guarda la de este proceso", exc_info=True)
			return
		nuevos = copy.deepcopy(self._por_defecto)
		_fusionar(nuevos, leidos)
		self._sanear(nuevos)
		for clave in self._propias:
			seccion, _punto, nombre = clave.partition(".")
			propia = self._datos.get(seccion)
			if isinstance(propia, dict) and nombre in propia:
				destino = nuevos.setdefault(seccion, {})
				if isinstance(destino, dict):
					destino[nombre] = copy.deepcopy(propia[nombre])
		nuevos[CLAVE_VERSION] = self._datos.get(CLAVE_VERSION, self._version)
		diferencias = _diferencias(self._datos, nuevos)
		if diferencias:
			log.info("Configuración guardada por otro proceso: se conservan sus %d cambios", len(diferencias))
		self._externos.extend(diferencias)
		self._datos = nuevos

	def recargar(self) -> list[str]:
		"""Vuelve a leer el archivo (lo ha cambiado otro proceso) y avisa de cada clave que haya cambiado.

		Antes se guarda lo pendiente de este proceso, para no perderlo. Los
		suscriptores reciben los avisos como si el cambio se hubiera hecho
		aquí, en el hilo que llama. Devuelve las claves cambiadas.
		"""
		self.guardar_pendiente()
		with self._candado:
			hay_propias = bool(self._propias)
		if hay_propias:
			self.guardar()
		with self._candado:
			antes = copy.deepcopy(self._datos)
			externos, self._externos = self._externos, []
			cambiado_en_disco = self._sello_en_disco() != self._sello
		if cambiado_en_disco:
			self.cargar()
		with self._candado:
			nuevos = _diferencias(antes, self._datos)
		cambios: dict[str, tuple[Any, Any]] = {clave: (anterior, nuevo) for clave, anterior, nuevo in externos}
		for clave, anterior, nuevo in nuevos:
			cambios[clave] = (cambios[clave][0], nuevo) if clave in cambios else (anterior, nuevo)
		avisos = [(clave, anterior, nuevo) for clave, (anterior, nuevo) in cambios.items() if anterior != nuevo]
		if avisos:
			log.info("Configuración releída: %d cambios de otro proceso", len(avisos))
		self._notificar(avisos)
		return [clave for clave, _anterior, _nuevo in avisos]

	def _leer_respaldo(self) -> dict | None:
		"""Intenta ``config.json.bak`` (último guardado correcto)."""
		respaldo = self.ruta.with_name(self.ruta.name + ".bak")
		if not respaldo.is_file():
			return None
		try:
			datos = self._leer_json(respaldo)
			log.warning("Configuración recuperada desde %s", respaldo.name)
			return datos
		except OSError, ValueError, UnicodeDecodeError:
			log.exception("La copia %s tampoco es válida", respaldo.name)
			return None

	def _migrar(self, datos: dict) -> bool:
		"""Aplica las migraciones pendientes. Devuelve ``True`` si cambió algo."""
		try:
			actual = int(datos.get(CLAVE_VERSION, 1) or 1)
		except TypeError, ValueError:
			actual = 1
		if actual > self._version:
			# Archivo escrito por una versión MÁS NUEVA: no se toca su estructura.
			log.warning(
				"La configuración es de la versión de esquema %d y esta aplicación usa la %d; se conservan las claves desconocidas.",
				actual,
				self._version,
			)
			return False
		cambiado = False
		for version in range(actual, self._version):
			migracion = self._migraciones.get(version)
			if migracion is None:
				continue
			try:
				migracion(datos)
				log.info("Configuración migrada de la versión %d a la %d", version, version + 1)
				cambiado = True
			except Exception:  # noqa: BLE001 - una migración rota no debe impedir arrancar
				# Se sigue con lo que haya; el saneado posterior repone valores por defecto.
				log.exception("Falló la migración de configuración %d → %d", version, version + 1)
		datos[CLAVE_VERSION] = self._version
		return cambiado

	def _sanear(self, datos: dict) -> bool:
		"""Sustituye por su valor por defecto cada valor de tipo o rango inválido."""
		cambiado = False
		for seccion, claves in self._por_defecto.items():
			if not isinstance(datos.get(seccion), dict):
				log.warning("Sección «%s» inválida en la configuración; se restablece", seccion)
				datos[seccion] = copy.deepcopy(claves)
				cambiado = True
				continue
			for nombre, defecto in claves.items():
				clave = f"{seccion}.{nombre}"
				try:
					validar_valor(clave, datos[seccion].get(nombre), self._reglas, self._por_defecto)
				except ErrorValidacion as error:
					log.warning("Valor no válido en la configuración (%s); se usa el de fábrica", error)
					datos[seccion][nombre] = copy.deepcopy(defecto)
					cambiado = True
					continue
				# No cuenta como cambio: es el mismo valor con el tipo esperado.
				datos[seccion][nombre] = _con_tipo_de_fabrica(datos[seccion].get(nombre), defecto)
		return cambiado

	# ── Lectura y escritura de valores ───────────────────────────────────────

	def obtener(self, clave: str, defecto: Any = None) -> Any:
		"""Devuelve el valor de «seccion.clave», o ``defecto`` si la clave no existe.

		Devuelve una COPIA: modificar una lista o un diccionario devuelto no
		altera la configuración sin pasar por ``establecer`` (ni se salta los
		avisos). ``obtener("sonido")`` devuelve la sección entera.
		"""
		with self._candado:
			actual: Any = self._datos
			for parte in clave.split("."):
				if not isinstance(actual, dict) or parte not in actual:
					return defecto
				actual = actual[parte]
			return copy.deepcopy(actual)

	def valor_por_defecto(self, clave: str) -> Any:
		"""Valor de fábrica de «seccion.clave» (``KeyError`` si no existe)."""
		seccion, _sep, nombre = clave.partition(".")
		return copy.deepcopy(self._por_defecto[seccion][nombre])

	def claves(self) -> list[str]:
		"""Todas las claves «seccion.clave» conocidas (las de fábrica)."""
		return [f"{seccion}.{nombre}" for seccion, claves in self._por_defecto.items() for nombre in claves]

	def secciones(self) -> list[str]:
		"""Nombres de las secciones de fábrica, en su orden."""
		return list(self._por_defecto)

	def regla(self, clave: str) -> Regla | None:
		"""Regla de validación de la clave (``None`` si solo se comprueba el tipo)."""
		return self._reglas.get(clave)

	def validar(self, clave: str, valor: Any) -> None:
		"""Lanza ``ErrorValidacion`` si ``valor`` no sirve para ``clave`` (no cambia nada)."""
		validar_valor(clave, valor, self._reglas, self._por_defecto)

	def establecer(self, clave: str, valor: Any, *, guardar: bool = True) -> bool:
		"""Cambia «seccion.clave», guarda (si ``guardar``) y avisa a los suscriptores.

		:return: ``True`` si el valor cambió.
		:raises ErrorValidacion: si el valor no cumple su tipo o su regla.
		"""
		return self.establecer_varias({clave: valor}, guardar=guardar)

	def establecer_varias(self, cambios: dict[str, Any], *, guardar: bool = True) -> bool:
		"""Cambia varias claves con UN solo guardado. Valida todas antes de tocar nada.

		:return: ``True`` si cambió algún valor.
		:raises ErrorValidacion: si algún valor no es válido (no se cambia ninguno).
		:raises ErrorConfiguracion: si una clave está mal formada.
		"""
		for clave, valor in cambios.items():
			partes = clave.split(".")
			if len(partes) < 2 or not all(partes):
				raise ErrorConfiguracion(f"Clave mal formada: «{clave}» (se espera «seccion.clave»)")
			validar_valor(clave, valor, self._reglas, self._por_defecto)
		avisos: list[tuple[str, Any, Any]] = []
		with self._candado:
			for clave, valor in cambios.items():
				partes = clave.split(".")
				if len(partes) == 2:
					fabrica = self._por_defecto.get(partes[0], {})
					valor = _con_tipo_de_fabrica(valor, fabrica.get(partes[1]) if isinstance(fabrica, dict) else None)
				contenedor = self._datos
				for parte in partes[:-1]:
					siguiente = contenedor.get(parte)
					if not isinstance(siguiente, dict):
						siguiente = {}
						contenedor[parte] = siguiente
					contenedor = siguiente
				nombre = partes[-1]
				anterior = copy.deepcopy(contenedor.get(nombre))
				if nombre in contenedor and contenedor[nombre] == valor and type(contenedor[nombre]) is type(valor):
					continue
				contenedor[nombre] = copy.deepcopy(valor)
				avisos.append((clave, anterior, copy.deepcopy(valor)))
				self._propias.add(".".join(partes[:2]))
			if not avisos:
				return False
			if self._profundidad_lote > 0:
				self._cambios_lote.extend(avisos)
				self._pendiente_lote = self._pendiente_lote or guardar
				return True
		if guardar:
			self.guardar()
		self._notificar(avisos)
		return True

	def establecer_diferido(self, clave: str, valor: Any, retraso: float = 0.8) -> bool:
		"""Como ``establecer``, pero agrupa el guardado ``retraso`` segundos.

		Para controles que cambian muchas veces por segundo (volumen, velocidad):
		cada pulsación de flecha no debe escribir el archivo con ``fsync`` en el
		hilo de la interfaz. Llame a ``guardar_pendiente()`` al cerrar.
		"""
		cambiado = self.establecer(clave, valor, guardar=False)
		if cambiado:
			with self._candado:
				if self._temporizador is not None:
					self._temporizador.cancel()
				self._temporizador = threading.Timer(max(0.05, retraso), self._al_vencer_temporizador)
				self._temporizador.daemon = True
				self._temporizador.name = "config-guardado-diferido"
				self._temporizador.start()
		return cambiado

	def _al_vencer_temporizador(self) -> None:
		with self._candado:
			self._temporizador = None
		try:
			self.guardar()
		except Exception:  # noqa: BLE001 - en un hilo de temporizador nadie recogería la excepción
			log.exception("Falló el guardado diferido de la configuración")

	def guardar_pendiente(self) -> bool:
		"""Guarda YA si hay un guardado diferido en espera (al cerrar la aplicación).

		:return: ``False`` solo si había algo pendiente y no se pudo escribir.
		"""
		with self._candado:
			temporizador = self._temporizador
			self._temporizador = None
		if temporizador is not None:
			temporizador.cancel()
			return self.guardar()
		return True

	@contextmanager
	def lote(self) -> Iterator[Configuracion]:
		"""Agrupa varios ``establecer`` en un solo guardado y un solo reparto de avisos.

		Si el bloque lanza una excepción, lo ya cambiado se queda en memoria y se
		guarda igualmente (los cambios eran válidos uno a uno).
		"""
		with self._candado:
			self._profundidad_lote += 1
		try:
			yield self
		finally:
			avisos: list[tuple[str, Any, Any]] = []
			guardar = False
			with self._candado:
				self._profundidad_lote -= 1
				terminado = self._profundidad_lote == 0
				if terminado:
					avisos = self._cambios_lote
					self._cambios_lote = []
					guardar = self._pendiente_lote
					self._pendiente_lote = False
			if terminado:
				if guardar:
					self.guardar()
				self._notificar(avisos)

	def restablecer(self, seccion: str | None = None, *, guardar: bool = True) -> None:
		"""Vuelve a los valores de fábrica (todo o una sección) y avisa."""
		with self.lote():
			secciones = [seccion] if seccion else list(self._por_defecto)
			cambios = {
				f"{nombre_seccion}.{nombre}": copy.deepcopy(valor)
				for nombre_seccion in secciones
				for nombre, valor in self._por_defecto[nombre_seccion].items()
			}
			self.establecer_varias(cambios, guardar=guardar)
		log.info("Configuración restablecida a valores de fábrica: %s", seccion or "todas las secciones")

	# ── Guardado ─────────────────────────────────────────────────────────────

	def guardar(self) -> bool:
		"""Escribe el archivo de forma atómica y deja una copia ``.bak`` del anterior.

		No lanza excepciones: se llama al cerrar la aplicación y un disco lleno
		no debe impedir que la ventana se cierre. El fallo queda en el registro.

		:return: ``True`` si el archivo quedó escrito.
		"""
		with self._candado:
			if self._guardado_bloqueado:
				log.warning("Guardado omitido: el archivo original no se pudo leer y no se sobrescribe")
				return False
			# Lo que haya guardado el otro proceso (Estudio o reproductor) no se pisa: solo se escriben encima los cambios propios.
			self._absorber_externos()
			texto = json.dumps(self._datos, ensure_ascii=False, indent="\t", sort_keys=False)
			propias = set(self._propias)
		with self._candado_disco:
			carpeta = self.ruta.parent
			# Temporal ÚNICO (proceso + hilo) en la MISMA carpeta: os.replace solo es
			# atómico dentro del mismo volumen, y dos guardados no comparten temporal.
			temporal = carpeta / f"{self.ruta.name}.{os.getpid()}-{threading.get_ident()}.tmp"
			try:
				carpeta.mkdir(parents=True, exist_ok=True)
				with open(temporal, "w", encoding="utf-8", newline="\n") as archivo:
					archivo.write(texto)
					archivo.flush()
					os.fsync(archivo.fileno())
				if self.ruta.exists():
					try:
						shutil.copy2(self.ruta, self.ruta.with_name(self.ruta.name + ".bak"))
					except OSError:
						# Sin .bak se pierde una red de seguridad, no el guardado.
						log.warning("No se pudo actualizar la copia .bak de la configuración", exc_info=True)
				_reemplazar(temporal, self.ruta)
				with self._candado:
					self._sello = self._sello_en_disco()
					# Lo escrito ya está en el disco; una clave nueva cambiada mientras se escribía sigue pendiente.
					self._propias -= propias
			except OSError:
				log.exception("No se pudo guardar la configuración en %s", self.ruta)
				try:
					temporal.unlink(missing_ok=True)
				except OSError:
					log.debug("No se pudo borrar el temporal %s", temporal, exc_info=True)
				return False
		log.debug("Configuración guardada en %s", self.ruta)
		return True

	# ── Suscriptores ─────────────────────────────────────────────────────────

	def suscribir(self, funcion: Callable[[str, Any, Any], None], prefijo: str = "") -> Callable[[], None]:
		"""Avisa a ``funcion(clave, anterior, nuevo)`` de cada cambio.

		El aviso llega en el hilo que hizo el cambio. Si ``funcion`` toca
		controles wx, debe pasar por ``wx.CallAfter``.

		:param prefijo: solo claves que empiecen así (``"sonido."``).
		:return: función que cancela la suscripción.
		"""
		suscriptor = _Suscriptor(funcion, prefijo)
		with self._candado:
			self._suscriptores.append(suscriptor)

		def cancelar() -> None:
			with self._candado:
				if suscriptor in self._suscriptores:
					self._suscriptores.remove(suscriptor)

		return cancelar

	def _notificar(self, avisos: list[tuple[str, Any, Any]]) -> None:
		"""Reparte los avisos FUERA del candado (un suscriptor lento no bloquea a nadie)."""
		if not avisos:
			return
		with self._candado:
			vivos = [suscriptor for suscriptor in self._suscriptores if suscriptor.funcion() is not None]
			self._suscriptores = vivos
			suscriptores = list(vivos)
		for clave, anterior, nuevo in avisos:
			for suscriptor in suscriptores:
				if not clave.startswith(suscriptor.prefijo):
					continue
				funcion = suscriptor.funcion()
				if funcion is None:
					continue
				try:
					funcion(clave, anterior, nuevo)
				except Exception:  # noqa: BLE001 - un suscriptor roto no impide que los demás se enteren
					log.exception("Falló un suscriptor de la configuración al cambiar «%s»", clave)


# ── Instancia compartida ─────────────────────────────────────────────────────

_instancia: Configuracion | None = None
_candado_instancia = threading.Lock()


def obtener_configuracion() -> Configuracion:
	"""Instancia única, creada la primera vez que se pide (no al importar).

	Crearla al importar leería ``data`` durante las pruebas o al importar el
	módulo desde herramientas.
	"""
	global _instancia
	with _candado_instancia:
		if _instancia is None:
			_instancia = Configuracion()
		return _instancia


def establecer_configuracion(configuracion: Configuracion | None) -> None:
	"""Fija (o borra, con ``None``) la instancia compartida.

	La usa el arranque para que ``obtener_configuracion()`` devuelva la misma
	instancia que creó ``main.py``, y las pruebas para no arrastrar la de otra.
	"""
	global _instancia
	with _candado_instancia:
		_instancia = configuracion
