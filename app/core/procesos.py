"""Procesos auxiliares sin huérfanos: el Estudio lanza el reproductor como proceso hijo.

El reproductor (pygame) y el Estudio (wxPython) no pueden compartir proceso:
cada uno tiene su bucle de eventos y su ventana. El Estudio lo lanza aparte
y este módulo garantiza dos cosas:

- **Se lanza igual desde código y compilado.** Desde código es
  ``python main.py --jugar ...``; en la versión compilada no hay
  ``python.exe`` y se usa el segundo ejecutable, ``EntornoLabJugar.exe``.
  ``lanzar_reproductor`` elige el que toca.
- **No quedan huérfanos.** Cada hijo entra en un *Job Object* de Windows con
  ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``: cuando el Estudio termina (aunque
  sea de golpe, o lo cierren desde el Administrador de tareas), Windows
  cierra el Job y mata al reproductor. Sin esto, un Estudio caído dejaría un
  reproductor sonando sin ventana desde la que pararlo.

Además, al salir con normalidad se terminan los hijos que sigan vivos
(``terminar_todos`` se registra con ``atexit``): es la red de seguridad para
el caso, raro, de que el Job no se haya podido crear.

Uso::

	from app.core import procesos

	proceso = procesos.lanzar_reproductor(["mi_casa.elab", "--alumno", "ana"])
	if proceso.vivo():
		...
	proceso.terminar()          # o proceso.esperar(5.0)

Nada de esto debe llamarse esperando en el hilo de la interfaz:
``esperar()`` sin límite bloquea. Use ``vivo()`` desde un temporizador o
``esperar`` dentro de una tarea de fondo.

Solo biblioteca estándar; no importa wx ni pygame.
"""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from app.core import paths
from app.core.version import EJECUTABLE_REPRODUCTOR

log = logging.getLogger(__name__)

# Argumento con el que main.py delega en el reproductor.
ARGUMENTO_JUGAR = "--jugar"

# Constantes de la API de Windows (winnt.h, jobapi2.h).
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JobObjectExtendedLimitInformation = 9
_CREATE_NO_WINDOW = 0x08000000

_candado = threading.Lock()
# El descriptor del Job debe vivir todo el proceso: al cerrarse (o morir el
# proceso) Windows mata a los hijos. None = aún no creado; 0 = no se pudo crear.
_job: int | None = None
_kernel32: Any = None
_vivos: list[Proceso] = []
_atexit_registrado = False


class ErrorProceso(Exception):
	"""No se pudo lanzar un proceso auxiliar (ejecutable ausente, permiso denegado...)."""


# ── Job Object ───────────────────────────────────────────────────────────────


def _preparar_kernel32() -> Any:
	"""Carga kernel32 con las firmas explícitas (en 64 bits, sin ellas se truncan los descriptores)."""
	global _kernel32
	if _kernel32 is not None:
		return _kernel32
	import ctypes
	from ctypes import wintypes

	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
	kernel32.CreateJobObjectW.restype = wintypes.HANDLE
	kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
	kernel32.SetInformationJobObject.restype = wintypes.BOOL
	kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
	kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
	kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
	kernel32.CloseHandle.restype = wintypes.BOOL
	_kernel32 = kernel32
	return kernel32


def _crear_job() -> int:
	"""Crea el Job con «matar al cerrar». Devuelve el descriptor, o 0 si no se pudo."""
	import ctypes
	from ctypes import wintypes

	class IoCounters(ctypes.Structure):
		_fields_ = [
			("ReadOperationCount", ctypes.c_ulonglong),
			("WriteOperationCount", ctypes.c_ulonglong),
			("OtherOperationCount", ctypes.c_ulonglong),
			("ReadTransferCount", ctypes.c_ulonglong),
			("WriteTransferCount", ctypes.c_ulonglong),
			("OtherTransferCount", ctypes.c_ulonglong),
		]

	class LimitesBasicos(ctypes.Structure):
		_fields_ = [
			("PerProcessUserTimeLimit", ctypes.c_longlong),
			("PerJobUserTimeLimit", ctypes.c_longlong),
			("LimitFlags", wintypes.DWORD),
			("MinimumWorkingSetSize", ctypes.c_size_t),
			("MaximumWorkingSetSize", ctypes.c_size_t),
			("ActiveProcessLimit", wintypes.DWORD),
			("Affinity", ctypes.c_size_t),
			("PriorityClass", wintypes.DWORD),
			("SchedulingClass", wintypes.DWORD),
		]

	class LimitesExtendidos(ctypes.Structure):
		_fields_ = [
			("BasicLimitInformation", LimitesBasicos),
			("IoInfo", IoCounters),
			("ProcessMemoryLimit", ctypes.c_size_t),
			("JobMemoryLimit", ctypes.c_size_t),
			("PeakProcessMemoryUsed", ctypes.c_size_t),
			("PeakJobMemoryUsed", ctypes.c_size_t),
		]

	kernel32 = _preparar_kernel32()
	descriptor = kernel32.CreateJobObjectW(None, None)
	if not descriptor:
		log.warning("No se pudo crear el Job Object (error %d); los procesos hijos no quedarán atados.", ctypes.get_last_error())
		return 0
	limites = LimitesExtendidos()
	limites.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
	correcto = kernel32.SetInformationJobObject(
		descriptor, _JobObjectExtendedLimitInformation, ctypes.byref(limites), ctypes.sizeof(limites)
	)
	if not correcto:
		log.warning("No se pudo configurar el Job Object (error %d); los procesos hijos no quedarán atados.", ctypes.get_last_error())
		kernel32.CloseHandle(descriptor)
		return 0
	return int(descriptor)


def _obtener_job() -> int:
	"""Descriptor del Job compartido por todos los hijos (se crea la primera vez). 0 si no hay."""
	global _job
	if sys.platform != "win32":
		return 0
	with _candado:
		if _job is None:
			try:
				_job = _crear_job()
			except OSError, AttributeError:
				log.warning("No se pudo preparar el Job Object; los procesos hijos no quedarán atados.", exc_info=True)
				_job = 0
		return _job


def _atar_al_job(proceso: subprocess.Popen) -> bool:
	"""Mete el proceso en el Job. ``False`` si no se pudo (el hijo sigue funcionando, sin esa garantía)."""
	job = _obtener_job()
	if not job:
		return False
	import ctypes

	descriptor = getattr(proceso, "_handle", None)
	if descriptor is None:
		return False
	if not _preparar_kernel32().AssignProcessToJobObject(job, int(descriptor)):
		log.warning("No se pudo atar el proceso %d al Job Object (error %d).", proceso.pid, ctypes.get_last_error())
		return False
	return True


# ── Proceso ──────────────────────────────────────────────────────────────────


class Proceso:
	"""Un proceso hijo en marcha (o ya terminado)."""

	def __init__(self, popen: subprocess.Popen, orden: list[str], atado: bool) -> None:
		self._popen = popen
		#: Orden completa con la que se lanzó (para el registro y las pruebas).
		self.orden = list(orden)
		#: True si Windows lo matará cuando muera este proceso (está en el Job Object).
		self.atado = atado
		#: True en cuanto se llama a ``terminar``: quien vigila el proceso sabe así que su fin no es inesperado.
		self.terminado_por_el_estudio = False

	@property
	def pid(self) -> int:
		"""Identificador del proceso en Windows."""
		return self._popen.pid

	@property
	def codigo(self) -> int | None:
		"""Código de salida, o ``None`` si sigue en marcha."""
		return self._popen.poll()

	def vivo(self) -> bool:
		"""True mientras el proceso no haya terminado. No bloquea."""
		return self._popen.poll() is None

	def esperar(self, tiempo: float | None = None) -> int | None:
		"""Espera a que termine y devuelve su código de salida.

		:param tiempo: segundos máximos; ``None`` espera sin límite (nunca
			desde el hilo de la interfaz).
		:return: el código de salida, o ``None`` si pasó el tiempo y sigue vivo.
		"""
		try:
			codigo = self._popen.wait(timeout=tiempo)
		except subprocess.TimeoutExpired:
			return None
		_olvidar(self)
		return codigo

	def terminar(self, espera: float = 3.0) -> int | None:
		"""Termina el proceso y devuelve su código de salida (``None`` si no se dejó matar).

		En Windows no hay señal de cierre amable para un proceso sin consola:
		``terminate`` lo corta en seco. Quien quiera un cierre ordenado (guardar
		la sesión del alumno) debe pedírselo antes por su propio canal (el
		mensaje ``terminar`` de la supervisión) y llamar aquí solo si no
		responde.
		"""
		if self._popen.poll() is None:
			self.terminado_por_el_estudio = True
			try:
				self._popen.terminate()
			except OSError:
				# Carrera habitual: terminó por su cuenta entre el poll y el terminate.
				log.debug("El proceso %d ya no admitía terminate.", self.pid, exc_info=True)
			try:
				self._popen.wait(timeout=espera)
			except subprocess.TimeoutExpired:
				log.warning("El proceso %d no terminó en %.1f s; se fuerza.", self.pid, espera)
				try:
					self._popen.kill()
					self._popen.wait(timeout=espera)
				except OSError, subprocess.TimeoutExpired:
					log.exception("No se pudo terminar el proceso %d.", self.pid)
		codigo = self._popen.poll()
		if codigo is not None:
			_olvidar(self)
		return codigo

	def __repr__(self) -> str:
		estado = "vivo" if self.vivo() else f"terminado con {self.codigo}"
		return f"<Proceso {self.pid} {estado}>"


def _olvidar(proceso: Proceso) -> None:
	with _candado:
		if proceso in _vivos:
			_vivos.remove(proceso)


def procesos_vivos() -> list[Proceso]:
	"""Procesos lanzados desde aquí que siguen en marcha."""
	with _candado:
		candidatos = list(_vivos)
	return [proceso for proceso in candidatos if proceso.vivo()]


def terminar_todos(espera: float = 2.0) -> None:
	"""Termina los hijos que sigan vivos. Se llama sola al salir (``atexit``)."""
	for proceso in procesos_vivos():
		log.info("Terminando el proceso hijo %d al salir.", proceso.pid)
		proceso.terminar(espera)


# ── Lanzamiento ──────────────────────────────────────────────────────────────


def lanzar(
	orden: list[str],
	*,
	carpeta: Path | None = None,
	entorno: dict[str, str] | None = None,
	heredar_salida: bool = False,
) -> Proceso:
	"""Lanza ``orden`` como proceso hijo atado al Job Object. No espera a que termine.

	:param orden: ejecutable y argumentos, como lista (nunca una cadena para el
		intérprete de órdenes: un nombre de archivo con espacios o comillas no
		debe poder alterar la orden).
	:param carpeta: carpeta de trabajo; por defecto, la del programa.
	:param entorno: variables de entorno; por defecto, las de este proceso
		(así el hijo ve el mismo ``APP_DATA_DIR``).
	:param heredar_salida: ``True`` deja que el hijo escriba en la consola de
		este proceso (depuración). Por defecto su salida se descarta: sus
		errores van a su propio registro.
	:raises ErrorProceso: si no se pudo arrancar.
	"""
	global _atexit_registrado
	if not orden:
		raise ErrorProceso("La orden está vacía.")
	opciones: dict[str, Any] = {
		"cwd": str(carpeta or paths.ruta_base()),
		"env": dict(os.environ if entorno is None else entorno),
		"stdin": subprocess.DEVNULL,
		"close_fds": True,
	}
	if not heredar_salida:
		opciones["stdout"] = subprocess.DEVNULL
		opciones["stderr"] = subprocess.DEVNULL
	if sys.platform == "win32" and not heredar_salida:
		# Sin esto, lanzar python.exe desde un Estudio sin consola abriría una
		# ventana negra que roba el foco al lector de pantalla.
		opciones["creationflags"] = _CREATE_NO_WINDOW
	try:
		popen = subprocess.Popen(orden, **opciones)  # noqa: S603 - orden en lista, construida por la aplicación
	except OSError as error:
		raise ErrorProceso(f"No se pudo lanzar «{Path(orden[0]).name}»: {error}") from error
	atado = _atar_al_job(popen)
	proceso = Proceso(popen, orden, atado)
	with _candado:
		_vivos[:] = [otro for otro in _vivos if otro.vivo()]
		_vivos.append(proceso)
		if not _atexit_registrado:
			atexit.register(terminar_todos)
			_atexit_registrado = True
	log.info("Proceso hijo lanzado: pid %d, %s%s", popen.pid, Path(orden[0]).name, "" if atado else " (sin Job Object)")
	return proceso


def orden_reproductor(argumentos: list[str]) -> list[str]:
	"""Orden completa para arrancar el reproductor con ``argumentos``.

	- Compilada: ``<carpeta del programa>/EntornoLabJugar.exe argumentos``.
	- Desde código: ``python <raíz>/main.py --jugar argumentos`` con el mismo
	  intérprete que ejecuta el Estudio (el del entorno virtual).
	"""
	if paths.CONGELADA:
		return [str(paths.ruta_base() / EJECUTABLE_REPRODUCTOR), *argumentos]
	return [sys.executable, str(paths.ruta_base() / "main.py"), ARGUMENTO_JUGAR, *argumentos]


def lanzar_reproductor(argumentos: list[str]) -> Proceso:
	"""Arranca el reproductor (Jugar o modo recorrido) como proceso hijo del Estudio.

	:param argumentos: los del reproductor, sin ``--jugar``: paquete,
		``--actividad``, ``--alumno``, ``--sala``, ``--codigo``, ``--inicio``...
		Para el modo recorrido, ``["--recorrido", paquete, "--sala", ..., "--codigo", ...]``.
	:raises ErrorProceso: si falta el ejecutable o no se pudo arrancar.
	"""
	orden = orden_reproductor([str(argumento) for argumento in argumentos])
	if paths.CONGELADA and not Path(orden[0]).is_file():
		raise ErrorProceso(f"No se encuentra {EJECUTABLE_REPRODUCTOR} junto al programa.")
	heredar = os.environ.get("APP_DEPURACION", "").strip() not in ("", "0")
	return lanzar(orden, heredar_salida=heredar)
