"""Diálogo «Acerca de»: autor, licencia, enlaces y datos técnicos para soporte.

No se usa ``wx.adv.AboutBox``: su ventana nativa mezcla etiquetas estáticas
que el lector no siempre recorre y no deja copiar el texto. Aquí va todo en
un campo de solo lectura con «Copiar al portapapeles», que es lo que el
usuario necesita para pegar en un correo de soporte.

Los enlaces (proyecto, fallos, café) se abren con funciones aparte para que
el menú Ayuda pueda ofrecerlos como órdenes propias, con su atajo y su texto
de ayuda: un enlace dentro de un texto de solo lectura no se puede activar
con el lector de pantalla.
"""

from __future__ import annotations

import logging
import platform
import sys
import webbrowser

import wx

from app.core import paths
from app.core.i18n import _
from app.core.version import ANIO, APP_VERSION, AUTOR, CAFE, FALLOS, LICENCIA, MASTODON, NOMBRE_APLICACION, WEB
from app.ui.dialogo_texto import mostrar_texto

log = logging.getLogger(__name__)


def texto_acerca_de() -> str:
	"""Compone el texto del diálogo (sin ventanas, para poder probarlo)."""
	lineas = [
		f"{NOMBRE_APLICACION} {APP_VERSION}",
		_("Creación de entornos y aprendizaje de orientación espacial para personas ciegas o con baja visión."),
		"",
		_("Autor: {autor}").format(autor=AUTOR),
		_("Copyright {anio} {autor}").format(anio=ANIO, autor=AUTOR),
		_("Licencia: {licencia}. Es software libre: puede usarlo, estudiarlo, compartirlo y mejorarlo.").format(licencia=LICENCIA),
		"",
		_("Página del proyecto: {enlace}").format(enlace=WEB),
		_("Avisar de un fallo: {enlace}").format(enlace=FALLOS),
		_("Mastodon: {enlace}").format(enlace=MASTODON),
		"",
		_("Si le gusta mi trabajo, invíteme a un café: {enlace}").format(enlace=CAFE),
		_("EntornoLab es gratis y lo seguirá siendo. En el menú Ayuda tiene la orden «Invítame a un café»."),
		"",
		_(
			"Aviso: es una herramienta educativa y de entrenamiento. No diagnostica ni trata, y no sustituye al aprendizaje en el lugar real con un profesional."
		),
		"",
		_("Incluye OpenAL Soft, con licencia LGPL, como biblioteca aparte en data/bin/openal."),
		_(
			"Incluye BASS, de Un4seen Developments, para el motor de sonido «3D con BASS». BASS no es software libre: "
			"es gratuita solo para uso no comercial. Para un uso comercial hace falta su licencia de pago, o bien elegir "
			"otro motor de sonido y borrar bass.dll."
		),
		_("Las licencias de todo lo que acompaña al programa están en data/docs/licencias."),
		"",
		_("Versión de Python: {version} ({bits})").format(version=platform.python_version(), bits=platform.architecture()[0]),
		_("Versión de wxPython: {version}").format(version=wx.version()),
		_("Sistema: {sistema}").format(sistema=platform.platform()),
		_("Versión compilada: {valor}").format(valor=_("sí") if paths.CONGELADA else _("no")),
		_("Carpeta de datos: {ruta}").format(ruta=paths.ruta_datos()),
		_("Ejecutable: {ruta}").format(ruta=sys.executable),
	]
	return "\n".join(lineas)


def abrir_enlace(enlace: str) -> bool:
	"""Abre ``enlace`` en el navegador. Devuelve False si no se pudo."""
	try:
		return bool(webbrowser.open(enlace))
	except OSError, webbrowser.Error:
		log.exception("No se pudo abrir el enlace %s", enlace)
		return False


def invitar_a_un_cafe() -> bool:
	"""Abre la página de donaciones del autor."""
	return abrir_enlace(CAFE)


def abrir_pagina_del_proyecto() -> bool:
	"""Abre la página del proyecto."""
	return abrir_enlace(WEB)


def avisar_de_un_fallo() -> bool:
	"""Abre la página para avisar de fallos."""
	return abrir_enlace(FALLOS)


def mostrar_acerca_de(padre: wx.Window | None) -> None:
	"""Abre el diálogo «Acerca de» de forma modal."""
	mostrar_texto(
		padre,
		_("Acerca de {nombre}").format(nombre=NOMBRE_APLICACION),
		_("&Información:"),
		texto_acerca_de(),
		copiable=True,
	)
