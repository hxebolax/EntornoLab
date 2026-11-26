"""Entrada del alumno: acciones con nombre, teclado, mando y vibración.

El motor no sabe de teclas ni de botones: solo recibe acciones con nombre
(``avanzar``, ``donde_estoy``...). Este paquete traduce lo que llega de pygame
a esas acciones, con mapas reasignables que se cargan y guardan como
diccionarios (quien los persiste es la configuración, no este paquete).
"""
