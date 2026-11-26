"""Actualización de EntornoLab desde GitHub, segura y con vuelta atrás.

EntornoLab se distribuye como una carpeta portable con dos ejecutables (el
Estudio y el reproductor). Este módulo la pone al día sin tocar los datos del
profesional ni de los alumnos. Sin wx: la interfaz está en
``app/ui/dialogo_actualizacion.py``.

De dónde sale la versión (el mismo esquema que usa Puerto Bravo):

- Canal «estable»: ``https://github.com/hxebolax/EntornoLab/releases/latest/download/version.json``.
  GitHub resuelve «latest» a la última publicación que no es preliminar.
- Canal «pruebas»: el ``version.json`` de la publicación fija de etiqueta
  ``pruebas``. Quien elige este canal recibe la versión más alta de las dos.

Flujo:

1. :func:`comprobar` descarga ``version.json`` (un fichero pequeño), VERIFICA su
   firma Ed25519 con la clave pública incrustada aquí antes de mirar ningún
   campo, compara versiones y aplica la protección contra retrocesos (nunca se
   acepta una versión menor que la última que arrancó bien en este equipo).
2. :func:`descargar` baja el ZIP (reanudable) sin pasar del tamaño firmado y
   :func:`verificar_paquete` comprueba tamaño y SHA-256.
3. :func:`extraer_seguro` valida TODAS las entradas (rutas absolutas, ``..``,
   enlaces, nombres reservados, tamaño) y separa el programa de los recursos de
   ``data``. Lo que el ZIP traiga para ``config``, ``db``, ``sessions``,
   ``entornos`` o ``logs`` se descarta. Un complemento de serie solo se copia si
   no pisa uno más nuevo o uno que instaló el usuario.
4. :func:`descargar_y_preparar` comprueba ANTES de cerrar nada que se puede
   escribir (Archivos de programa), que hay espacio y que las rutas caben, y
   anota el inventario de lo instalado. :func:`preparar_sustitucion` genera un
   ``.bat`` (y ``recuperar.bat``) y :func:`lanzar_sustitucion` lo lanza; la
   interfaz cierra el Estudio. El script espera a que se cierren el Estudio Y
   cualquier reproductor de esta carpeta, comprueba que ningún otro programa
   tiene en uso los ficheros (antivirus, indexador), aparta cada elemento del
   programa a la copia de seguridad RENOMBRÁNDOLO y coloca el nuevo (renombrar
   funciona con una DLL cargada y no necesita espacio), relanza la versión nueva
   con ``--tras-actualizar`` y espera el marcador de salud. Si algo falla,
   devuelve cada elemento a su sitio y comprueba con el inventario que la
   versión anterior ha quedado entera.
5. La versión nueva llama a :func:`confirmar_arranque` unos segundos después de
   abrir su ventana.
6. Si se va la luz a mitad, al arrancar :func:`recuperar_al_arrancar` ve el
   diario y lanza ``recuperar.bat``, que deshace la sustitución.

Por qué un ``.bat``: la aplicación compilada no trae un ``python.exe`` utilizable
(el intérprete va dentro de los ejecutables que hay que sustituir), mientras que
``cmd.exe`` y ``powershell`` están en todos los Windows admitidos.

Ficheros que no se dejan borrar (solo lectura, en uso, DLL cargadas): se borran
con reintentos quitando el atributo; si no, se apartan y se borran en el
siguiente arranque. La propia sustitución no borra ni sobrescribe nada: renombra.

Privacidad: solo se hacen peticiones ``GET`` a GitHub, sin ningún dato del
equipo, del profesional ni de los alumnos (ver ``app/core/red.py``). Nada se
comprueba sin permiso: la comprobación al arrancar está apagada de fábrica y
la aplicación pregunta una sola vez (:func:`debe_preguntar`).

Procede de la plantilla del agente «actualizador».
"""

from __future__ import annotations

import base64
import binascii
import errno
import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.parse
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core import descargas, paths, red
from app.core.configuracion import obtener_configuracion
from app.core.i18n import _
from app.core.version import APP_VERSION, EJECUTABLE_ESTUDIO, EJECUTABLE_REPRODUCTOR, NOMBRE_APLICACION

log = logging.getLogger(__name__)

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────
REPOSITORIO = "hxebolax/EntornoLab"
# «latest» es, en GitHub, la última publicación que NO está marcada como preliminar.
URL_ESTABLE = f"https://github.com/{REPOSITORIO}/releases/latest/download/version.json"
# Publicación fija, marcada como preliminar, cuyos recursos se sustituyen en cada versión de pruebas.
ETIQUETA_PRUEBAS = "pruebas"
URL_PRUEBAS = f"https://github.com/{REPOSITORIO}/releases/download/{ETIQUETA_PRUEBAS}/version.json"
CANALES = ("estable", "pruebas")
# Claves PÚBLICAS Ed25519 en hexadecimal (64 caracteres). Se acepta la firma de
# CUALQUIERA de ellas: así se puede rotar la clave publicando una versión que ya
# conozca la nueva antes de retirar la antigua. Vacía = se rechaza todo.
# La privada no está en el código ni en GitHub (ver tools/generar_claves.py).
CLAVES_PUBLICAS_ED25519: tuple[str, ...] = ("2fca72d3d36f25e7d2ddce22bcef39e68d7eca606736fa730550963a62e76cec",)
# Subcarpetas de data que son RECURSOS del programa y que una versión nueva
# refresca (añade o reemplaza ficheros, nunca borra). Todo lo demás de data
# (config, db, sessions, entornos, logs, cache, backups...) es del usuario y no
# se toca. «plugins» tiene además una regla propia: ver ``_complementos_a_saltar``.
DATA_ACTUALIZABLE: tuple[str, ...] = ("bin", "sounds", "locales", "docs", "icons", "ejemplos", "plugins")
CARPETA_COMPLEMENTOS = "plugins"
FICHA_COMPLEMENTO = "complemento.json"
# Lista de los complementos que viajan con la aplicación ({id: versión}); la
# escribe tools/publicar_version.py dentro del ZIP, en data/plugins.
FICHERO_DE_SERIE = "de_serie.json"
# Registro de los complementos instalados por el usuario (lo lleva
# app/services/complementos_en_linea.py); está en data/config: es del usuario.
REGISTRO_COMPLEMENTOS = "complementos.json"
# ─────────────────────────────────────────────────────────────────────────────

ARGUMENTO_TRAS_ACTUALIZAR = "--tras-actualizar"
CAMPO_FIRMA = "firma_ed25519"
# Segundos que la versión nueva tiene para escribir el marcador de salud.
ESPERA_SALUD = 60
# Segundos que el script espera a que el Estudio y los reproductores se cierren.
# Si no se cierran, la actualización se CANCELA: nunca se mata una aplicación
# que puede tener trabajo sin guardar o a un alumno en mitad de una sesión.
ESPERA_CIERRE = 90
# Segundos tras mostrar la ventana principal antes de confirmar el arranque.
RETRASO_CONFIRMACION = 5
# Horas mínimas entre dos comprobaciones automáticas.
HORAS_ENTRE_COMPROBACIONES = 24
MAX_MANIFIESTO = 256 * 1024
MAX_DESCARGA = 2 * 1024**3
MAX_EXPANDIDO = 4 * 1024**3
MAX_MIEMBROS = 50_000
# Reintentos (con espera creciente: 0,25 s, 0,5 s, 1 s... hasta 8 s) ante un
# archivo bloqueado por el antivirus, el indexador o una copia que se está
# cerrando. 7 reintentos son unos 30 segundos en el peor caso.
REINTENTOS_BLOQUEO = 7
# Espacio que debe quedar libre después de descomprimir: registros, diario y margen.
MARGEN_ESPACIO = 64 * 1024**2
# Longitud máxima de una ruta en Windows sin la opción de rutas largas activada.
LIMITE_RUTA = 259
_NOMBRES_RESERVADOS = {"con", "prn", "aux", "nul"} | {f"com{n}" for n in range(1, 10)} | {f"lpt{n}" for n in range(1, 10)}

Progreso = Callable[[str, int, int], None]
"""``progreso(fase, hecho, total)``; fases: descarga, verificacion, extraccion, preparacion."""


# ════════════════════════════════════════════════════════════════════════════
# Errores: el mensaje de cada uno está pensado para leérselo al usuario
# ════════════════════════════════════════════════════════════════════════════


class ErrorActualizacion(Exception):
	"""Error de actualización con un mensaje claro para el usuario."""

	#: True si tiene sentido ofrecer «Reintentar» (fallo pasajero de red).
	reintentar = False


class ErrorConexion(ErrorActualizacion):
	"""No se pudo hablar con el servidor o la descarga se interrumpió."""

	reintentar = True
	#: El gestor de tareas lo registra como aviso de una línea, sin traza.
	transitorio = True


class ErrorFirma(ErrorActualizacion):
	"""El manifiesto no está firmado, la firma no es válida o su contenido no es admisible."""


class ErrorVerificacion(ErrorActualizacion):
	"""El paquete descargado no coincide con el manifiesto (tamaño o SHA-256)."""


class ErrorPaquete(ErrorActualizacion):
	"""El ZIP es peligroso, inválido o no parece de esta aplicación."""


class ErrorRetroceso(ErrorActualizacion):
	"""El servidor ofrece una versión inferior a la última confirmada en este equipo."""


class ErrorCancelado(ErrorActualizacion):
	"""El usuario canceló la descarga (la parte descargada se conserva)."""


class ErrorPermisos(ErrorActualizacion):
	"""Windows no deja escribir en la carpeta de la aplicación (Archivos de programa, permisos)."""


class ErrorEspacio(ErrorActualizacion):
	"""No hay espacio libre suficiente en el disco de la aplicación."""


class ErrorRutaLarga(ErrorActualizacion):
	"""Alguna ruta de la versión nueva pasaría del límite de Windows."""


class ErrorEnCurso(ErrorActualizacion):
	"""Ya hay una sustitución en marcha o a medias en esta instalación."""


class VersionInvalida(ValueError):
	"""La cadena no es una versión reconocible."""


# ════════════════════════════════════════════════════════════════════════════
# Configuración y datos
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class Configuracion:
	"""Todo lo que el actualizador necesita saber de la instalación.

	Se pasa explícitamente (en lugar de leer variables globales) para que las
	pruebas trabajen sobre instalaciones falsas en carpetas temporales.
	"""

	version_actual: str
	carpeta_app: Path
	carpeta_datos: Path | None = None
	nombre_app: str = NOMBRE_APLICACION
	ejecutable: str = EJECUTABLE_ESTUDIO
	ejecutable_reproductor: str = EJECUTABLE_REPRODUCTOR
	url_estable: str = URL_ESTABLE
	url_pruebas: str = URL_PRUEBAS
	canal: str = "estable"
	claves_publicas: tuple[str, ...] = CLAVES_PUBLICAS_ED25519
	comando: list[str] | None = None
	data_actualizable: tuple[str, ...] = DATA_ACTUALIZABLE
	espera_salud: int = ESPERA_SALUD
	espera_cierre: int = ESPERA_CIERRE
	pid_a_esperar: int | None = None
	max_expandido: int = MAX_EXPANDIDO
	permitir_desde_codigo: bool = False
	reintentos_bloqueo: int = REINTENTOS_BLOQUEO
	#: Solo para las pruebas: «aplicar» provoca un fallo a mitad de la sustitución y
	#: «pausa» la detiene ahí para poder matar el script (corte de luz simulado).
	punto_de_fallo: str = ""

	def __post_init__(self) -> None:
		self.carpeta_app = Path(self.carpeta_app).resolve()
		self.carpeta_datos = Path(self.carpeta_datos).resolve() if self.carpeta_datos else self.carpeta_app / "data"
		if self.canal not in CANALES:
			self.canal = "estable"
		if self.comando is None:
			self.comando = _comando_por_defecto()

	@property
	def carpeta_trabajo(self) -> Path:
		"""Donde se descarga, se extrae y vive el script: dentro de ``data/temp``."""
		return self.carpeta_datos / "temp" / "actualizacion"

	@property
	def carpeta_respaldo(self) -> Path:
		"""Copia de seguridad del programa mientras la versión nueva no confirme su arranque."""
		return self.carpeta_datos / "temp" / "version_anterior"

	@property
	def archivo_estado(self) -> Path:
		"""Memoria contra retrocesos: la versión más alta que arrancó bien aquí."""
		return self.carpeta_datos / "config" / "actualizaciones.json"

	@property
	def marcador_salud(self) -> Path:
		"""Lo escribe la versión nueva al arrancar bien; el script lo espera."""
		return self.carpeta_trabajo / "salud.txt"

	@property
	def aviso_espera_salud(self) -> Path:
		"""Lo deja el script con la versión que espera: cualquier copia de esa versión confirma."""
		return self.carpeta_trabajo / "esperando_salud.txt"

	@property
	def archivo_resultado(self) -> Path:
		"""Lo deja el script al terminar: correcta, revertida, no_aplicada o rota."""
		return self.carpeta_trabajo / "resultado.txt"

	@property
	def registro_script(self) -> Path:
		"""Registro paso a paso del script de sustitución."""
		return self.carpeta_datos / "logs" / "actualizacion.log"

	@property
	def carpeta_complementos(self) -> Path:
		"""Complementos instalados (los de serie y los del usuario)."""
		return self.carpeta_datos / CARPETA_COMPLEMENTOS

	@property
	def diario(self) -> Path:
		"""Lo escribe el script mientras la instalación está a medias: si existe al arrancar, hubo un corte."""
		return self.carpeta_trabajo / "diario.txt"

	@property
	def inventario(self) -> Path:
		"""Ficheros del programa antes de actualizar (ruta y tamaño): la vuelta atrás se comprueba con él."""
		return self.carpeta_trabajo / "original.txt"

	@property
	def lista_nuevos(self) -> Path:
		"""Ficheros que escribe la versión nueva; la vuelta atrás quita los que no existían antes."""
		return self.carpeta_trabajo / "nuevos.txt"

	@property
	def motor(self) -> Path:
		"""Guion de PowerShell que mueve los ficheros con reintentos (lo llama el .bat)."""
		return self.carpeta_trabajo / "sustituir.ps1"

	@property
	def script_recuperar(self) -> Path:
		"""Script que deshace una sustitución interrumpida; también se puede ejecutar a mano."""
		return self.carpeta_trabajo / "recuperar.bat"

	@property
	def pid_script(self) -> Path:
		"""PID del cmd.exe que ejecuta el script: así se sabe si sigue en marcha."""
		return self.carpeta_trabajo / "pid_script.txt"

	@property
	def carpeta_por_borrar(self) -> Path:
		"""Restos que no se dejaron borrar (en uso); se borran en el siguiente arranque."""
		return self.carpeta_trabajo / "por_borrar"


def _comando_por_defecto() -> list[str]:
	"""Orden para relanzar el Estudio: el .exe compilado o ``python main.py``."""
	if paths.CONGELADA:
		return [sys.executable]
	return [sys.executable, str(paths.ruta_base() / "main.py")]


def configuracion_por_defecto(version_actual: str | None = None) -> Configuracion:
	"""Configuración de la aplicación en ejecución (portable: todo junto al programa).

	Respeta ``APP_DATA_DIR`` (pruebas y perfiles aparte) y el canal elegido en
	las preferencias.
	"""
	return Configuracion(
		version_actual=version_actual or APP_VERSION,
		carpeta_app=paths.ruta_base(),
		carpeta_datos=paths.ruta_datos(),
		canal=canal_elegido(),
	)


@dataclass(frozen=True)
class InfoActualizacion:
	"""Versión disponible, tal como la describe el manifiesto firmado."""

	version: str
	archivo: str
	url_zip: str
	sha256: str
	tamano: int
	fecha: str = ""
	novedades: str = ""
	canal: str = "estable"


def puede_instalar(config: Configuracion) -> bool:
	"""La sustitución solo se hace en la versión compilada.

	Desde el código fuente se puede comprobar y avisar, pero sustituir los
	ficheros del proyecto del desarrollador con un ZIP compilado sería destructivo.
	"""
	return paths.CONGELADA or config.permitir_desde_codigo


# ════════════════════════════════════════════════════════════════════════════
# Preferencias (data/config/config.json, sección «actualizaciones»)
# ════════════════════════════════════════════════════════════════════════════


def canal_elegido() -> str:
	"""Canal de las preferencias: «estable» o «pruebas»."""
	canal = str(obtener_configuracion().obtener("actualizaciones.canal"))
	return canal if canal in CANALES else "estable"


def establecer_canal(canal: str) -> None:
	"""Guarda el canal del que se toman las versiones."""
	if canal not in CANALES:
		raise ValueError(f"Canal no válido: {canal!r}")
	obtener_configuracion().establecer("actualizaciones.canal", canal)


def debe_preguntar() -> bool:
	"""True mientras no se haya preguntado si se quiere comprobar al arrancar.

	La aplicación no se conecta a Internet sin permiso: la comprobación al
	arrancar está apagada de fábrica y se ofrece UNA vez, con una pregunta clara.
	"""
	return not bool(obtener_configuracion().obtener("actualizaciones.preguntado"))


def comprobacion_al_arrancar() -> bool:
	"""True si el usuario dio permiso para comprobar al arrancar."""
	return bool(obtener_configuracion().obtener("actualizaciones.comprobar_al_arrancar"))


def establecer_comprobacion_al_arrancar(activar: bool) -> None:
	"""Guarda la respuesta del usuario y anota que ya se le preguntó."""
	obtener_configuracion().establecer_varias({"actualizaciones.comprobar_al_arrancar": bool(activar), "actualizaciones.preguntado": True})
	log.info("Comprobación de actualizaciones al arrancar: %s", "activada" if activar else "desactivada")


def toca_comprobar(ahora: datetime | None = None, horas: float = HORAS_ENTRE_COMPROBACIONES) -> bool:
	"""True si hay permiso y han pasado ``horas`` desde la última comprobación automática."""
	if not comprobacion_al_arrancar():
		return False
	ultima = str(obtener_configuracion().obtener("actualizaciones.ultima_comprobacion") or "")
	if not ultima:
		return True
	try:
		transcurrido = ((ahora or datetime.now(timezone.utc)) - datetime.fromisoformat(ultima)).total_seconds()
	except TypeError, ValueError:
		log.debug("Fecha de última comprobación no válida: %r", ultima)
		return True
	return transcurrido >= horas * 3600 or transcurrido < 0


def _anotar_comprobacion() -> None:
	try:
		obtener_configuracion().establecer("actualizaciones.ultima_comprobacion", datetime.now(timezone.utc).isoformat(timespec="seconds"))
	except OSError, ValueError:
		log.warning("No se pudo anotar la fecha de la comprobación", exc_info=True)


def version_saltada() -> str:
	"""Versión que el usuario pidió no volver a ofrecer en la comprobación automática."""
	return str(obtener_configuracion().obtener("actualizaciones.version_saltada") or "")


def saltar_version(version: str) -> None:
	"""Recuerda que el usuario no quiere que se le ofrezca esta versión (vacía = ninguna)."""
	log.info("El usuario salta la versión %s", version or "(ninguna)")
	obtener_configuracion().establecer("actualizaciones.version_saltada", str(version)[:64])


# ════════════════════════════════════════════════════════════════════════════
# Versiones (semver sencillo + PEP 440 básico, sin dependencias)
# ════════════════════════════════════════════════════════════════════════════

_PATRON_VERSION = re.compile(
	r"""
	^\s*v?
	(?P<release>\d+(?:\.\d+)*)
	(?:[-_.]?(?P<pre_l>alpha|beta|preview|pre|rc|a|b|c)[-_.]?(?P<pre_n>\d+)?)?
	(?:(?:[-_.]?(?P<post_l>post|rev|r)[-_.]?(?P<post_n>\d+)?)|(?:-(?P<post_implicito>\d+)))?
	(?:[-_.]?(?P<dev_l>dev)[-_.]?(?P<dev_n>\d+)?)?
	(?:\+(?P<local>[a-z0-9]+(?:[-_.][a-z0-9]+)*))?
	\s*$
	""",
	re.VERBOSE | re.IGNORECASE,
)
_RANGO_PRE = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "c": 2, "rc": 2, "pre": 2, "preview": 2}


def clave_version(texto: str) -> tuple:
	"""Convierte una versión en una tupla ordenable según PEP 440.

	Orden: ``1.0.dev1 < 1.0a1 < 1.0b1 < 1.0rc1 < 1.0 == 1.0.0 < 1.0.post1``.
	Admite el semver habitual (``1.2.3-beta.1``). La parte local (``+abc``) no
	cuenta para el orden. ``1.0-1`` es una posterior (post), como en PEP 440.
	"""
	coincidencia = _PATRON_VERSION.match(str(texto or ""))
	if not coincidencia:
		raise VersionInvalida(f"Versión no válida: {texto!r}")
	release = tuple(int(parte) for parte in coincidencia["release"].split("."))
	while len(release) > 1 and release[-1] == 0:
		release = release[:-1]
	pre_l = coincidencia["pre_l"]
	post_presente = bool(coincidencia["post_l"] or coincidencia["post_implicito"])
	dev_presente = bool(coincidencia["dev_l"])
	if pre_l:
		pre = (0, _RANGO_PRE[pre_l.lower()], int(coincidencia["pre_n"] or 0))
	elif dev_presente and not post_presente:
		pre = (-1, 0, 0)  # 1.0.dev1 va antes que cualquier pre-versión de 1.0
	else:
		pre = (1, 0, 0)
	if post_presente:
		post = (1, int(coincidencia["post_n"] or coincidencia["post_implicito"] or 0))
	else:
		post = (0, 0)
	dev = (0, int(coincidencia["dev_n"] or 0)) if dev_presente else (1, 0)
	return (release, pre, post, dev)


def comparar_versiones(a: str, b: str) -> int:
	"""Devuelve -1, 0 o 1 según ``a`` sea menor, igual o mayor que ``b``."""
	clave_a, clave_b = clave_version(a), clave_version(b)
	return (clave_a > clave_b) - (clave_a < clave_b)


def es_mas_nueva(a: str, b: str) -> bool:
	"""Indica si ``a`` es estrictamente más nueva que ``b``."""
	return comparar_versiones(a, b) > 0


# ════════════════════════════════════════════════════════════════════════════
# Firma
# ════════════════════════════════════════════════════════════════════════════


def serializar_canonico(manifiesto: dict) -> bytes:
	"""Bytes exactos que se firman: JSON ordenado, separadores fijos, sin la firma.

	Debe ser IDÉNTICA a la de ``tools/firmar_version.py`` (una prueba lo
	comprueba). Firmar el manifiesto completo, y no solo «versión + sha», impide
	que alguien cambie las novedades, la URL o el tamaño sin invalidar la firma.
	"""
	datos = {clave: valor for clave, valor in manifiesto.items() if clave != CAMPO_FIRMA}
	return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def verificar_firma(manifiesto: dict, claves_publicas: tuple[str, ...] | list[str]) -> None:
	"""Comprueba la firma Ed25519 del manifiesto con alguna de las claves públicas.

	:raises ErrorFirma: sin claves, sin firma, firma mal formada o no válida.
	"""
	if not claves_publicas:
		raise ErrorFirma(
			_("La aplicación no tiene configurada ninguna clave de verificación; por seguridad no se aceptan actualizaciones.")
		)
	firma_b64 = manifiesto.get(CAMPO_FIRMA)
	if not isinstance(firma_b64, str) or not firma_b64.strip():
		raise ErrorFirma(_("La información de la versión nueva no está firmada; no se instalará."))
	try:
		firma = base64.b64decode(firma_b64, validate=True)
	except (binascii.Error, ValueError) as error:
		raise ErrorFirma(_("La firma de la versión nueva está dañada; no se instalará.")) from error
	try:
		from cryptography.exceptions import InvalidSignature
		from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
	except ImportError as error:
		log.exception("Falta el paquete cryptography: no se puede verificar la firma")
		raise ErrorFirma(_("Falta el componente que verifica las firmas; no se puede actualizar de forma segura.")) from error
	mensaje = serializar_canonico(manifiesto)
	for clave_hex in claves_publicas:
		try:
			clave = Ed25519PublicKey.from_public_bytes(bytes.fromhex(clave_hex))
		except ValueError:
			log.error("Clave pública mal formada en la configuración: %s…", str(clave_hex)[:16])
			continue
		try:
			clave.verify(firma, mensaje)
		except InvalidSignature:
			log.debug("La firma no corresponde a la clave %s…", clave_hex[:16])
			continue
		log.info("Firma del manifiesto verificada con la clave %s…", clave_hex[:16])
		return
	raise ErrorFirma(_("La firma de la versión nueva no es válida; no se instalará."))


# ════════════════════════════════════════════════════════════════════════════
# Memoria contra retrocesos (data/config/actualizaciones.json)
# ════════════════════════════════════════════════════════════════════════════


def leer_estado(config: Configuracion) -> dict:
	"""Lee la memoria del actualizador; si falta o está dañada, empieza vacía."""
	try:
		datos = json.loads(config.archivo_estado.read_text(encoding="utf-8"))
	except FileNotFoundError:
		return {}
	except OSError, ValueError:
		# Dañada: se sigue sin memoria (la regla «más nueva que la instalada»
		# sigue protegiendo) en lugar de bloquear las actualizaciones para siempre.
		log.warning("No se pudo leer %s; se empieza con el estado vacío", config.archivo_estado, exc_info=True)
		return {}
	return datos if isinstance(datos, dict) else {}


def guardar_estado(config: Configuracion, estado: dict) -> None:
	"""Guarda el estado de forma atómica (temporal + ``os.replace``)."""
	ruta = config.archivo_estado
	ruta.parent.mkdir(parents=True, exist_ok=True)
	temporal = ruta.with_name(ruta.name + ".tmp")
	temporal.write_text(json.dumps(estado, indent="\t", ensure_ascii=False), encoding="utf-8")
	os.replace(temporal, ruta)


def confirmar_version(config: Configuracion, version: str | None = None) -> None:
	"""Anota la versión como instalada y confirmada (memoria contra retrocesos).

	Solo SUBE: guarda la mayor entre la anotada y la actual. Se alimenta
	únicamente de versiones que han arrancado de verdad en este equipo, nunca
	de lo que diga el servidor; así una errata publicada en ``version.json`` no
	puede bloquear las actualizaciones para siempre.
	"""
	version = version or config.version_actual
	estado = leer_estado(config)
	anterior = str(estado.get("version_confirmada") or "")
	try:
		if anterior and comparar_versiones(anterior, version) >= 0:
			return
	except VersionInvalida:
		log.warning("Versión confirmada no válida en el estado (%r); se sustituye", anterior)
	estado["version_confirmada"] = version
	try:
		guardar_estado(config, estado)
		log.info("Versión %s confirmada (protección contra retrocesos)", version)
	except OSError:
		log.warning("No se pudo anotar la versión confirmada", exc_info=True)


# ════════════════════════════════════════════════════════════════════════════
# Comprobación
# ════════════════════════════════════════════════════════════════════════════


def _error_de_red(error: red.ErrorRed) -> ErrorActualizacion:
	"""Convierte un error de ``app.core.red`` en uno de actualización, conservando el mensaje."""
	if error.categoria == "cancelado":
		return ErrorCancelado(error.mensaje_usuario)
	if error.categoria == "seguridad":
		return ErrorFirma(error.mensaje_usuario)
	nuevo = ErrorConexion(error.mensaje_usuario)
	nuevo.reintentar = error.reintentar
	nuevo.transitorio = error.reintentar
	return nuevo


def leer_manifiesto(url: str, cancelacion: Any = None) -> dict:
	"""Descarga un manifiesto JSON pequeño (``version.json`` o el índice del catálogo).

	No verifica nada: quien lo llama comprueba la firma antes de usar ningún campo.
	"""
	try:
		return red.leer_json(url, MAX_MANIFIESTO, cancelacion=cancelacion)
	except red.ErrorRed as error:
		if error.codigo_http == 404:
			raise ErrorConexion(_("El servidor no tiene publicada esa información todavía (error 404).")) from error
		raise _error_de_red(error) from error


def _info_desde_manifiesto(config: Configuracion, manifiesto: dict, url_manifiesto: str, canal: str) -> InfoActualizacion:
	"""Valida los campos (ya con la firma comprobada) y construye la información.

	:param canal: canal de la dirección de la que se leyó. Del canal estable
		solo se aceptan manifiestos estables: aunque la firma sea buena, nadie
		puede colocar ahí el de una versión de pruebas.
	"""
	version = manifiesto.get("version")
	archivo = manifiesto.get("file")
	sha = str(manifiesto.get("sha256") or "").strip().lower()
	tamano = manifiesto.get("size")
	aplicacion = manifiesto.get("app")
	canal_manifiesto = str(manifiesto.get("canal") or "estable")
	if aplicacion is not None and aplicacion != config.nombre_app:
		raise ErrorFirma(_("La versión publicada es de otra aplicación; se ignora."))
	if canal_manifiesto not in CANALES or (canal == "estable" and canal_manifiesto != "estable"):
		raise ErrorFirma(_("La versión publicada no corresponde al canal elegido; se ignora."))
	try:
		clave_version(str(version))
	except VersionInvalida as error:
		raise ErrorFirma(_("El servidor publica una versión con formato no válido.")) from error
	if not isinstance(archivo, str) or not re.fullmatch(r"[\w.\-]+\.zip", archivo) or ".." in archivo:
		raise ErrorFirma(_("El nombre del paquete publicado no es válido."))
	if not re.fullmatch(r"[0-9a-f]{64}", sha):
		raise ErrorFirma(_("El paquete publicado no trae una huella SHA-256 válida."))
	if not isinstance(tamano, int) or isinstance(tamano, bool) or not 0 < tamano <= MAX_DESCARGA:
		raise ErrorFirma(_("El tamaño del paquete publicado no es válido."))
	url_zip = str(manifiesto.get("url") or urllib.parse.urljoin(url_manifiesto, urllib.parse.quote(archivo)))
	try:
		red.comprobar_url(url_zip)
	except red.ErrorRed as error:
		raise ErrorFirma(error.mensaje_usuario) from error
	return InfoActualizacion(
		version=str(version),
		archivo=archivo,
		url_zip=url_zip,
		sha256=sha,
		tamano=tamano,
		fecha=str(manifiesto.get("date") or ""),
		novedades=str(manifiesto.get("novedades") or "").strip(),
		canal=canal_manifiesto,
	)


def fuentes(config: Configuracion) -> list[tuple[str, str]]:
	"""Direcciones que se consultan, como pares (canal, URL), según el canal elegido."""
	lista = [("estable", config.url_estable)]
	if config.canal == "pruebas":
		lista.append(("pruebas", config.url_pruebas))
	return lista


def comprobar(config: Configuracion, *, respetar_saltada: bool = False, cancelacion: Any = None) -> InfoActualizacion | None:
	"""Consulta GitHub y devuelve la versión nueva, o ``None`` si no la hay.

	:param respetar_saltada: ``True`` en la comprobación automática (no molesta
		con la versión que el usuario pidió saltar); ``False`` en la manual.
	:raises ErrorActualizacion: red, firma, formato o retroceso. La firma se
		verifica ANTES de mirar ningún otro campo.
	"""
	log.info("Comprobando actualizaciones (canal %s, versión instalada %s)", config.canal, config.version_actual)
	candidatas: list[InfoActualizacion] = []
	errores: list[ErrorActualizacion] = []
	for canal, url in fuentes(config):
		try:
			manifiesto = leer_manifiesto(url, cancelacion)
			verificar_firma(manifiesto, config.claves_publicas)
			candidatas.append(_info_desde_manifiesto(config, manifiesto, url, canal))
		except ErrorCancelado:
			raise
		except ErrorActualizacion as error:
			log.warning("No se pudo usar el canal %s (%s): %s", canal, url, error)
			errores.append(error)
	if not candidatas:
		raise errores[0]
	info = max(candidatas, key=lambda candidata: clave_version(candidata.version))
	_anotar_comprobacion()
	if not es_mas_nueva(info.version, config.version_actual):
		log.info("No hay versión nueva: el servidor ofrece %s", info.version)
		return None
	confirmada = str(leer_estado(config).get("version_confirmada") or "")
	try:
		retroceso = bool(confirmada) and comparar_versiones(info.version, confirmada) < 0
	except VersionInvalida:
		log.warning("Versión confirmada no válida en el estado (%r); se ignora", confirmada)
		retroceso = False
	if retroceso:
		log.warning("Retroceso rechazado: el servidor ofrece %s, inferior a la confirmada %s", info.version, confirmada)
		raise ErrorRetroceso(
			_(
				"El servidor ofrece la versión {nueva}, anterior a la {confirmada} que ya se instaló en este equipo. "
				"Por seguridad se rechaza."
			).format(nueva=info.version, confirmada=confirmada)
		)
	if respetar_saltada and version_saltada() == info.version:
		log.info("La versión %s está saltada por el usuario", info.version)
		return None
	log.info("Versión nueva disponible: %s (%d bytes, canal %s)", info.version, info.tamano, info.canal)
	return info


# ════════════════════════════════════════════════════════════════════════════
# Descarga y verificación
# ════════════════════════════════════════════════════════════════════════════


def _avisar(progreso: Progreso | None, fase: str, hecho: int, total: int) -> None:
	if progreso is None:
		return
	try:
		progreso(fase, hecho, total)
	except Exception:  # noqa: BLE001 - función ajena: un fallo al pintar el progreso no estropea la actualización
		log.debug("Fallo en la función de progreso", exc_info=True)


def sha256_de(ruta: Path) -> str:
	"""SHA-256 de un fichero leyendo por bloques de 1 MB."""
	resumen = hashlib.sha256()
	with ruta.open("rb") as archivo:
		for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
			resumen.update(bloque)
	return resumen.hexdigest()


def descargar(config: Configuracion, info: InfoActualizacion, progreso: Progreso | None = None, cancelacion: Any = None) -> Path:
	"""Descarga el ZIP a ``data/temp/actualizacion/descarga`` y devuelve su ruta.

	La parte ya descargada se guarda como ``.parcial`` y se reanuda si el
	servidor lo admite. Nunca se escriben más bytes de los anunciados en el
	manifiesto firmado y el SHA-256 se comprueba antes de dar el fichero por bueno.

	:param cancelacion: ``threading.Event``, token con ``cancelado`` o función.
	"""
	carpeta = config.carpeta_trabajo / "descarga"
	try:
		resultado = descargas.descargar(
			info.url_zip,
			carpeta / info.archivo,
			sha256=info.sha256,
			tamano=info.tamano,
			al_progresar=lambda hecho, _total: _avisar(progreso, "descarga", hecho, info.tamano),
			cancelacion=cancelacion,
		)
	except descargas.DescargaCancelada as error:
		raise ErrorCancelado(_("Descarga cancelada. Podrá continuarla más tarde.")) from error
	except descargas.ErrorIntegridad as error:
		raise ErrorVerificacion(error.mensaje_usuario) from error
	except red.ErrorRed as error:
		raise _error_de_red(error) from error
	except OSError as error:
		log.exception("Fallo de disco al descargar la actualización")
		raise ErrorActualizacion(red.clasificar_error(error).mensaje) from error
	return resultado.ruta


def verificar_paquete(ruta: Path, info: InfoActualizacion) -> None:
	"""Comprueba tamaño y SHA-256; si no coinciden, BORRA el fichero y lo rechaza."""
	tamano = ruta.stat().st_size
	if tamano != info.tamano:
		ruta.unlink(missing_ok=True)
		raise ErrorVerificacion(_("El paquete descargado no tiene el tamaño anunciado; no se instalará."))
	real = sha256_de(ruta)
	if not hmac.compare_digest(real, info.sha256):
		log.error("SHA-256 incorrecto: esperado %s, obtenido %s", info.sha256, real)
		ruta.unlink(missing_ok=True)
		raise ErrorVerificacion(_("El paquete descargado no supera la verificación de integridad; no se instalará."))
	log.info("Paquete verificado: %d bytes, SHA-256 correcto", tamano)


# ════════════════════════════════════════════════════════════════════════════
# Extracción segura
# ════════════════════════════════════════════════════════════════════════════


def partes_seguras(nombre: str) -> list[str]:
	"""Partes de una ruta de un ZIP, o ``ErrorPaquete`` si es peligrosa.

	Rechaza rutas absolutas, unidades y flujos alternativos (``:``), ``..``,
	nombres que Windows altera (acabados en punto o espacio) y dispositivos
	reservados (``CON``, ``NUL``...).
	"""
	if "\x00" in nombre:
		raise ErrorPaquete(_("El paquete contiene un nombre de fichero no válido."))
	normal = nombre.replace("\\", "/")
	if normal.startswith("/") or ":" in normal:
		raise ErrorPaquete(_("El paquete contiene una ruta absoluta ({nombre}); se rechaza.").format(nombre=nombre))
	partes = [parte for parte in normal.split("/") if parte not in ("", ".")]
	for parte in partes:
		if parte == "..":
			raise ErrorPaquete(_("El paquete intenta escribir fuera de su carpeta ({nombre}); se rechaza.").format(nombre=nombre))
		if parte != parte.rstrip(" ."):
			raise ErrorPaquete(_("El paquete contiene un nombre no válido en Windows ({nombre}).").format(nombre=nombre))
		if parte.split(".")[0].lower() in _NOMBRES_RESERVADOS:
			raise ErrorPaquete(_("El paquete contiene un nombre reservado de Windows ({nombre}).").format(nombre=nombre))
	return partes


def _version_de_ficha(datos: bytes) -> str:
	"""Versión declarada en un ``complemento.json`` (vacía si no se entiende)."""
	try:
		ficha = json.loads(datos.decode("utf-8-sig"))
	except UnicodeDecodeError, ValueError:
		return ""
	return str(ficha.get("version") or "") if isinstance(ficha, dict) else ""


def complementos_del_usuario(carpeta_datos: Path) -> set[str]:
	"""Identificadores de los complementos que instaló el usuario (no venían con la aplicación)."""
	try:
		datos = json.loads((carpeta_datos / "config" / REGISTRO_COMPLEMENTOS).read_text(encoding="utf-8"))
	except FileNotFoundError:
		return set()
	except OSError, ValueError:
		log.warning("No se pudo leer el registro de complementos del usuario", exc_info=True)
		return set()
	instalados = datos.get("instalados") if isinstance(datos, dict) else None
	return set(instalados) if isinstance(instalados, dict) else set()


def _complementos_a_saltar(config: Configuracion, versiones_zip: dict[str, str]) -> set[str]:
	"""Complementos de serie del ZIP que NO deben copiarse sobre los instalados.

	La versión nueva de la aplicación trae sus complementos de serie, pero el
	usuario puede tener el mismo complemento más reciente (lo actualizó desde
	el catálogo en línea) o haberlo instalado por su cuenta. Regla:

	- no está instalado: se copia;
	- el del ZIP es más nuevo que el instalado: se copia (se pone al día);
	- misma versión y no es del usuario: se copia (se repara);
	- en cualquier otro caso se conserva el instalado.
	"""
	del_usuario = complementos_del_usuario(config.carpeta_datos)
	saltar: set[str] = set()
	for identificador, version_zip in versiones_zip.items():
		ficha = config.carpeta_complementos / identificador / FICHA_COMPLEMENTO
		try:
			instalada = _version_de_ficha(ficha.read_bytes())
		except FileNotFoundError:
			continue
		except OSError:
			log.warning("No se pudo leer %s; se conserva el complemento instalado", ficha, exc_info=True)
			saltar.add(identificador)
			continue
		try:
			comparacion = comparar_versiones(version_zip, instalada)
		except VersionInvalida:
			log.warning(
				"Versiones no comparables del complemento %s (%r y %r); se conserva el instalado", identificador, version_zip, instalada
			)
			saltar.add(identificador)
			continue
		if comparacion < 0 or (comparacion == 0 and identificador in del_usuario):
			log.info("Se conserva el complemento «%s» %s (la versión nueva trae %s)", identificador, instalada, version_zip)
			saltar.add(identificador)
	return saltar


# ════════════════════════════════════════════════════════════════════════════
# Borrado robusto de restos
# ════════════════════════════════════════════════════════════════════════════
# Windows no deja borrar un fichero de solo lectura, uno que tiene abierto otro
# programa (el antivirus o el indexador lo abren justo después de crearlo) ni
# una DLL que alguien tiene cargada. Ninguna de esas cosas debe parar una
# actualización ni dejar restos para siempre: se quita el atributo, se reintenta
# con espera creciente, se aparta con otro nombre y se borra en el siguiente
# arranque; como último recurso se pide a Windows que lo borre al reiniciar.


def _ruta_larga(ruta: Path) -> str:
	"""Ruta con ``\\\\?\\`` en Windows: los restos de una versión pueden pasar de 260 caracteres."""
	texto = str(Path(ruta).absolute())
	if os.name != "nt" or texto.startswith("\\\\?\\"):
		return texto
	if texto.startswith("\\\\"):
		return "\\\\?\\UNC\\" + texto[2:]
	return "\\\\?\\" + texto


def _hacer_escribible_y_reintentar(funcion: Callable[[str], Any], ruta: str, _excepcion: BaseException) -> None:
	"""Un fichero o una carpeta de solo lectura da «Acceso denegado»: se quita el atributo y se reintenta."""
	try:
		os.chmod(ruta, stat.S_IWRITE)
		funcion(ruta)
	except FileNotFoundError:
		log.debug("%s ya no existe", ruta)
	except OSError:
		log.debug("No se pudo borrar %s", ruta, exc_info=True)


def borrar_carpeta(ruta: Path, intentos: int = 4) -> bool:
	"""Borra una carpeta aunque tenga elementos de solo lectura o rutas largas. Nunca lanza.

	Un enlace o una unión (junction) se quitan sin entrar en ellos: nunca se
	borra lo que hay al otro lado. Se reintenta con espera creciente porque un
	antivirus o el indexador pueden tener abierto algo recién creado. Devuelve
	si la carpeta ya no existe.
	"""
	ruta = Path(ruta)
	try:
		if ruta.is_symlink() or ruta.is_junction():
			if ruta.is_dir():
				os.rmdir(ruta)
			else:
				ruta.unlink()
			return not ruta.exists()
		espera = 0.25
		for intento in range(max(1, intentos)):
			if not ruta.exists():
				return True
			if intento:
				time.sleep(espera)
				espera = min(espera * 2, 4.0)
			shutil.rmtree(_ruta_larga(ruta), onexc=_hacer_escribible_y_reintentar)
		return not ruta.exists()
	except OSError:
		log.debug("No se pudo borrar %s", ruta, exc_info=True)
		return not ruta.exists()


def _borrar_fichero(ruta: Path) -> bool:
	"""Borra un fichero aunque sea de solo lectura. Nunca lanza; devuelve si ya no existe."""
	try:
		os.chmod(_ruta_larga(ruta), stat.S_IWRITE)
		os.unlink(_ruta_larga(ruta))
	except FileNotFoundError:
		return True
	except OSError:
		log.debug("No se pudo borrar %s", ruta, exc_info=True)
	return not ruta.exists()


def _apartar(ruta: Path, carpeta_destino: Path) -> Path | None:
	"""Mueve ``ruta`` a ``carpeta_destino`` con un nombre único; ``None`` si tampoco se puede.

	Renombrar funciona en casos en los que borrar no: una DLL cargada por otro
	proceso se puede renombrar, pero no borrar.
	"""
	carpeta_destino.mkdir(parents=True, exist_ok=True)
	apartada = carpeta_destino / f"{ruta.name}-{time.time_ns()}"
	try:
		os.rename(_ruta_larga(ruta), _ruta_larga(apartada))
	except OSError:
		log.debug("No se pudo apartar %s", ruta, exc_info=True)
		return None
	return apartada


def programar_borrado_al_reiniciar(ruta: Path) -> bool:
	"""Pide a Windows que borre ``ruta`` (y lo que contenga) en el próximo reinicio.

	Es el último recurso para un resto que sigue en uso (``MoveFileExW`` con
	``MOVEFILE_DELAY_UNTIL_REBOOT``). Windows solo lo admite con permisos de
	administrador; sin ellos se registra y el resto se reintenta en el siguiente
	arranque de la aplicación, que es lo que ocurre casi siempre.
	"""
	if sys.platform != "win32":
		return False
	import ctypes
	from ctypes import wintypes

	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
	kernel32.MoveFileExW.restype = wintypes.BOOL
	retrasar_hasta_reinicio = 0x4
	elementos: list[str] = []
	if ruta.is_dir() and not ruta.is_symlink():
		for raiz, carpetas, ficheros in os.walk(_ruta_larga(ruta), topdown=False):
			elementos.extend(os.path.join(raiz, nombre) for nombre in ficheros)
			elementos.extend(os.path.join(raiz, nombre) for nombre in carpetas)
	elementos.append(_ruta_larga(ruta))
	for elemento in elementos:
		if not kernel32.MoveFileExW(elemento, None, retrasar_hasta_reinicio):
			log.info(
				"Windows no deja programar el borrado de %s al reiniciar (error %d; hacen falta permisos de administrador); "
				"se reintentará en el próximo arranque",
				ruta,
				ctypes.get_last_error(),
			)
			return False
	log.info("Borrado de %s programado para el próximo reinicio", ruta)
	return True


def _vaciar_destino(destino: Path, carpeta_apartados: Path) -> None:
	"""Deja libre ``destino`` antes de extraer, aunque un intento anterior lo dejara bloqueado.

	Si no se puede borrar (Windows dice «Acceso denegado» en algo que tiene
	abierto otro programa o que tiene permisos raros), se aparta con otro nombre
	y se sigue: :func:`limpiar_trabajo` lo vuelve a intentar al arrancar. Solo si
	tampoco se puede apartar se para con un mensaje que dice qué carpeta borrar.
	"""
	if not destino.exists() or borrar_carpeta(destino):
		return
	apartada = _apartar(destino, carpeta_apartados)
	if apartada is None:
		log.error("No se puede borrar ni apartar %s de un intento anterior", destino)
		raise ErrorActualizacion(
			_(
				"Windows no deja borrar lo que quedó de un intento anterior de actualizar. "
				"Cierre {aplicacion}, borre la carpeta data\\temp\\actualizacion que está dentro de la carpeta "
				"de {aplicacion} y vuelva a buscar actualizaciones."
			).format(aplicacion=NOMBRE_APLICACION)
		)
	log.warning("Restos de un intento anterior que no se dejan borrar; apartados en %s", apartada)


# ════════════════════════════════════════════════════════════════════════════
# Comprobaciones previas: antes de descargar y antes de tocar nada
# ════════════════════════════════════════════════════════════════════════════


def _es_disco_lleno(error: OSError) -> bool:
	"""``ENOSPC`` o los errores 39 y 112 de Windows («el disco está lleno»)."""
	return error.errno == errno.ENOSPC or getattr(error, "winerror", None) in (39, 112)


def _probar_escritura(carpeta: Path) -> None:
	"""Crea, renombra y borra un fichero en ``carpeta``: lo mismo que hará la sustitución.

	``os.access`` no sirve en Windows (solo mira el atributo de solo lectura) y
	en Archivos de programa sin permisos de administrador falla justo esto.
	"""
	prueba = carpeta / f".entornolab_prueba_{os.getpid()}_{time.time_ns()}"
	renombrada = prueba.with_suffix(".renombrada")
	try:
		prueba.write_bytes(b"x")
		os.rename(prueba, renombrada)
		os.unlink(renombrada)
	except OSError as error:
		for resto in (prueba, renombrada):
			_borrar_fichero(resto)
		if _es_disco_lleno(error):
			raise ErrorEspacio(_("No hay espacio libre suficiente en el disco para actualizar.")) from error
		log.warning("No se puede escribir en %s", carpeta, exc_info=True)
		raise ErrorPermisos(
			_(
				"Windows no deja modificar la carpeta de {aplicacion} ({carpeta}). Si está en Archivos de programa, "
				"muévala a una carpeta suya, como Documentos, o actualice abriendo {aplicacion} como administrador."
			).format(aplicacion=NOMBRE_APLICACION, carpeta=carpeta)
		) from error


def comprobar_permisos(config: Configuracion) -> None:
	"""Comprueba ANTES de descargar que se puede escribir donde hará falta.

	En la carpeta de la aplicación, en cada subcarpeta del programa (``lib``...),
	en ``data/temp`` y en las carpetas de recursos de ``data``. Así un
	EntornoLab copiado en Archivos de programa recibe un mensaje claro en lugar
	de descargar 100 MB para nada o de quedarse a medias.

	:raises ErrorPermisos: con la carpeta que falla.
	"""
	carpetas = [config.carpeta_app]
	try:
		carpetas.extend(
			hijo for hijo in sorted(config.carpeta_app.iterdir()) if hijo.is_dir() and hijo.name.lower() != "data" and not hijo.is_symlink()
		)
	except OSError as error:
		raise ErrorPermisos(
			_("No se puede leer la carpeta de {aplicacion} ({carpeta}).").format(aplicacion=NOMBRE_APLICACION, carpeta=config.carpeta_app)
		) from error
	config.carpeta_trabajo.mkdir(parents=True, exist_ok=True)
	carpetas.append(config.carpeta_trabajo)
	carpetas.extend(config.carpeta_datos / nombre for nombre in config.data_actualizable if (config.carpeta_datos / nombre).is_dir())
	for carpeta in carpetas:
		_probar_escritura(carpeta)
	log.info("Permisos de escritura comprobados en %d carpetas", len(carpetas))


def comprobar_espacio(carpeta: Path, necesario: int) -> None:
	"""Lanza :class:`ErrorEspacio` si en el disco de ``carpeta`` no quedan ``necesario`` bytes."""
	libre = shutil.disk_usage(carpeta).free
	if libre < necesario:
		log.warning("Espacio insuficiente en %s: libres %d bytes, hacen falta %d", carpeta, libre, necesario)
		raise ErrorEspacio(
			_("No hay espacio libre suficiente en el disco para actualizar: hacen falta {necesario} MB y quedan {libre} MB.").format(
				necesario=necesario // 1024**2 + 1, libre=libre // 1024**2
			)
		)


def rutas_largas_activadas() -> bool:
	"""True si Windows tiene activadas las rutas de más de 260 caracteres (``LongPathsEnabled``)."""
	if sys.platform != "win32":
		return True
	import winreg

	try:
		with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as clave:
			valor, _tipo = winreg.QueryValueEx(clave, "LongPathsEnabled")
	except OSError:
		log.debug("No se pudo leer LongPathsEnabled", exc_info=True)
		return False
	return bool(valor)


def _listar_ficheros(raiz: Path) -> list[tuple[str, int]]:
	"""(ruta relativa con «\\», tamaño) de cada fichero bajo ``raiz``, sin entrar en enlaces."""
	resultado: list[tuple[str, int]] = []
	base = _ruta_larga(raiz)
	for carpeta, subcarpetas, ficheros in os.walk(base):
		subcarpetas[:] = [nombre for nombre in subcarpetas if not os.path.islink(os.path.join(carpeta, nombre))]
		relativa = os.path.relpath(carpeta, base)
		for nombre in ficheros:
			completa = os.path.join(carpeta, nombre)
			ruta = nombre if relativa == "." else os.path.join(relativa, nombre)
			resultado.append((ruta.replace("/", "\\"), os.stat(completa).st_size))
	return resultado


def comprobar_rutas(config: Configuracion, nuevos: list[str]) -> None:
	"""Rechaza la versión nueva si alguna ruta pasaría del límite de Windows.

	El script mueve los ficheros con rutas ``\\\\?\\`` y no tiene límite, pero la
	versión nueva tiene que poder ARRANCAR desde esa carpeta: sin las rutas largas
	activadas, un fichero de ``lib`` demasiado hondo la dejaría rota.
	"""
	if not nuevos or rutas_largas_activadas():
		return
	mas_larga = max(nuevos, key=len)
	longitud = len(str(config.carpeta_app)) + 1 + len(mas_larga)
	if longitud > LIMITE_RUTA:
		log.warning("Ruta demasiado larga tras actualizar: %d caracteres (%s)", longitud, mas_larga)
		raise ErrorRutaLarga(
			_(
				"La carpeta de {aplicacion} está demasiado honda: la versión nueva tendría rutas de {longitud} caracteres "
				"y Windows solo admite {limite}. Mueva la carpeta a una ruta más corta, por ejemplo C:\\{aplicacion}."
			).format(aplicacion=NOMBRE_APLICACION, longitud=longitud, limite=LIMITE_RUTA)
		)


def escribir_inventario(config: Configuracion, extraida: Path) -> list[str]:
	"""Anota lo que hay instalado y lo que trae la versión nueva; devuelve las rutas nuevas.

	- ``original.txt``: cada fichero del programa (todo salvo ``data``) y de las
	  carpetas de recursos de ``data``, con su tamaño. Con él la vuelta atrás
	  COMPRUEBA que la versión anterior ha quedado entera.
	- ``nuevos.txt``: cada fichero que escribirá la versión nueva. Tras un corte
	  de luz, la vuelta atrás quita los que no existían antes aunque la carpeta
	  ``nueva`` haya quedado a medias.
	"""
	original: list[tuple[str, int]] = []
	for hijo in sorted(config.carpeta_app.iterdir()):
		if hijo.name.lower() == "data" or hijo.is_symlink():
			continue
		if hijo.is_dir():
			original.extend((f"{hijo.name}\\{ruta}", tamano) for ruta, tamano in _listar_ficheros(hijo))
		else:
			original.append((hijo.name, hijo.stat().st_size))
	for nombre in config.data_actualizable:
		carpeta = config.carpeta_datos / nombre
		if carpeta.is_dir():
			original.extend((f"data\\{nombre}\\{ruta}", tamano) for ruta, tamano in _listar_ficheros(carpeta))
	nuevos = [ruta for ruta, _tamano in _listar_ficheros(extraida / "programa")]
	if (extraida / "recursos").is_dir():
		nuevos.extend(f"data\\{ruta}" for ruta, _tamano in _listar_ficheros(extraida / "recursos"))
	config.inventario.write_text("".join(f"{ruta}\t{tamano}\n" for ruta, tamano in original), encoding="utf-8")
	config.lista_nuevos.write_text("".join(f"{ruta}\n" for ruta in nuevos), encoding="utf-8")
	log.info("Inventario: %d ficheros instalados, %d de la versión nueva", len(original), len(nuevos))
	return nuevos


def extraer_seguro(ruta_zip: Path, destino: Path, config: Configuracion, progreso: Progreso | None = None) -> Path:
	"""Extrae el ZIP en ``destino/programa`` y ``destino/recursos``.

	Primero valida TODAS las entradas y solo después escribe: un paquete con una
	sola entrada peligrosa se rechaza entero. Quita la carpeta raíz común
	(``EntornoLab/``) que pone el empaquetado. De ``data/`` solo acepta las
	subcarpetas de ``data_actualizable``; lo demás (config, db, sessions,
	entornos, logs...) se descarta, y los complementos siguen la regla de
	``_complementos_a_saltar``.
	"""
	_vaciar_destino(destino, config.carpeta_por_borrar)
	programa, recursos = destino / "programa", destino / "recursos"
	programa.mkdir(parents=True)
	raiz_segura = destino.resolve()
	permitidas = {nombre.lower() for nombre in config.data_actualizable}
	try:
		with zipfile.ZipFile(ruta_zip) as paquete:
			infos = paquete.infolist()
			if len(infos) > MAX_MIEMBROS:
				raise ErrorPaquete(_("El paquete contiene demasiados ficheros; se rechaza."))
			entradas: list[tuple[zipfile.ZipInfo, list[str]]] = []
			vistos: set[str] = set()
			declarado = 0
			for info in infos:
				partes = partes_seguras(info.filename)
				if stat.S_ISLNK(info.external_attr >> 16):
					raise ErrorPaquete(_("El paquete contiene enlaces simbólicos ({nombre}); se rechaza.").format(nombre=info.filename))
				if info.flag_bits & 0x1:
					raise ErrorPaquete(_("El paquete contiene ficheros cifrados; se rechaza."))
				if info.is_dir() or not partes:
					continue
				clave = "/".join(partes).lower()
				if clave in vistos:
					raise ErrorPaquete(_("El paquete repite el fichero {nombre}; se rechaza.").format(nombre=info.filename))
				vistos.add(clave)
				declarado += info.file_size
				entradas.append((info, partes))
			if declarado > config.max_expandido:
				raise ErrorPaquete(_("El paquete ocupa demasiado al descomprimirse; se rechaza."))
			prefijo = 0
			primeras = {partes[0] for _info, partes in entradas}
			if len(primeras) == 1 and all(len(partes) > 1 for _info, partes in entradas):
				prefijo = 1
			# Versión de cada complemento de serie que trae el ZIP, para decidir cuáles se copian.
			versiones_zip: dict[str, str] = {}
			for info, partes in entradas:
				relativas = [parte.lower() for parte in partes[prefijo:]]
				if len(relativas) == 4 and relativas[:2] == ["data", CARPETA_COMPLEMENTOS] and relativas[3] == FICHA_COMPLEMENTO:
					versiones_zip[partes[prefijo + 2]] = _version_de_ficha(paquete.read(info)) if info.file_size <= 20 * 1024 * 1024 else ""
			saltar = _complementos_a_saltar(config, versiones_zip) if CARPETA_COMPLEMENTOS in permitidas else set()
			escrito_total = 0
			for indice, (info, partes) in enumerate(entradas, start=1):
				relativas = partes[prefijo:]
				if relativas[0].lower() == "data":
					if len(relativas) < 3 or relativas[1].lower() not in permitidas:
						log.warning("Se descarta %s del paquete: los datos del usuario nunca se sustituyen", info.filename)
						continue
					if relativas[1].lower() == CARPETA_COMPLEMENTOS and len(relativas) >= 4 and relativas[2] in saltar:
						continue
					destino_archivo = recursos.joinpath(*relativas[1:])
				else:
					destino_archivo = programa.joinpath(*relativas)
				if not destino_archivo.resolve().is_relative_to(raiz_segura):
					raise ErrorPaquete(
						_("El paquete intenta escribir fuera de su carpeta ({nombre}); se rechaza.").format(nombre=info.filename)
					)
				# Con «\\?\» delante: la carpeta del usuario más data\temp\actualizacion\nueva\programa
				# puede pasar de 260 caracteres aunque la instalación no.
				os.makedirs(_ruta_larga(destino_archivo.parent), exist_ok=True)
				with paquete.open(info) as origen, open(_ruta_larga(destino_archivo), "wb") as salida:
					for bloque in iter(lambda: origen.read(1024 * 1024), b""):
						escrito_total += len(bloque)
						if escrito_total > config.max_expandido:
							raise ErrorPaquete(_("El paquete ocupa demasiado al descomprimirse; se rechaza."))
						salida.write(bloque)
				_avisar(progreso, "extraccion", indice, len(entradas))
	except zipfile.BadZipFile as error:
		borrar_carpeta(destino)
		raise ErrorPaquete(_("El paquete descargado está dañado.")) from error
	except ErrorActualizacion:
		borrar_carpeta(destino)
		raise
	except OSError as error:
		borrar_carpeta(destino)
		if _es_disco_lleno(error):
			log.warning("Disco lleno al descomprimir la actualización", exc_info=True)
			raise ErrorEspacio(
				_("El disco se ha llenado al descomprimir la actualización. Libere espacio y vuelva a intentarlo.")
			) from error
		log.exception("Fallo de disco al descomprimir la actualización")
		raise ErrorActualizacion(
			_("No se pudo descomprimir la actualización ({error}). La instalación no se ha tocado.").format(error=error.strerror or error)
		) from error
	except BaseException:
		borrar_carpeta(destino)
		raise
	if not (programa / config.ejecutable).is_file():
		borrar_carpeta(destino)
		raise ErrorPaquete(_("El paquete no parece una versión de {aplicacion}; no se instalará.").format(aplicacion=config.nombre_app))
	log.info("Paquete extraído en %s (%d ficheros)", destino, len(entradas))
	return destino


# ════════════════════════════════════════════════════════════════════════════
# Script de sustitución
# ════════════════════════════════════════════════════════════════════════════

# Cómo se sustituye (todas las reglas están comprobadas en las pruebas):
#
# - NADA se copia encima de nada. Cada elemento del programa (``lib``, cada fichero
#   de la raíz, los dos ejecutables) se RENOMBRA a la copia de seguridad y el nuevo
#   se renombra a su sitio. En el mismo disco renombrar es instantáneo, no necesita
#   espacio y funciona con una DLL que otro proceso tiene cargada (que no se puede
#   sobrescribir ni borrar). Si una carpeta no se deja renombrar (tiene algo
#   abierto), se hace fichero a fichero.
# - Antes de tocar nada, el motor comprueba que se puede escribir y que ningún otro
#   programa tiene abierto sin compartir un fichero que haya que sustituir (abriéndolo
#   con el mismo permiso que pide renombrar). Reintenta con espera creciente: el
#   antivirus y el indexador sueltan los ficheros enseguida.
# - Mientras la instalación está a medias existe ``diario.txt``. Si se va la luz o se
#   mata el script, la aplicación lo ve al arrancar y lanza ``recuperar.bat`` (que
#   también se puede ejecutar a mano). La vuelta atrás se puede repetir sin riesgo y
#   COMPRUEBA con ``original.txt`` que la versión anterior queda entera.
# - El motor es un guion de PowerShell que recibe las rutas por variables de
#   entorno (ningún carácter de una ruta rompe nada) y usa rutas ``\\?\`` (sin el
#   límite de 260 caracteres). Se ejecuta como bloque de órdenes, no como fichero
#   .ps1, para que no le afecte la directiva de ejecución de scripts.
# - En el .bat: todo el flujo con «goto» (dentro de bloques ( ) las %variables% se
#   expanden al leer el bloque); esperas con «ping -n 2 127.0.0.1» (≈1 s; «timeout»
#   falla sin consola); find/findstr con ruta completa (un PATH con utilidades GNU
#   tiene otro «find»); mensajes del registro sin tildes ni rutas (``:anotar`` los
#   escribe sin comillas y un «&» en una ruta partiría la orden).
# - Tras cerrarse el Estudio se espera también a los reproductores y a cualquier otro
#   proceso de esta carpeta, sin matarlos nunca.

_PLANTILLA_MOTOR = r"""# Motor de sustitucion de EntornoLab, generado por app/services/actualizador.py. No lo edite.
# Lo llama actualizar.bat (o recuperar.bat) con una operacion: comprobar, aplicar, restaurar,
# terminar o limpiar. Las rutas llegan por variables de entorno, nunca en la linea de ordenes.
param([Parameter(Mandatory = $true)][string]$Operacion)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$App = [string]$env:APP
$Datos = $App.TrimEnd('\') + '\data'
$Trabajo = [string]$env:TRABAJO
$Nueva = $Trabajo.TrimEnd('\') + '\nueva'
$Respaldo = [string]$env:RESPALDO
$PorBorrar = $Trabajo.TrimEnd('\') + '\por_borrar'
$Registro = [string]$env:REGISTRO
$Detalle = $Trabajo.TrimEnd('\') + '\detalle.txt'
$Inventario = $Trabajo.TrimEnd('\') + '\original.txt'
$ListaNuevos = $Trabajo.TrimEnd('\') + '\nuevos.txt'
$Reintentos = [int]$env:REINTENTOS
$PuntoFallo = [string]$env:PUNTO_FALLO
$Recursos = @(([string]$env:RECURSOS).Split(' ') | Where-Object { $_ })
$Ejecutables = @([string]$env:EJECUTABLE, [string]$env:EJECUTABLE_REPRODUCTOR)
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$script:Actual = ''

function Largo([string]$Ruta) {
	if ($Ruta.StartsWith('\\?\')) { return $Ruta }
	if ($Ruta.StartsWith('\\')) { return '\\?\UNC\' + $Ruta.Substring(2) }
	return '\\?\' + $Ruta
}

function Unir([string]$Base, [string]$Resto) { return $Base.TrimEnd('\') + '\' + $Resto }

function Anotar([string]$Texto) {
	$linea = '[' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff') + '] ' + $Texto + "`r`n"
	try { [IO.File]::AppendAllText((Largo $Registro), $linea, $Utf8) } catch { [Console]::Error.WriteLine('No se pudo escribir el registro: ' + $Texto) }
}

function Interna($Excepcion) {
	$e = $Excepcion
	while ($e.InnerException) { $e = $e.InnerException }
	return $e
}

function Codigo($Excepcion) { return ((Interna $Excepcion).HResult -band 0xFFFF) }

function Motivo-De([int]$Numero) {
	if (@(32, 33, 1224) -contains $Numero) { return 'fichero_bloqueado' }
	if (@(5, 19, 1314) -contains $Numero) { return 'sin_permiso' }
	if (@(39, 112) -contains $Numero) { return 'sin_espacio' }
	if (@(206) -contains $Numero) { return 'ruta_larga' }
	return 'fallo_copia'
}

# Codigo de salida 1: algo se movio y hay que volver atras; 2: no se ha tocado nada.
function Fallar([string]$Motivo, [string]$Archivo, [string]$Texto, [int]$Salida = 1) {
	Anotar ('ERROR (' + $Motivo + '): ' + $Texto)
	try { [IO.File]::WriteAllText((Largo $Detalle), 'motivo=' + $Motivo + "`r`narchivo=" + $Archivo + "`r`n", $Utf8) } catch { Anotar 'No se pudo escribir detalle.txt' }
	exit $Salida
}

# Repite la accion con espera creciente (0,25 s, 0,5 s, 1 s... hasta 8 s) mientras el error
# sea de los pasajeros: en uso por otro proceso, acceso denegado o bloqueo de una region.
function Con-Reintentos([scriptblock]$Accion, [string]$Que, [int]$Maximo) {
	$espera = 250
	for ($intento = 0; ; $intento++) {
		try {
			& $Accion
			if ($intento -gt 0) { Anotar ('Hecho tras ' + $intento + ' reintentos: ' + $Que) }
			return
		} catch {
			$numero = Codigo $_.Exception
			if ($intento -ge $Maximo -or @(5, 32, 33, 145, 1224) -notcontains $numero) { throw }
			if ($intento -eq 0) { Anotar ('En uso o bloqueado (error ' + $numero + '): ' + $Que + '; se reintenta con espera creciente') }
			Start-Sleep -Milliseconds $espera
			$espera = [Math]::Min($espera * 2, 8000)
		}
	}
}

function Es-Carpeta([string]$Ruta) { return [IO.Directory]::Exists((Largo $Ruta)) }
function Es-Fichero([string]$Ruta) { return [IO.File]::Exists((Largo $Ruta)) }

function Mover-Fichero([string]$Origen, [string]$Destino, [string]$Que) {
	$o = Largo $Origen
	$d = Largo $Destino
	[void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($d))
	Con-Reintentos ({ [IO.File]::Move($o, $d) }.GetNewClosure()) $Que $Reintentos
}

function Mover-Carpeta([string]$Origen, [string]$Destino, [string]$Que, [int]$Maximo) {
	$o = Largo $Origen
	$d = Largo $Destino
	[void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($d))
	Con-Reintentos ({ [IO.Directory]::Move($o, $d) }.GetNewClosure()) $Que $Maximo
}

# Rutas relativas de los ficheros (o tambien de las carpetas) sin entrar en enlaces ni uniones.
function Elementos([string]$Carpeta, [bool]$ConCarpetas) {
	$base = Largo $Carpeta
	$lista = New-Object System.Collections.Generic.List[string]
	if (-not [IO.Directory]::Exists($base)) { return ,$lista }
	$pendientes = New-Object System.Collections.Generic.Stack[string]
	$pendientes.Push($base)
	while ($pendientes.Count -gt 0) {
		$actual = $pendientes.Pop()
		foreach ($fichero in [IO.Directory]::GetFiles($actual)) { $lista.Add($fichero.Substring($base.Length + 1)) }
		foreach ($sub in [IO.Directory]::GetDirectories($actual)) {
			if (([IO.File]::GetAttributes($sub) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
			if ($ConCarpetas) { $lista.Add($sub.Substring($base.Length + 1)) }
			$pendientes.Push($sub)
		}
	}
	return ,$lista
}

function Ficheros([string]$Carpeta) { return ,(Elementos $Carpeta $false) }

function Leer-Lineas([string]$Ruta) {
	if (-not (Es-Fichero $Ruta)) { return ,@() }
	return ,@([IO.File]::ReadAllLines((Largo $Ruta), $Utf8) | Where-Object { $_ })
}

function Leer-Inventario {
	$tabla = New-Object 'System.Collections.Generic.Dictionary[string,long]' ([StringComparer]::OrdinalIgnoreCase)
	foreach ($linea in (Leer-Lineas $Inventario)) {
		$partes = $linea.Split("`t")
		$tabla[$partes[0]] = [long]$partes[1]
	}
	return ,$tabla
}

# Borra un arbol aunque tenga elementos de solo lectura; devuelve si ya no existe.
function Borrar-Arbol([string]$Ruta, [int]$Intentos) {
	$l = Largo $Ruta
	$espera = 250
	for ($i = 0; $i -lt $Intentos; $i++) {
		if (-not [IO.Directory]::Exists($l)) { return $true }
		try {
			foreach ($rel in (Elementos $Ruta $true)) { [IO.File]::SetAttributes((Largo (Unir $Ruta $rel)), [IO.FileAttributes]::Normal) }
			[IO.Directory]::Delete($l, $true)
			return $true
		} catch {
			if ($i -eq $Intentos - 1) { Anotar ('No se puede borrar todavia ' + $Ruta + ' (error ' + (Codigo $_.Exception) + '); se borrara mas tarde') }
			Start-Sleep -Milliseconds $espera
			$espera = [Math]::Min($espera * 2, 4000)
		}
	}
	return (-not [IO.Directory]::Exists($l))
}

# Lo que no se deja borrar (una DLL que otro proceso sigue usando) se aparta a por_borrar:
# la aplicacion lo vuelve a intentar en cada arranque.
function Borrar-O-Apartar([string]$Ruta, [string]$Nombre) {
	if (Borrar-Arbol $Ruta 3) { return }
	try {
		Mover-Carpeta $Ruta (Unir $PorBorrar ($Nombre + '-' + [DateTime]::UtcNow.Ticks)) $Nombre 2
		Anotar ('Apartado para borrarlo en el siguiente arranque: ' + $Nombre)
	} catch {
		Anotar ('Tampoco se puede apartar ' + $Nombre + '; se borrara en el siguiente arranque')
	}
}

function Punto-De-Prueba {
	if ($PuntoFallo -eq 'aplicar') {
		Anotar 'PRUEBA: fallo forzado a mitad de la sustitucion'
		throw (New-Object IO.IOException('Fallo forzado por la prueba'))
	}
	if ($PuntoFallo -eq 'pausa') {
		Anotar 'PRUEBA: pausa a mitad de la sustitucion (corte de luz simulado)'
		while ($true) { Start-Sleep -Seconds 1 }
	}
}

function Carpetas-A-Probar {
	$lista = New-Object System.Collections.Generic.List[string]
	$lista.Add($App)
	foreach ($sub in [IO.Directory]::GetDirectories((Largo $App))) {
		$nombre = [IO.Path]::GetFileName($sub)
		if ($nombre -ne 'data' -and ([IO.File]::GetAttributes($sub) -band [IO.FileAttributes]::ReparsePoint) -eq 0) { $lista.Add((Unir $App $nombre)) }
	}
	foreach ($nombre in $Recursos) {
		if (Es-Carpeta (Unir $Datos $nombre)) { $lista.Add((Unir $Datos $nombre)) }
	}
	return ,$lista
}

function Preparar-Respaldo {
	if (Es-Carpeta $Respaldo) {
		Anotar 'Quedaba una copia de seguridad de otra vez; se quita'
		if (-not (Borrar-Arbol $Respaldo 3)) {
			$script:Actual = 'data\temp\version_anterior'
			Mover-Carpeta $Respaldo (Unir $PorBorrar ('version_anterior-' + [DateTime]::UtcNow.Ticks)) 'copia de seguridad antigua' $Reintentos
		}
	}
	[void][IO.Directory]::CreateDirectory((Largo (Unir $Respaldo 'programa')))
	[void][IO.Directory]::CreateDirectory((Largo (Unir $Respaldo 'recursos')))
}

# 1. Sin tocar nada: permisos de escritura y ficheros en uso.
function Op-Comprobar {
	foreach ($carpeta in (Carpetas-A-Probar)) {
		$script:Actual = $carpeta.Substring([Math]::Min($carpeta.Length, $App.TrimEnd('\').Length)).TrimStart('\')
		if (-not $script:Actual) { $script:Actual = '.' }
		$prueba = Unir $carpeta ('.prueba_escritura_' + $PID)
		[IO.File]::WriteAllText((Largo $prueba), 'x')
		[IO.File]::Move((Largo $prueba), (Largo ($prueba + '.2')))
		[IO.File]::Delete((Largo ($prueba + '.2')))
	}
	$total = 0
	foreach ($rel in (Leer-Lineas $ListaNuevos)) {
		$ruta = Largo (Unir $App $rel)
		if (-not [IO.File]::Exists($ruta)) { continue }
		$script:Actual = $rel
		# El mismo permiso (DELETE) que pide renombrar: falla si otro programa lo tiene abierto sin
		# compartir, y no falla con una DLL cargada (que si se puede renombrar).
		Con-Reintentos ({
			$f = New-Object IO.FileStream($ruta, [IO.FileMode]::Open, [Security.AccessControl.FileSystemRights]'Delete, ReadAttributes', [IO.FileShare]'ReadWrite, Delete', 4096, [IO.FileOptions]::None)
			$f.Dispose()
		}.GetNewClosure()) $rel $Reintentos
		$total++
	}
	Anotar ('Permisos comprobados; ' + $total + ' ficheros que se sustituyen, ninguno en uso')
	Preparar-Respaldo
	$script:Actual = ''
}

function Reemplazar-Fichero([string]$Origen, [string]$Destino, [string]$Copia, [string]$Rel) {
	$script:Actual = $Rel
	if (Es-Fichero $Destino) { Mover-Fichero $Destino $Copia $Rel }
	elseif (Es-Carpeta $Destino) { Mover-Carpeta $Destino $Copia $Rel $Reintentos }
	Mover-Fichero $Origen $Destino $Rel
}

# Fichero a fichero: se aparta todo lo instalado (tambien lo que la version nueva ya no trae) y se
# coloca lo nuevo. Lo que solo era de la version anterior y no se deja mover se queda donde esta.
function Fusionar([string]$Origen, [string]$Destino, [string]$Copia, [string]$Rel) {
	if (Es-Carpeta $Destino) {
		foreach ($r in (Ficheros $Destino)) {
			$script:Actual = $Rel + '\' + $r
			try {
				Mover-Fichero (Unir $Destino $r) (Unir $Copia $r) $script:Actual
			} catch {
				if (Es-Fichero (Unir $Origen $r)) { throw }
				Anotar ('No se puede apartar ' + $script:Actual + ' (en uso); como la version nueva no lo trae, se deja donde esta')
			}
		}
	}
	foreach ($r in (Ficheros $Origen)) {
		$script:Actual = $Rel + '\' + $r
		Mover-Fichero (Unir $Origen $r) (Unir $Destino $r) $script:Actual
	}
}

function Reemplazar([string]$Origen, [string]$Destino, [string]$Copia, [string]$Rel) {
	$script:Actual = $Rel
	if (-not (Es-Carpeta $Origen)) { Reemplazar-Fichero $Origen $Destino $Copia $Rel; return }
	if (Es-Fichero $Destino) { Mover-Fichero $Destino $Copia $Rel }
	if (Es-Carpeta $Destino) {
		try {
			Mover-Carpeta $Destino $Copia $Rel 2
		} catch {
			Anotar ('La carpeta ' + $Rel + ' tiene algo en uso (error ' + (Codigo $_.Exception) + '); se sustituye fichero a fichero')
			Fusionar $Origen $Destino $Copia $Rel
			return
		}
	}
	try {
		Mover-Carpeta $Origen $Destino $Rel $Reintentos
	} catch {
		Anotar ('No se puede colocar la carpeta ' + $Rel + ' de una vez (error ' + (Codigo $_.Exception) + '); se coloca fichero a fichero')
		Fusionar $Origen $Destino $Copia $Rel
	}
}

# 2. Colocar la version nueva. Primero las carpetas, despues los ficheros sueltos y los dos
#    ejecutables al final: hasta el ultimo momento, lo que arranca es la version anterior.
function Op-Aplicar {
	$programa = Unir $Nueva 'programa'
	$copiaPrograma = Unir $Respaldo 'programa'
	# Nunca con una copia de seguridad ajena: la vuelta atras la pondria en su sitio.
	if ((Elementos $copiaPrograma $true).Count -gt 0 -or (Elementos (Unir $Respaldo 'recursos') $true).Count -gt 0) {
		Fallar 'respaldo_ocupado' 'data\temp\version_anterior' 'La copia de seguridad no esta vacia; no se toca nada' 2
	}
	$nombres = @([IO.Directory]::GetFileSystemEntries((Largo $programa)) | ForEach-Object { [IO.Path]::GetFileName($_) })
	$ordenados = @($nombres | Sort-Object @{ Expression = { if (Es-Carpeta (Unir $programa $_)) { 0 } elseif ($Ejecutables -contains $_) { 2 } else { 1 } } }, @{ Expression = { $_ } })
	$mitad = [Math]::Floor($ordenados.Count / 2)
	$hechos = 0
	foreach ($nombre in $ordenados) {
		if ($hechos -eq $mitad) { Punto-De-Prueba }
		Reemplazar (Unir $programa $nombre) (Unir $App $nombre) (Unir $copiaPrograma $nombre) $nombre
		$hechos++
	}
	$recursos = Unir $Nueva 'recursos'
	$n = 0
	foreach ($rel in (Ficheros $recursos)) {
		Reemplazar-Fichero (Unir $recursos $rel) (Unir $Datos $rel) (Unir (Unir $Respaldo 'recursos') $rel) ('data\' + $rel)
		$n++
	}
	$script:Actual = ''
	Anotar ('Version nueva colocada: ' + $ordenados.Count + ' elementos del programa y ' + $n + ' recursos')
}

function Devolver-Fichero([string]$Copia, [string]$Destino, [string]$Descartada, [string]$Rel) {
	$script:Actual = $Rel
	if (Es-Fichero $Destino) { Mover-Fichero $Destino $Descartada $Rel }
	elseif (Es-Carpeta $Destino) { Mover-Carpeta $Destino $Descartada $Rel $Reintentos }
	Mover-Fichero $Copia $Destino $Rel
}

# 3. Vuelta atras. Se puede repetir: solo mueve lo que sigue en la copia de seguridad y quita lo
#    que la version nueva trajo y antes no existia. Al final COMPRUEBA con el inventario.
function Op-Restaurar {
	if (-not (Es-Fichero $Inventario)) { Fallar 'sin_inventario' '' 'Falta original.txt: no se puede comprobar la vuelta atras' }
	$original = Leer-Inventario
	$superiores = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
	foreach ($rel in $original.Keys) { [void]$superiores.Add($rel.Split('\')[0]) }
	$nuevos = Leer-Lineas $ListaNuevos
	$superioresNuevos = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
	foreach ($rel in $nuevos) { [void]$superioresNuevos.Add($rel.Split('\')[0]) }
	$descartada = Unir (Unir $Trabajo 'descartada') ([string][DateTime]::UtcNow.Ticks)
	$copiaPrograma = Unir $Respaldo 'programa'
	$devueltos = 0
	if (Es-Carpeta $copiaPrograma) {
		foreach ($ruta in [IO.Directory]::GetFileSystemEntries((Largo $copiaPrograma))) {
			$nombre = [IO.Path]::GetFileName($ruta)
			$copia = Unir $copiaPrograma $nombre
			$destino = Unir $App $nombre
			$script:Actual = $nombre
			if (-not (Es-Carpeta $copia)) { Devolver-Fichero $copia $destino (Unir $descartada $nombre) $nombre; $devueltos++; continue }
			if (-not (Es-Carpeta $destino) -and -not (Es-Fichero $destino)) {
				Mover-Carpeta $copia $destino $nombre $Reintentos
				$devueltos++
				continue
			}
			foreach ($r in (Ficheros $copia)) {
				Devolver-Fichero (Unir $copia $r) (Unir $destino $r) (Unir $descartada ($nombre + '\' + $r)) ($nombre + '\' + $r)
				$devueltos++
			}
		}
	}
	# Lo que la version nueva puso en la raiz y antes no existia (data nunca se toca).
	foreach ($ruta in [IO.Directory]::GetFileSystemEntries((Largo $App))) {
		$nombre = [IO.Path]::GetFileName($ruta)
		if ($nombre -eq 'data' -or $superiores.Contains($nombre) -or -not $superioresNuevos.Contains($nombre)) { continue }
		$script:Actual = $nombre
		if (Es-Carpeta (Unir $App $nombre)) { Mover-Carpeta (Unir $App $nombre) (Unir $descartada ('sobrantes\' + $nombre)) $nombre $Reintentos }
		else { Mover-Fichero (Unir $App $nombre) (Unir $descartada ('sobrantes\' + $nombre)) $nombre }
	}
	$copiaRecursos = Unir $Respaldo 'recursos'
	foreach ($rel in (Ficheros $copiaRecursos)) {
		Devolver-Fichero (Unir $copiaRecursos $rel) (Unir $Datos $rel) (Unir $descartada ('data\' + $rel)) ('data\' + $rel)
		$devueltos++
	}
	# Ficheros nuevos dentro de carpetas que ya existian (lib, recursos de data).
	foreach ($rel in $nuevos) {
		if ($original.ContainsKey($rel)) { continue }
		$ruta = Unir $App $rel
		if (Es-Fichero $ruta) {
			$script:Actual = $rel
			Mover-Fichero $ruta (Unir $descartada ('sobrantes\' + $rel)) $rel
		}
	}
	$faltan = 0
	$primero = ''
	foreach ($par in $original.GetEnumerator()) {
		$info = New-Object IO.FileInfo((Largo (Unir $App $par.Key)))
		if (-not $info.Exists -or $info.Length -ne $par.Value) {
			$faltan++
			if (-not $primero) { $primero = $par.Key }
		}
	}
	if ($faltan -gt 0) { Fallar 'restauracion_incompleta' $primero ('Tras la vuelta atras faltan o no coinciden ' + $faltan + ' ficheros; el primero: ' + $primero) }
	$script:Actual = ''
	Anotar ('Vuelta atras comprobada: ' + $devueltos + ' elementos devueltos; los ' + $original.Count + ' ficheros de la version anterior estan en su sitio')
	Borrar-O-Apartar $Respaldo 'version_anterior'
	Borrar-O-Apartar (Unir $Trabajo 'descartada') 'descartada'
}

# 4. La version nueva confirmo su arranque: se quita la copia de seguridad.
function Op-Terminar {
	Borrar-O-Apartar $Respaldo 'version_anterior'
	Anotar 'Copia de seguridad retirada'
}

function Op-Limpiar {
	foreach ($nombre in 'nueva', 'descarga', 'descartada') {
		$ruta = Unir $Trabajo $nombre
		if (Es-Carpeta $ruta) { Borrar-O-Apartar $ruta $nombre }
	}
	if (Es-Carpeta $PorBorrar) { [void](Borrar-Arbol $PorBorrar 2) }
}

try {
	switch ($Operacion) {
		'comprobar' { Op-Comprobar }
		'aplicar' { Op-Aplicar }
		'restaurar' { Op-Restaurar }
		'terminar' { Op-Terminar }
		'limpiar' { Op-Limpiar }
		default { throw ('Operacion desconocida: ' + $Operacion) }
	}
} catch {
	$numero = Codigo $_.Exception
	Fallar (Motivo-De $numero) $script:Actual ('Fallo en ' + $Operacion + ' con ' + $script:Actual + ' (error ' + $numero + '): ' + (Interna $_.Exception).Message)
}
exit 0
"""

_PLANTILLA_BAT = r"""@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem Script de sustitucion generado por app/services/actualizador.py. No lo edite.
rem Modo actualizar: espera a que se cierre la aplicacion y coloca la version nueva.
rem Modo recuperar: deshace una sustitucion interrumpida (corte de luz, proceso cerrado a la fuerza).
rem recuperar.bat se puede ejecutar a mano, con doble clic, si la aplicacion no arranca.
rem Sin el PSModulePath de PowerShell 7: el powershell.exe 5.1 de abajo usa sus propios modulos.
set "PSModulePath="
set "MODO={modo}"
set "APP={app}"
set "DATOS_APP=%APP%\data"
set "TRABAJO={trabajo}"
set "NUEVA=%TRABAJO%\nueva"
set "RESPALDO={respaldo}"
set "MARCADOR={marcador}"
set "RESULTADO={resultado}"
set "ARCHIVO_PID=%TRABAJO%\pid_nueva.txt"
set "PID_SCRIPT=%TRABAJO%\pid_script.txt"
set "DIARIO=%TRABAJO%\diario.txt"
set "DETALLE=%TRABAJO%\detalle.txt"
set "MOTOR=%TRABAJO%\sustituir.ps1"
set "REGISTRO={registro}"
set "EJECUTABLE={ejecutable}"
set "EJECUTABLE_REPRODUCTOR={ejecutable_reproductor}"
set "VERSION_NUEVA={version_nueva}"
set "VERSION_ACTUAL={version_actual}"
set "PID_APP={pid}"
if not "%~1"=="" set "PID_APP=%~1"
set "ESPERA_CIERRE={espera_cierre}"
set "ESPERA_SALUD={espera_salud}"
set "REINTENTOS={reintentos}"
set "PUNTO_FALLO={punto_de_fallo}"
set "RECURSOS={recursos}"
set "SISTEMA=%SystemRoot%\System32"
set "MOTIVO=desconocido"
set "ESPERANDO=%TRABAJO%\esperando_salud.txt"
rem Carpeta para buscar procesos abiertos de ESTA instalacion (PowerShell la lee del entorno): cualquier
rem ejecutable que viva en ella (el Estudio y el reproductor) o cuya linea de ordenes la nombre.
set "RUTA_EXE=%APP%\%EJECUTABLE%"
set "POWERSHELL=%SISTEMA%\WindowsPowerShell\v1.0\powershell.exe"
set "CARPETA_APP_BUSCADA=%APP%\"
rem Entre comillas, | y ^ son literales: no se escapan.
set "COPIAS_ABIERTAS=Get-CimInstance Win32_Process | Where-Object { (($_.ExecutablePath -and $_.ExecutablePath.StartsWith($env:CARPETA_APP_BUSCADA, [System.StringComparison]::OrdinalIgnoreCase)) -or ($_.CommandLine -and $_.CommandLine.Contains($env:CARPETA_APP_BUSCADA))) -and $_.Name -notmatch '^(cmd|conhost|powershell|robocopy|find|findstr|tasklist|ping|taskkill)' }"

rem PID de este script (el cmd.exe que lo ejecuta): la aplicacion lo mira para saber si sigue en marcha.
"%POWERSHELL%" -NoProfile -NonInteractive -Command "[IO.File]::WriteAllText($env:PID_SCRIPT, [string](Get-CimInstance Win32_Process -Filter ('ProcessId=' + $PID)).ParentProcessId)" >nul 2>&1

call :anotar "Inicio (%MODO%): de %VERSION_ACTUAL% a %VERSION_NUEVA%"
if /I "%MODO%"=="recuperar" goto recuperar
if exist "%DIARIO%" goto recuperar
if not exist "%APP%\%EJECUTABLE%" goto instalacion_no_valida
if not exist "%NUEVA%\programa\%EJECUTABLE%" goto instalacion_no_valida

rem 1. Esperar a que la aplicacion se cierre (sin matarla nunca).
set /a INTENTOS=0
:esperar_cierre
"%SISTEMA%\tasklist.exe" /FI "PID eq %PID_APP%" /NH 2>nul | "%SISTEMA%\find.exe" " %PID_APP% " >nul
if errorlevel 1 goto cerrada
set /a INTENTOS+=1
if %INTENTOS% geq %ESPERA_CIERRE% goto no_se_cierra
ping -n 2 127.0.0.1 >nul
goto esperar_cierre

:cerrada
call :anotar "Aplicacion cerrada"
rem 1b. Esperar a que no quede ningun otro proceso de ESTA instalacion: el reproductor
rem     (tambien el que abre la sala), un segundo Estudio... Tampoco se les mata: puede
rem     haber un alumno en plena sesion.
set /a INTENTOS=0
:esperar_reproductores
call :hay_copia_abierta
if errorlevel 1 goto todo_cerrado
if %INTENTOS% equ 0 call :anotar "Hay un reproductor u otra copia abierta; se espera a que se cierre"
set /a INTENTOS+=1
if %INTENTOS% geq %ESPERA_CIERRE% goto no_se_cierra
ping -n 2 127.0.0.1 >nul
goto esperar_reproductores

:todo_cerrado
rem 2. Sin tocar nada: permisos de escritura y ficheros en uso (con reintentos de espera creciente).
del /f /q "%MARCADOR%" "%ARCHIVO_PID%" "%DETALLE%" >nul 2>&1
call :motor comprobar
if errorlevel 1 goto fallo_comprobacion

rem 3. Sustituir. Mientras exista el diario la instalacion esta a medias: si se corta la luz,
rem    la aplicacion lo ve al arrancar y lanza recuperar.bat.
call :diario aplicando
call :anotar "Se coloca la version nueva"
call :motor aplicar
if errorlevel 2 goto fallo_comprobacion
if errorlevel 1 goto fallo_copia
call :diario confirmando
call :anotar "Version nueva colocada; se lanza con {argumento}"

rem 4. Lanzar la version nueva guardando su PID (start no lo da; PowerShell si).
rem    Antes se avisa de la version esperada: si el usuario abre la aplicacion a
rem    mano a la vez, la copia que quede abierta tambien escribe el marcador.
>"%ESPERANDO%" echo %VERSION_NUEVA%
{linea_lanzar}
set "NUEVO_PID="
if exist "%ARCHIVO_PID%" set /p NUEVO_PID=<"%ARCHIVO_PID%"
echo(%NUEVO_PID%| "%SISTEMA%\findstr.exe" /r /x "[0-9][0-9]*" >nul || set "NUEVO_PID="
if not defined NUEVO_PID goto sin_pid
call :anotar "Version nueva en marcha con PID %NUEVO_PID%; esperando el marcador de salud"

rem 5. Esperar el marcador de salud.
set /a SEGUNDOS=0
:esperar_salud
if exist "%MARCADOR%" goto comprobar_marcador
"%SISTEMA%\tasklist.exe" /FI "PID eq %NUEVO_PID%" /NH 2>nul | "%SISTEMA%\find.exe" " %NUEVO_PID% " >nul
if errorlevel 1 goto nueva_cerrada
set /a SEGUNDOS+=1
if %SEGUNDOS% geq %ESPERA_SALUD% goto sin_salud
ping -n 2 127.0.0.1 >nul
goto esperar_salud

:comprobar_marcador
ping -n 2 127.0.0.1 >nul
"%SISTEMA%\findstr.exe" /l /c:"ok %VERSION_NUEVA%" "%MARCADOR%" >nul && goto sana
set "MOTIVO=marcador_incorrecto"
goto matar_y_volver

:nueva_cerrada
ping -n 2 127.0.0.1 >nul
if exist "%MARCADOR%" goto comprobar_marcador
rem La copia lanzada se cerro. Si queda otra copia de esta instalacion abierta
rem (el usuario la abrio a mano), se sigue esperando su marcador.
call :hay_copia_abierta
if errorlevel 1 goto nueva_cerrada_sin_copias
call :anotar "La copia lanzada se cerro, pero hay otra abierta; se espera su marcador"
:esperar_otra_copia
if exist "%MARCADOR%" goto comprobar_marcador
set /a SEGUNDOS+=1
if %SEGUNDOS% geq %ESPERA_SALUD% goto sin_salud_otra
call :hay_copia_abierta
if errorlevel 1 goto nueva_cerrada_sin_copias
ping -n 2 127.0.0.1 >nul
goto esperar_otra_copia

:nueva_cerrada_sin_copias
if exist "%MARCADOR%" goto comprobar_marcador
set "MOTIVO=se_cerro_sin_confirmar"
goto volver_atras

:sin_salud_otra
set "MOTIVO=sin_marcador_de_salud"
goto volver_atras

:sin_salud
set "MOTIVO=sin_marcador_de_salud"
:matar_y_volver
"%SISTEMA%\taskkill.exe" /F /T /PID %NUEVO_PID% >nul 2>&1
ping -n 3 127.0.0.1 >nul
goto volver_atras

:sin_pid
set "MOTIVO=no_se_pudo_lanzar"
goto volver_atras

:fallo_copia
call :leer_motivo fallo_copia
goto volver_atras

rem 6. Vuelta atras: el motor devuelve cada elemento a su sitio (NUNCA toca los datos del
rem    usuario) y comprueba con el inventario que la version anterior ha quedado entera.
:volver_atras
call :diario restaurando
call :anotar "Vuelta atras (%MOTIVO%): se restaura %VERSION_ACTUAL%"
rem Nunca se mueve un programa en uso: se cierran antes las copias de ESTA instalacion.
call :cerrar_copias_abiertas
call :motor restaurar
if errorlevel 1 goto fallo_restaurar
del /f /q "%DIARIO%" >nul 2>&1
call :anotar "Version %VERSION_ACTUAL% restaurada y comprobada; se relanza"
call :resultado revertida
call :limpiar
call :relanzar
goto fin

:fallo_restaurar
call :anotar "ERROR GRAVE: la vuelta atras no ha terminado. Cierre la aplicacion y ejecute recuperar.bat de data\temp\actualizacion"
set "MOTIVO=restauracion_incompleta"
call :resultado rota
goto fin

:fallo_comprobacion
del /f /q "%DIARIO%" >nul 2>&1
call :leer_motivo fallo_comprobacion
call :anotar "No se puede sustituir (%MOTIVO%); la instalacion NO se ha tocado"
call :resultado no_aplicada
call :limpiar
call :relanzar
goto fin

:no_se_cierra
set "MOTIVO=la_aplicacion_no_se_cerro"
call :anotar "La aplicacion o un reproductor seguian abiertos tras %ESPERA_CIERRE% intentos; se cancela sin tocar nada"
call :resultado no_aplicada
call :limpiar
goto fin

:instalacion_no_valida
set "MOTIVO=instalacion_no_valida"
call :anotar "ERROR: falta el ejecutable en la instalacion o en la version nueva; no se toca nada"
call :resultado no_aplicada
goto fin

:sana
call :anotar "Arranque confirmado: actualizacion a %VERSION_NUEVA% completada"
set "MOTIVO=ninguno"
rem Primero el diario: desde aqui la version nueva es la buena y la copia ya no se restaura.
del /f /q "%DIARIO%" >nul 2>&1
call :motor terminar
call :resultado correcta
call :limpiar
if /I "%MODO%"=="recuperar" call :relanzar
goto fin

rem 7. Recuperacion tras un corte: si la version nueva ya habia confirmado su arranque se da
rem    por buena; si no, se vuelve a la anterior.
:recuperar
if not exist "%DIARIO%" goto nada_que_recuperar
call :anotar "Se recupera una sustitucion interrumpida"
if "%PID_APP%"=="0" goto recuperar_decidir
set /a INTENTOS=0
:recuperar_esperar_app
"%SISTEMA%\tasklist.exe" /FI "PID eq %PID_APP%" /NH 2>nul | "%SISTEMA%\find.exe" " %PID_APP% " >nul
if errorlevel 1 goto recuperar_decidir
set /a INTENTOS+=1
if %INTENTOS% geq %ESPERA_CIERRE% goto recuperar_decidir
ping -n 2 127.0.0.1 >nul
goto recuperar_esperar_app
:recuperar_decidir
"%SISTEMA%\findstr.exe" /b /l /c:"estado=confirmando" "%DIARIO%" >nul || goto recuperar_volver
if not exist "%MARCADOR%" goto recuperar_volver
"%SISTEMA%\findstr.exe" /l /c:"ok %VERSION_NUEVA%" "%MARCADOR%" >nul || goto recuperar_volver
call :anotar "La version nueva ya habia confirmado su arranque; se da por buena"
goto sana
:recuperar_volver
set "MOTIVO=interrumpida"
goto volver_atras

:nada_que_recuperar
call :anotar "No hay ninguna sustitucion a medias; nada que recuperar"
goto fin

:fin
call :anotar "Fin del script"
del /f /q "%PID_SCRIPT%" >nul 2>&1
rem Con la instalacion a medias el script se conserva: hace falta para recuperarla.
if exist "%DIARIO%" goto fin_conservando
endlocal
(goto) 2>nul & del /f /q "%~f0"
:fin_conservando
endlocal
exit /b 1

:anotar
>>"%REGISTRO%" echo [%date% %time%] %~1
exit /b 0

:diario
>"%DIARIO%" echo estado=%~1
>>"%DIARIO%" echo version=%VERSION_NUEVA%
>>"%DIARIO%" echo anterior=%VERSION_ACTUAL%
exit /b 0

rem Los errores de PowerShell van a un fichero aparte: el registro lo escribe el propio motor
rem y no puede estar abierto a la vez por esta redireccion.
:motor
"%POWERSHELL%" -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$motor = [scriptblock]::Create([IO.File]::ReadAllText($env:MOTOR)); & $motor %~1; exit $LASTEXITCODE" >nul 2>"%TRABAJO%\motor_errores.txt"
set "SALIDA_MOTOR=%errorlevel%"
for %%E in ("%TRABAJO%\motor_errores.txt") do if %%~zE gtr 0 type "%TRABAJO%\motor_errores.txt" >>"%REGISTRO%"
del /f /q "%TRABAJO%\motor_errores.txt" >nul 2>&1
exit /b %SALIDA_MOTOR%

rem Vuelve a abrir la aplicacion. Con PowerShell y no con «start»: start vuelve a interpretar
rem la orden y una carpeta con «&» (por ejemplo «Cosas & mas») la partiria.
:relanzar
{linea_relanzar}
exit /b 0

:leer_motivo
set "MOTIVO=%~1"
if not exist "%DETALLE%" exit /b 0
for /f "usebackq tokens=1,* delims==" %%A in ("%DETALLE%") do if /I "%%A"=="motivo" set "MOTIVO=%%B"
exit /b 0

:limpiar
call :motor limpiar
del /f /q "%ARCHIVO_PID%" "%MARCADOR%" "%ESPERANDO%" "%DETALLE%" "%TRABAJO%\original.txt" "%TRABAJO%\nuevos.txt" "%MOTOR%" >nul 2>&1
if /I not "%MODO%"=="recuperar" del /f /q "%TRABAJO%\recuperar.bat" >nul 2>&1
exit /b 0

rem errorlevel 0 si hay alguna copia abierta de ESTA instalacion: su ejecutable, o un
rem proceso cuya linea de ordenes apunta a la carpeta (nunca cmd, PowerShell ni
rem herramientas del propio script). Se busca por ruta, no por nombre: otra copia
rem del programa en otra carpeta no cuenta.
:hay_copia_abierta
"%POWERSHELL%" -NoProfile -NonInteractive -Command "if (@(%COPIAS_ABIERTAS%).Count -gt 0) { exit 0 } else { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:cerrar_copias_abiertas
call :hay_copia_abierta
if errorlevel 1 exit /b 0
call :anotar "Hay copias de la aplicacion abiertas; se cierran antes de restaurar"
"%POWERSHELL%" -NoProfile -NonInteractive -Command "%COPIAS_ABIERTAS% | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
set /a ESPERAS=0
:esperar_copias
call :hay_copia_abierta
if errorlevel 1 exit /b 0
set /a ESPERAS+=1
if %ESPERAS% geq 15 exit /b 0
ping -n 2 127.0.0.1 >nul
goto esperar_copias

:resultado
>"%RESULTADO%" echo estado=%~1
>>"%RESULTADO%" echo motivo=%MOTIVO%
>>"%RESULTADO%" echo version=%VERSION_NUEVA%
>>"%RESULTADO%" echo anterior=%VERSION_ACTUAL%
if exist "%DETALLE%" "%SISTEMA%\findstr.exe" /b /l /c:"archivo=" "%DETALLE%" >>"%RESULTADO%"
exit /b 0
"""


def _bat(texto: str) -> str:
	"""Escapa ``%`` para un .bat (en un .bat, ``%%`` es un ``%`` literal)."""
	return str(texto).replace("%", "%%")


def _ps(texto: str) -> str:
	"""Cadena de PowerShell entre comillas simples (la comilla se duplica)."""
	return "'" + str(texto).replace("'", "''") + "'"


def _linea_lanzar(config: Configuracion, archivo_pid: Path | None) -> str:
	"""Orden que lanza la aplicación con PowerShell.

	Con ``archivo_pid``, lanza la versión nueva con ``--tras-actualizar`` y guarda
	su PID: ``start`` de cmd no lo devuelve, y sin PID no se podría terminar una
	versión nueva colgada antes de restaurar. Sin él, la vuelve a abrir sin más.
	Las comillas dobles de los argumentos se construyen con ``[char]34`` para no
	romper las comillas de la línea de cmd.
	"""
	programa, *argumentos = config.comando or [str(config.carpeta_app / config.ejecutable)]
	piezas = [f"[char]34 + {_ps(argumento)} + [char]34" for argumento in argumentos]
	if archivo_pid is not None:
		piezas.append(_ps(ARGUMENTO_TRAS_ACTUALIZAR))
	separador = " + ' ' + "
	lista = f" -ArgumentList ({separador.join(piezas)})" if piezas else ""
	guion = (
		"$ErrorActionPreference = 'Stop'; "
		f"$p = Start-Process -FilePath {_ps(programa)}{lista} "
		f"-WorkingDirectory {_ps(config.carpeta_app)} -PassThru"
	)
	if archivo_pid is not None:
		guion += f"; [IO.File]::WriteAllText({_ps(archivo_pid)}, [string]$p.Id)"
	return (
		'"%SISTEMA%\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -NonInteractive '
		f'-ExecutionPolicy Bypass -Command "{_bat(guion)}" >nul 2>&1'
	)


def _comprobar_instalacion(config: Configuracion) -> None:
	"""Defensa antes de generar un script que mueve archivos."""
	carpeta = config.carpeta_app
	if carpeta.parent == carpeta:
		raise ErrorActualizacion(_("La aplicación está en la raíz de una unidad; no se actualiza automáticamente."))
	if not (carpeta / config.ejecutable).is_file():
		raise ErrorActualizacion(
			_("No se encuentra {ejecutable} en la carpeta de la aplicación; no se puede actualizar.").format(ejecutable=config.ejecutable)
		)
	for nombre in config.data_actualizable:
		if not re.fullmatch(r"[A-Za-z0-9_-]+", nombre):
			raise ErrorActualizacion(f"Nombre de subcarpeta de data no válido: {nombre!r}")
	if config.punto_de_fallo not in ("", "aplicar", "pausa"):
		raise ValueError(f"Punto de fallo de prueba no válido: {config.punto_de_fallo!r}")


def _escribir_scripts(config: Configuracion, version_nueva: str, version_actual: str) -> Path:
	"""Escribe el motor, ``actualizar.bat`` y ``recuperar.bat``; devuelve la ruta del primero de los .bat.

	Los .bat van en CRLF y UTF-8 sin BOM (con ``chcp 65001``). ``recuperar.bat``
	es el mismo script en modo recuperación, sin proceso que esperar: así sirve
	también para ejecutarlo a mano si la aplicación no llegara a arrancar.
	"""
	trabajo = config.carpeta_trabajo
	trabajo.mkdir(parents=True, exist_ok=True)
	config.registro_script.parent.mkdir(parents=True, exist_ok=True)
	valores = {
		"app": _bat(config.carpeta_app),
		"trabajo": _bat(trabajo),
		"respaldo": _bat(config.carpeta_respaldo),
		"marcador": _bat(config.marcador_salud),
		"resultado": _bat(config.archivo_resultado),
		"registro": _bat(config.registro_script),
		"ejecutable": _bat(config.ejecutable),
		"ejecutable_reproductor": _bat(config.ejecutable_reproductor),
		"version_nueva": _bat(version_nueva),
		"version_actual": _bat(version_actual),
		"espera_cierre": str(int(config.espera_cierre)),
		"espera_salud": str(int(config.espera_salud)),
		"reintentos": str(max(0, int(config.reintentos_bloqueo))),
		"punto_de_fallo": config.punto_de_fallo,
		"recursos": " ".join(config.data_actualizable),
		"argumento": ARGUMENTO_TRAS_ACTUALIZAR,
		"linea_lanzar": _linea_lanzar(config, trabajo / "pid_nueva.txt"),
		"linea_relanzar": _linea_lanzar(config, None),
	}
	config.motor.write_bytes(_PLANTILLA_MOTOR.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
	rutas: dict[str, Path] = {}
	for modo, nombre, pid in (
		("actualizar", "actualizar.bat", str(int(config.pid_a_esperar or os.getpid()))),
		("recuperar", config.script_recuperar.name, "0"),
	):
		contenido = _PLANTILLA_BAT
		for clave, valor in {**valores, "modo": modo, "pid": pid}.items():
			contenido = contenido.replace("{" + clave + "}", valor)
		ruta = trabajo / nombre
		ruta.write_bytes(contenido.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
		rutas[modo] = ruta
	return rutas["actualizar"]


def preparar_sustitucion(config: Configuracion, info: InfoActualizacion) -> Path:
	"""Genera ``data/temp/actualizacion/actualizar.bat`` (y ``recuperar.bat`` y el motor)."""
	_comprobar_instalacion(config)
	for viejo in (config.marcador_salud, config.archivo_resultado, config.diario, config.carpeta_trabajo / "detalle.txt"):
		viejo.unlink(missing_ok=True)
	ruta = _escribir_scripts(config, info.version, config.version_actual)
	log.info("Script de sustitución preparado en %s", ruta)
	return ruta


def lanzar_sustitucion(ruta_bat: Path, argumentos: list[str] | tuple[str, ...] = ()) -> subprocess.Popen:
	"""Lanza el .bat oculto y desacoplado, para que sobreviva al cierre de la app.

	Se ejecuta con la carpeta del script como directorio de trabajo y como
	``.\\actualizar.bat``: así ``cmd /c`` no tiene que interpretar comillas de una
	ruta que pueda contener ``&`` u otros caracteres especiales. El ``.\\`` es
	necesario: con ``NoDefaultCurrentDirectoryInExePath`` definida, cmd no busca
	en la carpeta actual y el nombre suelto «no se reconoce como un comando».
	"""
	crear_sin_ventana = 0x08000000
	nuevo_grupo = 0x00000200
	salir_del_job = 0x01000000
	cmd = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "cmd.exe")
	opciones = {
		"cwd": str(ruta_bat.parent),
		"stdin": subprocess.DEVNULL,
		"stdout": subprocess.DEVNULL,
		"stderr": subprocess.DEVNULL,
		"close_fds": True,
	}
	orden = [cmd, "/d", "/c", ".\\" + ruta_bat.name, *argumentos]
	log.info("Lanzando el script de sustitución %s", ruta_bat)
	try:
		# Si la aplicación está dentro de un Job Object que mata a sus hijos al
		# cerrarse, hay que salir de él o el script moriría con ella.
		return subprocess.Popen(orden, creationflags=crear_sin_ventana | nuevo_grupo | salir_del_job, **opciones)
	except OSError:
		log.debug("No se pudo salir del Job Object; se lanza sin esa bandera", exc_info=True)
		return subprocess.Popen(orden, creationflags=crear_sin_ventana | nuevo_grupo, **opciones)


def descargar_y_preparar(config: Configuracion, info: InfoActualizacion, progreso: Progreso | None = None, cancelacion: Any = None) -> Path:
	"""Descarga, verifica, extrae, comprueba y genera el script. Pensada para una tarea de fondo.

	Todo lo que puede impedir la sustitución se comprueba aquí, ANTES de cerrar
	el Estudio: que no haya otra a medias, permisos de escritura, espacio libre
	y longitud de las rutas. Devuelve la ruta del ``.bat``; después la interfaz
	comprueba que no queda ningún reproductor abierto, llama a
	:func:`lanzar_sustitucion` y cierra el Estudio.
	"""
	if not puede_instalar(config):
		raise ErrorActualizacion(_("Esta copia se ejecuta desde el código fuente: no se sustituye automáticamente."))
	_comprobar_instalacion(config)
	if sustitucion_pendiente(config):
		raise ErrorEnCurso(
			_(
				"Hay una actualización anterior a medias en esta instalación. Cierre {aplicacion} y vuelva a abrirlo: "
				"se recuperará sola antes de poder actualizar otra vez."
			).format(aplicacion=NOMBRE_APLICACION)
		)
	comprobar_permisos(config)
	# El ZIP, lo descomprimido (que suele ocupar unas tres veces más) y un margen.
	comprobar_espacio(config.carpeta_trabajo, info.tamano * 4 + MARGEN_ESPACIO)
	ruta_zip = descargar(config, info, progreso, cancelacion)
	_avisar(progreso, "verificacion", 0, 1)
	verificar_paquete(ruta_zip, info)
	_avisar(progreso, "verificacion", 1, 1)
	extraida = extraer_seguro(ruta_zip, config.carpeta_trabajo / "nueva", config, progreso)
	ruta_zip.unlink(missing_ok=True)
	_avisar(progreso, "preparacion", 0, 1)
	nuevos = escribir_inventario(config, extraida)
	comprobar_rutas(config, nuevos)
	# Mover no necesita espacio; los registros, el diario y la versión nueva al arrancar, sí.
	comprobar_espacio(config.carpeta_trabajo, MARGEN_ESPACIO)
	ruta_bat = preparar_sustitucion(config, info)
	_avisar(progreso, "preparacion", 1, 1)
	return ruta_bat


def _proceso_vivo_desde(pid: int, antes_de: float) -> bool:
	"""True si ``pid`` es un ``cmd.exe`` vivo que arrancó antes de ``antes_de`` (marca de tiempo).

	La hora de inicio descarta un PID reutilizado: tras un corte de luz, otro
	cmd.exe puede tener el mismo número, pero habrá arrancado después.
	"""
	if sys.platform != "win32" or pid <= 0:
		return False
	import ctypes
	from ctypes import wintypes

	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.OpenProcess.restype = wintypes.HANDLE
	kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
	kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
	kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
	kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
	kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
	proceso = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
	if not proceso:
		return False
	try:
		codigo = wintypes.DWORD()
		if not kernel32.GetExitCodeProcess(proceso, ctypes.byref(codigo)) or codigo.value != 259:  # STILL_ACTIVE
			return False
		bufer = ctypes.create_unicode_buffer(32768)
		longitud = wintypes.DWORD(len(bufer))
		if not kernel32.QueryFullProcessImageNameW(proceso, 0, bufer, ctypes.byref(longitud)):
			return False
		if os.path.basename(bufer.value).lower() != "cmd.exe":
			return False
		inicio, salida, nucleo, usuario = (wintypes.FILETIME() for _ in range(4))
		if not kernel32.GetProcessTimes(proceso, ctypes.byref(inicio), ctypes.byref(salida), ctypes.byref(nucleo), ctypes.byref(usuario)):
			return False
		# FILETIME: intervalos de 100 ns desde 1601.
		segundos = ((inicio.dwHighDateTime << 32) | inicio.dwLowDateTime) / 10_000_000 - 11_644_473_600
		return segundos <= antes_de + 2
	finally:
		kernel32.CloseHandle(proceso)


def script_en_marcha(config: Configuracion) -> bool:
	"""¿Sigue en marcha el script de sustitución de esta instalación?

	El script deja su PID en ``pid_script.txt`` al empezar y lo borra al
	terminar. Si falta (PowerShell no pudo escribirlo) pero hay un diario
	reciente, se supone que sí: es mejor esperar que estorbar a un script vivo.
	"""
	try:
		texto = config.pid_script.read_text(encoding="utf-8", errors="replace").strip()
		escrito = config.pid_script.stat().st_mtime
	except FileNotFoundError:
		try:
			return time.time() - config.diario.stat().st_mtime < 15 * 60
		except FileNotFoundError:
			return False
	except OSError:
		log.warning("No se pudo leer el PID del script de sustitución", exc_info=True)
		return False
	if not texto.isdigit():
		return False
	return _proceso_vivo_desde(int(texto), escrito)


def sustitucion_pendiente(config: Configuracion) -> bool:
	"""True si hay una sustitución a medias (diario presente) o un script trabajando."""
	return config.diario.is_file() or script_en_marcha(config)


def _leer_clave_valor(ruta: Path) -> dict[str, str]:
	"""Lee un fichero ``clave=valor`` de los que escribe el script."""
	datos: dict[str, str] = {}
	for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
		clave, _separador, valor = linea.partition("=")
		if clave.strip():
			datos[clave.strip()] = valor.strip()
	return datos


def recuperar_si_interrumpida(config: Configuracion, lanzar: Callable[[Path, list[str]], Any] | None = None) -> bool:
	"""Al arrancar: si una sustitución quedó a medias (corte de luz), lanza ``recuperar.bat``.

	Devuelve True si se lanzó: entonces la aplicación debe cerrarse enseguida
	(el script espera a que se cierre, deshace la sustitución, comprueba la
	versión anterior y la vuelve a abrir, que explicará lo ocurrido). Los
	scripts se vuelven a escribir por si faltaran. No se relanza si ya falló
	una recuperación (resultado «rota»): el usuario recibe el mensaje y puede
	ejecutar ``recuperar.bat`` a mano.
	"""
	if not config.diario.is_file():
		return False
	try:
		if config.archivo_resultado.is_file() and _leer_clave_valor(config.archivo_resultado).get("estado") == "rota":
			log.warning("Una recuperación anterior no terminó; no se vuelve a lanzar sola")
			return False
		if script_en_marcha(config):
			log.info("Hay una sustitución a medias, pero su script sigue en marcha; no se interviene")
			return False
		diario = _leer_clave_valor(config.diario)
		version_nueva = diario.get("version") or "?"
		version_anterior = diario.get("anterior") or config.version_actual
		log.warning(
			"Sustitución interrumpida (estado %s, de %s a %s): se lanza la recuperación",
			diario.get("estado"),
			version_anterior,
			version_nueva,
		)
		_escribir_scripts(config, version_nueva, version_anterior)
		(lanzar or lanzar_sustitucion)(config.script_recuperar, [str(os.getpid())])
	except OSError:
		log.exception("No se pudo lanzar la recuperación de la actualización interrumpida")
		return False
	return True


def recuperar_al_arrancar() -> bool:
	"""Lo llama ``main.py`` antes de abrir ninguna ventana. Nunca impide arrancar.

	Solo en la versión compilada (desde el código fuente no se sustituye nada).
	"""
	# La versión que lanza el propio script (con --tras-actualizar) arranca con el diario
	# presente a propósito: el script sigue vivo esperando su marcador de salud.
	if not paths.CONGELADA or ARGUMENTO_TRAS_ACTUALIZAR in sys.argv:
		return False
	try:
		return recuperar_si_interrumpida(configuracion_por_defecto())
	except Exception:  # noqa: BLE001 - un resto ilegible de una actualización no debe impedir arrancar
		log.exception("No se pudo comprobar si quedó una actualización a medias")
		return False


# ════════════════════════════════════════════════════════════════════════════
# El segundo ejecutable: reproductores abiertos
# ════════════════════════════════════════════════════════════════════════════


def _procesos_con_imagen(ruta_ejecutable: Path) -> list[int]:
	"""PID de los procesos de Windows cuyo ejecutable es exactamente ``ruta_ejecutable``.

	Se busca por ruta completa y no por nombre: un reproductor de OTRA copia de
	EntornoLab (en otra carpeta o en un pendrive) no impide actualizar esta.
	"""
	if sys.platform != "win32":
		return []
	import ctypes
	from ctypes import wintypes

	class Entrada(ctypes.Structure):
		_fields_ = [  # noqa: RUF012 - estructura PROCESSENTRY32W de Windows
			("dwSize", wintypes.DWORD),
			("cntUsage", wintypes.DWORD),
			("th32ProcessID", wintypes.DWORD),
			("th32DefaultHeapID", ctypes.c_size_t),
			("th32ModuleID", wintypes.DWORD),
			("cntThreads", wintypes.DWORD),
			("th32ParentProcessID", wintypes.DWORD),
			("pcPriClassBase", wintypes.LONG),
			("dwFlags", wintypes.DWORD),
			("szExeFile", wintypes.WCHAR * 260),
		]

	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
	kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
	kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entrada)]
	kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entrada)]
	kernel32.OpenProcess.restype = wintypes.HANDLE
	kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
	kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
	kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
	buscada = os.path.normcase(str(ruta_ejecutable))
	nombre = ruta_ejecutable.name.lower()
	encontrados: list[int] = []
	instantanea = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
	if not instantanea or instantanea == wintypes.HANDLE(-1).value:
		log.warning("No se pudo enumerar los procesos (error %d)", ctypes.get_last_error())
		return []
	try:
		entrada = Entrada()
		entrada.dwSize = ctypes.sizeof(Entrada)
		sigue = kernel32.Process32FirstW(instantanea, ctypes.byref(entrada))
		while sigue:
			if entrada.szExeFile.lower() == nombre and entrada.th32ProcessID != os.getpid():
				proceso = kernel32.OpenProcess(0x1000, False, entrada.th32ProcessID)  # PROCESS_QUERY_LIMITED_INFORMATION
				if proceso:
					try:
						bufer = ctypes.create_unicode_buffer(32768)
						longitud = wintypes.DWORD(len(bufer))
						if kernel32.QueryFullProcessImageNameW(proceso, 0, bufer, ctypes.byref(longitud)) and (
							os.path.normcase(bufer.value) == buscada
						):
							encontrados.append(int(entrada.th32ProcessID))
					finally:
						kernel32.CloseHandle(proceso)
			sigue = kernel32.Process32NextW(instantanea, ctypes.byref(entrada))
	finally:
		kernel32.CloseHandle(instantanea)
	return encontrados


def reproductores_abiertos(config: Configuracion) -> list[int]:
	"""PID de los reproductores de ESTA instalación que siguen abiertos.

	Mientras haya alguno no se puede sustituir ``EntornoLabJugar.exe`` ni sus
	bibliotecas, y cerrarlo a la fuerza cortaría la sesión de un alumno. Suma
	los que lanzó el Estudio (``app.core.procesos``) y los que alguien abrió
	por su cuenta desde la misma carpeta.
	"""
	from app.core import procesos

	encontrados = {proceso.pid for proceso in procesos.procesos_vivos()}
	try:
		encontrados.update(_procesos_con_imagen(config.carpeta_app / config.ejecutable_reproductor))
	except OSError:
		log.warning("No se pudo comprobar si hay reproductores abiertos", exc_info=True)
	return sorted(encontrados)


def cerrar_reproductores(config: Configuracion, espera: float = 3.0) -> list[int]:
	"""Cierra los reproductores que lanzó el Estudio y devuelve los que siguen abiertos.

	Solo se llama después de AVISAR al usuario y de que acepte: la sesión en
	curso del alumno se pierde. Los reproductores abiertos por su cuenta no se
	tocan: hay que cerrarlos a mano (el script de sustitución los espera).
	"""
	from app.core import procesos

	procesos.terminar_todos(espera)
	return reproductores_abiertos(config)


# ════════════════════════════════════════════════════════════════════════════
# Arranque de la aplicación
# ════════════════════════════════════════════════════════════════════════════


def _se_espera_esta_version(config: Configuracion) -> bool:
	"""¿Hay un script de sustitución esperando el marcador de salud de esta versión?

	Si el usuario abre la aplicación a mano justo cuando el script lanza la
	versión nueva, la que lanzó el script ve «otra instancia» y se cierra, y la
	que queda abierta no tenía ``--tras-actualizar``: el script volvería atrás
	con la aplicación abierta. Por eso cualquier copia de la versión esperada
	confirma que arranca bien.
	"""
	try:
		esperada = config.aviso_espera_salud.read_text(encoding="utf-8").strip()
	except OSError:
		return False
	return esperada == config.version_actual


def confirmar_arranque(config: Configuracion, tras_actualizar: bool | None = None) -> None:
	"""Llamar unos segundos después de mostrar la ventana principal.

	Anota la versión como confirmada (protección contra retrocesos) y, si la
	aplicación arrancó con ``--tras-actualizar``, escribe el marcador de salud
	que espera el script. Esperar unos segundos demuestra que la ventana se
	abrió y el bucle de eventos funciona, no solo que ``main.py`` empezó.
	"""
	if tras_actualizar is None:
		tras_actualizar = ARGUMENTO_TRAS_ACTUALIZAR in sys.argv
	confirmar_version(config)
	if not tras_actualizar and not _se_espera_esta_version(config):
		return
	try:
		config.marcador_salud.parent.mkdir(parents=True, exist_ok=True)
		temporal = config.marcador_salud.with_name("salud.tmp")
		temporal.write_text(f"ok {config.version_actual}\n", encoding="utf-8")
		os.replace(temporal, config.marcador_salud)
		log.info("Marcador de salud escrito para la versión %s", config.version_actual)
	except OSError:
		log.exception("No se pudo escribir el marcador de salud: el script volverá a la versión anterior")


def limpiar_trabajo(config: Configuracion) -> None:
	"""Borra los restos de actualizaciones terminadas, salvo una descarga a medias.

	No toca nada mientras haya una sustitución a medias (``diario.txt``) o el
	script siga en marcha: esos ficheros son los que permiten recuperarla. Lo
	que no se deja borrar (una DLL de la versión anterior que otro proceso aún
	tiene cargada, un fichero que el antivirus está revisando) se reintenta en
	el siguiente arranque y, si hay permisos, se programa para el reinicio.
	"""
	trabajo = config.carpeta_trabajo
	if sustitucion_pendiente(config):
		log.info("Hay una sustitución a medias o en marcha; no se limpia %s", trabajo)
		return
	pendientes: list[Path] = []
	if config.carpeta_respaldo.exists():
		pendientes.append(config.carpeta_respaldo)
	if trabajo.is_dir():
		pendientes.extend(elemento for elemento in sorted(trabajo.iterdir()) if elemento.name != "descarga")
	for elemento in pendientes:
		if elemento.is_dir() and not elemento.is_symlink():
			if borrar_carpeta(elemento):
				continue
			log.info("No se pudo borrar %s (algo sigue en uso); se reintentará en el próximo arranque", elemento)
			programar_borrado_al_reiniciar(elemento)
		elif not _borrar_fichero(elemento):
			log.info("No se pudo borrar %s; se reintentará en el próximo arranque", elemento)


def leer_resultado(config: Configuracion) -> dict[str, str] | None:
	"""Lo que dejó el script en ``resultado.txt`` (estado, motivo, version, anterior, archivo), sin borrarlo."""
	try:
		return _leer_clave_valor(config.archivo_resultado)
	except FileNotFoundError:
		return None
	except OSError:
		log.warning("No se pudo leer el resultado de la actualización", exc_info=True)
		return None


def _causa(motivo: str, archivo: str) -> str | None:
	"""Por qué no se pudo actualizar, en palabras del usuario (o ``None`` si no hay una causa concreta)."""
	if motivo == "fichero_bloqueado":
		if archivo:
			return _(
				"otro programa tenía en uso el archivo {archivo} (suele ser el antivirus, el indexador de Windows "
				"o una copia de {aplicacion} abierta)"
			).format(archivo=archivo, aplicacion=NOMBRE_APLICACION)
		return _(
			"otro programa tenía en uso un archivo de {aplicacion} (suele ser el antivirus, el indexador de Windows o una copia abierta)"
		).format(aplicacion=NOMBRE_APLICACION)
	if motivo == "sin_permiso":
		return _(
			"Windows no deja modificar la carpeta de {aplicacion}; si está en Archivos de programa, muévala a una carpeta suya, como Documentos"
		).format(aplicacion=NOMBRE_APLICACION)
	if motivo == "sin_espacio":
		return _("el disco se ha llenado")
	if motivo == "ruta_larga":
		return _("la carpeta de {aplicacion} está demasiado honda; muévala a una ruta más corta").format(aplicacion=NOMBRE_APLICACION)
	if motivo == "interrumpida":
		return _("se interrumpió antes de terminar, por ejemplo por un corte de luz o porque se cerró el proceso a la fuerza")
	return None


# Motivos por los que la versión nueva se colocó pero no llegó a arrancar bien:
# solo entonces se salta la versión (volver a ofrecerla daría el mismo fallo).
_NO_ARRANCO = ("se_cerro_sin_confirmar", "sin_marcador_de_salud", "marcador_incorrecto", "no_se_pudo_lanzar")


def mensaje_resultado(datos: dict[str, str], version_actual: str) -> str | None:
	"""Mensaje accesible que explica cómo acabó la actualización anterior.

	Siempre dice en qué versión sigue la aplicación y que los datos del
	usuario no se han tocado; ``None`` si la actualización salió bien (la
	versión nueva ya lo anuncia al arrancar).
	"""
	estado, version, motivo = datos.get("estado", ""), datos.get("version", "?"), datos.get("motivo", "")
	anterior = datos.get("anterior") or version_actual
	if estado == "correcta":
		return None
	causa = _causa(motivo, datos.get("archivo", ""))
	if estado == "revertida" and motivo in _NO_ARRANCO:
		return _(
			"La versión {nueva} no arrancó correctamente y se ha vuelto a la versión {actual}. "
			"Sus datos no se han tocado. Los detalles están en data/logs/actualizacion.log."
		).format(nueva=version, actual=anterior)
	if estado == "no_aplicada" and motivo == "la_aplicacion_no_se_cerro":
		return _(
			"La actualización a la versión {version} no se aplicó porque la aplicación o un reproductor seguían abiertos. "
			"Puede volver a intentarlo desde el menú Ayuda."
		).format(version=version)
	if estado in ("revertida", "no_aplicada") and causa:
		return _(
			"No se pudo actualizar a la versión {nueva} porque {causa}. Sigue en la versión {actual} y sus datos no se han tocado. "
			"Puede volver a intentarlo desde el menú Ayuda."
		).format(nueva=version, causa=causa, actual=anterior)
	if estado == "revertida":
		return _(
			"No se pudo terminar de actualizar a la versión {nueva} y se ha vuelto a la versión {actual}. "
			"Sus datos no se han tocado. Los detalles están en data/logs/actualizacion.log."
		).format(nueva=version, actual=anterior)
	if estado == "no_aplicada":
		return _(
			"La actualización a la versión {version} no se aplicó y la instalación no se ha tocado. "
			"Los detalles están en data/logs/actualizacion.log."
		).format(version=version)
	return _(
		"La actualización a la versión {nueva} falló y no se pudo terminar de volver a la versión {actual}. Sus datos no se han tocado. "
		"Para repararlo, cierre {aplicacion} y ejecute recuperar.bat, que está en la carpeta data\\temp\\actualizacion; "
		"los detalles están en data/logs/actualizacion.log."
	).format(nueva=version, actual=anterior, aplicacion=NOMBRE_APLICACION)


def leer_resultado_anterior(config: Configuracion) -> str | None:
	"""Lee lo que dejó el script y devuelve un mensaje para el usuario (o ``None``).

	Llamar al arrancar. Si la versión nueva no arrancó, la salta para que la
	comprobación automática no la vuelva a ofrecer en bucle. Si el fallo fue
	pasajero (un archivo en uso, un corte de luz) no se salta: se puede
	reintentar. Con el resultado «rota» se conserva todo lo necesario para
	recuperar la instalación.
	"""
	datos = leer_resultado(config)
	if datos is None:
		return None
	try:
		config.archivo_resultado.unlink()
	except OSError:
		log.warning("No se pudo borrar el resultado de la actualización", exc_info=True)
		return None
	limpiar_trabajo(config)
	estado, version, motivo = datos.get("estado", ""), datos.get("version", "?"), datos.get("motivo", "")
	log.info(
		"Resultado de la actualización anterior: %s (versión %s, motivo %s, archivo %s)", estado, version, motivo, datos.get("archivo", "")
	)
	if estado == "revertida" and motivo in _NO_ARRANCO:
		try:
			saltar_version(version)
		except OSError, ValueError:
			log.warning("No se pudo anotar la versión fallida como saltada", exc_info=True)
	return mensaje_resultado(datos, config.version_actual)
