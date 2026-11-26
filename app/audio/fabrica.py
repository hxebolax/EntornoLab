"""Elige y arranca el motor de sonido, con reservas: el programa nunca se queda sin arrancar por el sonido.

``crear_motor(config)`` prueba el motor configurado y, si no está disponible o falla al abrir la
salida, el siguiente de la cadena::

    openal → clasico → estereo → nulo

El motor de serie es ``openal``. ``bass`` viene incluido (el paquete ``basskit`` con ``bass.dll`` viaja
con el programa) y se elige en las preferencias, pero no está en la cadena de reserva: nadie cae en él
sin pedirlo, porque no es binaural y su licencia solo permite el uso no comercial. Si se pide y no
arranca (por ejemplo, porque se ha retirado ``bass.dll``), cae a ``openal`` y sigue la misma cadena.

Cada caída queda en el registro con su motivo, y el motor devuelto recuerda en ``pedido`` cuál se
había pedido, para que las preferencias puedan decir «se pidió OpenAL, pero está sonando el clásico».

``config`` es un dict (la sección de sonido de la configuración; otro módulo la conecta)::

    {
      "motor": "openal",            openal | clasico | estereo | bass | nulo
      "dispositivo": "",            nombre de la salida; vacío = la de Windows
      "segunda_salida": "",         solo motor clásico: salida del profesional
      "salida": "auriculares",      auriculares (binaural) | altavoces (estéreo sin HRTF); solo OpenAL
      "cabeza": "",                 perfil HRTF; vacío = el integrado
      "refuerzo_detras": 1.0,       0 a 1
      "reverberacion": true, "nivel_reverberacion": 1.0,
      "volumenes": {"maestro": 0.8, "efectos": 1.0, ...},
      "distancia_referencia": 1.0, "distancia_caida": 1.0, "distancia_maxima": 60.0,
      "mono": false,                los dos oídos oyen lo mismo
      "atenuar_voz": true,
      "proteccion": {"techo_fuente": 1.0, "techo_mezcla": 0.9, ...},
      "memoria": false              sin tarjeta de sonido (pruebas): openal, clasico y bass
    }

La variable de entorno ``APP_SIN_SONIDO=1`` fuerza el motor nulo (pruebas automáticas).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.audio.base import ErrorMotor, MotorAudio
from app.core.i18n import N_, _

log = logging.getLogger(__name__)

# Cadena de reserva, de mejor a peor. BASS no está: es elegible, pero nunca una reserva.
CADENA: tuple[str, ...] = ("openal", "clasico", "estereo", "nulo")
MOTORES: tuple[str, ...] = ("openal", "clasico", "estereo", "bass", "nulo")
MOTOR_DE_SERIE = "openal"
VARIABLE_SIN_SONIDO = "APP_SIN_SONIDO"

NOMBRES: dict[str, str] = {
	"openal": N_("Binaural (OpenAL Soft, para auriculares)"),
	"clasico": N_("Clásico (mezcla propia, admite segunda salida)"),
	"estereo": N_("Estéreo simple (equipos modestos y altavoces)"),
	"bass": N_("3D con BASS (panorama sin HRTF; solo uso no comercial)"),
	"nulo": N_("Sin sonido"),
}


def clase_motor(nombre: str) -> type[MotorAudio]:
	"""La clase de un motor. Se importa al pedirla: así un motor roto no impide usar los demás."""
	if nombre == "openal":
		from app.audio.motor_openal import MotorOpenAL

		return MotorOpenAL
	if nombre == "clasico":
		from app.audio.motor_clasico import MotorClasico

		return MotorClasico
	if nombre == "estereo":
		from app.audio.motor_estereo import MotorEstereo

		return MotorEstereo
	if nombre == "bass":
		from app.audio.motor_bass import MotorBass

		return MotorBass
	if nombre == "nulo":
		from app.audio.motor_nulo import MotorNulo

		return MotorNulo
	raise KeyError(nombre)


def nombre_motor(nombre: str) -> str:
	"""Nombre para mostrar de un motor."""
	texto = NOMBRES.get(nombre)
	return _(texto) if texto is not None else nombre


def motores_disponibles() -> list[dict]:
	"""Todos los motores, con si se pueden usar en este equipo y, si no, por qué.

	Cada elemento: ``{"id", "nombre", "disponible", "motivo"}``. No abre ningún dispositivo.
	"""
	lista: list[dict] = []
	for identificador in MOTORES:
		try:
			hay, motivo = clase_motor(identificador).disponible()
		except (ImportError, OSError) as error:
			log.warning("No se pudo comprobar el motor de sonido %s.", identificador, exc_info=True)
			hay, motivo = False, str(error)
		lista.append({"id": identificador, "nombre": nombre_motor(identificador), "disponible": hay, "motivo": motivo})
	return lista


def cadena_de(pedido: str) -> list[str]:
	"""El orden en que se prueban los motores cuando se pide ``pedido``."""
	if pedido in CADENA:
		return list(CADENA[CADENA.index(pedido) :])
	if pedido == "bass":
		return ["bass", *CADENA]
	return list(CADENA)


def crear_motor(config: dict | None = None, banco: Any = None) -> MotorAudio:
	"""Devuelve un motor ya iniciado: el configurado o, si no puede ser, el siguiente de la cadena.

	``banco`` (un :class:`app.audio.banco.Banco`) se conecta como ``resolver`` del motor, para que
	encuentre los sonidos por su nombre sin cargarlos antes. Nunca lanza: en el peor caso devuelve el
	motor nulo.
	"""
	config = dict(config or {})
	pedido = str(config.get("motor") or MOTOR_DE_SERIE)
	if pedido not in MOTORES:
		log.warning("Motor de sonido desconocido en la configuración: %s; se usa %s.", pedido, MOTOR_DE_SERIE)
		pedido = MOTOR_DE_SERIE
	if os.environ.get(VARIABLE_SIN_SONIDO) == "1":
		log.info("%s=1: se usa el motor de sonido nulo.", VARIABLE_SIN_SONIDO)
		orden = ["nulo"]
	else:
		orden = cadena_de(pedido)
	dispositivo = str(config.get("dispositivo") or "") or None
	for identificador in orden:
		try:
			clase = clase_motor(identificador)
			hay, motivo = clase.disponible()
			if not hay:
				log.warning("Motor de sonido %s no disponible: %s", identificador, motivo)
				continue
			motor = clase()
			motor.pedido = pedido  # type: ignore[attr-defined]
			if banco is not None:
				motor.resolver = banco.datos  # type: ignore[attr-defined]
			motor.iniciar(dispositivo, config)
		except ErrorMotor as error:
			log.warning("El motor de sonido %s no ha arrancado: %s. Se prueba el siguiente.", identificador, error)
			continue
		except ImportError, OSError:
			log.warning("El motor de sonido %s no ha arrancado. Se prueba el siguiente.", identificador, exc_info=True)
			continue
		except Exception:  # noqa: BLE001 - una biblioteca de sonido puede fallar de cualquier forma; se cae al siguiente motor
			log.exception("Fallo inesperado al arrancar el motor de sonido %s. Se prueba el siguiente.", identificador)
			continue
		if identificador != pedido:
			log.warning("Se pidió el motor de sonido %s, pero está en uso %s.", pedido, identificador)
		else:
			log.info("Motor de sonido en uso: %s.", identificador)
		return motor
	# No debería ocurrir (el nulo no falla), pero el programa no puede quedarse sin motor.
	from app.audio.motor_nulo import MotorNulo

	motor = MotorNulo()
	motor.pedido = pedido
	motor.iniciar(None, config)
	return motor
