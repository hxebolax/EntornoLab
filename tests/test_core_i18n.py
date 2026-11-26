"""Pruebas de la traducción: catálogos, elección de idioma, cambio en caliente, datos y herramientas.

Trabajan con un catálogo de prueba («xx») creado en la carpeta data temporal:
nunca tocan los catálogos reales de ``data/locales``.
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest

from app.core import catalogo_po, i18n
from tools import actualizar_po, compilar_traducciones, extraer_cadenas, informe_traducciones

CABECERA = (
	'msgid ""\n'
	'msgstr ""\n'
	'"Language: xx\\n"\n'
	'"Content-Type: text/plain; charset=UTF-8\\n"\n'
	'"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n'
	"\n"
)

CATALOGO = CABECERA + (
	'msgid "&Guardar"\n'
	'msgstr "&Save"\n'
	"\n"
	'msgid "Hola, {nombre}"\n'
	'msgstr "Hello, {nombre}"\n'
	"\n"
	'msgid "Se encontró {n} premio"\n'
	'msgid_plural "Se encontraron {n} premios"\n'
	'msgstr[0] "{n} prize found"\n'
	'msgstr[1] "{n} prizes found"\n'
	"\n"
	'msgctxt "verbo"\n'
	'msgid "Abrir"\n'
	'msgstr "Open"\n'
	"\n"
	"#, fuzzy\n"
	'msgid "Dudosa"\n'
	'msgstr "Doubtful"\n'
	"\n"
	'msgid "Marcador roto {nombre}"\n'
	'msgstr "Broken placeholder {name}"\n'
	"\n"
	'msgid "Sin traducir"\n'
	'msgstr ""\n'
)


def _escribir_po(datos: Path, idioma: str = "xx", texto: str = CATALOGO) -> Path:
	ruta = datos / "locales" / idioma / "LC_MESSAGES" / f"{i18n.DOMINIO}.po"
	ruta.parent.mkdir(parents=True, exist_ok=True)
	ruta.write_text(texto, encoding="utf-8", newline="\n")
	return ruta


@pytest.fixture
def catalogo_xx(data_temporal, monkeypatch):
	"""Catálogo de prueba «xx» sin compilar; el idioma no se fuerza por entorno."""
	monkeypatch.delenv(i18n.VARIABLE_IDIOMA, raising=False)
	return _escribir_po(data_temporal)


# ── API que usa todo el proyecto ─────────────────────────────────────────────


def test_api_publica_que_importa_todo_el_proyecto():
	from app.core.i18n import IDIOMA_ORIGEN, N_, _, _n, cambiar_idioma, idioma_actual, idiomas_disponibles

	assert IDIOMA_ORIGEN == "es"
	assert _("Texto sin traducción") == "Texto sin traducción"
	assert _n("un paso", "varios pasos", 1) == "un paso"
	assert _n("un paso", "varios pasos", 3) == "varios pasos"
	assert N_("Constante") == "Constante"
	assert idioma_actual() == "es"
	assert idiomas_disponibles()[0] == "es"
	assert cambiar_idioma("es") is True


def test_cadena_vacia_no_devuelve_la_cabecera(catalogo_xx):
	assert i18n.cambiar_idioma("xx") is True
	assert i18n._("") == ""


def test_builtins_usan_el_catalogo_activo(catalogo_xx):
	# Las ventanas del esqueleto llaman a builtins._ sin importar nada.
	assert builtins._("&Guardar") == "&Guardar"
	i18n.cambiar_idioma("xx")
	assert builtins._("&Guardar") == "&Save"
	assert builtins.ngettext("Se encontró {n} premio", "Se encontraron {n} premios", 2) == "{n} prizes found"


# ── Carga de catálogos ───────────────────────────────────────────────────────


def test_lee_el_po_sin_compilar(catalogo_xx):
	assert "xx" in i18n.idiomas_disponibles()
	assert i18n.cambiar_idioma("xx") is True
	assert i18n.idioma_actual() == "xx"
	assert i18n._("&Guardar") == "&Save"
	assert i18n._("Hola, {nombre}").format(nombre="Ana") == "Hello, Ana"
	assert i18n.pgettext("verbo", "Abrir") == "Open"


def test_plurales(catalogo_xx):
	i18n.cambiar_idioma("xx")
	assert i18n._n("Se encontró {n} premio", "Se encontraron {n} premios", 1).format(n=1) == "1 prize found"
	assert i18n._n("Se encontró {n} premio", "Se encontraron {n} premios", 5).format(n=5) == "5 prizes found"
	# Un plural sin traducir cae al español con la regla del español.
	assert i18n._n("un paso", "{n} pasos", 2) == "{n} pasos"


def test_entradas_dudosas_se_quedan_en_espanol(catalogo_xx):
	i18n.cambiar_idioma("xx")
	assert i18n._("Dudosa") == "Dudosa", "una entrada fuzzy no se usa hasta revisarla"
	assert i18n._("Sin traducir") == "Sin traducir"
	# Con el marcador cambiado, .format() fallaría: la entrada se omite.
	assert i18n._("Marcador roto {nombre}").format(nombre="x") == "Marcador roto x"


def test_lee_el_mo_compilado_y_prefiere_el_mas_reciente(catalogo_xx):
	import os

	informe = compilar_traducciones.compilar(catalogo_xx)
	assert informe.destino is not None and informe.destino.is_file()
	assert informe.compiladas == 4
	assert informe.aproximadas == 1 and informe.sin_traducir == 1
	assert any("marcadores" in error for error in informe.errores)
	# Con el .mo más reciente que el .po se lee el .mo aunque el .po cambie de contenido...
	catalogo_xx.write_text(CATALOGO.replace("&Save", "&Keep"), encoding="utf-8", newline="\n")
	antiguo = informe.destino.stat().st_mtime - 100
	os.utime(catalogo_xx, (antiguo, antiguo))
	i18n.cambiar_idioma("xx")
	assert i18n._("&Guardar") == "&Save"
	# ...y con el .po más reciente (quien traduce acaba de guardarlo) manda el .po.
	nuevo = informe.destino.stat().st_mtime + 100
	os.utime(catalogo_xx, (nuevo, nuevo))
	i18n.cambiar_idioma("xx")
	assert i18n._("&Guardar") == "&Keep"


def test_solo_con_mo_tambien_funciona(catalogo_xx):
	compilar_traducciones.compilar(catalogo_xx)
	catalogo_xx.unlink()
	assert "xx" in i18n.idiomas_disponibles()
	assert i18n.cambiar_idioma("xx") is True
	assert i18n._("&Guardar") == "&Save"


def test_idioma_inexistente_vuelve_al_espanol(catalogo_xx, caplog):
	assert i18n.cambiar_idioma("zz") is False
	assert i18n.idioma_actual() == "es"
	assert i18n._("&Guardar") == "&Guardar"
	assert "se usa el español" in caplog.text


def test_catalogo_danado_no_impide_arrancar(data_temporal, monkeypatch):
	monkeypatch.delenv(i18n.VARIABLE_IDIOMA, raising=False)
	_escribir_po(data_temporal, texto='msgid "sin cerrar\nmsgstr "x"\n')
	mo = data_temporal / "locales" / "xx" / "LC_MESSAGES" / f"{i18n.DOMINIO}.mo"
	mo.write_bytes(b"esto no es un catalogo")
	assert i18n.inicializar("xx") == "es"
	assert i18n._("&Guardar") == "&Guardar"


def test_variante_regional_cae_al_idioma_general(catalogo_xx):
	assert i18n.cambiar_idioma("xx_YY") is True
	assert i18n.idioma_actual() == "xx"


# ── Elección del idioma ──────────────────────────────────────────────────────


def test_orden_de_preferencia(catalogo_xx, monkeypatch):
	monkeypatch.setattr(i18n, "idioma_sistema", lambda: "xx_YY")
	# 3. Sin configuración («auto»), el del sistema.
	assert i18n.resolver_idioma(None) == "xx_YY"
	assert i18n.resolver_idioma("auto") == "xx_YY"
	assert i18n.inicializar("auto") == "xx"
	# 2. La configuración manda sobre el sistema.
	assert i18n.resolver_idioma("es") == "es"
	assert i18n.inicializar("es") == "es"
	# 1. APP_IDIOMA manda sobre todo.
	monkeypatch.setenv(i18n.VARIABLE_IDIOMA, "xx")
	assert i18n.resolver_idioma("es") == "xx"
	assert i18n.inicializar("es") == "xx"
	# 4. Sin nada de lo anterior, español.
	monkeypatch.delenv(i18n.VARIABLE_IDIOMA)
	monkeypatch.setattr(i18n, "idioma_sistema", lambda: "")
	assert i18n.inicializar(None) == "es"


def test_normalizar_codigos():
	assert i18n.normalizar("es-ES") == "es_ES"
	assert i18n.normalizar("es_ES.UTF-8") == "es_ES"
	assert i18n.normalizar("EN") == "en"
	assert i18n.normalizar("pt_br") == "pt_BR"
	assert i18n.normalizar(None) == ""
	assert i18n.es_idioma_origen("es_MX")
	assert not i18n.es_idioma_origen("en")
	assert i18n.nombre_idioma("en") == "English"
	assert i18n.nombre_idioma("pt_BR") == "Português do Brasil"
	assert i18n.nombre_idioma("xx") == "xx"


def test_cambiar_idioma_avisa_a_los_oyentes(catalogo_xx, monkeypatch):
	monkeypatch.setattr(i18n, "_oyentes", [])
	avisados: list[str] = []
	i18n.al_cambiar_idioma(avisados.append)
	i18n.al_cambiar_idioma(lambda idioma: 1 / 0)  # un oyente roto no para a los demás
	i18n.al_cambiar_idioma(avisados.append)  # registrada dos veces: se avisa una
	assert i18n.cambiar_idioma("xx") is True
	assert i18n.cambiar_idioma("es") is True
	assert avisados == ["xx", "es"]


def test_configurar_wx_y_aviso_de_reinicio(catalogo_xx, monkeypatch):
	wx = pytest.importorskip("wx")
	creados: list[int] = []

	class LocaleFalso:
		"""Sustituto de wx.Locale: crear uno real en mitad de la sesión alteraría las demás pruebas."""

		def __init__(self, idioma: int) -> None:
			creados.append(idioma)

		@staticmethod
		def AddCatalogLookupPathPrefix(ruta: str) -> None:  # noqa: N802 - API de wx
			assert Path(ruta).name == "locale"

		@staticmethod
		def FindLanguageInfo(codigo: str):  # noqa: N802 - API de wx
			return None

		def IsOk(self) -> bool:  # noqa: N802 - API de wx
			return True

		def GetCanonicalName(self) -> str:  # noqa: N802 - API de wx
			return "es_ES"

	monkeypatch.setattr(wx, "Locale", LocaleFalso)
	monkeypatch.setattr(i18n, "_locale_wx", None)
	monkeypatch.setattr(i18n, "_idioma_wx", None)
	assert i18n.necesita_reinicio() is False, "sin wx.Locale creado no hay nada que reiniciar"
	objeto = i18n.configurar_wx("es")
	assert isinstance(objeto, LocaleFalso)
	assert creados == [wx.LANGUAGE_SPANISH], "un idioma que wx no conoce cae al español"
	assert i18n._locale_wx is objeto, "la referencia debe conservarse o los botones vuelven al inglés"
	assert i18n.necesita_reinicio() is False
	i18n.cambiar_idioma("xx")
	assert i18n.necesita_reinicio() is True, "los botones estándar de wx siguen en el idioma anterior"


# ── Traducción de datos ──────────────────────────────────────────────────────

COMPLEMENTO = {
	"id": "mobiliario",
	"nombre": "Mobiliario",
	"descripcion": "Muebles de casa",
	"objetos": [
		{
			"id": "mesa",
			"nombre": "Mesa",
			"categoria": "Muebles",
			"material": "madera",
			"etiquetas": ["Mesa", "comedor"],
			"acciones": [{"id": "abrir", "nombre": "Abrir", "sonido": "Abrir"}],
		},
		{"id": "silla", "nombre": "Silla", "material": "Mesa"},
	],
}


def test_traducir_datos_por_texto():
	traducido = i18n.traducir_datos(
		COMPLEMENTO, {"Mesa": "Table", "Silla": "Chair", "Abrir": "Open", "Muebles": "Furniture", "mobiliario": "NO"}
	)
	assert traducido["nombre"] == "Mobiliario", "lo que no tiene traducción se queda en español"
	assert traducido["id"] == "mobiliario", "los identificadores no se tocan"
	mesa, silla = traducido["objetos"]
	assert mesa["nombre"] == "Table"
	assert mesa["categoria"] == "Furniture"
	assert mesa["etiquetas"] == ["Table", "comedor"]
	assert mesa["acciones"][0]["nombre"] == "Open"
	assert mesa["acciones"][0]["sonido"] == "Abrir", "un nombre de sonido no es texto para el usuario"
	assert silla["nombre"] == "Chair"
	assert silla["material"] == "Mesa", "un identificador que coincide con una palabra no se traduce"


def test_traducir_datos_no_modifica_el_original():
	copia = json.loads(json.dumps(COMPLEMENTO))
	i18n.traducir_datos(COMPLEMENTO, {"Mesa": "Table"})
	assert COMPLEMENTO == copia


def test_traducir_datos_por_ruta_tiene_prioridad():
	traducciones = {
		"textos": {"Mesa": "Table", "Abrir": "Open"},
		"rutas": {
			"objetos/mesa/nombre": "Dining table",
			"objetos/mesa/acciones/abrir/nombre": "Open the drawer",
			"descripcion": "Home furniture",
		},
	}
	traducido = i18n.traducir_datos(COMPLEMENTO, traducciones)
	assert traducido["descripcion"] == "Home furniture"
	assert traducido["objetos"][0]["nombre"] == "Dining table"
	assert traducido["objetos"][0]["etiquetas"][0] == "Table"
	assert traducido["objetos"][0]["acciones"][0]["nombre"] == "Open the drawer"


def test_traducir_datos_mensajes_y_campos_propios():
	actividad = {"id": "a1", "mensajes": {"inicio": "Empezamos", "final": "Fin"}, "tipo": "Fin", "rotulo": "Fin"}
	traducido = i18n.traducir_datos(actividad, {"Empezamos": "Let's start", "Fin": "The end"})
	assert traducido["mensajes"] == {"inicio": "Let's start", "final": "The end"}
	assert traducido["tipo"] == "Fin" and traducido["rotulo"] == "Fin"
	con_campos = i18n.traducir_datos(actividad, {"Fin": "The end"}, campos={"rotulo"})
	assert con_campos["rotulo"] == "The end" and con_campos["mensajes"]["final"] == "Fin"


def test_traducir_datos_tolera_tablas_mal_formadas(caplog):
	assert i18n.traducir_datos(COMPLEMENTO, {}) == COMPLEMENTO
	assert i18n.traducir_datos(COMPLEMENTO, {"textos": ["no", "es", "un", "diccionario"]}) == COMPLEMENTO
	assert "mal formada" in caplog.text
	# Una traducción que no es texto se ignora en vez de romper el dato.
	assert i18n.traducir_datos(COMPLEMENTO, {"Mesa": 7})["objetos"][0]["nombre"] == "Mesa"


def test_traducciones_de_datos_desde_la_carpeta_del_complemento(tmp_path, catalogo_xx):
	carpeta = tmp_path / "mobiliario"
	(carpeta / "locales").mkdir(parents=True)
	(carpeta / "locales" / "xx.json").write_text(json.dumps({"Mesa": "Table"}), encoding="utf-8")
	assert i18n.cargar_traducciones_de_datos(carpeta) == {}, "en español no se carga nada"
	assert i18n.traducir_datos_de_carpeta(carpeta, COMPLEMENTO)["objetos"][0]["nombre"] == "Mesa"
	i18n.cambiar_idioma("xx")
	assert i18n.cargar_traducciones_de_datos(carpeta) == {"Mesa": "Table"}
	assert i18n.traducir_datos_de_carpeta(carpeta, COMPLEMENTO)["objetos"][0]["nombre"] == "Table"
	assert i18n.cargar_traducciones_de_datos(carpeta, "xx_YY") == {"Mesa": "Table"}, "la variante regional cae al idioma general"
	assert i18n.cargar_traducciones_de_datos(carpeta, "zz") == {}
	(carpeta / "locales" / "xx.json").write_text("{roto", encoding="utf-8")
	assert i18n.cargar_traducciones_de_datos(carpeta) == {}, "un JSON dañado no rompe la carga del complemento"


# ── Herramientas de tools/ ───────────────────────────────────────────────────

CODIGO = """
from app.core.i18n import _, _n, N_

TIPOS = {"puerta": N_("Puerta")}

def textos(n, nombre, tipo):
	# Traductores: saludo de la pantalla inicial.
	a = _("Hola, {nombre}").format(nombre=nombre)
	b = _n("Se encontró {n} premio", "Se encontraron {n} premios", n).format(n=n)
	c = _("Primera parte " "segunda")
	d = _(TIPOS[tipo])
	return a, b, c, d
"""


def test_extrae_las_funciones_del_proyecto():
	apariciones, problemas = extraer_cadenas.extraer_de_codigo(CODIGO, "app/prueba.py")
	textos = {aparicion.msgid: aparicion for aparicion in apariciones}
	assert set(textos) == {"Puerta", "Hola, {nombre}", "Se encontró {n} premio", "Primera parte segunda"}
	assert textos["Se encontró {n} premio"].msgid_plural == "Se encontraron {n} premios", "_n es el plural de este proyecto"
	assert textos["Hola, {nombre}"].comentarios == ["Traductores: saludo de la pantalla inicial."]
	# Traducir una variable marcada con N_ es el uso normal: no es un error.
	assert [problema.grave for problema in problemas] == [False]
	assert problemas[0].variable


def test_formatear_dentro_de_la_traduccion_es_un_error():
	codigo = 'a = _(f"Hola, {nombre}")\nb = _("%s pasos" % n)\nc = _("{n} pasos".format(n=n))\nd = _("")\n'
	apariciones, problemas = extraer_cadenas.extraer_de_codigo(codigo, "app/prueba.py")
	assert apariciones == []
	assert len(problemas) == 4 and all(problema.grave for problema in problemas)


def _proyecto_de_prueba(raiz: Path) -> None:
	(raiz / "app" / "core").mkdir(parents=True)
	(raiz / "app" / "core" / "i18n.py").write_text('DOMINIO = "entornolab"\n', encoding="utf-8")
	(raiz / "app" / "core" / "version.py").write_text('APP_VERSION = "9.9.9"\n', encoding="utf-8")
	(raiz / "app" / "prueba.py").write_text(CODIGO, encoding="utf-8")
	(raiz / "jugar.py").write_text('titulo = _("Jugar")\n', encoding="utf-8")


def test_flujo_completo_de_un_idioma_nuevo(tmp_path, monkeypatch, capsys):
	"""Extraer → crear el idioma → traducir → compilar → cargar con la aplicación → informe."""
	raiz = tmp_path / "proyecto"
	_proyecto_de_prueba(raiz)
	assert extraer_cadenas.main(["--raiz", str(raiz)]) == 0
	pot = raiz / "data" / "locales" / "entornolab.pot"
	assert pot.is_file()
	assert '"Jugar"' in pot.read_text(encoding="utf-8"), "también se extraen las cadenas de jugar.py"

	assert actualizar_po.main(["--raiz", str(raiz), "--nuevo", "xx"]) == 0
	po = raiz / "data" / "locales" / "xx" / "LC_MESSAGES" / "entornolab.po"
	catalogo = catalogo_po.leer_po(po)
	assert catalogo.metadatos()["Language"] == "xx"
	assert len(catalogo.entradas) == 5

	assert informe_traducciones.main(["--raiz", str(raiz), "--estricto"]) == 1, "con todo por traducir, el modo estricto falla"
	assert "Sin traducir: 5" in capsys.readouterr().out

	for entrada in catalogo.entradas:
		if entrada.msgid == "Hola, {nombre}":
			entrada.msgstr = "Hello, {nombre}"
		elif entrada.es_plural:
			entrada.msgstr_plural = {0: "{n} prize", 1: "{n} prizes"}
	catalogo.fijar_metadato("Plural-Forms", "nplurals=2; plural=(n != 1);")
	catalogo_po.escribir_po(catalogo, po)
	assert compilar_traducciones.main(["--raiz", str(raiz)]) == 0
	assert po.with_suffix(".mo").is_file()

	assert informe_traducciones.main(["--raiz", str(raiz), "--detalle"]) == 0
	salida = capsys.readouterr().out
	assert "Traducidas: 2" in salida and "Sin traducir: 3" in salida
	assert "«Puerta» (app/prueba.py:4)" in salida, "el detalle dice dónde está cada cadena pendiente"

	# La aplicación lo carga desde la carpeta data de ese proyecto.
	monkeypatch.setenv("APP_DATA_DIR", str(raiz / "data"))
	monkeypatch.delenv(i18n.VARIABLE_IDIOMA, raising=False)
	assert i18n.idiomas_disponibles() == ["es", "xx"]
	assert i18n.inicializar("xx") == "xx"
	assert i18n._("Hola, {nombre}") == "Hello, {nombre}"
	assert i18n._n("Se encontró {n} premio", "Se encontraron {n} premios", 2) == "{n} prizes"
	assert i18n._("Puerta") == "Puerta"


def test_actualizar_conserva_traducciones_y_marca_obsoletas(tmp_path):
	raiz = tmp_path / "proyecto"
	_proyecto_de_prueba(raiz)
	extraer_cadenas.main(["--raiz", str(raiz)])
	actualizar_po.main(["--raiz", str(raiz), "--nuevo", "xx"])
	po = raiz / "data" / "locales" / "xx" / "LC_MESSAGES" / "entornolab.po"
	catalogo = catalogo_po.leer_po(po)
	for entrada in catalogo.entradas:
		if entrada.msgid == "Puerta":
			entrada.msgstr = "Door"
		if entrada.msgid == "Jugar":
			entrada.msgstr = "Play"
	catalogo_po.escribir_po(catalogo, po)
	# El código cambia: desaparece «Jugar» y aparece una cadena nueva.
	(raiz / "jugar.py").write_text('titulo = _("Empezar a jugar ahora")\n', encoding="utf-8")
	extraer_cadenas.main(["--raiz", str(raiz)])
	assert actualizar_po.main(["--raiz", str(raiz), "--sin-aproximadas"]) == 0
	por_texto = {entrada.msgid: entrada for entrada in catalogo_po.leer_po(po).entradas}
	assert por_texto["Puerta"].msgstr == "Door", "las traducciones existentes se conservan"
	assert por_texto["Empezar a jugar ahora"].msgstr == "", "lo nuevo entra vacío"
	assert por_texto["Jugar"].obsoleta and por_texto["Jugar"].msgstr == "Play", "lo que desaparece no se pierde"


def test_catalogos_reales_del_proyecto_sin_errores():
	"""Los ``.po`` que se distribuyen no tienen traducciones que la aplicación vaya a descartar."""
	from tests.conftest import RAIZ

	archivos = sorted((RAIZ / "data" / "locales").glob("*/LC_MESSAGES/*.po"))
	for archivo in archivos:
		informe = informe_traducciones.analizar(archivo)
		assert not informe.fallo_lectura, informe.fallo_lectura
		assert informe.errores == [], f"{archivo}: {informe.errores[:3]}"
