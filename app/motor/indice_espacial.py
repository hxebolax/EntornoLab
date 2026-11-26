"""La rejilla de cajas del motor: vive en ``app.dominio.indice_espacial``.

Se movió al dominio para que la usen también el modelo (``Planta.espacios_en``)
y el Estudio sin que el dominio dependa del motor. Este módulo la reexporta
para no romper las importaciones del motor ni de sus pruebas.
"""

from __future__ import annotations

from app.dominio.indice_espacial import MAX_CELDAS, Caja, RejillaCajas

__all__ = ["MAX_CELDAS", "Caja", "RejillaCajas"]
