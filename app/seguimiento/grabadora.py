"""Grabación de una sesión en el reproductor e incorporación posterior a la base.

El reproductor no abre la base de datos (puede estar en otro ordenador y no
tiene la contraseña del profesional): escribe cada sesión en un fichero
``data/sessions/<id>.json.gz`` que solo contiene el ALIAS del alumno, nunca
su nombre real. Después, el Estudio llama a ``incorporar_sesiones`` y las
pasa a la base.

Formato del fichero (JSON comprimido con gzip, UTF-8):

```
{
  "manifiesto": {"formato": 1, "aplicacion": "EntornoLab", "version": "...", "id": "<32 hex>",
                 "alias": "...", "entorno": {"id", "nombre"}, "actividad": {"id", "nombre", "tipo"},
                 "modo": "juego|practica|examen", "inicio": ISO, "fin": ISO,
                 "completada": bool, "parcial": bool, "frecuencia_hz": 4},
  "resumen": {...},                      ver medidas.calcular_resumen
  "traza": {"muestras": [[t, planta, x, y, rumbo], ...],
            "eventos": [{"t", "tipo", "datos", "pos": [planta, x, y]}, ...],
            "pausas": [[t, duracion], ...],
            "marcas": [{"t", "planta", "x", "y", "texto"}, ...]}
}
```

``t`` es siempre el segundo de tiempo ACTIVO de la sesión: en pausa el reloj
no corre, así los exámenes no cuentan el tiempo parado.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core import paths
from app.core.i18n import _
from app.core.version import APP_VERSION
from app.seguimiento import medidas, recompensas, sesiones
from app.seguimiento.base import MODOS, BaseSeguimiento, ErrorDatos, normalizar_busqueda

log = logging.getLogger(__name__)

FRECUENCIA_HZ = 4
EXTENSION = ".json.gz"
# Tamaño máximo descomprimido que se acepta al leer un fichero de sesión.
TAMANO_MAXIMO = 64 * 1024 * 1024
ALIAS_INVITADO = "invitado"
# Claves de los ajustes de la ficha con el nivel alcanzado en cada actividad y la sesión que lo dio.
CLAVE_NIVELES = "niveles"
CLAVE_NIVELES_FIN = "niveles_fin"


def carpeta_sesiones() -> Path:
	"""``data/sessions``, creándola si falta."""
	return paths.ruta_sesiones()


def _ahora() -> datetime:
	return datetime.now(UTC)


class Grabadora:
	"""Acumula la traza y los eventos de una sesión y la escribe al terminar.

	La usa el bucle del juego: ninguna de sus llamadas bloquea (el guardado
	automático se hace en un hilo aparte con una copia de los datos).

	:param alias: alias del alumno. NUNCA el nombre real: este fichero viaja
		en claro y puede estar en el ordenador del alumno.
	:param espacios: espacios del entorno (id, nombre, planta, contorno) para
		calcular visitados y no visitados.
	:param camino_optimo_m: longitud del camino más corto, si la actividad tiene uno.
	:param carpeta: dónde se escribe; por defecto ``data/sessions``.
	:param reloj: reloj monótono (inyectable en pruebas) para medir las pausas.
	:param autoguardado_s: cada cuántos segundos de juego se deja un guardado
		parcial, para no perder la sesión si el programa se cierra mal. 0 lo desactiva.
	"""

	def __init__(
		self,
		alias: str,
		entorno_id: str = "",
		entorno_nombre: str = "",
		actividad_id: str = "",
		actividad_nombre: str = "",
		actividad_tipo: str = "",
		modo: str = "juego",
		*,
		espacios: Sequence[Mapping[str, Any]] = (),
		camino_optimo_m: float | None = None,
		carpeta: Path | str | None = None,
		reloj: Callable[[], float] = time.monotonic,
		ahora: Callable[[], datetime] = _ahora,
		autoguardado_s: float = 60.0,
		id_sesion: str | None = None,
	) -> None:
		if modo not in MODOS:
			raise ErrorDatos(_("Modo de sesión desconocido: {modo}").format(modo=modo))
		self.id = id_sesion or uuid.uuid4().hex
		if not sesiones.PATRON_ID.match(self.id):
			raise ErrorDatos(_("El identificador de la sesión no es válido."))
		self.alias = alias.strip() or ALIAS_INVITADO
		self._entorno = {"id": entorno_id, "nombre": entorno_nombre}
		self._actividad = {"id": actividad_id, "nombre": actividad_nombre, "tipo": actividad_tipo}
		self._modo = modo
		self._espacios = [dict(espacio) for espacio in espacios]
		self.camino_optimo_m = camino_optimo_m
		self._carpeta = Path(carpeta) if carpeta is not None else None
		self._reloj = reloj
		self._ahora = ahora
		self._autoguardado_s = autoguardado_s
		self._inicio = ahora()
		self._muestras: list[list[Any]] = []
		self._eventos: list[dict[str, Any]] = []
		self._pausas: list[list[float]] = []
		self._marcas: list[dict[str, Any]] = []
		self._t = 0.0
		self._ultima_muestra_t = -1.0
		self._pos: tuple[str, float, float] | None = None
		self._pausa_desde: float | None = None
		self._tiempo_pausa = 0.0
		self._puntuaciones: dict[str, Any] | None = None
		self._ultimo_guardado_t = 0.0
		self._hilo_guardado: threading.Thread | None = None
		self._terminada = False

	# ── Entrada de datos ─────────────────────────────────────────────────────

	@property
	def ruta(self) -> Path:
		"""Fichero donde se escribe la sesión."""
		carpeta = self._carpeta if self._carpeta is not None else carpeta_sesiones()
		return carpeta / f"{self.id}{EXTENSION}"

	@property
	def en_pausa(self) -> bool:
		"""True mientras la sesión está en pausa."""
		return self._pausa_desde is not None

	@property
	def tiempo_activo(self) -> float:
		"""Último instante de tiempo activo conocido."""
		return self._t

	def muestra(self, t: float, planta: str, x: float, y: float, rumbo: float) -> bool:
		"""Recibe la posición del alumno; guarda como mucho cuatro por segundo.

		Se puede llamar en cada fotograma: la grabadora descarta las que
		sobran. En pausa no se guarda nada. Devuelve True si se guardó.
		"""
		if self._terminada or self.en_pausa:
			return False
		self._t = max(self._t, float(t))
		self._pos = (str(planta), float(x), float(y))
		if self._muestras and t - self._ultima_muestra_t < (1.0 / FRECUENCIA_HZ) - 1e-6:
			return False
		self._ultima_muestra_t = float(t)
		self._muestras.append([round(float(t), 3), str(planta), round(float(x), 3), round(float(y), 3), round(float(rumbo), 1)])
		if self._autoguardado_s > 0 and self._t - self._ultimo_guardado_t >= self._autoguardado_s:
			self._ultimo_guardado_t = self._t
			self._guardar_en_segundo_plano()
		return True

	def evento(self, tipo: str, datos: Mapping[str, Any] | None = None, t: float | None = None) -> None:
		"""Apunta un ``EvRegistro`` del motor (choque, ayuda, objetivo, premio, entrada_espacio...)."""
		if self._terminada:
			return
		instante = self._t if t is None else float(t)
		self._t = max(self._t, instante)
		ficha: dict[str, Any] = {"t": round(instante, 3), "tipo": str(tipo), "datos": dict(datos or {})}
		if self._pos is not None:
			ficha["pos"] = [self._pos[0], round(self._pos[1], 3), round(self._pos[2], 3)]
		self._eventos.append(ficha)

	def registrar(self, ev: Any) -> None:
		"""Apunta un objeto ``EvRegistro`` (cualquier cosa con ``tipo`` y ``datos``)."""
		self.evento(ev.tipo, getattr(ev, "datos", None))

	def pausar(self, si: bool) -> None:
		"""Empieza o termina una pausa. El tiempo en pausa se mide aparte y no cuenta como activo."""
		if self._terminada:
			return
		if si and self._pausa_desde is None:
			self._pausa_desde = self._reloj()
			self._pausas.append([round(self._t, 3), 0.0])
		elif not si and self._pausa_desde is not None:
			duracion = max(0.0, self._reloj() - self._pausa_desde)
			self._pausa_desde = None
			self._tiempo_pausa += duracion
			self._pausas[-1][1] = round(duracion, 3)

	def marca(self, texto: str = "", t: float | None = None) -> None:
		"""Marca del profesional: señala un momento, con una nota opcional."""
		if self._terminada:
			return
		instante = self._t if t is None else float(t)
		ficha: dict[str, Any] = {"t": round(instante, 3), "planta": "", "x": None, "y": None, "texto": texto.strip()[:2000]}
		if self._pos is not None:
			ficha["planta"] = self._pos[0]
			ficha["x"] = round(self._pos[1], 3)
			ficha["y"] = round(self._pos[2], 3)
		self._marcas.append(ficha)

	def intervencion(self, tipo: str, datos: Mapping[str, Any] | None = None) -> None:
		"""Apunta una intervención del profesional (pausa, recolocar, mensaje, pista...).

		No se guarda el texto de los mensajes: basta saber que hubo una
		intervención y de qué clase, y el texto podría contener datos personales.
		"""
		limpios = {clave: valor for clave, valor in dict(datos or {}).items() if clave != "texto"}
		limpios["tipo"] = str(tipo)
		self.evento("intervencion", limpios)

	def puntuaciones(self, valores: Mapping[str, Any]) -> None:
		"""Puntuaciones de examen calculadas por el motor; se guardan sin interpretar."""
		self._puntuaciones = dict(valores)

	# ── Escritura ────────────────────────────────────────────────────────────

	def _documento(self, completada: bool, parcial: bool, resultado: Mapping[str, Any] | None) -> dict[str, Any]:
		muestras = list(self._muestras)
		eventos = list(self._eventos)
		pausas = [list(pausa) for pausa in self._pausas]
		en_pausa = self._tiempo_pausa
		if self._pausa_desde is not None:
			en_pausa += max(0.0, self._reloj() - self._pausa_desde)
		resumen = medidas.calcular_resumen(
			muestras,
			eventos,
			espacios=self._espacios,
			camino_optimo_m=self.camino_optimo_m,
			pausas=pausas,
			tiempo_activo_s=self._t,
			tiempo_pausa_s=en_pausa,
			puntuaciones=self._puntuaciones,
			resultado=resultado,
		)
		return {
			"manifiesto": {
				"formato": sesiones.FORMATO_SESION,
				"aplicacion": "EntornoLab",
				"version": APP_VERSION,
				"id": self.id,
				"alias": self.alias,
				"entorno": dict(self._entorno),
				"actividad": dict(self._actividad),
				"modo": self._modo,
				"inicio": self._inicio.isoformat(timespec="seconds"),
				"fin": self._ahora().isoformat(timespec="seconds"),
				"completada": completada,
				"parcial": parcial,
				"frecuencia_hz": FRECUENCIA_HZ,
			},
			"resumen": resumen,
			"traza": {"muestras": muestras, "eventos": eventos, "pausas": pausas, "marcas": [dict(m) for m in self._marcas]},
		}

	def _guardar_en_segundo_plano(self) -> None:
		if self._hilo_guardado is not None and self._hilo_guardado.is_alive():
			return
		documento = self._documento(False, True, None)
		ruta = self.ruta

		def trabajo() -> None:
			try:
				escribir_sesion(ruta, documento)
			except OSError:
				log.exception("No se ha podido hacer el guardado parcial de la sesión")

		self._hilo_guardado = threading.Thread(target=trabajo, name="guardado-sesion", daemon=True)
		self._hilo_guardado.start()

	def terminar(self, completada: bool = False, resultado: Mapping[str, Any] | None = None) -> Path:
		"""Cierra la sesión y escribe el fichero definitivo. Devuelve su ruta.

		:param completada: si el alumno llegó al final de la actividad.
		:param resultado: el diccionario de ``EvFin`` del motor.
		"""
		if self._terminada:
			return self.ruta
		self.pausar(False)
		if self._hilo_guardado is not None:
			# El guardado parcial y el definitivo escriben el mismo fichero: se espera al primero.
			self._hilo_guardado.join(timeout=10.0)
		documento = self._documento(completada, False, resultado)
		self._terminada = True
		escribir_sesion(self.ruta, documento)
		log.info("Sesión grabada: %d muestras, %d eventos", len(self._muestras), len(self._eventos))
		return self.ruta


# ── Ficheros de sesión ───────────────────────────────────────────────────────


def escribir_sesion(ruta: Path, documento: Mapping[str, Any]) -> None:
	"""Escribe un fichero de sesión de forma atómica (temporal + renombrar)."""
	ruta.parent.mkdir(parents=True, exist_ok=True)
	temporal = ruta.with_name(f"{ruta.name}.{threading.get_ident()}.tmp")
	datos = json.dumps(documento, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
	try:
		with gzip.open(temporal, "wb", compresslevel=6) as salida:
			salida.write(datos)
		os.replace(temporal, ruta)
	finally:
		if temporal.exists():
			temporal.unlink()


def leer_sesion(ruta: Path) -> dict[str, Any]:
	"""Lee un fichero de sesión. Lanza ``ErrorDatos`` si no es legible o es desmesurado."""
	try:
		with gzip.open(ruta, "rb") as entrada:
			datos = entrada.read(TAMANO_MAXIMO + 1)
	except (OSError, EOFError) as error:
		raise ErrorDatos(_("No se ha podido leer el fichero de sesión.")) from error
	if len(datos) > TAMANO_MAXIMO:
		raise ErrorDatos(_("El fichero de sesión es demasiado grande."))
	try:
		documento = json.loads(datos.decode("utf-8"))
	except ValueError as error:
		raise ErrorDatos(_("El fichero de sesión está dañado.")) from error
	if not isinstance(documento, dict):
		raise ErrorDatos(_("El fichero de sesión no tiene el formato esperado."))
	return documento


@dataclass
class ResultadoIncorporacion:
	"""Qué pasó al incorporar una carpeta de sesiones (para contárselo al profesional)."""

	nuevas: int = 0
	actualizadas: int = 0
	repetidas: int = 0
	sin_alumno: int = 0
	alumnos_creados: int = 0
	# (nombre del fichero, motivo legible). El nombre es el id de la sesión: no es un dato personal.
	erroneas: list[tuple[str, str]] = field(default_factory=list)


def incorporar_sesiones(
	carpeta: Path | str | None,
	base: BaseSeguimiento,
	*,
	crear_alumnos: bool = True,
	borrar_incorporadas: bool = False,
) -> ResultadoIncorporacion:
	"""Pasa a la base las sesiones de una carpeta. Idempotente.

	Llamarla dos veces no duplica nada: cada sesión tiene un id único y la
	que ya está en la base se salta. Un fichero dañado se apunta en
	``erroneas`` y se sigue con los demás.

	:param carpeta: por defecto ``data/sessions``.
	:param crear_alumnos: si el alias de una sesión no tiene ficha, se crea
		una mínima (solo el alias). Con False, esas sesiones se cuentan en
		``sin_alumno`` y se dejan en la carpeta.
	:param borrar_incorporadas: borra cada fichero una vez guardado en la base
		(recomendable: el fichero está sin cifrar).
	"""
	# Importación diferida: alumnos.py usa este módulo para borrar los ficheros de un alumno.
	from app.seguimiento.alumnos import Fichas

	origen = Path(carpeta) if carpeta is not None else carpeta_sesiones()
	resultado = ResultadoIncorporacion()
	if not origen.is_dir():
		return resultado
	fichas = Fichas(base)
	for ruta in sorted(origen.glob(f"*{EXTENSION}")):
		try:
			documento = leer_sesion(ruta)
			partes = sesiones.validar_documento(documento)
			alumno = fichas.por_alias(partes["alias"])
			if alumno is None and not crear_alumnos:
				resultado.sin_alumno += 1
				continue
			if alumno is None:
				alumno = fichas.alta(partes["alias"])
				resultado.alumnos_creados += 1
			estado = sesiones.guardar_sesion(base, alumno.id, documento)
			if estado != "repetida":
				recompensas.registrar_de_sesion(base, alumno.id, partes["id"], partes["resumen"], fecha=partes["fin"])
				if not partes["parcial"]:
					anotar_nivel_de_sesion(fichas, alumno, partes)
		except ErrorDatos as error:
			resultado.erroneas.append((ruta.name, str(error)))
			log.warning("Fichero de sesión no incorporado: %s", ruta.name)
			continue
		if estado == "nueva":
			resultado.nuevas += 1
		elif estado == "actualizada":
			resultado.actualizadas += 1
		else:
			resultado.repetidas += 1
		if borrar_incorporadas and not partes["parcial"]:
			try:
				ruta.unlink()
			except OSError:
				log.warning("No se ha podido borrar el fichero de sesión ya incorporado %s", ruta.name, exc_info=True)
	log.info(
		"Sesiones incorporadas: %d nuevas, %d actualizadas, %d repetidas, %d erróneas",
		resultado.nuevas,
		resultado.actualizadas,
		resultado.repetidas,
		len(resultado.erroneas),
	)
	return resultado


def anotar_nivel_de_sesion(fichas: Any, alumno: Any, partes: Mapping[str, Any]) -> Any:
	"""Lleva a la ficha el nivel de ayudas con el que el alumno empezará la próxima vez esa actividad.

	Es el ``nivel_siguiente`` del resultado de la sesión. Se guarda en los
	ajustes de la ficha (``niveles``: «entorno/actividad» → nivel) con la hora
	de fin de la sesión que lo dio (``niveles_fin``): si se incorpora antes una
	sesión más nueva que otra, la vieja no hace retroceder el nivel. Desde la
	ficha vuelve al reproductor por la sala (orden ``alumno``). Devuelve la
	ficha, cambiada o no.
	"""
	resultado = partes.get("resumen", {}).get("resultado")
	siguiente = resultado.get("nivel_siguiente") if isinstance(resultado, Mapping) else None
	if isinstance(siguiente, bool) or not isinstance(siguiente, int) or siguiente < 0 or not partes.get("actividad_id"):
		return alumno
	clave = f"{partes.get('entorno_id', '')}/{partes['actividad_id']}"
	fin = str(partes.get("fin") or "")
	ajustes = dict(alumno.ajustes)
	niveles = dict(ajustes.get(CLAVE_NIVELES) or {})
	fechas = dict(ajustes.get(CLAVE_NIVELES_FIN) or {})
	if str(fechas.get(clave) or "") > fin or (niveles.get(clave) == siguiente and fechas.get(clave) == fin):
		return alumno
	niveles[clave] = siguiente
	fechas[clave] = fin
	ajustes[CLAVE_NIVELES] = niveles
	ajustes[CLAVE_NIVELES_FIN] = fechas
	log.info("Nivel de una actividad anotado en la ficha al incorporar la sesión")
	return fichas.editar(alumno.id, ajustes=ajustes)


def borrar_ficheros_de_alias(carpeta: Path | str | None, alias: str) -> int:
	"""Borra los ficheros de sesión de un alias. Devuelve cuántos.

	Forma parte del borrado completo de un alumno: sus sesiones sin
	incorporar también son datos suyos.
	"""
	origen = Path(carpeta) if carpeta is not None else carpeta_sesiones()
	if not origen.is_dir():
		return 0
	buscado = normalizar_busqueda(alias)
	borrados = 0
	for ruta in origen.glob(f"*{EXTENSION}"):
		try:
			manifiesto = leer_sesion(ruta).get("manifiesto")
		except ErrorDatos:
			log.warning("Fichero de sesión ilegible al borrar un alumno: %s", ruta.name)
			continue
		if isinstance(manifiesto, dict) and normalizar_busqueda(str(manifiesto.get("alias", ""))) == buscado:
			try:
				ruta.unlink()
				borrados += 1
			except OSError:
				log.exception("No se ha podido borrar el fichero de sesión %s", ruta.name)
	return borrados


def caducar_ficheros(carpeta: Path | str | None, dias: int, ahora: float | None = None) -> int:
	"""Borra los ficheros de sesión con más de ``dias`` días. Devuelve cuántos."""
	if dias < 1:
		raise ErrorDatos(_("La caducidad debe ser de un día o más."))
	origen = Path(carpeta) if carpeta is not None else carpeta_sesiones()
	if not origen.is_dir():
		return 0
	limite = (time.time() if ahora is None else ahora) - dias * 86400.0
	borrados = 0
	for ruta in origen.glob(f"*{EXTENSION}"):
		try:
			if ruta.stat().st_mtime < limite:
				ruta.unlink()
				borrados += 1
		except OSError:
			log.exception("No se ha podido borrar el fichero de sesión caducado %s", ruta.name)
	return borrados
