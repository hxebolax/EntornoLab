"""Paquetes de sonidos: listarlos, elegir uno en caliente y escuchar una muestra.

Es la puerta sencilla que usan el reproductor (menú hablado de ajustes) y el Estudio (preferencias).
El trabajo de verdad lo hacen :class:`app.audio.banco.Banco` (qué fichero corresponde a cada nombre
y a qué nivel) y el motor de sonido (``recargar_sonido``); aquí solo se une con la configuración:

- ``sonido.paquete``: identificador del paquete elegido (el nombre de su carpeta).
- ``sonido.igualar_paquetes``: llevar cada sonido al nivel del de serie.
- ``sonido.volumen_sonidos``: ajuste del usuario por sonido, ``{nombre: factor}``.

Uso típico::

    banco = Banco()
    motor = crear_motor(config_sonido, banco)
    presentador = Presentador(motor, voz, haptica, cabeza, banco=banco)
    cancelar = paquetes.conectar(banco)            # aplica lo guardado y sigue los cambios

    for paquete in paquetes.listar(banco): ...     # menú: paquete["nombre"], paquete["descripcion"]
    paquetes.escuchar("natural", motor, banco)     # una muestra, sin cambiar de paquete
    paquetes.elegir("natural")                     # se guarda y se oye al momento, también a mitad de partida

``elegir`` solo escribe la preferencia: el banco se entera por la suscripción de :func:`conectar` y el
presentador recarga el motor en su siguiente ``aplicar``. Así da igual quién cambie la preferencia
(el menú del reproductor, el diálogo del Estudio u otro proceso que edite la configuración).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from app.audio import niveles, sintesis
from app.audio.banco import PAQUETE_POR_DEFECTO, PREFIJO_MUESTRA, Banco
from app.audio.base import FRECUENCIA, preparar_datos
from app.core.i18n import _

log = logging.getLogger(__name__)

CLAVE_PAQUETE = "sonido.paquete"
CLAVE_IGUALAR = "sonido.igualar_paquetes"
CLAVE_VOLUMENES = "sonido.volumen_sonidos"
# Lo que suena al pedir una muestra de un paquete: de todo un poco, y corto.
MUESTRA: tuple[str, ...] = ("pasos/madera_izq_1", "pasos/madera_der_1", "golpe/madera", "puerta/abrir", "baliza/pulso", "premio/recogido")
# Silencio entre los sonidos de la muestra, en segundos.
PAUSA_MUESTRA = 0.18
# Un sonido de la muestra no ocupa más que esto (un ambiente de diez segundos no es una muestra).
MAXIMO_POR_SONIDO = 2.5


def _configuracion(config: Any) -> Any:
	if config is not None:
		return config
	from app.core.configuracion import obtener_configuracion

	return obtener_configuracion()


def listar(banco: Banco | None = None) -> list[dict]:
	"""Los paquetes de sonidos instalados, el de por defecto primero.

	Cada uno: ``{"id", "nombre", "descripcion", "autor", "licencia", "version", "generado", "sonidos",
	"total", "completo", "parcial", "defecto", "actual", "carpeta"}`` (ver
	:meth:`Banco.paquetes_disponibles`). Sin ``banco`` se mira en las carpetas de serie, y «actual» es
	el que dice la configuración.
	"""
	if banco is not None:
		return banco.paquetes_disponibles()
	lista = Banco(carpetas_complementos=[]).paquetes_disponibles()
	elegido = actual()
	for paquete in lista:
		paquete["actual"] = paquete["id"] == elegido
	if not any(paquete["actual"] for paquete in lista):
		for paquete in lista:
			paquete["actual"] = paquete["defecto"]
	return lista


def actual(config: Any = None) -> str:
	"""Identificador del paquete guardado en la configuración (``por_defecto`` si no hay ninguno)."""
	valor = _configuracion(config).obtener(CLAVE_PAQUETE, PAQUETE_POR_DEFECTO)
	return str(valor or PAQUETE_POR_DEFECTO)


def describir(paquete: dict) -> str:
	"""Una frase para decir en voz alta al pasar por un paquete en un menú."""
	if paquete.get("completo"):
		cuenta = _("trae los {total} sonidos").format(total=paquete.get("total", 0))
	else:
		cuenta = _("trae {sonidos} de {total} sonidos; el resto suena con los de serie").format(
			sonidos=paquete.get("sonidos", 0), total=paquete.get("total", 0)
		)
	partes = [str(paquete.get("nombre", "")), str(paquete.get("descripcion", "")), cuenta]
	return ". ".join(parte.rstrip(". ") for parte in partes if parte) + "."


def elegir(identificador: str, config: Any = None, banco: Banco | None = None) -> bool:
	"""Elige un paquete de sonidos y lo guarda. Devuelve False (sin cambiar nada) si no está instalado.

	El cambio se oye al momento si hay un banco conectado con :func:`conectar`. ``banco`` solo sirve
	para comprobar que el paquete existe en sus carpetas (si no se da, se mira en las de serie).
	"""
	pedido = str(identificador or PAQUETE_POR_DEFECTO)
	disponibles = {paquete["id"] for paquete in listar(banco)}
	if pedido != PAQUETE_POR_DEFECTO and pedido not in disponibles:
		log.warning("No se puede elegir el paquete de sonidos «%s»: no está instalado.", pedido)
		return False
	_configuracion(config).establecer(CLAVE_PAQUETE, pedido)
	return True


def poner_volumen(nombre: str, factor: float, config: Any = None) -> float:
	"""Sube o baja un sonido concreto (de 0,3 a 2; 1 lo deja como viene) y lo guarda. Devuelve el ajuste que queda."""
	configuracion = _configuracion(config)
	ajuste = round(niveles.ajuste_valido(factor), 2)
	guardados = configuracion.obtener(CLAVE_VOLUMENES, {})
	volumenes = dict(guardados) if isinstance(guardados, dict) else {}
	if abs(ajuste - 1.0) < 0.005:
		volumenes.pop(nombre, None)
	else:
		volumenes[nombre] = ajuste
	configuracion.establecer(CLAVE_VOLUMENES, volumenes)
	return ajuste


def conectar(banco: Banco, config: Any = None) -> Callable[[], None]:
	"""Pone en ``banco`` lo que dice la configuración y lo mantiene al día. Devuelve la función que desconecta.

	A partir de aquí, cambiar ``sonido.paquete``, ``sonido.igualar_paquetes`` o
	``sonido.volumen_sonidos`` (desde donde sea) cambia el banco en el acto; el banco avisa a su vez
	al presentador, que recarga el motor de sonido.
	"""
	configuracion = _configuracion(config)

	def aplicar(clave: str, _anterior: Any, nuevo: Any) -> None:
		if clave == CLAVE_PAQUETE:
			banco.poner_paquete(str(nuevo or PAQUETE_POR_DEFECTO))
		elif clave == CLAVE_IGUALAR:
			banco.poner_igualado(bool(nuevo))
		elif clave == CLAVE_VOLUMENES or clave.startswith(CLAVE_VOLUMENES + "."):
			guardados = configuracion.obtener(CLAVE_VOLUMENES, {})
			banco.poner_volumenes(guardados if isinstance(guardados, dict) else {})

	guardados = configuracion.obtener(CLAVE_VOLUMENES, {})
	banco.poner_volumenes(guardados if isinstance(guardados, dict) else {})
	banco.poner_igualado(bool(configuracion.obtener(CLAVE_IGUALAR, True)))
	banco.poner_paquete(actual(configuracion))
	# Una función suelta (no un método): la configuración la retiene hasta que se cancele.
	return configuracion.suscribir(aplicar, prefijo="sonido.")


def muestra(identificador: str, banco: Banco | None = None, nombres: Sequence[str] | None = None) -> tuple[np.ndarray, int]:
	"""Una muestra de un paquete: varios de sus sonidos seguidos, en un solo trozo mono. Devuelve (muestras, frecuencia).

	Los sonidos se toman tal como sonarían con ese paquete puesto (igualados, y los que no trae, del
	de por defecto), sin cambiar el paquete en uso.
	"""
	banco = banco if banco is not None else Banco(carpetas_complementos=[])
	pausa = np.zeros(int(FRECUENCIA * PAUSA_MUESTRA), dtype=np.float32)
	trozos: list[np.ndarray] = []
	for nombre in nombres or MUESTRA:
		encontrado = banco.sonido_de_paquete(identificador, nombre)
		datos = sintesis.a_mono(preparar_datos(encontrado.datos, encontrado.frecuencia))
		trozos.append(np.ascontiguousarray(datos[: int(FRECUENCIA * MAXIMO_POR_SONIDO)], dtype=np.float32))
		trozos.append(pausa)
	if not trozos:
		return np.zeros(1, dtype=np.float32), FRECUENCIA
	return np.concatenate(trozos[:-1]), FRECUENCIA


def escuchar(
	identificador: str,
	motor: Any,
	banco: Banco | None = None,
	nombres: Sequence[str] | None = None,
	volumen: float = 1.0,
) -> int:
	"""Hace sonar por ``motor`` una muestra del paquete, sin elegirlo. Devuelve el canal (0 si no pudo sonar).

	Suena por el bus de interfaz, sin posición ni eco, como los sonidos de los menús. Pedir otra
	muestra corta la anterior. El canal sirve para pararla (``motor.parar(canal, 0.1)``).
	"""
	datos, frecuencia = muestra(identificador, banco, nombres)
	nombre = f"{PREFIJO_MUESTRA}{identificador or PAQUETE_POR_DEFECTO}"
	anterior = int(getattr(motor, "_canal_muestra", 0) or 0)
	if anterior:
		motor.parar(anterior, 0.05)
	motor.cargar(nombre, datos=datos, frecuencia=frecuencia)
	canal = int(motor.reproducir(nombre, bus="interfaz", volumen=volumen, eco=False))
	motor._canal_muestra = canal  # noqa: SLF001 - apunte propio de este módulo sobre el motor, para cortar la muestra anterior
	return canal
