"""Seguimiento: fichas de alumnos, sesiones grabadas, medidas e informes.

Este paquete no importa ``wx`` ni ``pygame``: lo usan el Estudio (para las
fichas y los informes) y el reproductor (para grabar la sesión), y se prueba
sin ventana. Los datos que maneja son de salud y a menudo de menores: los
alumnos se identifican por alias, los campos sensibles se cifran y los
registros técnicos nunca contienen datos personales.
"""

from __future__ import annotations
