"""Supervisión en vivo: protocolo y conexión entre el Estudio (sala) y el reproductor (cliente).

Sin ``wx`` ni ``pygame``: la sala y el cliente viven en hilos propios y la
interfaz solo lee fotos y colas. No hay nube ni servidores externos: todo
ocurre en el mismo ordenador o en la red local, con emparejamiento por
código y conexión cifrada.
"""

from __future__ import annotations
