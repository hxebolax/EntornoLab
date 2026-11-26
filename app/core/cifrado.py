"""Cifrado por contraseña de los datos personales (fichas de alumnos).

Por qué existe además de ``secretos.py``: DPAPI liga lo cifrado al usuario de
Windows y al equipo. EntornoLab es portable y las fichas deben poder viajar
con la carpeta (un pendrive, otro ordenador del centro), así que aquí la
clave sale de una **contraseña del profesional** y de nada más.

Cómo funciona:

- **Derivación de la clave**: ``hashlib.scrypt`` (biblioteca estándar), que
  es lenta y gasta memoria a propósito: probar contraseñas a ciegas resulta
  caro. La sal es aleatoria, no es secreta y se guarda junto a los datos.
- **Cifrado autenticado**: AES-256 en modo GCM del paquete ``cryptography``.
  Además de ocultar el contenido, detecta cualquier cambio: un dato
  manipulado o una contraseña equivocada dan ``ErrorCifrado``, nunca basura.
- **Formato con versión**: cada bloque empieza por una marca, para poder
  cambiar de algoritmo en el futuro sin perder lo ya guardado.

Uso con la clave en memoria (lo normal: se deriva una vez al abrir la sesión
del profesional y se reutiliza)::

	sal = cifrado.nueva_sal()                       # se guarda junto a los datos
	clave = cifrado.derivar_clave(contrasena, sal)  # tarda décimas de segundo
	bloque = cifrado.cifrar(b"dato personal", clave)
	dato = cifrado.descifrar(bloque, clave)

Uso de un solo paso (un archivo suelto; la sal y los parámetros viajan dentro)::

	bloque = cifrado.cifrar_con_contrasena(datos, contrasena)
	datos = cifrado.descifrar_con_contrasena(bloque, contrasena)

Limitaciones que hay que conocer:

- Si se olvida la contraseña, los datos cifrados NO se pueden recuperar.
- ``derivar_clave`` tarda a propósito: llámela desde una tarea de fondo, no
  desde el hilo de la interfaz.
- Sin el paquete ``cryptography`` no se cifra ni se descifra
  (``ErrorCifrado``): no se sustituye por un cifrado casero, que daría una
  falsa sensación de seguridad.
- Python no permite borrar una contraseña de la memoria; no guarde la
  contraseña, solo la clave derivada, y suéltela al cerrar la sesión.

La contraseña y la clave nunca se escriben en el registro.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

log = logging.getLogger(__name__)

# Marca de un bloque cifrado con clave: «EntornoLab Cifrado, versión 1».
MARCA_BLOQUE = b"ELC1"
# Marca de un bloque cifrado con contraseña (lleva dentro sal y parámetros).
MARCA_CONTRASENA = b"ELP1"

LONGITUD_CLAVE = 32
LONGITUD_SAL = 16
LONGITUD_NONCE = 12
LONGITUD_SELLO = 16

# Coste de scrypt: N = 2**15 gasta unos 32 MB y décimas de segundo por
# intento en un equipo corriente. Es el mínimo recomendado para uso
# interactivo; subirlo dobla memoria y tiempo.
SCRYPT_LOG2_N = 15
SCRYPT_R = 8
SCRYPT_P = 1

# Texto fijo que se cifra para comprobar después si una contraseña es la buena.
_TEXTO_COMPROBANTE = b"EntornoLab/comprobante/v1"


class ErrorCifrado(Exception):
	"""No se pudo cifrar o descifrar: contraseña equivocada, datos manipulados o entrada no válida."""


def nueva_sal() -> bytes:
	"""Sal aleatoria para ``derivar_clave``. No es secreta: se guarda junto a los datos."""
	return os.urandom(LONGITUD_SAL)


def derivar_clave(
	contrasena: str,
	sal: bytes,
	*,
	log2_n: int = SCRYPT_LOG2_N,
	r: int = SCRYPT_R,
	p: int = SCRYPT_P,
) -> bytes:
	"""Convierte la contraseña del profesional en una clave de 32 bytes.

	La misma contraseña con la misma sal da siempre la misma clave; con otra
	sal, otra distinta (dos instalaciones con la misma contraseña no
	comparten clave).

	:param contrasena: texto que escribe el profesional. No puede estar vacío.
	:param sal: bytes aleatorios de ``nueva_sal()``, de 8 bytes como mínimo.
	:param log2_n: coste de scrypt como potencia de dos (15 → N = 32768).
	:raises ErrorCifrado: contraseña vacía, sal corta o parámetros no admitidos.
	"""
	if not isinstance(contrasena, str) or not contrasena:
		raise ErrorCifrado("La contraseña no puede estar vacía.")
	if not isinstance(sal, (bytes, bytearray)) or len(sal) < 8:
		raise ErrorCifrado("La sal debe tener al menos 8 bytes.")
	if not 10 <= log2_n <= 22 or not 1 <= r <= 32 or not 1 <= p <= 16:
		raise ErrorCifrado("Parámetros de derivación fuera de los límites admitidos.")
	n = 1 << log2_n
	try:
		return hashlib.scrypt(
			contrasena.encode("utf-8"),
			salt=bytes(sal),
			n=n,
			r=r,
			p=p,
			# scrypt necesita 128 * N * r bytes; el límite de serie de OpenSSL (32 MB) se queda justo.
			maxmem=128 * n * r * 2 + 1024 * 1024,
			dklen=LONGITUD_CLAVE,
		)
	except (ValueError, MemoryError, AttributeError) as error:
		raise ErrorCifrado(f"No se pudo derivar la clave: {type(error).__name__}.") from error


def _aesgcm(clave: bytes):
	"""Objeto de cifrado AES-GCM para ``clave``; ``ErrorCifrado`` si falta el paquete o la clave no vale."""
	if not isinstance(clave, (bytes, bytearray)) or len(clave) != LONGITUD_CLAVE:
		raise ErrorCifrado(f"La clave debe tener {LONGITUD_CLAVE} bytes (use derivar_clave).")
	return _clase_aesgcm()(bytes(clave))


def _clase_aesgcm():
	"""Importa la clase ``AESGCM``; ``ErrorCifrado`` con la causa real si no se puede.

	El fallo se apunta en el registro con su traza: en la versión compilada no
	basta con decir «falta el paquete», porque casi siempre el paquete está y lo
	que falla es una biblioteca de la que depende; sin la traza no hay forma de
	saber cuál.
	"""
	try:
		from cryptography.hazmat.primitives.ciphers.aead import AESGCM
	except ImportError as error:
		log.exception("No se puede cargar el cifrado AES-GCM del paquete «cryptography»")
		raise ErrorCifrado(
			f"Falta el paquete «cryptography» o una de sus partes ({type(error).__name__}: {error}); sin él no se pueden cifrar las fichas."
		) from error
	return AESGCM


def comprobar_disponible() -> str | None:
	"""Comprueba que se puede cifrar de verdad; devuelve None si todo va bien o el motivo si no.

	La usa ``--comprobar-arranque`` para que una compilación a la que le falte
	algo del cifrado falle al compilar y no cuando el profesional abre las fichas.
	"""
	try:
		clave = derivar_clave("comprobacion", nueva_sal())
		if descifrar(cifrar(b"ok", clave), clave) != b"ok":
			return "el cifrado de prueba no devuelve lo mismo"
	except ErrorCifrado as error:
		return str(error)
	return None


def cifrar(datos: bytes, clave: bytes, asociado: bytes = b"") -> bytes:
	"""Cifra ``datos`` con ``clave``. Devuelve marca + nonce + texto cifrado con sello.

	:param datos: contenido en claro.
	:param clave: 32 bytes de ``derivar_clave``.
	:param asociado: dato que NO se cifra pero queda atado al bloque (por
		ejemplo, el identificador del alumno): si alguien copia el bloque a
		otra ficha, no se podrá descifrar allí. Hay que pasar el mismo al
		descifrar.
	:raises ErrorCifrado: clave no válida o falta ``cryptography``.
	"""
	if not isinstance(datos, (bytes, bytearray)):
		raise ErrorCifrado("Solo se cifran bytes (codifique el texto en UTF-8).")
	cifrador = _aesgcm(clave)
	# Un nonce aleatorio de 96 bits por bloque: nunca se repite con la misma clave.
	nonce = os.urandom(LONGITUD_NONCE)
	return MARCA_BLOQUE + nonce + cifrador.encrypt(nonce, bytes(datos), bytes(asociado) or None)


def descifrar(datos: bytes, clave: bytes, asociado: bytes = b"") -> bytes:
	"""Descifra un bloque de ``cifrar``.

	:raises ErrorCifrado: clave equivocada, bloque manipulado, truncado o de otro formato.
	"""
	if not isinstance(datos, (bytes, bytearray)):
		raise ErrorCifrado("El bloque cifrado debe ser de bytes.")
	bloque = bytes(datos)
	minimo = len(MARCA_BLOQUE) + LONGITUD_NONCE + LONGITUD_SELLO
	if len(bloque) < minimo or not bloque.startswith(MARCA_BLOQUE):
		raise ErrorCifrado("El bloque no es un dato cifrado de EntornoLab o está incompleto.")
	cifrador = _aesgcm(clave)
	inicio = len(MARCA_BLOQUE)
	nonce = bloque[inicio : inicio + LONGITUD_NONCE]
	try:
		from cryptography.exceptions import InvalidTag

		return cifrador.decrypt(nonce, bloque[inicio + LONGITUD_NONCE :], bytes(asociado) or None)
	except InvalidTag as error:
		# Deliberadamente sin más detalle: no se distingue «contraseña mala» de «dato tocado».
		raise ErrorCifrado("No se pudo descifrar: la contraseña no es correcta o los datos están dañados.") from error


def cifrar_con_contrasena(datos: bytes, contrasena: str, asociado: bytes = b"") -> bytes:
	"""Cifra con una contraseña en un solo paso; la sal y los parámetros viajan en el bloque.

	Cómodo para un archivo suelto (una copia de seguridad). Para muchas
	fichas, derive la clave una vez y use ``cifrar``: cada llamada a esta
	función repite la derivación, que es lenta a propósito.
	"""
	sal = nueva_sal()
	clave = derivar_clave(contrasena, sal)
	cabecera = MARCA_CONTRASENA + bytes((SCRYPT_LOG2_N, SCRYPT_R, SCRYPT_P)) + sal
	# La cabecera se ata al bloque: cambiar la sal o el coste invalida el sello.
	return cabecera + cifrar(datos, clave, cabecera + bytes(asociado))


def descifrar_con_contrasena(datos: bytes, contrasena: str, asociado: bytes = b"") -> bytes:
	"""Descifra un bloque de ``cifrar_con_contrasena``.

	:raises ErrorCifrado: contraseña equivocada o bloque dañado.
	"""
	if not isinstance(datos, (bytes, bytearray)):
		raise ErrorCifrado("El bloque cifrado debe ser de bytes.")
	bloque = bytes(datos)
	largo_cabecera = len(MARCA_CONTRASENA) + 3 + LONGITUD_SAL
	if len(bloque) <= largo_cabecera or not bloque.startswith(MARCA_CONTRASENA):
		raise ErrorCifrado("El bloque no es un dato cifrado con contraseña de EntornoLab o está incompleto.")
	cabecera = bloque[:largo_cabecera]
	posicion = len(MARCA_CONTRASENA)
	log2_n = cabecera[posicion]
	r = cabecera[posicion + 1]
	p = cabecera[posicion + 2]
	sal = cabecera[posicion + 3 :]
	clave = derivar_clave(contrasena, sal, log2_n=log2_n, r=r, p=p)
	return descifrar(bloque[largo_cabecera:], clave, cabecera + bytes(asociado))


def crear_comprobante(clave: bytes) -> bytes:
	"""Bloque que permite comprobar más adelante si una clave es la correcta.

	Se guarda junto a la sal al definir la contraseña del profesional. No
	revela la clave ni la contraseña.
	"""
	return cifrar(_TEXTO_COMPROBANTE, clave)


def clave_correcta(clave: bytes, comprobante: bytes) -> bool:
	"""True si ``clave`` descifra el ``comprobante`` de ``crear_comprobante``.

	Devuelve False (sin lanzar) con una clave equivocada o un comprobante
	dañado; así la interfaz solo tiene que decir «contraseña incorrecta».
	"""
	try:
		claro = descifrar(comprobante, clave)
	except ErrorCifrado:
		log.debug("El comprobante no se pudo descifrar con la clave dada.")
		return False
	return hmac.compare_digest(claro, _TEXTO_COMPROBANTE)
