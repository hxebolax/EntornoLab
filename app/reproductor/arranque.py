"""Punto de entrada del reproductor: ``ejecutar(argumentos) -> int``.

Analiza y valida los argumentos del documento de arquitectura, crea la
aplicación pygame (``app.reproductor.aplicacion.Aplicacion``) y ejecuta su
bucle hasta que el alumno sale.

Qué encuentra hecho ``ejecutar`` cuando lo llaman ``main.py`` o ``jugar.py``
(``app.core.arranque.arrancar_reproductor``):

- El registro está configurado como proceso auxiliar (archivos ``jugar_*.log``).
- ``app.core.configuracion.obtener_configuracion()`` devuelve la configuración cargada.
- El idioma está elegido (``app.core.i18n``).
- NO existe ``wx.App`` ni se ha importado wx, y no se ha comprobado la
  instancia única: puede haber varios reproductores y un Estudio a la vez.

Argumentos::

	[--jugar] [paquete] [--actividad id] [--alumno alias]
	          [--sala host:puerto --codigo c] [--inicio planta,x,y,rumbo]
	--recorrido paquete --sala host:puerto --codigo c
	--comprobar-arranque      arranca con la ventana oculta, sin voz ni sonido, da unos fotogramas y sale
	--guion fichero.json [--informe informe.json] [paquete ...]
	                          sin ventana ni sonido, sigue los pasos del guion y sale (app/reproductor/guion.py)

Variables de entorno: ``APP_SIN_VENTANA=1`` arranca sin ventana ni sonido
(controladores «dummy» de SDL, motor nulo y voz muda) y ``APP_GUION`` /
``APP_GUION_INFORME`` equivalen a ``--guion`` / ``--informe``. Como el hijo
hereda el entorno, así se prueba el reproductor real lanzado por el Estudio.

Códigos de salida: 0 correcto, 2 argumentos (o guion) no válidos y, solo con
``--comprobar-arranque`` o un guion, 3 si el entorno pedido no se puede abrir;
4 si falla una comprobación del guion. En el uso normal un entorno dañado no
es un error de arranque: se dice en voz alta y se queda en el menú principal.

En el registro nunca se escriben el alias del alumno ni el código de
emparejamiento.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.i18n import _

log = logging.getLogger(__name__)

CODIGO_CORRECTO = 0
CODIGO_ARGUMENTOS = 2
CODIGO_ENTORNO = 3
# Fotogramas que da la comprobación de arranque antes de salir.
FOTOGRAMAS_DE_COMPROBACION = 5

MODO_JUGAR = "jugar"
MODO_RECORRIDO = "recorrido"


class ErrorArgumentos(ValueError):
	"""Los argumentos de la línea de órdenes no son válidos. El mensaje es para la persona usuaria."""


@dataclass(frozen=True)
class InicioPedido:
	"""Posición de inicio pedida con ``--inicio planta,x,y,rumbo``."""

	planta: str
	x: float
	y: float
	rumbo: float


@dataclass(frozen=True)
class OpcionesReproductor:
	"""Argumentos del reproductor ya validados."""

	modo: str
	paquete: Path | None = None
	actividad: str | None = None
	alumno: str | None = None
	sala_host: str | None = None
	sala_puerto: int | None = None
	codigo: str | None = None
	inicio: InicioPedido | None = None
	comprobar: bool = False
	guion: Path | None = None
	informe: Path | None = None

	@property
	def supervisado(self) -> bool:
		"""True si hay que conectarse a la sala de un Estudio."""
		return self.sala_host is not None


class _Analizador(argparse.ArgumentParser):
	"""``ArgumentParser`` que lanza ``ErrorArgumentos`` en vez de escribir en la consola y salir.

	El ejecutable compilado no tiene consola: el ``sys.exit(2)`` de argparse
	cerraría el reproductor sin que nadie supiera por qué.
	"""

	def error(self, message: str) -> None:  # noqa: A003 - nombre de la API de argparse
		raise ErrorArgumentos(message)


def _crear_analizador() -> _Analizador:
	analizador = _Analizador(prog="EntornoLabJugar", add_help=False, allow_abbrev=False)
	analizador.add_argument("--jugar", action="store_true")
	analizador.add_argument("--recorrido", action="store_true")
	analizador.add_argument("--comprobar-arranque", dest="comprobar", action="store_true")
	analizador.add_argument("paquete", nargs="?")
	analizador.add_argument("--actividad")
	analizador.add_argument("--alumno")
	analizador.add_argument("--sala")
	analizador.add_argument("--codigo")
	analizador.add_argument("--inicio")
	analizador.add_argument("--guion")
	analizador.add_argument("--informe")
	return analizador


def _analizar_sala(texto: str) -> tuple[str, int]:
	"""``host:puerto`` → (host, puerto). El host puede ser un nombre o una dirección IPv4."""
	host, separador, puerto = texto.rpartition(":")
	if not separador or not host.strip() or not puerto.strip().isdigit():
		raise ErrorArgumentos(_("La sala «{sala}» no es válida. Se espera equipo:puerto, por ejemplo 127.0.0.1:47900.").format(sala=texto))
	numero = int(puerto)
	if not 1 <= numero <= 65535:
		raise ErrorArgumentos(_("El puerto {puerto} de la sala no es válido.").format(puerto=numero))
	return host.strip(), numero


def _analizar_inicio(texto: str) -> InicioPedido:
	"""``planta,x,y,rumbo`` → ``InicioPedido``. El rumbo se lleva al intervalo de 0 a 360."""
	partes = [parte.strip() for parte in texto.split(",")]
	if len(partes) != 4 or not partes[0]:
		raise ErrorArgumentos(_("El inicio «{inicio}» no es válido. Se espera planta,x,y,rumbo.").format(inicio=texto))
	try:
		x = float(partes[1])
		y = float(partes[2])
		rumbo = float(partes[3])
	except ValueError as error:
		raise ErrorArgumentos(_("El inicio «{inicio}» no es válido. Se espera planta,x,y,rumbo.").format(inicio=texto)) from error
	if any(valor != valor or valor in (float("inf"), float("-inf")) for valor in (x, y, rumbo)):
		raise ErrorArgumentos(_("El inicio «{inicio}» no es válido. Se espera planta,x,y,rumbo.").format(inicio=texto))
	return InicioPedido(partes[0], x, y, rumbo % 360.0)


def analizar_argumentos(argumentos: list[str]) -> OpcionesReproductor:
	"""Convierte la línea de órdenes en ``OpcionesReproductor``.

	:param argumentos: los de la línea de órdenes, con o sin ``--jugar``.
	:raises ErrorArgumentos: con un mensaje para la persona usuaria.
	"""
	crudo = _crear_analizador().parse_args(list(argumentos))
	modo = MODO_RECORRIDO if crudo.recorrido else MODO_JUGAR
	paquete: Path | None = None
	if crudo.paquete:
		paquete = Path(crudo.paquete).expanduser()
		if not paquete.is_file():
			raise ErrorArgumentos(_("No se encuentra el entorno «{ruta}».").format(ruta=crudo.paquete))
	if bool(crudo.sala) != bool(crudo.codigo):
		raise ErrorArgumentos(_("La sala y el código de emparejamiento se indican juntos: --sala equipo:puerto --codigo código."))
	host: str | None = None
	puerto: int | None = None
	if crudo.sala:
		host, puerto = _analizar_sala(crudo.sala)
	if modo == MODO_RECORRIDO:
		if paquete is None:
			raise ErrorArgumentos(_("El modo recorrido necesita el entorno que se va a recorrer."))
		if host is None:
			raise ErrorArgumentos(_("El modo recorrido necesita la sala del Estudio: --sala equipo:puerto --codigo código."))
	inicio = _analizar_inicio(crudo.inicio) if crudo.inicio else None
	guion = Path(crudo.guion).expanduser() if crudo.guion else None
	if guion is not None and not guion.is_file():
		raise ErrorArgumentos(_("No se encuentra el guion «{ruta}».").format(ruta=crudo.guion))
	return OpcionesReproductor(
		modo=modo,
		paquete=paquete,
		actividad=crudo.actividad or None,
		alumno=crudo.alumno or None,
		sala_host=host,
		sala_puerto=puerto,
		codigo=crudo.codigo or None,
		inicio=inicio,
		comprobar=bool(crudo.comprobar),
		guion=guion,
		informe=Path(crudo.informe).expanduser() if crudo.informe else None,
	)


def ejecutar(argumentos: list[str]) -> int:
	"""Arranca el reproductor con ``argumentos`` y devuelve su código de salida.

	No lanza por argumentos no válidos (devuelve 2 y lo deja en el registro);
	cualquier otra excepción al crear la aplicación sube a la red de seguridad
	de quien llama, que la escribe en ``arranque_fallido.log`` y enseña un cartel.
	"""
	# El módulo del guion no carga pygame al importarse: se puede consultar antes de analizar nada.
	from app.reproductor import guion as modo_guion

	informe_pedido = modo_guion.ruta_de_entorno(modo_guion.VARIABLE_INFORME)
	try:
		opciones = analizar_argumentos(argumentos)
	except ErrorArgumentos as error:
		log.error("Argumentos del reproductor no válidos: %s", error)
		if informe_pedido is not None:
			modo_guion.escribir_informe(informe_pedido, modo_guion.informe_de_error(str(error), CODIGO_ARGUMENTOS))
		return CODIGO_ARGUMENTOS
	ruta_guion = opciones.guion or modo_guion.ruta_de_entorno(modo_guion.VARIABLE_GUION)
	ruta_informe = opciones.informe or informe_pedido
	guion = None
	if ruta_guion is not None:
		try:
			guion = modo_guion.cargar_guion(ruta_guion)
		except modo_guion.ErrorGuion as error:
			log.error("Guion no válido: %s", error)
			if ruta_informe is not None:
				modo_guion.escribir_informe(ruta_informe, modo_guion.informe_de_error(str(error), CODIGO_ARGUMENTOS))
			return CODIGO_ARGUMENTOS
	sin_ventana = guion is not None or modo_guion.pedido_sin_ventana()
	if sin_ventana:
		# Antes de importar pygame: los controladores de SDL se eligen al iniciarlo.
		modo_guion.preparar_sin_ventana()
	log.info(
		"Reproductor pedido: modo %s, entorno %s, actividad %s, supervisado %s, comprobación %s, sin ventana %s, guion %s.",
		opciones.modo,
		opciones.paquete.name if opciones.paquete else "ninguno",
		opciones.actividad or "ninguna",
		"sí" if opciones.supervisado else "no",
		"sí" if opciones.comprobar else "no",
		"sí" if sin_ventana else "no",
		ruta_guion.name if ruta_guion is not None else "ninguno",
	)
	# Se importa aquí y no arriba: analizar los argumentos no debe cargar pygame ni el sonido.
	from app.reproductor.aplicacion import Aplicacion

	# Sin ventana es el modo de pruebas de la aplicación: SDL «dummy», motor nulo, voz que solo apunta y sin mandos.
	aplicacion = Aplicacion(opciones, pruebas=sin_ventana, oculta=opciones.comprobar and not sin_ventana)
	if guion is not None:
		return modo_guion.ejecutar(aplicacion, guion, ruta_informe)
	if opciones.comprobar:
		codigo = aplicacion.bucle(fotogramas=FOTOGRAMAS_DE_COMPROBACION)
		if codigo != CODIGO_CORRECTO:
			log.warning("Comprobación de arranque: el entorno pedido no se puede abrir.")
		else:
			log.info("Comprobación de arranque correcta.")
		return codigo
	aplicacion.bucle()
	return CODIGO_CORRECTO
