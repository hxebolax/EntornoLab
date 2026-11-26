"""Pruebas de la configuración robusta: esquema, validación, migraciones, daños, avisos, hilos y guardado.

Las pruebas del esqueleto (``test_config.py``) siguen cubriendo lo básico a
través del nombre antiguo ``app.core.config``.
"""

from __future__ import annotations

import gc
import json
import threading

import pytest

from app.core import configuracion as mod
from app.core.configuracion import (
	CLAVE_VERSION,
	REGLAS,
	VALORES_POR_DEFECTO,
	Configuracion,
	ErrorConfiguracion,
	ErrorValidacion,
	Regla,
)

SECCIONES = [
	"general",
	"ventana",
	"registro",
	"sonido",
	"voz",
	"juego",
	"teclado",
	"mando",
	"editor",
	"supervision",
	"privacidad",
	"accesibilidad",
	"actualizaciones",
	"complementos",
	"importar",
]


@pytest.fixture
def ruta(tmp_path):
	return tmp_path / "config" / "config.json"


@pytest.fixture
def config(ruta):
	return Configuracion(ruta)


# ── Esquema del producto ─────────────────────────────────────────────────────


def test_secciones_del_producto(config):
	assert config.secciones() == SECCIONES
	assert set(VALORES_POR_DEFECTO) == set(SECCIONES)
	assert "sonido.motor" in config.claves() and "voz.detalle" in config.claves()


def test_valores_de_fabrica_cumplen_sus_reglas():
	"""Un valor de fábrica que no pasara su regla se «sanearía» a sí mismo en cada arranque."""
	for seccion, claves in VALORES_POR_DEFECTO.items():
		for nombre, valor in claves.items():
			mod.validar_valor(f"{seccion}.{nombre}", valor)


def test_toda_regla_corresponde_a_una_clave_existente():
	for clave in REGLAS:
		seccion, _punto, nombre = clave.partition(".")
		assert nombre in VALORES_POR_DEFECTO.get(seccion, {}), f"regla huérfana: {clave}"


def test_claves_que_usa_el_resto_del_proyecto(config):
	assert config.obtener("general.idioma") == "auto"
	assert config.obtener("sonido.motor") == "openal"
	assert config.obtener("sonido.modo_salida") == "auriculares"
	for bus in ("maestro", "efectos", "pasos", "ambiente", "ayudas", "interfaz", "musica", "voz"):
		assert 0.0 <= config.obtener(f"sonido.volumen_{bus}") <= 1.0
	assert config.obtener("voz.salida") == "automatica"
	assert config.obtener("voz.canales") == {"juego": True, "ayuda": True, "aviso": True, "profesional": True}
	assert config.obtener("juego.modo_movimiento") == "pasos"
	assert config.obtener("teclado.mapa") == {} and config.obtener("mando.mapa") == {}
	assert config.obtener("supervision.puerto") == 47900
	assert config.obtener("privacidad.cifrar_fichas") is True


# ── Lectura y escritura ──────────────────────────────────────────────────────


def test_obtener_clave_desconocida_devuelve_el_defecto(config):
	assert config.obtener("no.existe") is None
	assert config.obtener("no.existe", 7) == 7
	assert config.obtener("sonido.no_existe", "x") == "x"
	assert config.valor_por_defecto("juego.paso_m") == VALORES_POR_DEFECTO["juego"]["paso_m"]
	with pytest.raises(KeyError):
		config.valor_por_defecto("juego.no_existe")


def test_establecer_guarda_y_devuelve_si_cambio(config, ruta):
	assert not ruta.exists(), "leer no crea el archivo"
	assert config.establecer("sonido.volumen_maestro", 0.5) is True
	assert json.loads(ruta.read_text(encoding="utf-8"))["sonido"]["volumen_maestro"] == 0.5
	assert config.establecer("sonido.volumen_maestro", 0.5) is False, "el mismo valor no es un cambio"
	assert Configuracion(ruta).obtener("sonido.volumen_maestro") == 0.5


def test_establecer_sin_guardar_no_toca_el_disco(config, ruta):
	assert config.establecer("juego.unidad", "pasos", guardar=False) is True
	assert not ruta.exists()
	assert config.obtener("juego.unidad") == "pasos"
	assert config.guardar() is True
	assert Configuracion(ruta).obtener("juego.unidad") == "pasos"


def test_obtener_devuelve_copias(config):
	canales = config.obtener("voz.canales")
	canales["juego"] = False
	assert config.obtener("voz.canales")["juego"] is True
	mapa = {"juego": {"avanzar": ["arriba"]}}
	config.establecer("teclado.mapa", mapa)
	mapa["juego"]["avanzar"].append("w")
	assert config.obtener("teclado.mapa") == {"juego": {"avanzar": ["arriba"]}}, "tampoco se guarda la referencia recibida"


def test_claves_de_mas_de_dos_niveles(config, ruta):
	config.establecer("teclado.mapa.juego", {"avanzar": ["arriba"]})
	config.establecer("complemento.propio.opcion", 3)
	otra = Configuracion(ruta)
	assert otra.obtener("teclado.mapa.juego.avanzar") == ["arriba"]
	assert otra.obtener("teclado.mapa") == {"juego": {"avanzar": ["arriba"]}}
	assert otra.obtener("complemento.propio.opcion") == 3


def test_clave_mal_formada(config):
	for clave in ("sinpunto", ".clave", "seccion.", "a..b"):
		with pytest.raises(ErrorConfiguracion):
			config.establecer(clave, 1)


# ── Validación ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
	("clave", "valor"),
	[
		("sonido.motor", "directsound"),
		("sonido.volumen_maestro", 1.5),
		("sonido.volumen_maestro", "alto"),
		("sonido.proteccion_auditiva", 1),
		("voz.detalle", 4),
		("voz.detalle", True),
		("voz.velocidad", 2.5),
		("juego.modo_movimiento", "volando"),
		("juego.paso_m", 0.0),
		("supervision.puerto", 80),
		("privacidad.caducidad_dias", -1),
		("general.idioma", "x" * 40),
		("teclado.mapa", []),
	],
)
def test_valores_no_validos_se_rechazan(config, ruta, clave, valor):
	anterior = config.obtener(clave)
	with pytest.raises(ErrorValidacion):
		config.establecer(clave, valor)
	assert config.obtener(clave) == anterior
	assert not ruta.exists(), "un valor rechazado no provoca ningún guardado"


def test_un_entero_vale_donde_se_espera_un_decimal(config):
	assert config.establecer("sonido.volumen_maestro", 1) is False, "1 y 1.0 son el mismo volumen, pero..."
	assert config.establecer("sonido.volumen_maestro", 0) is True
	assert config.establecer("juego.giro_grados", 90) is True


def test_establecer_varias_valida_todo_antes_de_cambiar_nada(config):
	with pytest.raises(ErrorValidacion):
		config.establecer_varias({"juego.unidad": "pasos", "voz.detalle": 99})
	assert config.obtener("juego.unidad") == "metros", "si una falla, no se cambia ninguna"
	assert config.establecer_varias({"juego.unidad": "pasos", "voz.detalle": 3}) is True
	assert config.regla("voz.detalle") == Regla(minimo=0, maximo=3)
	config.validar("voz.detalle", 0)


def test_archivo_con_valores_fuera_de_rango_se_sanea(ruta, caplog):
	ruta.parent.mkdir(parents=True)
	ruta.write_text(
		json.dumps({"sonido": {"motor": "inventado", "volumen_maestro": 9, "volumen_pasos": 0.3}, "voz": {"detalle": "mucho"}, "juego": 5}),
		encoding="utf-8",
	)
	config = Configuracion(ruta)
	assert config.obtener("sonido.motor") == "openal"
	assert config.obtener("sonido.volumen_maestro") == 1.0
	assert config.obtener("sonido.volumen_pasos") == 0.3, "lo válido se respeta"
	assert config.obtener("voz.detalle") == 2
	assert config.obtener("juego.paso_m") == VALORES_POR_DEFECTO["juego"]["paso_m"], "una sección que no es un objeto se restablece"
	assert "no válido" in caplog.text
	assert json.loads(ruta.read_text(encoding="utf-8"))["sonido"]["motor"] == "openal", "el archivo queda corregido"


def test_claves_desconocidas_se_conservan_al_guardar(ruta):
	ruta.parent.mkdir(parents=True)
	ruta.write_text(json.dumps({"futuro": {"opcion": [1, 2]}, "sonido": {"de_otra_version": "x"}}), encoding="utf-8")
	config = Configuracion(ruta)
	config.establecer("juego.unidad", "pasos")
	guardado = json.loads(ruta.read_text(encoding="utf-8"))
	assert guardado["futuro"] == {"opcion": [1, 2]}
	assert guardado["sonido"]["de_otra_version"] == "x"


# ── Daños y recuperación ─────────────────────────────────────────────────────


def test_primer_arranque(config, ruta):
	assert config.primer_arranque is True
	assert config.recuperacion is None
	config.guardar()
	assert Configuracion(ruta).primer_arranque is False


def test_archivo_corrupto_recupera_la_copia_bak(ruta):
	config = Configuracion(ruta)
	config.establecer("juego.unidad", "pasos")
	config.establecer("juego.estilo", "infantil")  # el .bak guarda el estado anterior: unidad en pasos
	ruta.write_text('{"juego": {"unidad": ', encoding="utf-8")
	recuperada = Configuracion(ruta)
	assert recuperada.obtener("juego.unidad") == "pasos"
	assert "copia anterior" in recuperada.recuperacion
	assert len(list(ruta.parent.glob("config.json.corrupto-*"))) == 1, "el archivo dañado se conserva aparte"
	assert json.loads(ruta.read_text(encoding="utf-8"))["juego"]["unidad"] == "pasos"


def test_archivo_y_copia_corruptos_vuelven_a_fabrica(ruta):
	ruta.parent.mkdir(parents=True)
	ruta.write_text("no es json", encoding="utf-8")
	ruta.with_name("config.json.bak").write_text("tampoco", encoding="utf-8")
	config = Configuracion(ruta)
	assert config.obtener("sonido.motor") == "openal"
	assert "valores de fábrica" in config.recuperacion


def test_archivo_que_no_se_puede_leer_no_se_sobrescribe(ruta, monkeypatch):
	ruta.parent.mkdir(parents=True)
	original = json.dumps({"juego": {"unidad": "pasos"}})
	ruta.write_text(original, encoding="utf-8")

	def sin_permiso(self, ruta_leida):
		raise PermissionError("acceso denegado")

	monkeypatch.setattr(Configuracion, "_leer_json", sin_permiso)
	config = Configuracion(ruta)
	assert config.obtener("juego.unidad") == "metros"
	assert "sin guardar" in config.recuperacion
	assert config.guardar() is False
	config.establecer("juego.unidad", "metros")
	assert ruta.read_text(encoding="utf-8") == original, "perder la configuración real sería peor que no guardar"


def test_escritura_atomica_con_copia(config, ruta):
	config.establecer("juego.unidad", "pasos")
	config.establecer("juego.unidad", "metros")
	assert not list(ruta.parent.glob("*.tmp")), "no debe quedar el temporal"
	assert json.loads(ruta.with_name("config.json.bak").read_text(encoding="utf-8"))["juego"]["unidad"] == "pasos"
	assert "\t" in ruta.read_text(encoding="utf-8"), "sangrado con tabulaciones"


def test_fallo_al_reemplazar_deja_el_archivo_anterior(config, ruta, monkeypatch):
	config.establecer("juego.unidad", "pasos")

	def falla(origen, destino):
		raise OSError("disco lleno")

	monkeypatch.setattr(mod.os, "replace", falla)
	assert config.establecer("juego.unidad", "metros") is True, "el cambio queda en memoria"
	assert config.guardar() is False
	assert json.loads(ruta.read_text(encoding="utf-8"))["juego"]["unidad"] == "pasos"
	assert not list(ruta.parent.glob("*.tmp"))


# ── Migraciones ──────────────────────────────────────────────────────────────


def test_migracion_renombra_y_elimina(ruta):
	ruta.parent.mkdir(parents=True)
	ruta.write_text(json.dumps({CLAVE_VERSION: 1, "sonido": {"volumen": 0.4, "obsoleta": True}}), encoding="utf-8")
	llamadas = []

	def a_2(datos):
		llamadas.append(1)
		mod.renombrar_clave(datos, "sonido.volumen", "sonido.volumen_maestro")
		mod.eliminar_clave(datos, "sonido.obsoleta")

	config = Configuracion(ruta, version=2, migraciones={1: a_2})
	assert config.obtener("sonido.volumen_maestro") == 0.4
	assert config.obtener("sonido.volumen") is None and config.obtener("sonido.obsoleta") is None
	guardado = json.loads(ruta.read_text(encoding="utf-8"))
	assert guardado[CLAVE_VERSION] == 2 and "volumen" not in guardado["sonido"]
	# Solo una vez: al volver a cargar ya está en la versión 2.
	Configuracion(ruta, version=2, migraciones={1: a_2})
	assert llamadas == [1]


def test_migracion_rota_no_impide_arrancar(ruta, caplog):
	ruta.parent.mkdir(parents=True)
	ruta.write_text(json.dumps({CLAVE_VERSION: 1, "juego": {"unidad": "pasos"}}), encoding="utf-8")

	def rota(datos):
		raise RuntimeError("migración con un fallo")

	config = Configuracion(ruta, version=2, migraciones={1: rota})
	assert config.obtener("juego.unidad") == "pasos"
	assert "Falló la migración" in caplog.text


@pytest.mark.parametrize(
	("version", "guardada", "esperada"),
	[
		# Un «lector» de la versión 1 era «lector y, si no hay, SAPI»: ahora se llama «automatica».
		(1, "lector", "automatica"),
		(None, "lector", "automatica"),
		(1, "sapi", "sapi"),
		# En la versión 2, «lector» ya es «solo el lector de pantalla»: no se toca.
		(2, "lector", "lector"),
		(2, "ninguna", "ninguna"),
	],
)
def test_migracion_de_la_salida_de_voz(ruta, version, guardada, esperada):
	ruta.parent.mkdir(parents=True)
	datos: dict = {"voz": {"salida": guardada, "velocidad": 70}}
	if version is not None:
		datos[CLAVE_VERSION] = version
	ruta.write_text(json.dumps(datos), encoding="utf-8")
	config = Configuracion(ruta)
	assert config.obtener("voz.salida") == esperada
	assert config.obtener("voz.velocidad") == 70
	guardado = json.loads(ruta.read_text(encoding="utf-8"))
	assert guardado["voz"]["salida"] == esperada
	if version != 2:
		assert guardado[CLAVE_VERSION] == mod.VERSION_ESQUEMA
	# Idempotente: cargar de nuevo no cambia nada.
	assert Configuracion(ruta).obtener("voz.salida") == esperada


def test_salida_de_voz_admite_los_cuatro_valores(config):
	for valor in ("automatica", "lector", "sapi", "ninguna"):
		config.establecer("voz.salida", valor)
		assert config.obtener("voz.salida") == valor
	with pytest.raises(ErrorValidacion):
		config.establecer("voz.salida", "telepatía")
	assert config.valor_por_defecto("voz.salida") == "automatica"


def test_archivo_de_una_version_mas_nueva_no_se_toca(ruta):
	ruta.parent.mkdir(parents=True)
	ruta.write_text(json.dumps({CLAVE_VERSION: 99, "juego": {"unidad": "pasos", "del_futuro": 1}}), encoding="utf-8")
	config = Configuracion(ruta)
	assert config.obtener("juego.unidad") == "pasos"
	config.guardar()
	guardado = json.loads(ruta.read_text(encoding="utf-8"))
	assert guardado[CLAVE_VERSION] == 99 and guardado["juego"]["del_futuro"] == 1


def test_renombrar_clave_respeta_la_nueva_si_ya_existe():
	datos = {"a": {"vieja": 1}, "b": {"nueva": 2}}
	assert mod.renombrar_clave(datos, "a.vieja", "b.nueva") is True
	assert datos == {"b": {"nueva": 2}}, "gana la nueva y la sección vacía desaparece"
	assert mod.renombrar_clave(datos, "a.vieja", "b.nueva") is False, "idempotente"
	assert mod.eliminar_clave(datos, "b.nueva") is True and mod.eliminar_clave(datos, "b.nueva") is False


# ── Suscripciones ────────────────────────────────────────────────────────────


def test_suscriptores_reciben_clave_anterior_y_nuevo(config):
	avisos = []
	todos = []
	cancelar = config.suscribir(lambda clave, anterior, nuevo: avisos.append((clave, anterior, nuevo)), prefijo="sonido.")
	config.suscribir(lambda clave, anterior, nuevo: todos.append(clave))
	config.establecer("sonido.volumen_maestro", 0.2)
	config.establecer("juego.unidad", "pasos")
	config.establecer("sonido.volumen_maestro", 0.2)  # sin cambio: sin aviso
	assert avisos == [("sonido.volumen_maestro", 1.0, 0.2)]
	assert todos == ["sonido.volumen_maestro", "juego.unidad"]
	cancelar()
	config.establecer("sonido.volumen_maestro", 0.9)
	assert len(avisos) == 1


def test_un_suscriptor_roto_no_impide_avisar_a_los_demas(config, caplog):
	avisos = []
	config.suscribir(lambda clave, anterior, nuevo: 1 / 0)
	config.suscribir(lambda clave, anterior, nuevo: avisos.append(clave))
	config.establecer("juego.unidad", "pasos")
	assert avisos == ["juego.unidad"]
	assert "Falló un suscriptor" in caplog.text


def test_metodo_suscrito_no_retiene_a_su_objeto(config):
	class Ventana:
		def __init__(self):
			self.avisos = []

		def al_cambiar(self, clave, anterior, nuevo):
			self.avisos.append(clave)

	ventana = Ventana()
	config.suscribir(ventana.al_cambiar)
	config.establecer("juego.unidad", "pasos")
	assert ventana.avisos == ["juego.unidad"]
	del ventana
	gc.collect()
	config.establecer("juego.unidad", "metros")  # no debe fallar ni avisar a un objeto muerto
	assert config._suscriptores == []


def test_un_suscriptor_puede_leer_la_configuracion(config):
	leido = []
	config.suscribir(lambda clave, anterior, nuevo: leido.append(config.obtener(clave)))
	config.establecer("juego.unidad", "pasos")
	assert leido == ["pasos"]


# ── Lotes, guardado diferido y hilos ─────────────────────────────────────────


def _contar_guardados(config, monkeypatch) -> list[int]:
	guardados: list[int] = []
	original = config.guardar

	def contar():
		guardados.append(1)
		return original()

	monkeypatch.setattr(config, "guardar", contar)
	return guardados


def test_lote_un_solo_guardado_y_avisos_al_final(config, monkeypatch):
	guardados = _contar_guardados(config, monkeypatch)
	avisos = []
	config.suscribir(lambda clave, anterior, nuevo: avisos.append(clave))
	with config.lote():
		config.establecer("juego.unidad", "pasos")
		config.establecer("juego.estilo", "infantil")
		assert avisos == [] and guardados == []
	assert guardados == [1]
	assert avisos == ["juego.unidad", "juego.estilo"]


def test_establecer_varias_un_solo_guardado(config, monkeypatch):
	guardados = _contar_guardados(config, monkeypatch)
	config.establecer_varias({"juego.unidad": "pasos", "juego.estilo": "infantil", "voz.detalle": 1})
	assert guardados == [1]


def test_guardado_diferido_agrupa_y_guardar_pendiente_lo_fuerza(config, ruta, monkeypatch):
	guardados = _contar_guardados(config, monkeypatch)
	for valor in (0.1, 0.2, 0.3, 0.4):
		config.establecer_diferido("sonido.volumen_maestro", valor, retraso=30)
	assert guardados == [], "los cambios rápidos no escriben en disco"
	assert config.obtener("sonido.volumen_maestro") == 0.4
	assert config.guardar_pendiente() is True
	assert guardados == [1]
	assert json.loads(ruta.read_text(encoding="utf-8"))["sonido"]["volumen_maestro"] == 0.4
	assert config.guardar_pendiente() is True and guardados == [1], "sin nada pendiente no vuelve a escribir"


def test_guardado_diferido_vence_solo(config, ruta):
	config.establecer_diferido("sonido.volumen_maestro", 0.3, retraso=0.05)
	temporizador = config._temporizador
	assert temporizador is not None
	temporizador.join(5)
	assert json.loads(ruta.read_text(encoding="utf-8"))["sonido"]["volumen_maestro"] == 0.3


def test_restablecer_una_seccion_o_todo(config):
	config.establecer_varias({"juego.unidad": "pasos", "voz.detalle": 0})
	config.restablecer("juego")
	assert config.obtener("juego.unidad") == "metros" and config.obtener("voz.detalle") == 0
	config.restablecer()
	assert config.obtener("voz.detalle") == 2


def test_acceso_desde_varios_hilos(config, ruta):
	errores = []

	def trabajar(numero):
		try:
			for vuelta in range(25):
				config.establecer("voz.velocidad", (numero * 25 + vuelta) % 101)
				config.obtener("voz")
		except Exception as error:  # noqa: BLE001 - la prueba comprueba que no hay ninguno
			errores.append(error)

	hilos = [threading.Thread(target=trabajar, args=(numero,)) for numero in range(4)]
	for hilo in hilos:
		hilo.start()
	for hilo in hilos:
		hilo.join(30)
	assert errores == []
	assert json.loads(ruta.read_text(encoding="utf-8"))["voz"]["velocidad"] == config.obtener("voz.velocidad")
	assert not list(ruta.parent.glob("*.tmp"))


def test_cargar_de_nuevo_ve_lo_que_guardo_otro_proceso(config, ruta):
	otro = Configuracion(ruta)
	otro.establecer("sonido.motor", "clasico")
	assert config.obtener("sonido.motor") == "openal"
	config.cargar()
	assert config.obtener("sonido.motor") == "clasico"


# ── Instancia compartida y nombre antiguo ────────────────────────────────────


def test_instancia_compartida_se_crea_al_pedirla(data_temporal):
	mod.establecer_configuracion(None)
	primera = mod.obtener_configuracion()
	assert primera is mod.obtener_configuracion()
	assert primera.ruta == data_temporal / "config" / "config.json"
	propia = Configuracion(data_temporal / "otra.json")
	mod.establecer_configuracion(propia)
	assert mod.obtener_configuracion() is propia


def test_el_nombre_antiguo_del_modulo_sigue_valiendo():
	from app.core import config as antiguo

	assert antiguo.Configuracion is Configuracion
	assert antiguo.VALORES_POR_DEFECTO is VALORES_POR_DEFECTO


def test_claves_del_estudio_y_de_importar(config):
	"""Las claves que añade el Estudio existen con su valor de fábrica y validan su rango."""
	assert config.obtener("importar.overpass_url") == ""
	assert config.obtener("importar.nominatim_url") == ""
	assert config.obtener("importar.radio_m") == 150
	assert config.obtener("importar.aviso_privacidad_visto") is False
	assert config.obtener("complementos.desactivados") == []
	assert config.obtener("editor.recientes") == []
	assert config.obtener("editor.paso_libre_m") == 0.8
	config.establecer("importar.overpass_url", "https://overpass.example.org/api/interpreter")
	assert config.obtener("importar.overpass_url").startswith("https://")
	with pytest.raises(ErrorValidacion):
		config.establecer("importar.radio_m", 5000)
	with pytest.raises(ErrorValidacion):
		config.establecer("importar.nominatim_url", "x" * 2000)
	with pytest.raises(ErrorValidacion):
		config.establecer("editor.paso_libre_m", 0.1)
