"""Ayuda: la lista de teclas y botones del contexto actual, generada de ``app/entrada/acciones.py``.

No hay una lista escrita a mano que se pueda quedar vieja: cada línea sale de
la tabla de acciones y del mapa en uso (con las teclas que el alumno haya
reasignado) y, con un mando conectado, nombra sus botones tal como se llaman
en ese mando (A o Equis, LB o L1...). Se recorre como un menú, línea a línea,
porque quien usa voz no puede «echar un vistazo». La última línea genera el
paquete de diagnóstico para avisar de un fallo.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.core.i18n import _
from app.entrada import acciones
from app.reproductor.menus import Espera, Menu, Mensaje, Opcion

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion


def frases_de_ayuda(app: Aplicacion, contexto: str, extras: list[str] | None = None) -> list[str]:
	"""Una frase por acción del contexto («Flecha arriba: avanzar.»), más las propias de la pantalla."""
	frases = list(app.entrada.ayuda(contexto))
	frases.extend(extras or [])
	if contexto == acciones.MENU:
		frases.append(_("Inicio y Fin: primera y última opción."))
		frases.append(_("Una letra: salta a la siguiente opción que empieza por ella."))
	return frases


def abrir_ayuda(app: Aplicacion, contexto: str, extras: list[str] | None = None) -> Menu:
	"""Abre la lista de controles de ``contexto`` (``juego`` o ``menu``)."""
	if contexto == acciones.JUEGO:
		titulo = _("Ayuda: controles para recorrer el entorno")
	else:
		titulo = _("Ayuda: controles de los menús")
	if app.entrada.con_mando:
		nombres = ", ".join(app.entrada.mandos.conectados)
		intro = _("Se dicen los botones de tu mando: {mando}. El teclado sigue funcionando.").format(mando=nombres)
	else:
		intro = _("Se dicen las teclas. Si conectas un mando, se dirán sus botones.")

	def opciones() -> list[Opcion]:
		lineas = [
			Opcion(frase, ayuda=_("Es una línea de la ayuda: no hace nada al pulsar.")) for frase in frases_de_ayuda(app, contexto, extras)
		]
		lineas.append(
			Opcion(
				_("Generar paquete de diagnóstico"),
				lambda: generar_diagnostico(app),
				ayuda=_("Reúne los registros del programa, sin datos personales, en un fichero para enviarlo al avisar de un fallo."),
			)
		)
		return lineas

	menu = Menu(app, titulo, opciones, intro=intro)
	app.abrir(menu)
	return menu


def generar_diagnostico(app: Aplicacion) -> Espera:
	"""Genera el paquete de diagnóstico en un hilo y, al terminar, dice dónde lo ha dejado.

	El trabajo (leer, anonimizar y comprimir los registros) va en una ``Espera``
	para que el bucle del juego no se pare. El paquete no lleva configuración,
	fichas, sesiones ni entornos (``app.core.diagnostico``).
	"""
	from app.core import diagnostico
	from app.core.version import APP_VERSION, NOMBRE_APLICACION

	titulo = _("Paquete de diagnóstico")

	def al_terminar(ruta: Path | None) -> None:
		app.ultimo_paquete_diagnostico = ruta
		if ruta is None:
			frases = [_("No se pudo generar el paquete de diagnóstico. El motivo ha quedado en el registro.")]
		else:
			frases = [
				_("Paquete de diagnóstico creado: {nombre}.").format(nombre=ruta.name),
				_("Está en la carpeta {carpeta}.").format(carpeta=ruta.parent),
				_("Lleva los registros y los datos del sistema, sin datos personales. Adjúntalo al avisar de un fallo."),
			]
		app.abrir(Mensaje(app, titulo, frases))

	espera = Espera(
		app, _("Generando el paquete de diagnóstico."), lambda: diagnostico.generar_paquete(NOMBRE_APLICACION, APP_VERSION), al_terminar
	)
	app.abrir(espera)
	return espera
