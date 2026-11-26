"""Prueba de punta a punta del actualizador con la compilación REAL de EntornoLab.

Uso (desde la raíz del proyecto, con la compilación hecha)::

	.venv\\Scripts\\python.exe tools\\probar_actualizacion_real.py
	.venv\\Scripts\\python.exe tools\\probar_actualizacion_real.py --compilar   (compila antes las dos versiones)
	.venv\\Scripts\\python.exe tools\\probar_actualizacion_real.py --conservar  (no borra la carpeta de la prueba)

Qué hace, todo en una carpeta temporal propia que se borra al terminar:

1. Toma ``build/EntornoLab_v<actual>.zip`` (``entorno.bat compilar``) y fabrica la
   versión siguiente: copia el proyecto a la carpeta temporal, sube la versión
   SOLO en la copia, la compila con ``setup_cx.py`` y la empaqueta con
   ``tools/empaquetar.py``, que firma ``version.json`` con la clave de desarrollo
   (fuera del proyecto; esta herramienta nunca la lee, la copia ni la imprime).
2. Instala la versión actual en «Mis cosas\\EntornoLab (copia)», con datos del
   usuario (entornos, sesiones, copias, un complemento suyo, su registro).
3. Sirve la versión nueva desde un servidor HTTP local (``tests/servidor_http_prueba.py``).
4. Escenario A: abre el Estudio y un reproductor de verdad, carga una DLL de
   ``lib`` desde otro proceso y bloquea otro fichero de ``lib`` unos segundos
   (como un antivirus); prepara la actualización y lanza el script; cierra el
   Estudio y, un poco después, el reproductor. Debe acabar en la versión nueva,
   con el programa idéntico al compilado y los datos del usuario intactos.
5. Escenario B: instalación limpia y fallo forzado a mitad: debe volver a la
   versión actual, idéntica byte a byte, y arrancar.
6. Escenario C: instalación limpia, corte de luz simulado (se mata el script a
   mitad) y se abre el Estudio real: debe lanzar ``recuperar.bat`` él solo y
   volver a la versión actual.

La comprobación y la descarga las hace el código del proyecto (el mismo que va
compilado) porque la versión instalada solo consulta GitHub; la sustitución, el
arranque, el marcador de salud y la recuperación son los de los ejecutables reales.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
# Lo que no hace falta copiar para compilar la versión siguiente.
NO_COPIAR = {".venv", "venv", "build", "dist", "adjuntos", "htmlcov", ".pytest_cache", ".ruff_cache", "__pycache__", ".git"}
DLL_A_CARGAR = Path("lib/accessible_output2/lib/nvdaControllerClient64.dll")
FICHERO_A_BLOQUEAR = Path("lib/accessible_output2/lib/dolapi.dll")


def paso(texto: str) -> None:
	"""Escribe un paso de la prueba (se oye bien con lector de pantalla: una línea por paso)."""
	print(f"[{time.strftime('%H:%M:%S')}] {texto}", flush=True)


def leer_version(raiz: Path) -> str:
	"""APP_VERSION de ``app/core/version.py`` sin importar la aplicación."""
	texto = (raiz / "app" / "core" / "version.py").read_text(encoding="utf-8")
	return re.search(r"APP_VERSION\s*=\s*[\"']([^\"']+)[\"']", texto).group(1)


def version_siguiente(version: str) -> str:
	"""0.1.0 → 0.1.1."""
	partes = version.split(".")
	partes[-1] = str(int(partes[-1]) + 1)
	return ".".join(partes)


def ejecutar(orden: list[str], cwd: Path, entorno: dict[str, str] | None = None) -> None:
	"""Ejecuta una orden y para la prueba si falla."""
	resultado = subprocess.run(orden, cwd=cwd, env=entorno, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
	if resultado.returncode != 0:
		print(resultado.stdout[-4000:], resultado.stderr[-4000:], sep="\n")
		raise SystemExit(f"Falló: {' '.join(orden)} (código {resultado.returncode})")


def entorno_sin_redireccion() -> dict[str, str]:
	"""Entorno para la aplicación real: sin APP_DATA_DIR, que es solo de esta herramienta."""
	return {clave: valor for clave, valor in os.environ.items() if clave != "APP_DATA_DIR"}


def compilar_actual() -> None:
	"""Compila y empaqueta la versión actual del repositorio, como ``entorno.bat compilar``."""
	paso("Compilando la versión actual del proyecto (setup_cx.py build)...")
	ejecutar([PYTHON, "tools/antes_de_compilar.py"], RAIZ)
	ejecutar([PYTHON, "setup_cx.py", "build"], RAIZ)
	ejecutar([PYTHON, "tools/empaquetar.py"], RAIZ)


def fabricar_siguiente(base: Path, version: str) -> tuple[Path, Path, Path]:
	"""Copia el proyecto, sube la versión en la copia, la compila y la empaqueta.

	Devuelve (zip, version.json, carpeta compilada). El repositorio no se toca.
	"""
	copia = base / "proyecto"
	paso(f"Copiando el proyecto para fabricar la {version}...")
	shutil.copytree(RAIZ, copia, ignore=lambda _carpeta, nombres: [n for n in nombres if n in NO_COPIAR])
	for relativa, patron in (("app/core/version.py", r'(APP_VERSION\s*=\s*")[^"]+(")'), ("pyproject.toml", r'(^version\s*=\s*")[^"]+(")')):
		ruta = copia / relativa
		texto, cambios = re.subn(patron, rf"\g<1>{version}\g<2>", ruta.read_text(encoding="utf-8"), count=1, flags=re.MULTILINE)
		if cambios != 1:
			raise SystemExit(f"No se pudo cambiar la versión en la copia de {relativa}")
		ruta.write_text(texto, encoding="utf-8")
	# Sin notas no se compila (tools/antes_de_compilar.py): se añaden, también solo en la copia.
	novedades = copia / "data" / "docs" / "novedades.md"
	titulo, _salto, resto = novedades.read_text(encoding="utf-8").partition("\n\n")
	apartado = f"## Versión {version} - {time.strftime('%Y-%m-%d')}\n\n### Arreglos\n\n- Versión de prueba del actualizador.\n\n"
	novedades.write_text(f"{titulo}\n\n{apartado}{resto}", encoding="utf-8")
	paso(f"Compilando la {version} en la copia...")
	ejecutar([PYTHON, "tools/antes_de_compilar.py"], copia)
	ejecutar([PYTHON, "setup_cx.py", "build"], copia)
	paso(f"Empaquetando y firmando la {version} (tools/empaquetar.py)...")
	ejecutar([PYTHON, "tools/empaquetar.py"], copia)
	manifiesto = copia / "build" / "version.json"
	if "firma_ed25519" not in json.loads(manifiesto.read_text(encoding="utf-8")):
		raise SystemExit("version.json no quedó firmado: falta la clave de desarrollo fuera del proyecto")
	return copia / "build" / f"EntornoLab_v{version}.zip", manifiesto, copia / "build" / "entornolab"


def huellas_programa(carpeta: Path) -> dict[str, str]:
	"""SHA-256 de cada fichero del programa (todo salvo ``data``)."""
	resultado: dict[str, str] = {}
	for ruta in carpeta.rglob("*"):
		relativa = ruta.relative_to(carpeta)
		if ruta.is_file() and relativa.parts[0].lower() != "data":
			resultado[relativa.as_posix()] = hashlib.sha256(ruta.read_bytes()).hexdigest()
	return resultado


USUARIO = {
	"data/entornos/mi casa.elab": b"entorno del profesional (falso)" * 50,
	"data/sessions/sesion de ana.json.gz": b"sesion del alumno (falsa)" * 20,
	"data/backups/copia de marzo.zip": b"copia de seguridad (falsa)" * 20,
	"data/logs/mis notas.txt": "notas del profesional con tildes: ñandú\n".encode(),
	"data/plugins/propio_usuario/complemento.json": json.dumps(
		{"formato": 1, "id": "propio_usuario", "version": "1.0", "nombre": "Complemento del usuario", "objetos": []}
	).encode(),
	"data/plugins/propio_usuario/sonidos/mio.wav": b"RIFF falso" * 30,
	"data/config/complementos.json": json.dumps({"instalados": {"propio_usuario": {"version": "1.0"}}}).encode(),
}
CONFIGURACION = {
	# Sin preguntas ni voz al abrir: la prueba no puede responder diálogos.
	"general": {"comprobar_novedades": False, "anunciar_arranque": False},
	"actualizaciones": {"preguntado": True, "comprobar_al_arrancar": False},
	"voz": {"salida": "ninguna"},
}


def huellas_usuario(instalacion: Path) -> dict[str, str]:
	return {nombre: hashlib.sha256((instalacion / nombre).read_bytes()).hexdigest() for nombre in USUARIO}


def instalar(zip_: Path, instalacion: Path) -> None:
	"""Descomprime la versión como lo haría el usuario y le pone sus datos."""
	if instalacion.exists():
		borrar(instalacion)
	destino = instalacion.parent / "descomprimido"
	with zipfile.ZipFile(zip_) as paquete:
		paquete.extractall(destino)
	(destino / "EntornoLab").rename(instalacion)
	destino.rmdir()
	for nombre, contenido in USUARIO.items():
		ruta = instalacion / nombre
		ruta.parent.mkdir(parents=True, exist_ok=True)
		ruta.write_bytes(contenido)
	(instalacion / "data" / "config" / "config.json").write_text(json.dumps(CONFIGURACION), encoding="utf-8")


def borrar(carpeta: Path) -> None:
	"""Borra una carpeta de la prueba (con solo lectura y rutas largas)."""
	sys.path.insert(0, str(RAIZ))
	from app.services import actualizador

	if not actualizador.borrar_carpeta(carpeta, intentos=8):
		print(f"AVISO: no se pudo borrar {carpeta}")


def matar_restos(carpeta: Path) -> None:
	"""Cierra a la fuerza todo lo que siga ejecutándose desde la instalación de prueba."""
	filtro = str(carpeta).replace("'", "''")
	orden = (
		"Get-CimInstance Win32_Process | Where-Object { ($_.ExecutablePath -and $_.ExecutablePath.StartsWith('"
		+ filtro
		+ "', 'OrdinalIgnoreCase')) -or ($_.CommandLine -and $_.CommandLine.Contains('"
		+ filtro
		+ "')) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
	)
	subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", orden], capture_output=True, timeout=60, check=False)


def cerrar(proceso: subprocess.Popen, nombre: str, espera: float = 20) -> None:
	"""Cierra una ventana como el usuario (WM_CLOSE con taskkill sin /F); a la fuerza si no responde."""
	subprocess.run(["taskkill", "/PID", str(proceso.pid)], capture_output=True, check=False)
	try:
		proceso.wait(timeout=espera)
		paso(f"{nombre} cerrado")
	except subprocess.TimeoutExpired:
		subprocess.run(["taskkill", "/F", "/T", "/PID", str(proceso.pid)], capture_output=True, check=False)
		proceso.wait(timeout=30)
		paso(f"{nombre} no se cerraba solo; cerrado a la fuerza")


def esperar(condicion: Callable[[], bool], segundos: float) -> bool:
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if condicion():
			return True
		time.sleep(0.5)
	return condicion()


def leer_registro(ruta: Path) -> str:
	"""El registro del script; vacío mientras no exista (una instalación recién descomprimida no lo tiene)."""
	try:
		return ruta.read_text(encoding="utf-8", errors="replace")
	except FileNotFoundError:
		return ""


def version_confirmada(instalacion: Path) -> str:
	ruta = instalacion / "data" / "config" / "actualizaciones.json"
	try:
		return str(json.loads(ruta.read_text(encoding="utf-8")).get("version_confirmada") or "")
	except OSError, ValueError:
		return ""


def abrir_estudio(instalacion: Path, version: str) -> subprocess.Popen:
	"""Abre el Estudio real y espera a que confirme su arranque (unos 5 segundos tras abrir la ventana)."""
	(instalacion / "data" / "config" / "actualizaciones.json").unlink(missing_ok=True)
	estudio = subprocess.Popen([str(instalacion / "EntornoLab.exe")], cwd=instalacion, env=entorno_sin_redireccion())
	if not esperar(lambda: version_confirmada(instalacion) == version, 90):
		raise SystemExit(f"El Estudio {version} no confirmó su arranque")
	paso(f"Estudio {version} abierto (PID {estudio.pid})")
	return estudio


def comprobar_arranques(instalacion: Path) -> None:
	"""``--comprobar-arranque`` de los DOS ejecutables reales."""
	for ejecutable in ("EntornoLab.exe", "EntornoLabJugar.exe"):
		resultado = subprocess.run(
			[str(instalacion / ejecutable), "--comprobar-arranque"],
			cwd=instalacion,
			env=entorno_sin_redireccion(),
			timeout=180,
			check=False,
		)
		if resultado.returncode != 0:
			raise SystemExit(f"{ejecutable} --comprobar-arranque devolvió {resultado.returncode}")
		paso(f"{ejecutable} --comprobar-arranque: correcto")


def main() -> int:
	analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	analizador.add_argument("--compilar", action="store_true", help="compila antes la versión actual del repositorio")
	analizador.add_argument("--conservar", action="store_true", help="no borra la carpeta temporal al terminar")
	opciones = analizador.parse_args()
	if sys.platform != "win32":
		raise SystemExit("Solo en Windows")
	base = Path(tempfile.mkdtemp(prefix="entornolab_prueba_real_"))
	# El código del proyecto que hace de «diálogo» guarda sus preferencias aquí, no en el data/ real.
	os.environ["APP_DATA_DIR"] = str(base / "datos_de_la_herramienta")
	sys.path.insert(0, str(RAIZ))
	from app.core import red
	from app.services import actualizador
	from tests._instalacion_falsa import bloquear
	from tests.servidor_http_prueba import ServidorPrueba

	red.ESPERA_INICIAL = 0.05
	actual = leer_version(RAIZ)
	nueva = version_siguiente(actual)
	instalacion = base / "Mis cosas" / "EntornoLab (copia)"
	servidor: ServidorPrueba | None = None
	procesos: list[subprocess.Popen] = []
	try:
		if opciones.compilar:
			compilar_actual()
		zip_actual = RAIZ / "build" / f"EntornoLab_v{actual}.zip"
		if not zip_actual.is_file():
			raise SystemExit(f"Falta {zip_actual}: compile con entorno.bat compilar o use --compilar")
		zip_nueva, manifiesto, compilada_nueva = fabricar_siguiente(base, nueva)
		huellas_actual = huellas_programa(RAIZ / "build" / "entornolab")
		huellas_nueva = huellas_programa(compilada_nueva)
		servidor = ServidorPrueba(base / "web")
		shutil.copy2(zip_nueva, servidor.carpeta / zip_nueva.name)
		shutil.copy2(manifiesto, servidor.carpeta / "version.json")
		paso(f"Servidor local con la {nueva}: {servidor.url('version.json')}")

		def configuracion(**cambios) -> actualizador.Configuracion:
			return actualizador.Configuracion(
				version_actual=actual,
				carpeta_app=instalacion,
				url_estable=servidor.url("version.json"),
				comando=[str(instalacion / "EntornoLab.exe")],
				permitir_desde_codigo=True,
				**cambios,
			)

		def preparar(config: actualizador.Configuracion) -> Path:
			info = actualizador.comprobar(config)
			if info is None or info.version != nueva:
				raise SystemExit(f"No se ofrece la {nueva}")
			ruta_bat = actualizador.descargar_y_preparar(config, info)
			paso(f"Descargada, verificada (firma Ed25519 y SHA-256) y preparada la {nueva}")
			return ruta_bat

		def resultado(config: actualizador.Configuracion) -> dict[str, str]:
			return actualizador.leer_resultado(config) or {}

		# ── A: actualización con el reproductor abierto y ficheros de lib en uso ──
		paso("ESCENARIO A: actualización real con el reproductor abierto, una DLL cargada y un fichero bloqueado")
		instalar(zip_actual, instalacion)
		usuario_antes = huellas_usuario(instalacion)
		estudio = abrir_estudio(instalacion, actual)
		procesos.append(estudio)
		reproductor = subprocess.Popen([str(instalacion / "EntornoLabJugar.exe")], cwd=instalacion, env=entorno_sin_redireccion())
		procesos.append(reproductor)
		time.sleep(6)
		paso(f"Reproductor abierto (PID {reproductor.pid})")
		config = configuracion(pid_a_esperar=estudio.pid)
		ruta_bat = preparar(config)
		procesos.append(bloquear(instalacion / DLL_A_CARGAR, "dll"))
		paso(f"Otro proceso tiene cargada {DLL_A_CARGAR}")
		procesos.append(bloquear(instalacion / FICHERO_A_BLOQUEAR, "exclusivo", segundos=25))
		paso(f"Otro proceso tiene abierto sin compartir {FICHERO_A_BLOQUEAR} durante 25 s")
		os.environ.pop("APP_DATA_DIR", None)  # el script y la versión nueva usan el data/ de la instalación
		script = actualizador.lanzar_sustitucion(ruta_bat)
		procesos.append(script)
		time.sleep(2)
		cerrar(estudio, "Estudio")
		time.sleep(8)
		cerrar(reproductor, "Reproductor")
		script.wait(timeout=600)
		final = resultado(config)
		paso(f"Resultado del script: {final}")
		if final.get("estado") != "correcta":
			raise SystemExit(
				"ESCENARIO A: no terminó en la versión nueva\n" + config.registro_script.read_text(encoding="utf-8", errors="replace")
			)
		if version_confirmada(instalacion) != nueva:
			raise SystemExit("ESCENARIO A: la versión nueva no confirmó su arranque")
		matar_restos(instalacion)
		for proceso in procesos:
			if proceso.poll() is None:
				proceso.kill()
		time.sleep(2)
		instaladas = huellas_programa(instalacion)
		diferencias = {clave for clave in set(huellas_nueva) | set(instaladas) if huellas_nueva.get(clave) != instaladas.get(clave)}
		if diferencias:
			raise SystemExit(f"ESCENARIO A: el programa instalado no es idéntico al compilado: {sorted(diferencias)[:10]}")
		paso(f"Programa idéntico a la compilación {nueva} ({len(huellas_nueva)} ficheros)")
		if huellas_usuario(instalacion) != usuario_antes:
			raise SystemExit("ESCENARIO A: cambiaron datos del usuario")
		paso("Datos del usuario y complemento del usuario intactos (SHA-256)")
		comprobar_arranques(instalacion)
		registro_a = config.registro_script.read_text(encoding="utf-8", errors="replace")
		for linea in registro_a.splitlines():
			print("    " + linea)

		# ── B: fallo forzado a mitad ──
		paso("ESCENARIO B: fallo forzado a mitad de la sustitución")
		os.environ["APP_DATA_DIR"] = str(base / "datos_de_la_herramienta")
		instalar(zip_actual, instalacion)
		usuario_antes = huellas_usuario(instalacion)
		# Un proceso breve hace de «Estudio que se cierra» para el script.
		app = subprocess.Popen([PYTHON, "-c", "import time; time.sleep(2)"])
		config = configuracion(punto_de_fallo="aplicar", pid_a_esperar=app.pid)
		ruta_bat = preparar(config)
		os.environ.pop("APP_DATA_DIR", None)
		script = actualizador.lanzar_sustitucion(ruta_bat)
		script.wait(timeout=600)
		final = resultado(config)
		paso(f"Resultado del script: {final}")
		if final.get("estado") != "revertida":
			raise SystemExit("ESCENARIO B: no volvió atrás\n" + config.registro_script.read_text(encoding="utf-8", errors="replace"))
		if not esperar(lambda: version_confirmada(instalacion) == actual, 90):
			raise SystemExit("ESCENARIO B: la versión anterior no volvió a arrancar")
		paso(f"El script volvió a abrir la {actual} y confirmó su arranque")
		matar_restos(instalacion)
		time.sleep(2)
		if huellas_programa(instalacion) != huellas_actual:
			raise SystemExit("ESCENARIO B: la versión restaurada no es idéntica a la original")
		paso(f"Programa idéntico a la compilación {actual}")
		if huellas_usuario(instalacion) != usuario_antes:
			raise SystemExit("ESCENARIO B: cambiaron datos del usuario")
		paso("Datos del usuario intactos")
		comprobar_arranques(instalacion)

		# ── C: corte de luz y recuperación al abrir el Estudio real ──
		paso("ESCENARIO C: corte de luz a mitad y recuperación al abrir el Estudio")
		os.environ["APP_DATA_DIR"] = str(base / "datos_de_la_herramienta")
		instalar(zip_actual, instalacion)
		usuario_antes = huellas_usuario(instalacion)
		app = subprocess.Popen([PYTHON, "-c", "import time; time.sleep(2)"])
		config = configuracion(punto_de_fallo="pausa", pid_a_esperar=app.pid)
		ruta_bat = preparar(config)
		os.environ.pop("APP_DATA_DIR", None)
		script = actualizador.lanzar_sustitucion(ruta_bat)
		if not esperar(lambda: "PRUEBA: pausa" in leer_registro(config.registro_script), 180):
			raise SystemExit("ESCENARIO C: el script no llegó a la pausa")
		subprocess.run(["taskkill", "/F", "/T", "/PID", str(script.pid)], capture_output=True, check=False)
		script.wait(timeout=60)
		paso("Script matado a mitad (corte de luz simulado); la instalación queda a medias")
		(instalacion / "data" / "config" / "actualizaciones.json").unlink(missing_ok=True)
		abierto = subprocess.Popen([str(instalacion / "EntornoLab.exe")], cwd=instalacion, env=entorno_sin_redireccion())
		abierto.wait(timeout=120)
		paso(f"El Estudio vio la actualización a medias, lanzó recuperar.bat y se cerró (código {abierto.returncode})")
		if not esperar(lambda: (resultado(config).get("estado") or "") in ("revertida", "rota"), 300):
			raise SystemExit(
				"ESCENARIO C: la recuperación no terminó\n" + config.registro_script.read_text(encoding="utf-8", errors="replace")
			)
		final = resultado(config)
		paso(f"Resultado de la recuperación: {final}")
		if (final.get("estado"), final.get("motivo")) != ("revertida", "interrumpida"):
			raise SystemExit("ESCENARIO C: no se recuperó\n" + config.registro_script.read_text(encoding="utf-8", errors="replace"))
		if not esperar(lambda: version_confirmada(instalacion) == actual, 90):
			raise SystemExit("ESCENARIO C: la versión anterior no volvió a arrancar")
		mensaje = actualizador.mensaje_resultado(final, actual)
		paso(f"Mensaje que verá el usuario: {mensaje}")
		matar_restos(instalacion)
		time.sleep(2)
		if huellas_programa(instalacion) != huellas_actual:
			raise SystemExit("ESCENARIO C: la versión recuperada no es idéntica a la original")
		if huellas_usuario(instalacion) != usuario_antes:
			raise SystemExit("ESCENARIO C: cambiaron datos del usuario")
		paso(f"Programa idéntico a la {actual} y datos del usuario intactos")
		comprobar_arranques(instalacion)
		paso("TODO CORRECTO")
		return 0
	finally:
		matar_restos(instalacion)
		for proceso in procesos:
			if proceso.poll() is None:
				proceso.kill()
		if servidor is not None:
			servidor.cerrar()
		if opciones.conservar:
			paso(f"Carpeta de la prueba conservada: {base}")
		else:
			time.sleep(2)
			borrar(base)
			paso("Carpeta temporal de la prueba borrada")


if __name__ == "__main__":
	sys.exit(main())
