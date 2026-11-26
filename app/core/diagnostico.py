"""Paquete de diagnóstico para soporte.

Genera un ZIP en ``data/diagnostico`` con lo necesario para investigar un
problema que ha tenido otra persona, SIN datos privados:

- Las últimas sesiones de registro (ya redactadas al escribirse; se vuelven a
  redactar por si contienen algo anterior a la redacción).
- ``incidencias.log``, ``fallo_nativo.log`` y ``arranque_fallido.log``.
- ``sistema.txt``: versión de la aplicación, Python, wxPython, Windows,
  arquitectura, si está compilada, lectores de pantalla en ejecución y la
  lista de paquetes (sin rutas personales).

Todo pasa por :func:`anonimizar`: la carpeta del programa queda como
``<carpeta del programa>``, la del usuario como ``%USERPROFILE%`` y el nombre
de la cuenta de Windows como ``<usuario>``.

Nunca incluye configuración, bases de datos, fichas de alumnos, sesiones de
juego, entornos ni claves. Incluye los registros del Estudio (``sesion_*``)
y los del reproductor (``jugar_*``).

Procede de la plantilla del agente «logging-profesional».
"""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
import zipfile
from datetime import datetime
from importlib import metadata
from pathlib import Path

from app.core import registro

log = logging.getLogger(__name__)


def anonimizar(texto: str) -> str:
	"""Redacta secretos y sustituye las carpetas del equipo por marcadores.

	El paquete está pensado para enviarlo: la carpeta del programa pasa a
	``<carpeta del programa>``, la del usuario a ``%USERPROFILE%`` y el nombre
	de cualquier cuenta de Windows a ``<usuario>`` (ver
	``registro.anonimizar_rutas``). Las trazas ya llegan con rutas relativas.
	"""
	return registro.anonimizar_rutas(registro.acortar_rutas_de_traza(registro.redactar(texto)))


_LECTORES = {"nvda.exe": "NVDA", "jfw.exe": "JAWS", "narrator.exe": "Narrador", "zt.exe": "ZoomText"}


def _lectores_en_ejecucion() -> list[str]:
	"""Detecta los lectores de pantalla abiertos (solo informativo)."""
	try:
		salida = subprocess.run(
			["tasklist", "/fo", "csv", "/nh"],
			capture_output=True,
			text=True,
			timeout=10,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
			check=False,
		).stdout.lower()
	except OSError, subprocess.SubprocessError:
		return []
	return [nombre for proceso, nombre in _LECTORES.items() if f'"{proceso}"' in salida]


def informe_sistema(nombre_app: str = "", version: str = "") -> str:
	"""Texto con la información del entorno, sin rutas ni datos personales."""
	lineas = [
		f"Aplicación: {nombre_app} {version}".strip(),
		f"Fecha: {datetime.now().isoformat(timespec='seconds')}",
		f"Compilada: {'sí' if getattr(sys, 'frozen', False) else 'no'}",
		f"Python: {platform.python_version()} ({platform.architecture()[0]})",
		f"Sistema: {platform.platform()}",
	]
	try:
		import wx

		lineas.append(f"wxPython: {wx.version()}")
	except Exception:  # noqa: BLE001 - informativo
		lineas.append("wxPython: no disponible")
	lectores = _lectores_en_ejecucion()
	lineas.append(f"Lectores de pantalla en ejecución: {', '.join(lectores) or 'ninguno detectado'}")
	lineas.append("")
	lineas.append("Paquetes instalados:")
	try:
		paquetes = sorted(f"{d.metadata['Name']}=={d.version}" for d in metadata.distributions())
		lineas.extend(f"  {p}" for p in paquetes)
	except Exception:  # noqa: BLE001 - en la versión compilada puede no haber metadatos
		lineas.append("  (no disponible)")
	return anonimizar("\n".join(lineas))


def generar_paquete(nombre_app: str = "", version: str = "", sesiones: int = 3) -> Path:
	"""Crea el ZIP de diagnóstico y devuelve su ruta."""
	# Lo que aún esté en la cola de escritura también debe entrar en el paquete.
	registro.vaciar()
	carpeta_logs = registro.carpeta_registros()
	destino_dir = carpeta_logs.parent / "diagnostico"
	destino_dir.mkdir(parents=True, exist_ok=True)
	destino = destino_dir / f"diagnostico_{datetime.now():%Y%m%d_%H%M%S}.zip"

	sesiones_log: list[Path] = []
	for prefijo in (registro.PREFIJO_PRINCIPAL, registro.PREFIJO_REPRODUCTOR):
		# Solo el .log legible (y sus rotaciones); el .jsonl repite lo mismo.
		legibles = [ruta for ruta in sorted(carpeta_logs.glob(f"{prefijo}_*.log*")) if ".errores_registro" not in ruta.name]
		sesiones_log.extend(legibles[-sesiones:])
	nombres_fijos = ("incidencias.log", "fallo_nativo.log", f"fallo_nativo_{registro.PREFIJO_REPRODUCTOR}.log", "arranque_fallido.log")
	fijos = [carpeta_logs / nombre for nombre in nombres_fijos]
	with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zip_:
		for archivo in [*sesiones_log, *fijos]:
			if not archivo.is_file():
				continue
			texto = archivo.read_text(encoding="utf-8", errors="replace")
			zip_.writestr(f"logs/{archivo.name}", anonimizar(texto))
		zip_.writestr("sistema.txt", informe_sistema(nombre_app, version))
	log.info("Paquete de diagnóstico generado: %s", destino.name)
	return destino
