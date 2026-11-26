"""Seguimiento dentro del Estudio: alumnos, actividades, supervisión, sesiones, informes y cuaderno.

El resto del Estudio solo usa ``app.ui.seguimiento.integracion``. Este
``__init__`` no importa nada a propósito: así cargar el paquete no arrastra
wx ni abre la base de datos (los módulos de lógica se prueban sin ventana).
"""
