"""Nombre y versión de la aplicación: ÚNICA fuente de verdad.

``setup_cx.py`` la lee con una expresión regular (sin importar la
aplicación) y ``pyproject.toml`` debe coincidir; una prueba lo comprueba.
Para publicar una versión nueva solo se cambia ``APP_VERSION`` aquí.
"""

# Nombre visible: título de la ventana, «Acerca de», anuncios y registros.
NOMBRE_APLICACION = "EntornoLab"
# Identificador sin espacios: ejecutable, instancia única, carpeta de compilación.
ID_APLICACION = "entornolab"
APP_VERSION = "0.1.1"
# Nombres de los dos ejecutables de la versión compilada (los usan setup_cx.py,
# las herramientas de tools/ y app/core/procesos.py para lanzar el reproductor).
EJECUTABLE_ESTUDIO = "EntornoLab.exe"
EJECUTABLE_REPRODUCTOR = "EntornoLabJugar.exe"

# Autoría y enlaces: los muestran el «Acerca de» del Estudio y el menú del
# reproductor. Son los mismos datos que el autor usa en sus otros proyectos.
AUTOR = "Héctor J. Benítez Corredera"
ANIO = "2026"
LICENCIA = "GPL-3.0-or-later"
WEB = "https://github.com/hxebolax/EntornoLab"
FALLOS = "https://github.com/hxebolax/EntornoLab/issues"
MASTODON = "https://comunidad.nvda.es/@HXeBoLaX"
# Página de donaciones: «Invítame a un café si te gusta mi trabajo».
CAFE = "https://www.paypal.com/paypalme/hjbcdonaciones"
