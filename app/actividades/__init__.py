"""Actividades, juegos y exámenes de EntornoLab: declarativos, sin interfaz y sin sonido.

Una actividad es un JSON dentro del paquete ``.elab``; aquí se valida, se
describe, se convierte en un objeto que se cuelga de la ``Sesion`` del motor
y se puntúa. Nunca se ejecuta código procedente de un entorno.

Lo que usan el reproductor y el Estudio::

	from app.actividades import TIPOS, campos_de, nueva_actividad, validar_actividad, crear_actividad

	datos = nueva_actividad("busqueda", entorno, catalogo, cantidad=5)
	avisos = validar_actividad(datos, entorno, catalogo)
	actividad = crear_actividad(datos, entorno, catalogo, estilo="infantil", semilla=7)
	sesion = Sesion(entorno, catalogo, actividad.ajustes(ajustes_del_alumno), actividad=actividad, semilla=7, inicio=actividad.inicio())

Formato, puntuación y base científica de cada medida: ``docs/actividades.md``.
"""

from __future__ import annotations

from app.actividades import cuestionario, puntuacion, recompensas
from app.actividades.base import Actividad, Premio
from app.actividades.fabrica import CLASES, crear_actividad, describir_actividad, nueva_actividad
from app.actividades.formato import normalizar
from app.actividades.lugares import Lugar, pista_de_lugar, resolver_lugar
from app.actividades.plantillas import PLANTILLAS, plantillas_de
from app.actividades.reparto import repartir_premios
from app.actividades.tipos import (
	ESTILO_DEL_ALUMNO,
	ESTILOS,
	GRUPOS,
	MODOS,
	NIVELES_SERIE,
	NOMBRES_AYUDAS,
	TIPOS,
	VISIBILIDADES,
	Campo,
	InfoTipo,
	campos_de,
	leer_campo,
	poner_campo,
	valores_por_defecto,
)
from app.actividades.validacion import validar_actividad

__all__ = [
	"CLASES",
	"ESTILOS",
	"ESTILO_DEL_ALUMNO",
	"GRUPOS",
	"MODOS",
	"NIVELES_SERIE",
	"NOMBRES_AYUDAS",
	"PLANTILLAS",
	"TIPOS",
	"VISIBILIDADES",
	"Actividad",
	"Campo",
	"InfoTipo",
	"Lugar",
	"Premio",
	"campos_de",
	"crear_actividad",
	"cuestionario",
	"describir_actividad",
	"leer_campo",
	"normalizar",
	"nueva_actividad",
	"pista_de_lugar",
	"plantillas_de",
	"poner_campo",
	"puntuacion",
	"recompensas",
	"repartir_premios",
	"resolver_lugar",
	"validar_actividad",
	"valores_por_defecto",
]
