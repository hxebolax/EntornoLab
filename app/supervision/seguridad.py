"""Seguridad de la supervisión: código de emparejamiento, certificado propio, huellas e intentos.

Tres piezas, todas con la biblioteca estándar:

1. **Código de emparejamiento.** Un código corto que el profesional dicta al
   alumno. Nunca viaja por la red: cada lado demuestra que lo conoce con un
   HMAC sobre dos números aleatorios (uno de cada lado) y la huella del
   certificado. Atar la prueba a la huella hace que un intermediario con
   otro certificado no pueda reenviarla.
2. **TLS con certificado autofirmado.** La sala genera una vez una clave RSA
   de 2048 bits y un certificado X.509 (en Python puro, adaptado del
   generador del autor en JuegoGTA) y los guarda en ``data/config``. Nadie
   lo firma: la confianza viene de la huella.
3. **Huella recordada.** El cliente guarda la huella de cada sala la primera
   vez y se niega a conectar si un día es otra, hasta que la persona lo acepta.

LÍMITES que hay que conocer (se repiten en docs/supervision.md):

- Un código de 6 cifras frena conexiones accidentales y a curiosos, y el
  límite de intentos impide adivinarlo en línea. NO resiste a un atacante
  activo en la misma red que intercepte el PRIMER emparejamiento y pruebe
  códigos sin conexión; contra eso sirve comparar la huella que muestran la
  sala y el reproductor, o usar un código largo.
- La clave privada se guarda sin cifrar en ``data/config``: quien copie esa
  carpeta puede suplantar la sala.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import ssl
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core import paths

log = logging.getLogger(__name__)

NOMBRE_CERTIFICADO = "sala_certificado.pem"
NOMBRE_LLAVE = "sala_llave.pem"
NOMBRE_HUELLAS = "salas_conocidas.json"

LONGITUD_CODIGO = 6
# Solo cifras: se dictan de viva voz sin confusiones y se teclean en cualquier teclado.
_ALFABETO_CODIGO = "0123456789"


# ── Código de emparejamiento ─────────────────────────────────────────────────


def generar_codigo(longitud: int = LONGITUD_CODIGO) -> str:
	"""Código numérico aleatorio, fácil de dictar y de teclear con un lector de pantalla."""
	return "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(max(4, longitud)))


def normalizar_codigo(codigo: str) -> str:
	"""Quita espacios y guiones y pasa a mayúsculas: «12 34-56» vale lo mismo que «123456»."""
	return "".join(letra for letra in str(codigo).upper() if letra.isalnum())


def _prueba(papel: bytes, codigo: str, reto: str, nonce: str, huella: str) -> str:
	mensaje = b"|".join(
		[b"entornolab-supervision-1", papel, reto.encode("utf-8"), nonce.encode("utf-8"), huella.encode("ascii", "replace")]
	)
	return hmac.new(normalizar_codigo(codigo).encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


def prueba_cliente(codigo: str, reto: str, nonce: str, huella: str) -> str:
	"""Lo que el reproductor envía en ``hola`` para demostrar que conoce el código."""
	return _prueba(b"cliente", codigo, reto, nonce, huella)


def prueba_sala(codigo: str, reto: str, nonce: str, huella: str) -> str:
	"""Lo que la sala envía en ``bienvenida``: el reproductor comprueba que la sala también conoce el código."""
	return _prueba(b"sala", codigo, reto, nonce, huella)


def pruebas_iguales(a: str, b: str) -> bool:
	"""Comparación en tiempo constante."""
	return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def nuevo_nonce() -> str:
	"""Número aleatorio de un solo uso (32 caracteres hexadecimales)."""
	return secrets.token_hex(16)


# ── Límite de intentos ───────────────────────────────────────────────────────


class ControlIntentos:
	"""Bloquea temporalmente una dirección tras varios códigos incorrectos.

	Con 6 cifras hay un millón de códigos; con 5 intentos por minuto y
	dirección, recorrerlos en línea llevaría meses. Además hay un tope global
	(diez veces el de una dirección) por si se prueban códigos desde muchas
	direcciones a la vez: aun así harían falta días, y la sala avisa al
	profesional de cada código incorrecto.
	"""

	def __init__(self, maximo: int = 5, bloqueo_s: float = 60.0, reloj: Callable[[], float] = time.monotonic) -> None:
		self.maximo = max(1, maximo)
		self.bloqueo_s = bloqueo_s
		self._reloj = reloj
		self._fallos: dict[str, list[float]] = {}
		self._bloqueados: dict[str, float] = {}
		self._candado = threading.Lock()

	def _limpiar(self, ahora: float) -> None:
		for direccion in [d for d, hasta in self._bloqueados.items() if hasta <= ahora]:
			del self._bloqueados[direccion]
		for direccion in list(self._fallos):
			recientes = [t for t in self._fallos[direccion] if ahora - t < self.bloqueo_s]
			if recientes:
				self._fallos[direccion] = recientes
			else:
				del self._fallos[direccion]

	def espera(self, direccion: str) -> float:
		"""Segundos que le quedan de bloqueo a una dirección (0 si puede intentarlo)."""
		with self._candado:
			ahora = self._reloj()
			self._limpiar(ahora)
			global_hasta = self._bloqueados.get("*", 0.0)
			propia_hasta = self._bloqueados.get(direccion, 0.0)
			return max(0.0, max(global_hasta, propia_hasta) - ahora)

	def fallo(self, direccion: str) -> int:
		"""Apunta un código incorrecto. Devuelve los intentos que le quedan a esa dirección."""
		with self._candado:
			ahora = self._reloj()
			self._limpiar(ahora)
			self._fallos.setdefault(direccion, []).append(ahora)
			propios = len(self._fallos[direccion])
			totales = sum(len(lista) for lista in self._fallos.values())
			if propios >= self.maximo:
				self._bloqueados[direccion] = ahora + self.bloqueo_s
				del self._fallos[direccion]
			if totales >= self.maximo * 10:
				self._bloqueados["*"] = ahora + self.bloqueo_s
				self._fallos.clear()
			return max(0, self.maximo - propios)

	def acierto(self, direccion: str) -> None:
		"""Un emparejamiento correcto borra los fallos de esa dirección."""
		with self._candado:
			self._fallos.pop(direccion, None)

	def bloqueados(self) -> int:
		"""Cuántas direcciones están bloqueadas ahora."""
		with self._candado:
			self._limpiar(self._reloj())
			return len(self._bloqueados)


# ── Certificado autofirmado en Python puro ───────────────────────────────────

_PRIMOS_PEQUENOS = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p**0.5) + 1, 2))]

_OID_RSA = "1.2.840.113549.1.1.1"
_OID_SHA256_RSA = "1.2.840.113549.1.1.11"
_OID_SHA256 = "2.16.840.1.101.3.4.2.1"
_OID_NOMBRE_COMUN = "2.5.4.3"
_NULO = b"\x05\x00"


def _es_primo(n: int, rondas: int = 40) -> bool:
	"""Miller-Rabin, tras descartar los múltiplos de primos pequeños."""
	if n < 2:
		return False
	for p in _PRIMOS_PEQUENOS:
		if n % p == 0:
			return n == p
	d = n - 1
	s = 0
	while d % 2 == 0:
		d //= 2
		s += 1
	for _ronda in range(rondas):
		a = secrets.randbelow(n - 3) + 2
		x = pow(a, d, n)
		if x in (1, n - 1):
			continue
		for _paso in range(s - 1):
			x = pow(x, 2, n)
			if x == n - 1:
				break
		else:
			return False
	return True


def _primo(bits: int) -> int:
	while True:
		# Los dos bits de arriba puestos (el producto tendrá el tamaño pedido) e impar.
		candidato = secrets.randbits(bits) | (3 << (bits - 2)) | 1
		if _es_primo(candidato):
			return candidato


def _largo(n: int) -> bytes:
	if n < 128:
		return bytes([n])
	octetos = n.to_bytes((n.bit_length() + 7) // 8, "big")
	return bytes([0x80 | len(octetos)]) + octetos


def _tlv(etiqueta: int, contenido: bytes) -> bytes:
	return bytes([etiqueta]) + _largo(len(contenido)) + contenido


def _entero(n: int) -> bytes:
	# Con un cero delante si hace falta: en DER un entero con el bit alto puesto sería negativo.
	return _tlv(0x02, n.to_bytes(n.bit_length() // 8 + 1, "big"))


def _secuencia(*partes: bytes) -> bytes:
	return _tlv(0x30, b"".join(partes))


def _oid(texto: str) -> bytes:
	numeros = [int(x) for x in texto.split(".")]
	salida = bytes([40 * numeros[0] + numeros[1]])
	for numero in numeros[2:]:
		trozo = [numero & 0x7F]
		numero >>= 7
		while numero:
			trozo.append(0x80 | (numero & 0x7F))
			numero >>= 7
		salida += bytes(reversed(trozo))
	return _tlv(0x06, salida)


def _bits(contenido: bytes) -> bytes:
	return _tlv(0x03, b"\x00" + contenido)


def _pem(tipo: str, der: bytes) -> str:
	b64 = base64.b64encode(der).decode("ascii")
	lineas = [b64[i : i + 64] for i in range(0, len(b64), 64)]
	return f"-----BEGIN {tipo}-----\n" + "\n".join(lineas) + f"\n-----END {tipo}-----\n"


def _fecha_der(t: float) -> bytes:
	"""GeneralizedTime (año de cuatro cifras): UTCTime no sirve a partir de 2050."""
	return _tlv(0x18, time.strftime("%Y%m%d%H%M%SZ", time.gmtime(t)).encode("ascii"))


def crear_certificado(nombre: str = "EntornoLab", dias: int = 3650, bits: int = 2048) -> tuple[str, str]:
	"""Crea una clave RSA y un certificado X.509 autofirmado. Devuelve ``(certificado, llave)`` en PEM.

	Tarda unos segundos (busca dos primos de 1024 bits en Python puro): se
	hace una sola vez y se guarda. No lo firma ninguna autoridad; la
	seguridad la da que el reproductor recuerda su huella.
	"""
	e = 65537
	while True:
		p = _primo(bits // 2)
		q = _primo(bits // 2)
		n = p * q
		fi = (p - 1) * (q - 1)
		if p != q and n.bit_length() == bits and fi % e:
			break
	d = pow(e, -1, fi)
	llave = _secuencia(
		_entero(0),
		_entero(n),
		_entero(e),
		_entero(d),
		_entero(p),
		_entero(q),
		_entero(d % (p - 1)),
		_entero(d % (q - 1)),
		_entero(pow(q, -1, p)),
	)
	quien = _secuencia(_tlv(0x31, _secuencia(_oid(_OID_NOMBRE_COMUN), _tlv(0x0C, nombre.encode("utf-8")))))
	ahora = time.time()
	algoritmo = _secuencia(_oid(_OID_SHA256_RSA), _NULO)
	publica = _secuencia(_secuencia(_oid(_OID_RSA), _NULO), _bits(_secuencia(_entero(n), _entero(e))))
	fin = ahora + 86400.0 * dias
	# X.509 manda UTCTime hasta 2049 y GeneralizedTime desde 2050.
	validez = _secuencia(_fecha_validez(ahora - 86400.0), _fecha_validez(fin))
	cuerpo = _secuencia(_tlv(0xA0, _entero(2)), _entero(secrets.randbits(120) | 1), algoritmo, quien, validez, quien, publica)
	resumen = _secuencia(_secuencia(_oid(_OID_SHA256), _NULO), _tlv(0x04, hashlib.sha256(cuerpo).digest()))
	k = (bits + 7) // 8
	bloque = b"\x00\x01" + b"\xff" * (k - len(resumen) - 3) + b"\x00" + resumen  # PKCS#1 v1.5
	firma = pow(int.from_bytes(bloque, "big"), d, n).to_bytes(k, "big")
	certificado = _secuencia(cuerpo, algoritmo, _bits(firma))
	return _pem("CERTIFICATE", certificado), _pem("RSA PRIVATE KEY", llave)


def _fecha_validez(t: float) -> bytes:
	if time.gmtime(t).tm_year < 2050:
		return _tlv(0x17, time.strftime("%y%m%d%H%M%SZ", time.gmtime(t)).encode("ascii"))
	return _fecha_der(t)


def huella_de_der(der: bytes) -> str:
	"""Huella SHA-256 de un certificado en DER, en hexadecimal en minúsculas."""
	return hashlib.sha256(der).hexdigest()


def huella_de_pem(pem: str) -> str:
	"""Huella SHA-256 de un certificado en PEM."""
	return huella_de_der(ssl.PEM_cert_to_DER_cert(pem))


def huella_legible(huella: str, grupos: int = 4) -> str:
	"""Primeros grupos de la huella separados por espacios, para leerla en voz alta y compararla.

	Con 4 grupos de 4 cifras hexadecimales (64 bits) basta para comparar a
	oído; la huella completa se usa siempre en las comprobaciones automáticas.
	"""
	texto = huella.upper()
	return " ".join(texto[i : i + 4] for i in range(0, min(len(texto), grupos * 4), 4))


@dataclass(frozen=True)
class Certificado:
	"""Rutas del certificado y la clave de la sala, y su huella."""

	ruta_certificado: Path
	ruta_llave: Path
	huella: str


def asegurar_certificado(carpeta: Path | str | None = None, *, bits: int = 2048) -> Certificado:
	"""Devuelve el certificado de la sala, creándolo la primera vez.

	La primera llamada tarda unos segundos: conviene hacerla en un hilo de
	trabajo antes de abrir la sala en red.

	:param carpeta: por defecto ``data/config``.
	"""
	destino = Path(carpeta) if carpeta is not None else paths.ruta_configuracion()
	destino.mkdir(parents=True, exist_ok=True)
	ruta_cert = destino / NOMBRE_CERTIFICADO
	ruta_llave = destino / NOMBRE_LLAVE
	if ruta_cert.is_file() and ruta_llave.is_file():
		try:
			pem = ruta_cert.read_text(encoding="ascii")
			huella = huella_de_pem(pem)
			contexto_servidor(ruta_cert, ruta_llave)
			return Certificado(ruta_cert, ruta_llave, huella)
		except OSError, ValueError, ssl.SSLError:
			log.warning("El certificado guardado de la sala no sirve; se crea otro", exc_info=True)
	inicio = time.monotonic()
	certificado, llave = crear_certificado(bits=bits)
	for ruta, contenido in ((ruta_llave, llave), (ruta_cert, certificado)):
		temporal = ruta.with_name(ruta.name + ".tmp")
		with open(temporal, "w", encoding="ascii", newline="\n") as salida:
			salida.write(contenido)
		os.replace(temporal, ruta)
	log.info("Certificado de la sala creado en %.1f s", time.monotonic() - inicio)
	return Certificado(ruta_cert, ruta_llave, huella_de_pem(certificado))


def contexto_servidor(ruta_certificado: Path, ruta_llave: Path) -> ssl.SSLContext:
	"""Contexto TLS de la sala (TLS 1.2 como mínimo)."""
	contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
	contexto.minimum_version = ssl.TLSVersion.TLSv1_2
	contexto.load_cert_chain(str(ruta_certificado), str(ruta_llave))
	return contexto


def contexto_cliente() -> ssl.SSLContext:
	"""Contexto TLS del reproductor.

	No valida el certificado contra autoridades (es autofirmado y la sala
	no tiene nombre de dominio): la autenticidad se comprueba después, con
	la huella recordada y con la prueba del código atada a esa huella.
	"""
	contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
	contexto.minimum_version = ssl.TLSVersion.TLSv1_2
	contexto.check_hostname = False
	contexto.verify_mode = ssl.CERT_NONE
	return contexto


# ── Huellas recordadas por el cliente ────────────────────────────────────────


class AlmacenHuellas:
	"""Huellas de las salas ya conocidas, en ``data/config/salas_conocidas.json``.

	La clave es ``host:puerto``. Si la sala cambia de dirección (otra IP por
	DHCP) se tratará como nueva; si otra sala aparece en la dirección de una
	conocida, saltará el aviso de huella cambiada. Es el comportamiento
	prudente: ante la duda, se pregunta a la persona.
	"""

	def __init__(self, ruta: Path | str | None = None) -> None:
		self.ruta = Path(ruta) if ruta is not None else paths.ruta_configuracion() / NOMBRE_HUELLAS
		self._candado = threading.Lock()

	def _leer(self) -> dict[str, str]:
		try:
			with open(self.ruta, encoding="utf-8") as entrada:
				datos = json.load(entrada)
		except FileNotFoundError:
			return {}
		except OSError, ValueError:
			log.warning("No se ha podido leer el fichero de salas conocidas; se empieza de cero", exc_info=True)
			return {}
		if not isinstance(datos, dict):
			return {}
		return {str(clave): str(valor) for clave, valor in datos.items() if isinstance(valor, str)}

	@staticmethod
	def clave(host: str, puerto: int) -> str:
		"""Clave con la que se recuerda una sala."""
		return f"{host.strip().lower()}:{int(puerto)}"

	def obtener(self, host: str, puerto: int) -> str | None:
		"""Huella recordada de esa sala, o ``None`` si es la primera vez."""
		with self._candado:
			return self._leer().get(self.clave(host, puerto))

	def recordar(self, host: str, puerto: int, huella: str) -> None:
		"""Guarda (o sustituye) la huella de una sala. Escritura atómica."""
		with self._candado:
			datos = self._leer()
			datos[self.clave(host, puerto)] = huella
			self.ruta.parent.mkdir(parents=True, exist_ok=True)
			temporal = self.ruta.with_name(self.ruta.name + ".tmp")
			with open(temporal, "w", encoding="utf-8") as salida:
				json.dump(datos, salida, ensure_ascii=False, indent=2)
			os.replace(temporal, self.ruta)

	def olvidar(self, host: str, puerto: int) -> bool:
		"""Borra la huella recordada de una sala."""
		with self._candado:
			datos = self._leer()
			if datos.pop(self.clave(host, puerto), None) is None:
				return False
			temporal = self.ruta.with_name(self.ruta.name + ".tmp")
			with open(temporal, "w", encoding="utf-8") as salida:
				json.dump(datos, salida, ensure_ascii=False, indent=2)
			os.replace(temporal, self.ruta)
			return True
