"""Traducción de los textos de la aplicación (gettext). El español es el idioma del código.

El texto que se escribe en el código es el que se muestra si no hay
traducción. Todo texto para el usuario pasa por ``_()`` para que la
aplicación pueda traducirse sin tocar el código.

Este módulo no depende de wx ni de pygame (wx solo se importa dentro de
``configurar_wx``), porque lo importan todas las capas: motor, reproductor y
Estudio.

Uso en cualquier módulo::

	from app.core.i18n import _, _n, N_

	etiqueta = _("&Guardar")
	resumen = _n("Se encontró {n} premio", "Se encontraron {n} premios", n).format(n=n)
	TIPOS = {"puerta": N_("Puerta")}   # se marca al importar...
	texto = _(TIPOS["puerta"])         # ...y se traduce al mostrar

``_``, ``_n`` y compañía son funciones que consultan el catálogo ACTIVO en
cada llamada: un ``from app.core.i18n import _`` hecho antes de elegir el
idioma (o antes de cambiarlo en caliente) sigue traduciendo bien. Las mismas
funciones se publican en ``builtins`` para el código que usa ``_`` sin
importarlo (las ventanas del esqueleto).

Uso en el arranque::

	idioma = i18n.inicializar(configuracion.obtener("general.idioma"))
	aplicacion = wx.App(False)
	i18n.configurar_wx(idioma)      # botones estándar de wx en ese idioma

Dónde están los catálogos: ``data/locales/<idioma>/LC_MESSAGES/entornolab.po``
(editable) y ``entornolab.mo`` (compilado con ``tools/compilar_traducciones.py``).
Se lee el ``.mo``; si no existe o el ``.po`` es más reciente, se lee el
``.po`` directamente aplicando las mismas validaciones que el compilador. Así
quien traduce prueba su trabajo sin herramientas y la versión distribuida
(solo con ``.mo``) arranca más deprisa.

Orden para elegir el idioma:

1. La variable de entorno ``APP_IDIOMA`` (probar una traducción sin tocar la
   configuración; las pruebas la fijan a ``es``).
2. El valor guardado en la configuración (``general.idioma``); ``auto``
   significa «el del sistema».
3. El idioma de la interfaz de Windows.
4. Español.

Si el idioma elegido no tiene catálogo o está dañado, se usa el español y se
registra un aviso: la aplicación arranca siempre.

Cambio en caliente (``cambiar_idioma``):

- Cambia al momento todo texto que se pida con ``_()`` a partir de entonces
  (mensajes, anuncios de voz, menús hablados del reproductor, diálogos que se
  abran después).
- No cambia solo lo ya pintado en wx (menús, etiquetas, columnas): registre
  funciones con ``al_cambiar_idioma`` para reconstruirlo.
- Los botones estándar de wxWidgets necesitan reiniciar (``necesita_reinicio``):
  un ``wx.Locale`` no se puede sustituir de forma segura con ventanas abiertas.

Además, ``traducir_datos`` traduce DATOS (complementos y entornos de ejemplo)
con ficheros ``locales/<idioma>.json`` que viajan junto a esos datos.

Procede de la plantilla del agente «traducciones», adaptada a la API que el
proyecto ya usaba (``_``, ``_n``, ``N_``, ``IDIOMA_ORIGEN``).
"""

from __future__ import annotations

import builtins
import copy
import gettext
import io
import json
import locale
import logging
import os
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from app.core import paths

log = logging.getLogger(__name__)

# Nombre de los catálogos (<DOMINIO>.po / .mo / .pot). Las herramientas de
# tools/ lo leen de aquí: cámbielo solo en este archivo.
DOMINIO = "entornolab"
# Idioma en el que está escrito el código fuente.
IDIOMA_ORIGEN = "es"
# Alias con el nombre que usa la plantilla del agente de traducciones.
IDIOMA_BASE = IDIOMA_ORIGEN
VARIABLE_IDIOMA = "APP_IDIOMA"
# Valores de configuración que significan «el del sistema».
AUTOMATICO = frozenset({"", "auto", "automatico", "automático", "sistema"})

# Nombres de cada idioma EN ESE IDIOMA: quien no entiende español encuentra
# el suyo en el selector.
NOMBRES_IDIOMA = {
	"es": "Español",
	"en": "English",
	"fr": "Français",
	"de": "Deutsch",
	"it": "Italiano",
	"pt": "Português",
	"pt_BR": "Português do Brasil",
	"ca": "Català",
	"gl": "Galego",
	"eu": "Euskara",
	"nl": "Nederlands",
	"pl": "Polski",
	"ru": "Русский",
	"uk": "Українська",
	"tr": "Türkçe",
	"ar": "العربية",
	"zh": "中文",
	"ja": "日本語",
}

# Claves de los datos (complementos, entornos, actividades) cuyo contenido es
# texto para la persona usuaria. Todo lo que cuelga de una de ellas se puede
# traducir; lo demás (ids, tipos, materiales, sonidos) son identificadores.
CAMPOS_TRADUCIBLES = frozenset(
	{"nombre", "descripcion", "texto", "mensaje", "mensajes", "titulo", "ayuda", "etiquetas", "categoria", "notas", "pista", "aviso"}
)

_traduccion: gettext.NullTranslations = gettext.NullTranslations()
_idioma: str = IDIOMA_ORIGEN
# Se conserva la referencia: si el recolector destruye el wx.Locale, los
# botones estándar vuelven al inglés sin avisar.
_locale_wx: Any = None
# Idioma con el que se creó el wx.Locale (para saber si hace falta reiniciar).
_idioma_wx: str | None = None
_oyentes: list[Callable[[str], None]] = []


# ── Funciones de traducción ──────────────────────────────────────────────────


def _(texto: str) -> str:
	"""Devuelve ``texto`` en el idioma activo; en español si no hay traducción.

	La cadena vacía se devuelve tal cual: en gettext, ``_("")`` es la
	cabecera del catálogo y aparecería como texto en pantalla.
	"""
	if not texto:
		return texto
	return _traduccion.gettext(texto)


def _n(uno: str, varios: str, cantidad: int) -> str:
	"""Devuelve la forma singular o plural que corresponde a ``cantidad`` en el idioma activo."""
	return _traduccion.ngettext(uno, varios, cantidad)


def N_(texto: str) -> str:  # noqa: N802 - nombre convencional de gettext
	"""Marca un texto para traducir más tarde sin traducirlo ahora.

	Sirve para tablas de constantes que se definen al importar el módulo,
	antes de que se haya elegido el idioma; se traducen después con ``_()``.
	"""
	return texto


def pgettext(contexto: str, texto: str) -> str:
	"""Traduce ``texto`` distinguiendo su ``contexto`` («Abrir» verbo o adjetivo)."""
	if not texto:
		return texto
	return _traduccion.pgettext(contexto, texto)


def npgettext(contexto: str, uno: str, varios: str, cantidad: int) -> str:
	"""Plural con contexto."""
	return _traduccion.npgettext(contexto, uno, varios, cantidad)


# Nombres clásicos de gettext, para quien los prefiera.
ngettext = _n

# Idiomas que escriben los decimales con punto («3.5 meters»); los demás, con coma.
IDIOMAS_PUNTO_DECIMAL = frozenset({"en", "zh", "ja"})


def separador_decimal() -> str:
	"""Separador decimal del idioma activo: «,» en español («3,5 metros»), «.» en inglés.

	Los campos de la aplicación aceptan los dos al leer un número; esto solo
	decide cómo se ESCRIBE un número para mostrarlo o decirlo por voz.
	"""
	return "." if _idioma.split("_")[0] in IDIOMAS_PUNTO_DECIMAL else ","


def _publicar_en_builtins() -> None:
	"""Publica las funciones en ``builtins`` para el código que no las importa.

	Se publican las funciones de este módulo (que consultan el catálogo
	activo), no los métodos del catálogo: así un cambio de idioma en caliente
	no exige volver a publicarlas.
	"""
	builtins._ = _
	builtins.gettext = _
	builtins.ngettext = _n
	builtins.n_ = _n
	builtins._n = _n
	builtins.pgettext = pgettext
	builtins.npgettext = npgettext
	builtins.N_ = N_


# ── Rutas ────────────────────────────────────────────────────────────────────


def carpeta_locales() -> Path:
	"""``data/locales`` (o ``$APP_DATA_DIR/locales``). No la crea: solo se lee."""
	redireccion = os.environ.get(paths.VARIABLE_DATA, "").strip()
	datos = Path(redireccion).expanduser() if redireccion else paths.ruta_base() / "data"
	return datos / "locales"


def _archivos_de(idioma: str) -> tuple[Path, Path]:
	"""Rutas del ``.mo`` y del ``.po`` de un idioma (existan o no)."""
	carpeta = carpeta_locales() / idioma / "LC_MESSAGES"
	return carpeta / f"{DOMINIO}.mo", carpeta / f"{DOMINIO}.po"


# ── Detección ────────────────────────────────────────────────────────────────


def normalizar(codigo: str | None) -> str:
	"""``es-ES``, ``es_ES.UTF-8`` o ``Spanish_Spain`` → ``es_ES``; ``EN`` → ``en``."""
	if not codigo:
		return ""
	codigo = codigo.strip().split(".")[0].split("@")[0].replace("-", "_")
	if "_" in codigo and len(codigo.split("_")[0]) > 3:
		# Nombre largo de Windows («Spanish_Spain»): se traduce con la tabla de locale.
		codigo = locale.normalize(codigo).split(".")[0]
	partes = codigo.split("_")
	if len(partes) >= 2 and partes[1]:
		return f"{partes[0].lower()}_{partes[1].upper()}"
	return partes[0].lower()


def idioma_sistema() -> str:
	"""Idioma de la interfaz del sistema (``es_ES``, ``en_US``...) o ``""`` si no se sabe.

	En Windows se pregunta el idioma de la INTERFAZ del usuario, no el formato
	regional: alguien puede tener Windows en inglés con fechas españolas.
	"""
	if sys.platform == "win32":
		try:
			import ctypes

			identificador = ctypes.windll.kernel32.GetUserDefaultUILanguage()
			codigo = locale.windows_locale.get(identificador, "")
			if codigo:
				return normalizar(codigo)
		except AttributeError, OSError:
			log.debug("No se pudo consultar GetUserDefaultUILanguage", exc_info=True)
	for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
		valor = os.environ.get(variable, "")
		if valor:
			return normalizar(valor.split(":")[0])
	try:
		return normalizar(locale.getlocale()[0])
	except ValueError, TypeError:
		log.debug("locale.getlocale() no devolvió un idioma", exc_info=True)
		return ""


def es_idioma_origen(codigo: str) -> bool:
	"""True si ``codigo`` es español en cualquiera de sus variantes (``es``, ``es_MX``...)."""
	return normalizar(codigo).split("_")[0] == IDIOMA_ORIGEN


def idiomas_disponibles() -> list[str]:
	"""Códigos de idioma que se pueden elegir: el español y los que tienen catálogo.

	Vale tanto un ``.mo`` compilado como un ``.po`` sin compilar. El español
	va siempre el primero; los demás, por orden alfabético de su nombre.
	"""
	encontrados: set[str] = set()
	carpeta = carpeta_locales()
	if carpeta.is_dir():
		for subcarpeta in carpeta.iterdir():
			mensajes = subcarpeta / "LC_MESSAGES"
			if (mensajes / f"{DOMINIO}.mo").is_file() or (mensajes / f"{DOMINIO}.po").is_file():
				encontrados.add(subcarpeta.name)
	encontrados.discard(IDIOMA_ORIGEN)
	return [IDIOMA_ORIGEN, *sorted(encontrados, key=lambda codigo: nombre_idioma(codigo).casefold())]


def nombre_idioma(codigo: str) -> str:
	"""Nombre del idioma escrito en ese idioma (``en`` → ``English``); el código si no se conoce."""
	return NOMBRES_IDIOMA.get(codigo) or NOMBRES_IDIOMA.get(codigo.split("_")[0]) or codigo


def resolver_idioma(configurado: str | None = None) -> str:
	"""Idioma que se intentará cargar, según el orden descrito en el módulo."""
	forzado = os.environ.get(VARIABLE_IDIOMA, "").strip()
	if forzado:
		return normalizar(forzado)
	if configurado and configurado.strip().casefold() not in AUTOMATICO:
		return normalizar(configurado)
	return idioma_sistema() or IDIOMA_ORIGEN


# ── Carga de catálogos ───────────────────────────────────────────────────────


def _cargar_mo(ruta: Path) -> gettext.NullTranslations:
	"""Catálogo compilado. Lanza ``OSError`` o ``ValueError`` si está dañado."""
	with open(ruta, "rb") as archivo:
		return gettext.GNUTranslations(archivo)


def _cargar_po(ruta: Path) -> gettext.NullTranslations:
	"""Catálogo sin compilar, con las mismas validaciones que el compilador.

	Las entradas dudosas (aproximadas, vacías, con marcadores distintos del
	original) se omiten: para ellas se muestra el texto en español.
	"""
	from app.core import catalogo_po

	resultado = catalogo_po.mensajes_compilables(catalogo_po.leer_po(ruta))
	for error in resultado.errores:
		log.warning("Traducción omitida en %s: %s", ruta.name, error)
	return gettext.GNUTranslations(io.BytesIO(catalogo_po.generar_mo(resultado.mensajes)))


def _cargar_catalogo(idioma: str) -> gettext.NullTranslations | None:
	"""Catálogo de ``idioma`` exacto, o ``None`` si no existe o no se puede leer."""
	ruta_mo, ruta_po = _archivos_de(idioma)
	hay_mo = ruta_mo.is_file()
	hay_po = ruta_po.is_file()
	if not hay_mo and not hay_po:
		return None
	candidatos: list[tuple[Path, Callable[[Path], gettext.NullTranslations]]] = []
	po_mas_reciente = False
	if hay_mo and hay_po:
		try:
			po_mas_reciente = ruta_po.stat().st_mtime > ruta_mo.stat().st_mtime
		except OSError:
			log.debug("No se pudieron comparar las fechas de %s y %s", ruta_po, ruta_mo, exc_info=True)
	if hay_po and (not hay_mo or po_mas_reciente):
		candidatos.append((ruta_po, _cargar_po))
	if hay_mo:
		candidatos.append((ruta_mo, _cargar_mo))
	if hay_po and (ruta_po, _cargar_po) not in candidatos:
		candidatos.append((ruta_po, _cargar_po))
	for ruta, cargar in candidatos:
		try:
			return cargar(ruta)
		except OSError, ValueError, UnicodeDecodeError, EOFError, KeyError, IndexError:
			# Archivo dañado, a medio copiar o con una regla de plurales inválida.
			log.exception("El catálogo %s no se pudo cargar; se prueba la alternativa.", ruta)
	return None


def _cargar(solicitado: str) -> tuple[gettext.NullTranslations, str]:
	"""Catálogo y código efectivo para ``solicitado`` (``pt_BR`` cae a ``pt``; después, español)."""
	if es_idioma_origen(solicitado):
		return gettext.NullTranslations(), IDIOMA_ORIGEN
	intentos = [solicitado]
	general = solicitado.split("_")[0]
	if general != solicitado:
		intentos.append(general)
	for codigo in intentos:
		traduccion = _cargar_catalogo(codigo)
		if traduccion is not None:
			return traduccion, codigo
	log.warning("No hay traducción «%s» utilizable en %s; se usa el español.", solicitado, carpeta_locales())
	return gettext.NullTranslations(), IDIOMA_ORIGEN


def inicializar(idioma: str | None = None) -> str:
	"""Elige y carga el idioma de la sesión. Devuelve el código realmente activo.

	:param idioma: el guardado en la configuración; ``None`` o ``"auto"``
		para usar el del sistema.
	:return: ``"es"`` si se recurrió al español.
	"""
	global _traduccion, _idioma
	solicitado = resolver_idioma(idioma)
	traduccion, efectivo = _cargar(solicitado)
	_traduccion = traduccion
	_idioma = efectivo
	_publicar_en_builtins()
	log.info("Idioma de la interfaz: %s (solicitado: %s)", efectivo, solicitado)
	return efectivo


def idioma_actual() -> str:
	"""Código del idioma activo (por ejemplo ``es`` o ``en``)."""
	return _idioma


def traduccion_actual() -> gettext.NullTranslations:
	"""El catálogo activo, para quien necesite el objeto de gettext."""
	return _traduccion


# ── Cambio en caliente ───────────────────────────────────────────────────────


def al_cambiar_idioma(funcion: Callable[[str], None]) -> None:
	"""Registra una función que reconstruye textos ya pintados (menús, barra de estado)."""
	if funcion not in _oyentes:
		_oyentes.append(funcion)


def cambiar_idioma(codigo: str | None) -> bool:
	"""Activa el idioma ``codigo`` sin reiniciar y avisa a los oyentes.

	:param codigo: código de idioma, o ``"auto"`` / ``None`` para el del sistema.
	:return: ``False`` si no hay catálogo utilizable para él (se queda en
		español). Consulte ``necesita_reinicio()`` para saber si los botones
		estándar de wx siguen en el idioma anterior.
	"""
	global _traduccion, _idioma
	automatico = codigo is None or codigo.strip().casefold() in AUTOMATICO
	solicitado = (idioma_sistema() or IDIOMA_ORIGEN) if automatico else normalizar(codigo)
	traduccion, efectivo = _cargar(solicitado)
	_traduccion = traduccion
	_idioma = efectivo
	_publicar_en_builtins()
	log.info("Idioma cambiado a %s (solicitado: %s)", efectivo, solicitado)
	for funcion in list(_oyentes):
		try:
			funcion(efectivo)
		except Exception:  # noqa: BLE001 - un oyente roto no impide avisar a los demás
			log.exception("Falló al refrescar textos tras cambiar el idioma (%r)", funcion)
	conseguido = efectivo == solicitado or efectivo == solicitado.split("_")[0]
	return conseguido or (es_idioma_origen(solicitado) and efectivo == IDIOMA_ORIGEN)


def necesita_reinicio() -> bool:
	"""True si wxWidgets sigue en un idioma distinto del activo (hay que reiniciar el Estudio)."""
	return _idioma_wx is not None and _idioma_wx != _idioma


# ── wxWidgets ────────────────────────────────────────────────────────────────


def configurar_wx(idioma: str | None = None) -> Any:
	"""Crea el ``wx.Locale`` del idioma activo (botones estándar: Aceptar, Cancelar...).

	Llamar DESPUÉS de crear ``wx.App`` (``App.InitLocale`` reinicia la
	configuración regional al arrancar) y UNA sola vez por sesión. Devuelve el
	objeto, que este módulo también conserva.
	"""
	global _locale_wx, _idioma_wx
	import wx

	codigo = normalizar(idioma or _idioma) or IDIOMA_ORIGEN
	carpeta_wx = Path(wx.__file__).resolve().parent / "locale"
	if carpeta_wx.is_dir():
		# En la versión compilada el catálogo wxstd.mo está en lib/wx/locale.
		wx.Locale.AddCatalogLookupPathPrefix(str(carpeta_wx))
	informacion = wx.Locale.FindLanguageInfo(codigo) or wx.Locale.FindLanguageInfo(codigo.split("_")[0])
	identificador = informacion.Language if informacion else wx.LANGUAGE_SPANISH
	# wx.LogNull: si el idioma no está instalado en Windows, wx mostraría un
	# cuadro de error en inglés; se registra aquí en su lugar.
	sin_avisos = wx.LogNull()
	try:
		nuevo = wx.Locale(identificador)
	except Exception:  # noqa: BLE001 - sin wx.Locale la aplicación sigue; solo cambian los botones estándar
		log.warning("No se pudo crear wx.Locale para «%s»; los botones estándar pueden salir en inglés.", codigo, exc_info=True)
		return _locale_wx
	finally:
		del sin_avisos
	if not nuevo.IsOk():
		log.warning("wx.Locale(«%s») no está disponible en este sistema.", codigo)
	_locale_wx = nuevo
	_idioma_wx = _idioma
	log.debug("wx.Locale activo: %s", nuevo.GetCanonicalName())
	return nuevo


# ── Traducción de datos (complementos y entornos de ejemplo) ─────────────────


def _clave_de_elemento(elemento: Any, indice: int) -> str:
	"""Nombre de un elemento de lista dentro de una ruta: su ``id`` si lo tiene, o su posición."""
	if isinstance(elemento, dict) and isinstance(elemento.get("id"), str) and elemento["id"]:
		return elemento["id"]
	return str(indice)


def traducir_datos(textos_origen: dict, traducciones: dict, campos: Iterable[str] | None = None) -> dict:
	"""Devuelve una COPIA de ``textos_origen`` con los textos traducidos.

	Sirve para los datos que no están en el código y, por tanto, no llegan al
	catálogo gettext: ``complemento.json``, entornos de ejemplo y sus
	actividades. Cada uno lleva sus traducciones en ``locales/<idioma>.json``.

	``traducciones`` admite dos tablas, que pueden ir juntas::

		{
			"textos": {"Mesa": "Table", "Silla": "Chair"},
			"rutas": {"objetos/mesa/descripcion": "A four-legged table."}
		}

	- ``textos``: texto en español → traducción. Solo se aplica a los valores
	  que cuelgan de una clave de ``campos`` (``nombre``, ``descripcion``,
	  ``mensajes``...), para no tocar identificadores que casualmente
	  coincidan con una palabra.
	- ``rutas``: ruta del valor → traducción. La ruta une las claves con ``/``;
	  un elemento de una lista se nombra por su ``id`` o, si no tiene, por su
	  posición. Tiene prioridad y vale para cualquier valor de texto: resuelve
	  el caso de la misma palabra con dos traducciones.

	Un diccionario plano (sin ``textos`` ni ``rutas``) se toma como ``textos``.
	Lo que no tiene traducción se queda en español. Nunca lanza por una tabla
	mal formada: se registra y se devuelve el original.

	:param textos_origen: los datos en español (no se modifican).
	:param traducciones: contenido de ``locales/<idioma>.json``.
	:param campos: claves cuyo contenido es texto; por defecto ``CAMPOS_TRADUCIBLES``.
	"""
	resultado = copy.deepcopy(textos_origen)
	if not isinstance(traducciones, dict) or not traducciones:
		return resultado
	if "textos" in traducciones or "rutas" in traducciones:
		por_texto = traducciones.get("textos") or {}
		por_ruta = traducciones.get("rutas") or {}
	else:
		por_texto = traducciones
		por_ruta = {}
	if not isinstance(por_texto, dict) or not isinstance(por_ruta, dict):
		log.warning("Tabla de traducción de datos mal formada; se dejan los textos en español.")
		return resultado
	claves_texto = frozenset(CAMPOS_TRADUCIBLES if campos is None else campos)

	def traducir(valor: Any, ruta: str, traducible: bool) -> Any:
		if isinstance(valor, str):
			traducido = por_ruta.get(ruta)
			if not isinstance(traducido, str) and traducible:
				traducido = por_texto.get(valor)
			return traducido if isinstance(traducido, str) and traducido else valor
		if isinstance(valor, dict):
			for clave, contenido in valor.items():
				nueva_ruta = f"{ruta}/{clave}" if ruta else str(clave)
				valor[clave] = traducir(contenido, nueva_ruta, traducible or clave in claves_texto)
			return valor
		if isinstance(valor, list):
			for indice, contenido in enumerate(valor):
				nombre = _clave_de_elemento(contenido, indice)
				nueva_ruta = f"{ruta}/{nombre}" if ruta else nombre
				valor[indice] = traducir(contenido, nueva_ruta, traducible)
			return valor
		return valor

	return traducir(resultado, "", False)


def cargar_traducciones_de_datos(carpeta: Path, idioma: str | None = None) -> dict:
	"""Lee ``<carpeta>/locales/<idioma>.json`` (``pt_BR`` cae a ``pt``). ``{}`` si no hay.

	:param carpeta: carpeta del complemento o del entorno de ejemplo.
	:param idioma: código de idioma; por defecto, el activo.
	"""
	codigo = normalizar(idioma) if idioma else _idioma
	if not codigo or es_idioma_origen(codigo):
		return {}
	candidatos = [codigo]
	if "_" in codigo:
		candidatos.append(codigo.split("_")[0])
	for candidato in candidatos:
		ruta = Path(carpeta) / "locales" / f"{candidato}.json"
		if not ruta.is_file():
			continue
		try:
			datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
		except OSError, UnicodeDecodeError, json.JSONDecodeError:
			log.exception("No se pudo leer la traducción de datos %s; se usa el español.", ruta)
			return {}
		if isinstance(datos, dict):
			return datos
		log.warning("La traducción de datos %s no es un objeto JSON; se ignora.", ruta)
		return {}
	return {}


def traducir_datos_de_carpeta(carpeta: Path, textos_origen: dict, idioma: str | None = None) -> dict:
	"""Atajo: carga ``locales/<idioma>.json`` de ``carpeta`` y traduce ``textos_origen`` con él."""
	return traducir_datos(textos_origen, cargar_traducciones_de_datos(carpeta, idioma))


# ``_`` debe existir en builtins aunque un módulo se importe antes de
# inicializar (por ejemplo, en las pruebas). Se mira ``ngettext`` porque la
# consola interactiva ya define ``_`` (último resultado) y no hay que pisarlo.
if not hasattr(builtins, "ngettext"):
	_publicar_en_builtins()
