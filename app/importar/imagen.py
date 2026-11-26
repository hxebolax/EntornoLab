"""Imagen de fondo: un plano escaneado o una foto para calcar encima, sin vectorizar.

A veces lo único que hay de un edificio es un plano en papel o una foto del
plano de evacuación. No se intenta reconocer las paredes (saldría mal y
habría que corregirlo todo): la imagen se guarda como referencia para que el
plano gráfico del Estudio la pinte debajo y el profesional dibuje encima.

Para colocarla hacen falta dos puntos de calibración: dos sitios que se
reconocen en la imagen (en píxeles) y cuya posición en el entorno se conoce
(en metros). Con dos puntos quedan fijadas la escala, el giro y el
desplazamiento.

Dónde se guarda (compatible con el formato 1, que no tiene campo propio):

	entorno.procedencia["fondos"] = [
		{
			"planta": "pla-1",
			"imagen": "imagenes/plano.png",          recurso del paquete .elab
			"puntos": [
				{"imagen": [px, py], "mundo": [x, y]},
				{"imagen": [px, py], "mundo": [x, y]}
			],
			"opacidad": 0.5,
			"visible": true
		}
	]

Los píxeles se cuentan desde la esquina superior izquierda de la imagen, con
la y hacia abajo. La imagen viaja dentro del paquete, en ``imagenes/``, y no
sale del equipo.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any

from app.core.i18n import _
from app.dominio.formato import CARPETA_IMAGENES, EXTENSIONES_IMAGEN, MAX_BYTES_RECURSO, identificador_seguro
from app.dominio.geometria import Punto
from app.dominio.modelo import Entorno, Planta
from app.importar.comun import ErrorImportacion, leer_fichero

log = logging.getLogger(__name__)

CLAVE_FONDOS = "fondos"
# Dos puntos de calibración más juntos que esto (en píxeles o en metros) no fijan bien la escala.
SEPARACION_MINIMA_PX = 5.0
SEPARACION_MINIMA_M = 0.2


def preparar_recurso(ruta: str | os.PathLike[str]) -> tuple[str, bytes]:
	"""(nombre interno, bytes) de una imagen lista para guardarse dentro del paquete del entorno.

	El resultado se pasa a ``guardar_paquete(..., recursos={nombre: datos})``.
	Se comprueba el tipo y el tamaño aquí para avisar antes de dibujar nada.
	"""
	camino = Path(ruta)
	extension = camino.suffix.lower()
	if extension not in EXTENSIONES_IMAGEN:
		raise ErrorImportacion(
			_("«{nombre}» no es una imagen admitida. Formatos: {formatos}.").format(
				nombre=camino.name, formatos=", ".join(sorted(EXTENSIONES_IMAGEN))
			)
		)
	datos = leer_fichero(camino, MAX_BYTES_RECURSO)
	return f"{CARPETA_IMAGENES}/{identificador_seguro(camino.stem, 'fondo')}{extension}", datos


def _par(valor: Any, que: str) -> Punto:
	try:
		x, y = float(valor[0]), float(valor[1])
	except (TypeError, ValueError, IndexError) as error:
		raise ErrorImportacion(_("{que} tiene que ser un par de números.").format(que=que)) from error
	if not (math.isfinite(x) and math.isfinite(y)):
		raise ErrorImportacion(_("{que} tiene que ser un par de números.").format(que=que))
	return x, y


def definir_fondo(
	entorno: Entorno,
	planta: Planta,
	imagen: str,
	punto_imagen_1: Punto,
	punto_mundo_1: Punto,
	punto_imagen_2: Punto,
	punto_mundo_2: Punto,
	opacidad: float = 0.5,
) -> dict[str, Any]:
	"""Asocia a una planta una imagen de fondo con sus dos puntos de calibración.

	``imagen`` es el nombre del recurso dentro del paquete
	(``imagenes/plano.png``). Sustituye al fondo anterior de esa planta.
	"""
	puntos = [
		(_par(punto_imagen_1, _("El primer punto de la imagen")), _par(punto_mundo_1, _("El primer punto del entorno"))),
		(_par(punto_imagen_2, _("El segundo punto de la imagen")), _par(punto_mundo_2, _("El segundo punto del entorno"))),
	]
	if math.dist(puntos[0][0], puntos[1][0]) < SEPARACION_MINIMA_PX:
		raise ErrorImportacion(_("Los dos puntos de calibración están casi en el mismo sitio de la imagen: elija dos puntos alejados."))
	if math.dist(puntos[0][1], puntos[1][1]) < SEPARACION_MINIMA_M:
		raise ErrorImportacion(_("Los dos puntos de calibración están casi en el mismo sitio del entorno: elija dos puntos alejados."))
	if not str(imagen).strip():
		raise ErrorImportacion(_("Falta el nombre de la imagen."))
	fondo: dict[str, Any] = {
		"planta": planta.id,
		"imagen": str(imagen),
		"puntos": [{"imagen": [p[0][0], p[0][1]], "mundo": [p[1][0], p[1][1]]} for p in puntos],
		"opacidad": max(0.05, min(1.0, float(opacidad))),
		"visible": True,
	}
	quitar_fondo(entorno, planta.id)
	entorno.procedencia.setdefault(CLAVE_FONDOS, []).append(fondo)
	log.info("Imagen de fondo «%s» asociada a la planta %s", imagen, planta.id)
	return fondo


def fondos_de(entorno: Entorno, planta_id: str | None = None) -> list[dict[str, Any]]:
	"""Fondos definidos en el entorno (los de una planta, o todos); tolera datos mal formados."""
	fondos = entorno.procedencia.get(CLAVE_FONDOS)
	if not isinstance(fondos, list):
		return []
	return [fondo for fondo in fondos if isinstance(fondo, dict) and (planta_id is None or fondo.get("planta") == planta_id)]


def quitar_fondo(entorno: Entorno, planta_id: str) -> bool:
	"""Quita el fondo de una planta. True si había alguno."""
	fondos = entorno.procedencia.get(CLAVE_FONDOS)
	if not isinstance(fondos, list):
		return False
	quedan = [fondo for fondo in fondos if not (isinstance(fondo, dict) and fondo.get("planta") == planta_id)]
	habia = len(quedan) != len(fondos)
	if quedan:
		entorno.procedencia[CLAVE_FONDOS] = quedan
	else:
		entorno.procedencia.pop(CLAVE_FONDOS, None)
	return habia


def transformacion(fondo: dict[str, Any]) -> tuple[float, float, float, float]:
	"""(metros por píxel, giro en grados, x, y) de un fondo.

	Con eso el plano gráfico sabe pintar la imagen: (x, y) es la posición en
	el entorno de su píxel (0, 0), y el giro es antihorario visto en el
	plano. Lanza ``ErrorImportacion`` si los puntos guardados no sirven.
	"""
	try:
		(i1, m1), (i2, m2) = [(_par(p["imagen"], "imagen"), _par(p["mundo"], "mundo")) for p in fondo["puntos"][:2]]
	except (KeyError, TypeError, ValueError, IndexError) as error:
		raise ErrorImportacion(_("La imagen de fondo no tiene dos puntos de calibración válidos.")) from error
	# La y de la imagen crece hacia abajo: se le cambia el signo para trabajar con la y hacia arriba.
	vx, vy = i2[0] - i1[0], -(i2[1] - i1[1])
	wx, wy = m2[0] - m1[0], m2[1] - m1[1]
	largo_imagen = math.hypot(vx, vy)
	if largo_imagen < 1e-9:
		raise ErrorImportacion(_("La imagen de fondo no tiene dos puntos de calibración válidos."))
	escala = math.hypot(wx, wy) / largo_imagen
	giro = math.atan2(wy, wx) - math.atan2(vy, vx)
	coseno, seno = math.cos(giro), math.sin(giro)
	x0 = m1[0] - escala * (coseno * i1[0] - seno * -i1[1])
	y0 = m1[1] - escala * (seno * i1[0] + coseno * -i1[1])
	return escala, math.degrees(giro), x0, y0


def imagen_a_mundo(fondo: dict[str, Any], px: float, py: float) -> Punto:
	"""Posición en el entorno (metros) de un píxel de la imagen de fondo."""
	escala, giro, x0, y0 = transformacion(fondo)
	coseno, seno = math.cos(math.radians(giro)), math.sin(math.radians(giro))
	return x0 + escala * (coseno * px - seno * -py), y0 + escala * (seno * px + coseno * -py)


def mundo_a_imagen(fondo: dict[str, Any], x: float, y: float) -> Punto:
	"""Píxel de la imagen de fondo que corresponde a una posición del entorno."""
	escala, giro, x0, y0 = transformacion(fondo)
	coseno, seno = math.cos(math.radians(giro)), math.sin(math.radians(giro))
	dx, dy = (x - x0) / escala, (y - y0) / escala
	return coseno * dx + seno * dy, -(-seno * dx + coseno * dy)
