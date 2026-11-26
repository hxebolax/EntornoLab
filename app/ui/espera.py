"""Cuándo y cómo se hace en segundo plano una operación del Estudio que puede tardar.

Regla del Estudio (ver ``docs/desarrollo.md``): ninguna acción puede tener
ocupado el hilo de la interfaz más de 100 ms; mientras está ocupado, el
lector de pantalla se queda mudo y Windows marca la ventana como «No
responde». Lo que con un entorno pequeño tarda unos milisegundos (comprobar,
describir, exportar) con un barrio importado de miles de espacios tarda
segundos; entonces se hace en un hilo de trabajo con el diálogo de progreso
(``app.ui.dialogo_progreso``), que dice qué se hace, con cifras y tiempo, y
deja cancelar.

Con un entorno pequeño se hace directamente, sin diálogo: no tendría sentido
enseñar y anunciar un progreso que dura un instante (y el lector diría dos
veces el título del diálogo para nada).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.dominio.modelo import Entorno

log = logging.getLogger(__name__)

#: Elementos (espacios, aberturas, objetos, referencias…) a partir de los cuales una
#: operación de todo el entorno va a segundo plano. Medido: con 1.500 elementos,
#: comprobar o describir tarda unos 150 ms en esta máquina; con 10.000, varios segundos.
UMBRAL_ELEMENTOS = 1500


def tamano(entorno: Entorno | None) -> int:
	"""Cuántos elementos tiene el entorno (plantas, espacios y todo lo demás)."""
	if entorno is None:
		return 0
	return sum(
		len(planta.espacios)
		+ len(planta.aberturas)
		+ len(planta.objetos)
		+ len(planta.referencias)
		+ len(planta.fuentes)
		+ len(planta.zonas)
		+ len(planta.paredes)
		+ len(planta.vias)
		for planta in entorno.plantas
	)


def es_grande(entorno: Entorno | None) -> bool:
	"""True si las operaciones de todo el entorno deben ir a segundo plano con progreso."""
	return tamano(entorno) >= UMBRAL_ELEMENTOS


def hacer(contexto: Any, titulo: str, trabajo: Callable[[Any], Any], fase: str = "") -> Any:
	"""Ejecuta ``trabajo(tarea)``: en segundo plano con el diálogo de progreso si el entorno es grande; si no, aquí mismo.

	``trabajo`` puede llamar a ``dialogo_progreso.informar(tarea, fase, hecho, total)``
	en los dos casos (sin diálogo no hace nada visible). Devuelve su resultado;
	si se cancela lanza ``app.core.tareas.TareaCancelada``.

	Mientras dura, el diálogo de progreso es modal: el entorno no se puede
	editar a la vez, así que el trabajo puede leerlo sin copiarlo.
	"""
	from app.ui import dialogo_progreso

	gestor = getattr(contexto, "tareas", None)
	if gestor is None or not es_grande(getattr(contexto, "entorno", None)):
		return trabajo(dialogo_progreso.TareaDirecta())
	log.info("«%s» va a segundo plano: el entorno tiene %s elementos.", titulo, tamano(contexto.entorno))
	return dialogo_progreso.ejecutar_tarea(contexto.ventana, titulo, trabajo, gestor, getattr(contexto, "configuracion", None), fase)
