"""Nombre antiguo del módulo de configuración: reexporta ``app.core.configuracion``.

El esqueleto del proyecto importaba ``app.core.config``; la implementación
vive ahora en ``app/core/configuracion.py``. Este archivo existe solo para
que esas importaciones sigan funcionando. El código nuevo debe importar
``app.core.configuracion``.
"""

from __future__ import annotations

from app.core.configuracion import (
	MIGRACIONES,
	NOMBRE_ARCHIVO,
	REGLAS,
	VALORES_POR_DEFECTO,
	VERSION_ESQUEMA,
	Configuracion,
	ErrorConfiguracion,
	ErrorValidacion,
	Regla,
	establecer_configuracion,
	obtener_configuracion,
)

__all__ = [
	"MIGRACIONES",
	"NOMBRE_ARCHIVO",
	"REGLAS",
	"VALORES_POR_DEFECTO",
	"VERSION_ESQUEMA",
	"Configuracion",
	"ErrorConfiguracion",
	"ErrorValidacion",
	"Regla",
	"establecer_configuracion",
	"obtener_configuracion",
]
