"""Puente hacia ``app/core/catalogo_po.py`` para las herramientas de traducción.

La lectura, escritura y validación de catálogos vive en ``app/core`` porque
la aplicación también la usa (lee los ``.po`` sin compilar). Las herramientas
de ``tools/`` conservan su ``import catalogo_po`` de siempre gracias a este
archivo, que solo añade la raíz del proyecto a ``sys.path`` (al ejecutar
``python tools/extraer_cadenas.py`` la primera carpeta de búsqueda es
``tools``, no la raíz) y reexporta todo.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))

from app.core.catalogo_po import *  # noqa: E402, F403 - reexportación deliberada
