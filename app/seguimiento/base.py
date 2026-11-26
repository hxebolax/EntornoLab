"""Base de datos del seguimiento (``data/db/entornolab.db``) y cifrado de campos.

Decisiones y por qué (adaptado del agente «base-datos-sqlite»):

- **Una sola conexión protegida con un candado reentrante.** La base es
  pequeña (unas decenas de alumnos, unos miles de sesiones) y la usan el hilo
  de la interfaz y, como mucho, uno de trabajo: serializar todo en Python
  evita los «database is locked» sin la complejidad de varias conexiones.
- **WAL, claves foráneas y ``secure_delete``.** Las claves foráneas con
  ``ON DELETE CASCADE`` hacen que borrar un alumno se lleve todo lo suyo;
  ``secure_delete`` pone a cero las páginas liberadas, porque el borrado de
  datos de salud debe ser real y no solo «marcar como libre».
- **Transacciones explícitas** (``BEGIN IMMEDIATE``): no dependen de las
  reglas implícitas de ``sqlite3``. Anidadas con ``SAVEPOINT``.
- **Migraciones numeradas con ``PRAGMA user_version``**, cada una en su
  transacción, con copia de seguridad previa y rechazo de versiones futuras.
- **Cifrado por campos e inyectado.** Este módulo no sabe de algoritmos:
  recibe dos funciones ``cifrar(bytes) -> bytes`` y ``descifrar(bytes) ->
  bytes`` (las aporta ``app.core.cifrado`` con la contraseña del profesional).
  Así se prueba sin criptografía y no hay dependencia entre paquetes. Cada
  valor guardado lleva delante un octeto que dice si está cifrado, para poder
  abrir una base antigua sin cifrar y cifrarla al vuelo.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import threading
import unicodedata
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core import paths
from app.core.i18n import _

log = logging.getLogger(__name__)

NOMBRE_BASE = "entornolab.db"

# Valores admitidos; el esquema los repite en sus CHECK.
PERFILES: tuple[str, ...] = ("baston", "perro_guia", "baja_vision", "otro")
ESTILOS: tuple[str, ...] = ("infantil", "juvenil", "adulto")
MODOS: tuple[str, ...] = ("juego", "practica", "examen")
TIPOS_RECOMPENSA: tuple[str, ...] = ("estrella", "medalla", "objeto")

# Octeto que precede a cada campo sensible guardado.
_MARCA_CLARO = b"\x00"
_MARCA_CIFRADO = b"\x01"

# Texto conocido que se guarda cifrado para comprobar la clave al abrir.
_TEXTO_PRUEBA = b"entornolab-seguimiento"

# Columnas con datos sensibles: (tabla, columna). Las recorre el recifrado.
CAMPOS_CIFRADOS: tuple[tuple[str, str], ...] = (
	("alumnos", "nombre_real"),
	("alumnos", "notas"),
	("sesiones", "notas"),
	("evaluaciones_reales", "observaciones"),
	("marcas", "texto"),
)

Parametros = Sequence[Any] | dict[str, Any]


class ErrorBase(Exception):
	"""Problema de la base de datos que la aplicación debe mostrar; nunca se oculta."""


class ErrorMigracion(ErrorBase):
	"""Una migración falló; la base sigue en la versión anterior."""


class ErrorVersionFutura(ErrorMigracion):
	"""La base la creó una versión más nueva de la aplicación: no se toca."""


class ErrorClave(ErrorBase):
	"""La clave de cifrado no es la de esta base, o falta."""


class ErrorDatos(ErrorBase, ValueError):
	"""Un dato no es válido (alias vacío o repetido, perfil desconocido...)."""


# ── Cifrado inyectable ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class Cifrador:
	"""Pareja de funciones que cifran y descifran los campos sensibles.

	``cifrar`` y ``descifrar`` son ``None`` en el modo «sin cifrar», pensado
	para las pruebas y para quien todavía no ha puesto contraseña.
	"""

	cifrar: Callable[[bytes], bytes] | None = None
	descifrar: Callable[[bytes], bytes] | None = None

	def __post_init__(self) -> None:
		if (self.cifrar is None) != (self.descifrar is None):
			raise ValueError("cifrar y descifrar deben darse juntas o ninguna")

	@property
	def activo(self) -> bool:
		"""True si los campos se guardan cifrados."""
		return self.cifrar is not None

	@classmethod
	def sin_cifrar(cls) -> Cifrador:
		"""Modo de pruebas: los campos se guardan en claro."""
		return cls()

	@classmethod
	def con_clave(
		cls,
		clave: bytes,
		cifrar: Callable[[bytes, bytes], bytes],
		descifrar: Callable[[bytes, bytes], bytes],
	) -> Cifrador:
		"""Ata una clave a funciones de la forma ``f(datos, clave)``.

		Es la forma cómoda de enchufar un módulo de cifrado que trabaja con
		clave explícita sin que este paquete lo importe.
		"""
		if not isinstance(clave, (bytes, bytearray)) or not clave:
			raise ValueError("la clave debe ser una secuencia de octetos no vacía")
		clave_fija = bytes(clave)

		def cifrar_con(datos: bytes) -> bytes:
			return cifrar(datos, clave_fija)

		def descifrar_con(datos: bytes) -> bytes:
			return descifrar(datos, clave_fija)

		return cls(cifrar_con, descifrar_con)

	def guardar(self, texto: str | None) -> bytes | None:
		"""Convierte un texto en el valor que se escribe en la base (None se queda en NULL)."""
		if texto is None or texto == "":
			return None
		datos = texto.encode("utf-8")
		if self.cifrar is None:
			return _MARCA_CLARO + datos
		return _MARCA_CIFRADO + bytes(self.cifrar(datos))

	def leer(self, valor: bytes | None) -> str | None:
		"""Recupera el texto de un valor guardado.

		Un valor en claro se lee siempre (base antigua sin cifrar). Uno cifrado
		sin funciones de descifrado es un error que debe verse.
		"""
		if valor is None:
			return None
		valor = bytes(valor)
		marca, cuerpo = valor[:1], valor[1:]
		if marca == _MARCA_CLARO:
			return cuerpo.decode("utf-8")
		if marca != _MARCA_CIFRADO:
			raise ErrorBase(_("Hay un campo guardado con un formato desconocido."))
		if self.descifrar is None:
			raise ErrorClave(_("Los datos están cifrados y no se ha dado la clave."))
		try:
			return bytes(self.descifrar(cuerpo)).decode("utf-8")
		except Exception as error:
			# Cada módulo de cifrado lanza su propia excepción: aquí se unifica.
			raise ErrorClave(_("No se han podido descifrar los datos: la clave no es correcta.")) from error


# ── Utilidades ───────────────────────────────────────────────────────────────


def ahora_iso() -> str:
	"""Fecha y hora actuales en ISO 8601 y UTC: se ordenan bien como texto."""
	return datetime.now(UTC).isoformat(timespec="seconds")


def normalizar_busqueda(texto: str) -> str:
	"""Minúsculas y sin acentos, para buscar «maria» y encontrar «María»."""
	descompuesto = unicodedata.normalize("NFKD", texto.casefold())
	return "".join(letra for letra in descompuesto if not unicodedata.combining(letra)).strip()


def ruta_por_defecto() -> Path:
	"""``data/db/entornolab.db``, creando la carpeta si falta."""
	return paths.ruta_base_datos() / NOMBRE_BASE


def dividir_sentencias(script: str) -> list[str]:
	"""Divide un script SQL en sentencias completas.

	``executescript`` hace COMMIT antes de empezar y rompería la transacción
	de la migración; ``sqlite3.complete_statement`` sabe si un ``;`` cierra
	de verdad la sentencia.
	"""
	sentencias: list[str] = []
	actual = ""
	for trozo in script.split(";"):
		actual += trozo + ";"
		if sqlite3.complete_statement(actual):
			texto = actual.strip()
			if texto.strip(";").strip():
				sentencias.append(texto)
			actual = ""
	resto = actual[:-1].strip()
	if resto:
		sentencias.append(resto)
	return sentencias


@dataclass(frozen=True)
class Migracion:
	"""Un paso de esquema. Su posición en la lista es su número (la primera es la 1)."""

	descripcion: str
	sql: str | None = None
	funcion: Callable[[sqlite3.Connection], None] | None = None


_LISTA_PERFILES = ", ".join(f"'{valor}'" for valor in PERFILES)
_LISTA_ESTILOS = ", ".join(f"'{valor}'" for valor in ESTILOS)
_LISTA_MODOS = ", ".join(f"'{valor}'" for valor in MODOS)
_LISTA_RECOMPENSAS = ", ".join(f"'{valor}'" for valor in TIPOS_RECOMPENSA)

# REGLA: nunca se modifica ni se reordena una migración publicada; se añade otra.
MIGRACIONES: tuple[Migracion, ...] = (
	Migracion(
		"Esquema inicial del seguimiento",
		sql=f"""
			CREATE TABLE meta (
				clave TEXT PRIMARY KEY,
				valor BLOB
			);
			CREATE TABLE alumnos (
				id INTEGER PRIMARY KEY,
				alias TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (length(trim(alias)) > 0),
				alias_busqueda TEXT NOT NULL,
				nombre_real BLOB,                 -- cifrado, opcional
				notas BLOB,                       -- cifrado, opcional
				ano_nacimiento INTEGER,
				perfil TEXT NOT NULL DEFAULT 'otro' CHECK (perfil IN ({_LISTA_PERFILES})),
				estilo TEXT NOT NULL DEFAULT 'adulto' CHECK (estilo IN ({_LISTA_ESTILOS})),
				ajustes TEXT NOT NULL DEFAULT '{{}}',   -- JSON con los ajustes de juego
				alta TEXT NOT NULL,               -- ISO 8601 en UTC
				archivado INTEGER NOT NULL DEFAULT 0
			);
			CREATE INDEX idx_alumnos_busqueda ON alumnos (alias_busqueda);
			CREATE TABLE sesiones (
				id TEXT PRIMARY KEY,              -- el del fichero data/sessions/<id>.json.gz
				alumno_id INTEGER NOT NULL REFERENCES alumnos (id) ON DELETE CASCADE,
				entorno_id TEXT NOT NULL DEFAULT '',
				entorno_nombre TEXT NOT NULL DEFAULT '',
				actividad_id TEXT NOT NULL DEFAULT '',
				actividad_nombre TEXT NOT NULL DEFAULT '',
				actividad_tipo TEXT NOT NULL DEFAULT '',
				modo TEXT NOT NULL DEFAULT 'juego' CHECK (modo IN ({_LISTA_MODOS})),
				inicio TEXT NOT NULL,
				fin TEXT NOT NULL,
				tiempo_activo REAL NOT NULL DEFAULT 0,
				tiempo_pausa REAL NOT NULL DEFAULT 0,
				completada INTEGER NOT NULL DEFAULT 0,
				parcial INTEGER NOT NULL DEFAULT 0,   -- guardado automático de una sesión que no terminó
				resumen TEXT NOT NULL DEFAULT '{{}}',   -- JSON con todas las medidas
				traza BLOB,                       -- JSON comprimido con zlib
				notas BLOB                        -- cifrado: notas del profesional
			);
			CREATE INDEX idx_sesiones_alumno ON sesiones (alumno_id, inicio);
			CREATE INDEX idx_sesiones_entorno ON sesiones (alumno_id, entorno_id, actividad_id, inicio);
			CREATE TABLE evaluaciones_reales (
				id INTEGER PRIMARY KEY,
				alumno_id INTEGER NOT NULL REFERENCES alumnos (id) ON DELETE CASCADE,
				entorno_id TEXT NOT NULL DEFAULT '',
				entorno_nombre TEXT NOT NULL DEFAULT '',
				fecha TEXT NOT NULL,              -- AAAA-MM-DD
				lugar TEXT NOT NULL DEFAULT '',
				rutas TEXT NOT NULL DEFAULT '[]', -- JSON: [{{"nombre", "resultado", "notas"}}]
				nivel_ayuda TEXT NOT NULL DEFAULT '',
				tipo_recorrido TEXT NOT NULL DEFAULT '',
				ayudas_movilidad TEXT NOT NULL DEFAULT '[]',  -- JSON: lista de textos
				observaciones BLOB,               -- cifrado
				dias_desde_entrenamiento INTEGER
			);
			CREATE INDEX idx_evaluaciones_alumno ON evaluaciones_reales (alumno_id, fecha);
			CREATE TABLE recompensas (
				id INTEGER PRIMARY KEY,
				alumno_id INTEGER NOT NULL REFERENCES alumnos (id) ON DELETE CASCADE,
				tipo TEXT NOT NULL CHECK (tipo IN ({_LISTA_RECOMPENSAS})),
				nombre TEXT NOT NULL DEFAULT '',
				fecha TEXT NOT NULL,
				sesion_id TEXT REFERENCES sesiones (id) ON DELETE SET NULL
			);
			CREATE INDEX idx_recompensas_alumno ON recompensas (alumno_id, tipo, fecha);
			CREATE TABLE marcas (
				id INTEGER PRIMARY KEY,
				sesion_id TEXT NOT NULL REFERENCES sesiones (id) ON DELETE CASCADE,
				t REAL NOT NULL DEFAULT 0,        -- segundo de tiempo activo de la sesión
				planta TEXT NOT NULL DEFAULT '',
				x REAL,
				y REAL,
				texto BLOB                        -- cifrado: la nota del profesional
			);
			CREATE INDEX idx_marcas_sesion ON marcas (sesion_id, t);
		""",
	),
)


# ── Clase principal ──────────────────────────────────────────────────────────


class BaseSeguimiento:
	"""Acceso a la base del seguimiento con migraciones, copias y cifrado de campos.

	:param ruta: fichero de la base; por defecto ``data/db/entornolab.db``. Las
		pruebas pasan una ruta dentro de ``tmp_path``.
	:param cifrador: cómo se cifran los campos sensibles. ``None`` equivale a
		``Cifrador.sin_cifrar()``.
	:param carpeta_copias: dónde van las copias. Por defecto, ``data/backups`` para la
		base de serie y una carpeta ``copias`` junto al fichero si se abre otra ruta
		(así las pruebas no escriben fuera de su carpeta temporal).
	:param migraciones: lista de migraciones (se puede ampliar en pruebas).
	"""

	def __init__(
		self,
		ruta: Path | str | None = None,
		*,
		cifrador: Cifrador | None = None,
		carpeta_copias: Path | str | None = None,
		copias_conservadas: int = 5,
		migraciones: Sequence[Migracion] = MIGRACIONES,
	) -> None:
		self.ruta = Path(ruta) if ruta is not None else ruta_por_defecto()
		self.ruta.parent.mkdir(parents=True, exist_ok=True)
		if carpeta_copias is not None:
			self.carpeta_copias = Path(carpeta_copias)
		elif ruta is None:
			self.carpeta_copias = paths.ruta_copias()
		else:
			self.carpeta_copias = self.ruta.parent / "copias"
		self.cifrador = cifrador if cifrador is not None else Cifrador.sin_cifrar()
		self._migraciones = tuple(migraciones)
		self._conservadas = max(1, copias_conservadas)
		self._candado = threading.RLock()
		self._profundidad = 0
		self._cerrada = False
		self._conexion = self._conectar()
		try:
			self._migrar()
			self._comprobar_clave()
		except BaseException:
			self._conexion.close()
			self._cerrada = True
			raise

	# ── Conexión ─────────────────────────────────────────────────────────────

	def _conectar(self) -> sqlite3.Connection:
		try:
			conexion = sqlite3.connect(str(self.ruta), timeout=5.0, isolation_level=None, check_same_thread=False)
		except sqlite3.Error as error:
			raise ErrorBase(_("No se ha podido abrir la base de datos: {error}").format(error=error)) from error
		try:
			conexion.row_factory = sqlite3.Row
			conexion.execute("PRAGMA busy_timeout = 5000")
			conexion.execute("PRAGMA foreign_keys = ON")
			conexion.execute("PRAGMA secure_delete = ON")
			modo = conexion.execute("PRAGMA journal_mode = WAL").fetchone()[0]
			if str(modo).lower() != "wal":
				log.warning("SQLite no ha podido activar WAL (modo %s)", modo)
			conexion.execute("PRAGMA synchronous = NORMAL")
			problemas = [str(fila[0]) for fila in conexion.execute("PRAGMA quick_check").fetchall()]
			if problemas != ["ok"]:
				raise ErrorBase(_("La base de datos está dañada. Restaure una copia de seguridad."))
			return conexion
		except sqlite3.Error as error:
			conexion.close()
			raise ErrorBase(_("No se ha podido abrir la base de datos: {error}").format(error=error)) from error
		except BaseException:
			conexion.close()
			raise

	def _exigir_abierta(self) -> None:
		if self._cerrada:
			raise ErrorBase(_("La base de datos ya está cerrada."))

	# ── Migraciones ──────────────────────────────────────────────────────────

	def version(self) -> int:
		"""``PRAGMA user_version`` actual."""
		with self._candado:
			return int(self._conexion.execute("PRAGMA user_version").fetchone()[0])

	def _migrar(self) -> None:
		actual = self.version()
		total = len(self._migraciones)
		if actual > total:
			raise ErrorVersionFutura(
				_(
					"La base de datos es de la versión {actual} y este programa solo conoce hasta la {total}. "
					"Se creó con una versión más nueva de EntornoLab; actualice el programa para abrirla."
				).format(actual=actual, total=total)
			)
		if actual == total:
			return
		if actual > 0:
			self.copia_seguridad(motivo=f"antes-de-migrar-v{actual}")
		for numero in range(actual + 1, total + 1):
			migracion = self._migraciones[numero - 1]
			try:
				with self.transaccion() as tx:
					if migracion.sql:
						for sentencia in dividir_sentencias(migracion.sql):
							tx.execute(sentencia)
					if migracion.funcion is not None:
						migracion.funcion(tx)
					# PRAGMA no admite parámetros; «numero» es un entero propio.
					tx.execute(f"PRAGMA user_version = {int(numero)}")
			except Exception as error:
				raise ErrorMigracion(
					_("Ha fallado la migración {numero} de la base de datos; sigue en la versión {anterior}: {error}").format(
						numero=numero, anterior=numero - 1, error=error
					)
				) from error
			log.info("Base del seguimiento migrada a la versión %d: %s", numero, migracion.descripcion)

	# ── Clave de cifrado ─────────────────────────────────────────────────────

	def _comprobar_clave(self) -> None:
		"""Comprueba al abrir que la clave es la de esta base.

		Sin esto, una contraseña mal escrita no daría error hasta leer la
		primera ficha, o peor: escribiría fichas nuevas con otra clave.
		"""
		fila = self.consultar_uno("SELECT valor FROM meta WHERE clave = 'prueba_cifrado'")
		if fila is None:
			self._guardar_prueba()
			return
		valor = bytes(fila["valor"])
		estaba_cifrada = valor[:1] == _MARCA_CIFRADO
		if estaba_cifrada and not self.cifrador.activo:
			raise ErrorClave(_("La base de datos está cifrada: hace falta la contraseña del profesional."))
		if estaba_cifrada:
			texto = self.cifrador.leer(valor)
			if texto != _TEXTO_PRUEBA.decode("ascii"):
				raise ErrorClave(_("La contraseña no es la de esta base de datos."))
			return
		if self.cifrador.activo:
			# La base se creó sin cifrar y ahora hay clave: se cifra todo lo que había.
			log.info("La base estaba sin cifrar: se cifran los campos sensibles")
			self._recifrar(Cifrador.sin_cifrar(), self.cifrador)

	def _guardar_prueba(self) -> None:
		valor = self.cifrador.guardar(_TEXTO_PRUEBA.decode("ascii"))
		self.ejecutar("INSERT OR REPLACE INTO meta (clave, valor) VALUES ('prueba_cifrado', ?)", (valor,))

	def _recifrar(self, anterior: Cifrador, nuevo: Cifrador) -> None:
		with self.transaccion() as tx:
			for tabla, columna in CAMPOS_CIFRADOS:
				# Los nombres salen de una lista fija del código, no de datos.
				filas = tx.execute(f"SELECT rowid AS fila, {columna} AS valor FROM {tabla} WHERE {columna} IS NOT NULL").fetchall()
				for fila in filas:
					texto = anterior.leer(fila["valor"])
					tx.execute(f"UPDATE {tabla} SET {columna} = ? WHERE rowid = ?", (nuevo.guardar(texto), fila["fila"]))
			self.cifrador = nuevo
			self._guardar_prueba()

	def cambiar_cifrador(self, nuevo: Cifrador | None) -> None:
		"""Vuelve a cifrar todos los campos sensibles con otra clave (cambio de contraseña).

		Todo o nada: si algo falla, la base sigue con la clave anterior.
		"""
		anterior = self.cifrador
		try:
			self._recifrar(anterior, nuevo if nuevo is not None else Cifrador.sin_cifrar())
		except BaseException:
			self.cifrador = anterior
			raise
		log.info("Campos sensibles cifrados de nuevo con otra clave")

	def cifrar_texto(self, texto: str | None) -> bytes | None:
		"""Atajo de ``cifrador.guardar``."""
		return self.cifrador.guardar(texto)

	def descifrar_texto(self, valor: bytes | None) -> str | None:
		"""Atajo de ``cifrador.leer``."""
		return self.cifrador.leer(valor)

	# ── Transacciones y consultas ────────────────────────────────────────────

	@contextmanager
	def transaccion(self) -> Iterator[sqlite3.Connection]:
		"""Bloque atómico: COMMIT al salir bien, ROLLBACK si hay excepción. Anidable."""
		self._exigir_abierta()
		with self._candado:
			conexion = self._conexion
			if self._profundidad:
				nombre = f"punto_{self._profundidad}"
				conexion.execute(f"SAVEPOINT {nombre}")
				self._profundidad += 1
				try:
					yield conexion
				except BaseException:
					conexion.execute(f"ROLLBACK TO {nombre}")
					conexion.execute(f"RELEASE {nombre}")
					raise
				else:
					conexion.execute(f"RELEASE {nombre}")
				finally:
					self._profundidad -= 1
				return
			conexion.execute("BEGIN IMMEDIATE")
			self._profundidad = 1
			try:
				yield conexion
				conexion.execute("COMMIT")
			except BaseException as error:
				if conexion.in_transaction:
					try:
						conexion.execute("ROLLBACK")
					except sqlite3.Error:
						log.exception("Ha fallado el ROLLBACK")
				# Solo el tipo: el mensaje de un error de SQLite puede citar valores.
				log.warning("Transacción deshecha por %s", type(error).__name__)
				raise
			finally:
				self._profundidad = 0

	def ejecutar(self, sql: str, parametros: Parametros = ()) -> int:
		"""INSERT, UPDATE o DELETE con parámetros. Devuelve las filas afectadas."""
		with self.transaccion() as conexion:
			return conexion.execute(sql, parametros).rowcount

	def insertar(self, sql: str, parametros: Parametros = ()) -> int:
		"""INSERT que devuelve el ``rowid`` creado."""
		with self.transaccion() as conexion:
			return int(conexion.execute(sql, parametros).lastrowid or 0)

	def consultar(self, sql: str, parametros: Parametros = ()) -> list[sqlite3.Row]:
		"""SELECT con parámetros; filas con acceso por nombre."""
		self._exigir_abierta()
		with self._candado:
			return self._conexion.execute(sql, parametros).fetchall()

	def consultar_uno(self, sql: str, parametros: Parametros = ()) -> sqlite3.Row | None:
		"""Primera fila o ``None``."""
		self._exigir_abierta()
		with self._candado:
			return self._conexion.execute(sql, parametros).fetchone()

	def valor(self, sql: str, parametros: Parametros = (), por_defecto: Any = None) -> Any:
		"""Primera columna de la primera fila."""
		fila = self.consultar_uno(sql, parametros)
		return por_defecto if fila is None else fila[0]

	# ── Copias y mantenimiento ───────────────────────────────────────────────

	def copias(self) -> list[Path]:
		"""Copias de esta base, de la más antigua a la más reciente."""
		if not self.carpeta_copias.is_dir():
			return []
		return sorted(self.carpeta_copias.glob(f"{self.ruta.stem}-*.db"))

	def copia_seguridad(self, motivo: str = "manual") -> Path:
		"""Copia consistente en caliente con la API ``backup`` de SQLite.

		Copiar el fichero a mano mientras se escribe puede dar una copia
		inservible (en WAL faltarían los cambios del ``-wal``).
		"""
		self._exigir_abierta()
		if self._profundidad:
			raise ErrorBase(_("No se puede copiar la base de datos dentro de una transacción."))
		self.carpeta_copias.mkdir(parents=True, exist_ok=True)
		motivo_limpio = re.sub(r"[^A-Za-z0-9_-]+", "-", motivo).strip("-") or "copia"
		marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
		destino = self.carpeta_copias / f"{self.ruta.stem}-{marca}-{motivo_limpio}.db"
		temporal = destino.with_name(destino.name + ".tmp")
		with self._candado:
			conexion_destino = sqlite3.connect(str(temporal))
			try:
				self._conexion.backup(conexion_destino)
			finally:
				conexion_destino.close()
		os.replace(temporal, destino)
		log.info("Copia de seguridad creada: %s", destino.name)
		for sobrante in self.copias()[: -self._conservadas]:
			try:
				sobrante.unlink()
			except OSError:
				log.warning("No se ha podido borrar la copia antigua %s", sobrante.name, exc_info=True)
		return destino

	def purgar_copias(self) -> int:
		"""Borra todas las copias de seguridad. Devuelve cuántas.

		Lo usa el borrado completo de un alumno: una copia anterior seguiría
		conteniendo sus datos y el borrado no sería real.
		"""
		borradas = 0
		for copia in self.copias():
			try:
				copia.unlink()
				borradas += 1
			except OSError:
				log.exception("No se ha podido borrar la copia %s", copia.name)
		return borradas

	def compactar(self) -> None:
		"""VACUUM y vaciado del WAL: lo borrado deja de estar en el fichero.

		Reescribe toda la base; se llama tras un borrado completo o una
		caducidad, nunca en mitad de una transacción.
		"""
		self._exigir_abierta()
		with self._candado:
			if self._profundidad:
				raise ErrorBase(_("No se puede compactar la base de datos dentro de una transacción."))
			self._conexion.execute("PRAGMA wal_checkpoint(TRUNCATE)")
			self._conexion.execute("VACUUM")
			self._conexion.execute("PRAGMA wal_checkpoint(TRUNCATE)")

	def cerrar(self) -> None:
		"""Cierre ordenado e idempotente."""
		with self._candado:
			if self._cerrada:
				return
			self._cerrada = True
			try:
				self._conexion.execute("PRAGMA optimize")
				self._conexion.execute("PRAGMA wal_checkpoint(TRUNCATE)")
			except sqlite3.Error:
				log.warning("No se ha podido completar el cierre ordenado de la base", exc_info=True)
			finally:
				self._conexion.close()
		log.info("Base del seguimiento cerrada")

	def __enter__(self) -> BaseSeguimiento:
		return self

	def __exit__(self, *_excepcion: object) -> None:
		self.cerrar()


def abrir_base(
	ruta: Path | str | None = None,
	*,
	clave: bytes | None = None,
	cifrar: Callable[..., bytes] | None = None,
	descifrar: Callable[..., bytes] | None = None,
) -> BaseSeguimiento:
	"""Abre la base del seguimiento con la forma de cifrado que se indique.

	- Sin ``cifrar`` ni ``descifrar``: modo sin cifrar (pruebas).
	- Con las dos funciones y sin ``clave``: se usan tal cual, ``f(datos)``.
	- Con las dos funciones y ``clave``: se llaman como ``f(datos, clave)``.
	"""
	if cifrar is None and descifrar is None:
		if clave is not None:
			raise ValueError("se ha dado una clave pero no las funciones de cifrado")
		return BaseSeguimiento(ruta)
	if cifrar is None or descifrar is None:
		raise ValueError("cifrar y descifrar deben darse juntas")
	if clave is None:
		return BaseSeguimiento(ruta, cifrador=Cifrador(cifrar, descifrar))
	return BaseSeguimiento(ruta, cifrador=Cifrador.con_clave(clave, cifrar, descifrar))
