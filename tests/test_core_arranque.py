"""Pruebas del arranque: ``main.py --jugar``, ``jugar.py``, ``--comprobar-arranque`` y la red de seguridad.

Las que lanzan otro proceso usan la carpeta data temporal de la prueba y no
muestran ninguna ventana. Las del Estudio sin argumentos están en
``test_arranque.py`` (pruebas del esqueleto).
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from app.core import arranque, registro
from app.reproductor import arranque as reproductor

from .conftest import RAIZ


def _ejecutar(guion: str, datos, *argumentos: str) -> subprocess.CompletedProcess:
	entorno = {**os.environ, "APP_DATA_DIR": str(datos)}
	return subprocess.run(
		[sys.executable, str(RAIZ / guion), *argumentos],
		capture_output=True,
		text=True,
		encoding="utf-8",
		errors="replace",
		timeout=120,
		env=entorno,
		cwd=str(RAIZ),
		check=False,
	)


def _registros(datos, patron: str) -> str:
	return "".join(ruta.read_text(encoding="utf-8") for ruta in sorted((datos / "logs").glob(patron)))


# ── En otro proceso ──────────────────────────────────────────────────────────


@pytest.mark.lento
@pytest.mark.parametrize(
	("guion", "argumentos"),
	[
		("jugar.py", ["--comprobar-arranque"]),
		("main.py", ["--jugar", "--comprobar-arranque"]),
	],
)
def test_el_reproductor_arranca_y_sale_con_cero(data_temporal, guion, argumentos):
	resultado = _ejecutar(guion, data_temporal, *argumentos)
	assert resultado.returncode == 0, resultado.stderr
	texto = _registros(data_temporal, "jugar_*.log")
	assert "EntornoLab (reproductor)" in texto
	assert "Comprobación de arranque correcta" in texto
	assert "Reproductor terminado con el código 0" in texto
	assert "ERROR" not in texto and "CRITICAL" not in texto
	# El reproductor no es el Estudio: ni sus archivos de registro ni su incidencias.log.
	assert not list((data_temporal / "logs").glob("sesion_*.log"))
	assert not (data_temporal / "logs" / "incidencias.log").exists()
	assert not (data_temporal / "logs" / "arranque_fallido.log").exists()


@pytest.mark.lento
def test_el_reproductor_no_pasa_por_la_instancia_unica(app_wx, data_temporal):
	"""Con un Estudio abierto, ``main.py --jugar`` arranca igual y no le pide que se muestre."""
	from app.core.instancia_unica import InstanciaUnica
	from app.core.version import ID_APLICACION

	estudio = InstanciaUnica(ID_APLICACION)
	try:
		resultado = _ejecutar("main.py", data_temporal, "--jugar", "--comprobar-arranque")
		assert resultado.returncode == 0, resultado.stderr
		assert estudio.recoger_ordenes() == [], "el reproductor no deja órdenes en el buzón del Estudio"
		assert "Reproductor terminado con el código 0" in _registros(data_temporal, "jugar_*.log")
	finally:
		estudio.liberar()


@pytest.mark.lento
def test_el_reproductor_no_importa_wx(data_temporal, tmp_path):
	"""El segundo ejecutable no debe cargar wxPython: tarda en arrancar y no lo usa."""
	guion = tmp_path / "medir.py"
	guion.write_text(
		"import sys\n"
		f"sys.path.insert(0, {str(RAIZ)!r})\n"
		"import jugar\n"
		"codigo = jugar.principal(['--comprobar-arranque'])\n"
		"print('wx' in sys.modules, 'pygame' in sys.modules, codigo)\n",
		encoding="utf-8",
	)
	resultado = subprocess.run(
		[sys.executable, str(guion)],
		capture_output=True,
		text=True,
		timeout=120,
		check=False,
		env={**os.environ, "APP_DATA_DIR": str(data_temporal)},
	)
	assert resultado.returncode == 0, resultado.stderr
	assert resultado.stdout.split()[0] == "False"
	assert resultado.stdout.split()[2] == "0"


@pytest.mark.lento
def test_argumentos_no_validos_salen_con_dos_y_quedan_en_el_registro(data_temporal):
	resultado = _ejecutar("main.py", data_temporal, "--recorrido", "--comprobar-arranque")
	assert resultado.returncode == 2
	assert "Argumentos del reproductor no válidos" in _registros(data_temporal, "jugar_*.log")


@pytest.mark.lento
def test_el_estudio_con_comprobar_arranque_no_deja_errores(data_temporal):
	resultado = _ejecutar("main.py", data_temporal, "--comprobar-arranque")
	assert resultado.returncode == 0, resultado.stderr
	texto = _registros(data_temporal, "sesion_*.log")
	assert "Idioma de la interfaz: es" in texto
	assert "Arranque completado" in texto and "Cierre normal" in texto
	assert "WARNING" not in texto and "ERROR" not in texto and "CRITICAL" not in texto
	assert not list((data_temporal / "logs").glob("jugar_*.log"))


# ── Argumentos del reproductor ───────────────────────────────────────────────


@pytest.fixture
def paquete(tmp_path):
	ruta = tmp_path / "mi casa.elab"
	ruta.write_bytes(b"PK")
	return ruta


def test_argumentos_de_jugar(paquete):
	opciones = reproductor.analizar_argumentos(
		[
			"--jugar",
			str(paquete),
			"--actividad",
			"buscar",
			"--alumno",
			"ana",
			"--sala",
			"127.0.0.1:47900",
			"--codigo",
			"AB12",
			"--inicio",
			"p0,1.5,-2,450",
		]
	)
	assert opciones.modo == reproductor.MODO_JUGAR
	assert opciones.paquete == paquete
	assert opciones.actividad == "buscar" and opciones.alumno == "ana"
	assert (opciones.sala_host, opciones.sala_puerto, opciones.codigo) == ("127.0.0.1", 47900, "AB12")
	assert opciones.supervisado is True
	assert opciones.inicio == reproductor.InicioPedido("p0", 1.5, -2.0, 90.0), "el rumbo se lleva de 0 a 360"
	assert opciones.comprobar is False


def test_argumentos_minimos_y_de_recorrido(paquete):
	vacio = reproductor.analizar_argumentos([])
	assert vacio.modo == reproductor.MODO_JUGAR and vacio.paquete is None and vacio.supervisado is False
	assert reproductor.analizar_argumentos(["--comprobar-arranque"]).comprobar is True
	recorrido = reproductor.analizar_argumentos(["--recorrido", str(paquete), "--sala", "equipo-aula:5000", "--codigo", "X"])
	assert recorrido.modo == reproductor.MODO_RECORRIDO
	assert (recorrido.sala_host, recorrido.sala_puerto) == ("equipo-aula", 5000)


@pytest.mark.parametrize(
	"argumentos",
	[
		["no_existe.elab"],
		["--sala", "127.0.0.1:47900"],
		["--codigo", "AB12"],
		["--sala", "sin_puerto", "--codigo", "x"],
		["--sala", "equipo:0", "--codigo", "x"],
		["--sala", "equipo:70000", "--codigo", "x"],
		["--sala", ":47900", "--codigo", "x"],
		["--inicio", "p0,1,2"],
		["--inicio", "p0,uno,2,3"],
		["--inicio", ",1,2,3"],
		["--inicio", "p0,nan,2,3"],
		["--recorrido"],
		["--opcion-inventada"],
		["--actividad"],
		["uno.elab", "dos.elab"],
	],
)
def test_argumentos_no_validos(argumentos, paquete, caplog):
	with pytest.raises(reproductor.ErrorArgumentos):
		reproductor.analizar_argumentos(argumentos)
	# ejecutar() no lanza ni llama a sys.exit: devuelve 2 y lo deja en el registro.
	assert reproductor.ejecutar(argumentos) == reproductor.CODIGO_ARGUMENTOS
	assert "no válidos" in caplog.text


def test_recorrido_necesita_entorno_y_sala(paquete):
	with pytest.raises(reproductor.ErrorArgumentos):
		reproductor.analizar_argumentos(["--recorrido", str(paquete)])
	with pytest.raises(reproductor.ErrorArgumentos):
		reproductor.analizar_argumentos(["--recorrido", "--sala", "a:1", "--codigo", "x"])


def test_ejecutar_no_registra_datos_personales(paquete, caplog):
	# El paquete de la fixture no es un entorno de verdad: en la comprobación de arranque eso es el código 3.
	argumentos = [str(paquete), "--alumno", "Ana García", "--codigo", "SECRETO1", "--sala", "127.0.0.1:1", "--comprobar-arranque"]
	assert reproductor.ejecutar(argumentos) == reproductor.CODIGO_ENTORNO
	assert "Reproductor pedido" in caplog.text
	assert "Ana García" not in caplog.text, "el alias del alumno no va al registro"
	assert "SECRETO1" not in caplog.text, "el código de emparejamiento tampoco"


# ── Piezas comunes ───────────────────────────────────────────────────────────


def test_pide_reproductor():
	assert arranque.pide_reproductor(["--jugar"]) is True
	assert arranque.pide_reproductor(["casa.elab", "--recorrido"]) is True
	assert arranque.pide_reproductor(["--comprobar-arranque"]) is False
	assert arranque.pide_reproductor([]) is False


def test_los_argumentos_son_los_mismos_en_los_tres_sitios():
	import jugar
	import main

	for modulo in (main, jugar):
		assert modulo.ARGUMENTO_COMPROBAR == arranque.ARGUMENTO_COMPROBAR
		assert modulo.ARGUMENTO_JUGAR == arranque.ARGUMENTO_JUGAR
		assert modulo.ARGUMENTO_RECORRIDO == arranque.ARGUMENTO_RECORRIDO


def test_main_delega_en_el_reproductor_antes_que_nada(monkeypatch):
	import main

	llamadas = []
	monkeypatch.setattr(arranque, "arrancar_reproductor", lambda argumentos: llamadas.append(list(argumentos)) or 5)
	monkeypatch.setattr(main, "_principal_estudio", lambda argumentos: pytest.fail("no debe arrancar el Estudio"))
	assert main.principal(["--jugar", "casa.elab"]) == 5
	assert main.principal(["--recorrido", "casa.elab"]) == 5
	assert llamadas == [["--jugar", "casa.elab"], ["--recorrido", "casa.elab"]]


def test_main_sin_argumentos_de_juego_arranca_el_estudio(monkeypatch):
	import main

	monkeypatch.setattr(arranque, "arrancar_reproductor", lambda argumentos: pytest.fail("no debe arrancar el reproductor"))
	monkeypatch.setattr(main, "_principal_estudio", lambda argumentos: 9)
	assert main.principal([]) == 9
	assert main.principal(["documento.elab", "--comprobar-arranque"]) == 9


def test_red_de_seguridad_de_jugar(monkeypatch, data_temporal):
	import jugar

	carteles = []

	def falla(argumentos):
		raise RuntimeError("fallo simulado del reproductor")

	monkeypatch.setattr(jugar, "_principal", falla)
	monkeypatch.setattr(jugar, "_mostrar_error_arranque", carteles.append)
	assert jugar.principal([]) == 1
	assert carteles and "RuntimeError: fallo simulado del reproductor" in carteles[0]
	fallo = data_temporal / "logs" / "arranque_fallido.log"
	assert "fallo simulado del reproductor" in fallo.read_text(encoding="utf-8")
	assert str(fallo) in carteles[0], "el cartel dice dónde están los detalles"


def test_la_red_de_seguridad_deja_pasar_la_salida_voluntaria():
	def salir(argumentos):
		raise SystemExit(3)

	with pytest.raises(SystemExit):
		arranque.con_red_de_seguridad(salir, [], lambda mensaje: pytest.fail("no es un error"))
	assert arranque.con_red_de_seguridad(lambda argumentos: 4, [], lambda mensaje: None) == 4


def test_preparar_configuracion_e_idioma(data_temporal, monkeypatch):
	from app.core import configuracion, i18n

	monkeypatch.setenv(i18n.VARIABLE_IDIOMA, "es")
	config, idioma = arranque.preparar_configuracion_e_idioma()
	assert idioma == "es"
	assert configuracion.obtener_configuracion() is config, "el resto de la aplicación usa la misma instancia"
	assert config.ruta == data_temporal / "config" / "config.json"


def test_arrancar_reproductor_usa_registro_auxiliar(data_temporal, monkeypatch):
	excepthook = sys.excepthook
	monkeypatch.setattr(reproductor, "ejecutar", lambda argumentos: 0)
	try:
		assert arranque.arrancar_reproductor(["--jugar"]) == 0
		archivo = registro.archivo_sesion_actual()
		assert archivo is not None and archivo.name.startswith("jugar_")
		assert f"_p{os.getpid()}" in archivo.name, "dos reproductores abiertos a la vez no comparten archivo"
		assert registro.vaciar()
		assert not (data_temporal / "logs" / "incidencias.log").exists()
		assert not (data_temporal / "logs" / "jugar.en_curso").exists()
		assert (data_temporal / "logs" / "fallo_nativo_jugar.log").exists()
	finally:
		registro.detener_registro(cerrar_fallo_nativo=True)
	assert sys.excepthook is excepthook, "detener el registro devuelve los ganchos"
