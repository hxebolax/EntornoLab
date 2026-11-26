"""La traducción inglesa: catálogo completo y seguro, teclado sin choques en inglés, arranque y ayuda en inglés.

- El catálogo ``data/locales/en/LC_MESSAGES/entornolab.po`` traduce todos los
  mensajes de la plantilla, sin aproximadas ni errores, y conserva marcadores,
  letras de acceso, atajos de menú, saltos de línea y espacios de los bordes.
- Con la interfaz en inglés, la ventana principal y los diálogos principales
  pasan la revisión de teclado (``afirmar_teclado_correcto``): las letras de
  acceso no se repiten ni chocan con los menús de la barra.
- El Estudio y Jugar arrancan en inglés y el reproductor habla en inglés.
- F1 abre el manual en inglés (``data/docs/en``), y cada documento de usuario
  tiene su versión inglesa con un solo encabezado de nivel 1.
"""

# ruff: noqa: F811 - las fixtures importadas de _ui_seguimiento_util se usan como parámetros
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

wx = pytest.importorskip("wx")

from app.core import catalogo_po, documentacion, i18n  # noqa: E402
from app.core.config import Configuracion  # noqa: E402
from app.dominio import ejemplos  # noqa: E402
from app.ui import dialogos_herramientas, operaciones  # noqa: E402
from app.ui import esquema_preferencias as esquema  # noqa: E402
from app.ui import preferencias as ui_preferencias  # noqa: E402
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto, letra_de_acceso  # noqa: E402
from app.ui.contexto import ContextoEstudio  # noqa: E402
from app.ui.esquemas_elementos import ORDENES, esquema_de  # noqa: E402
from app.ui.formulario import DialogoFormulario  # noqa: E402
from tests._ui_estudio_util import cerrar_ventana, crear_ventana  # noqa: E402
from tests._ui_seguimiento_util import equipo, revisar, sin_voz  # noqa: E402, F401
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo  # noqa: E402
from tests.test_ui_estudio_ventana import TECLAS_PROPIAS, _un_elemento_de_cada_clase  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
LOCALES = RAIZ / "data" / "locales"
PO_INGLES = LOCALES / "en" / "LC_MESSAGES" / "entornolab.po"
PLANTILLA = LOCALES / "entornolab.pot"
DOCS = RAIZ / "data" / "docs"

#: Restos de español en un texto inglés: letras propias del español o palabras muy frecuentes.
_RE_ESPANOL = re.compile(r"[ñáéíóú¿¡]|\b(?:el|los|las|del|que|una|con|para|por|está|pulsa|elige)\b", re.IGNORECASE)


@pytest.fixture
def ingles(data_temporal):
	"""Interfaz en inglés con el catálogo real (copiado a la carpeta data de la prueba).

	``conftest`` devuelve el idioma al español al terminar cada prueba.
	"""
	shutil.copytree(LOCALES / "en", data_temporal / "locales" / "en")
	assert i18n.cambiar_idioma("en") is True
	assert i18n.idioma_actual() == "en"
	return data_temporal


# ── Catálogo ─────────────────────────────────────────────────────────────────


def test_catalogo_ingles_al_cien_por_cien_y_al_dia_con_la_plantilla():
	plantilla = {e.clave for e in catalogo_po.leer_po(PLANTILLA).entradas if not e.obsoleta}
	catalogo = catalogo_po.leer_po(PO_INGLES)
	activas = [e for e in catalogo.entradas if not e.obsoleta]
	assert {e.clave for e in activas} == plantilla, "pase tools/actualizar_po.py: el catálogo no está al día"
	assert [e.msgid for e in activas if not e.traducida] == []
	assert [e.msgid for e in activas if e.aproximada] == []
	resultado = catalogo_po.mensajes_compilables(catalogo)
	assert resultado.errores == []
	assert resultado.compiladas == len(plantilla)
	assert catalogo.metadatos().get("Language") == "en"


def _pares(entrada: catalogo_po.Entrada) -> list[tuple[str, str]]:
	if entrada.es_plural:
		return [(entrada.msgid, entrada.msgstr_plural[0]), (entrada.msgid_plural or "", entrada.msgstr_plural[1])]
	return [(entrada.msgid, entrada.msgstr)]


def _bordes(texto: str) -> tuple[int, int, bool, bool]:
	return (len(texto) - len(texto.lstrip(" ")), len(texto) - len(texto.rstrip(" ")), texto.startswith("\n"), texto.endswith("\n"))


def test_marcadores_letras_atajos_y_bordes_conservados():
	problemas: list[str] = []
	for entrada in catalogo_po.leer_po(PO_INGLES).entradas:
		if entrada.obsoleta:
			continue
		if entrada.es_plural:
			assert sorted(entrada.msgstr_plural) == [0, 1], entrada.msgid
			faltan = set(catalogo_po.marcadores(entrada.msgid_plural or "")) - set(catalogo_po.marcadores(entrada.msgstr_plural[1]))
			if faltan:
				problemas.append(f"{entrada.msgid!r}: el plural no usa {faltan}")
		elif sorted(catalogo_po.marcadores(entrada.msgid)) != sorted(catalogo_po.marcadores(entrada.msgstr)):
			problemas.append(f"{entrada.msgid!r}: marcadores distintos en {entrada.msgstr!r}")
		for original, traducido in _pares(entrada):
			if catalogo_po.aceleradores(original) != catalogo_po.aceleradores(traducido):
				problemas.append(f"{original!r}: número de & distinto en {traducido!r}")
			if catalogo_po.atajo_de_menu(original) != catalogo_po.atajo_de_menu(traducido):
				problemas.append(f"{original!r}: atajo tras el tabulador distinto en {traducido!r}")
			if _bordes(original) != _bordes(traducido):
				problemas.append(f"{original!r}: espacios o saltos de los bordes distintos en {traducido!r}")
			if original.count("\n") != traducido.count("\n"):
				problemas.append(f"{original!r}: número de saltos de línea distinto en {traducido!r}")
			letra = letra_de_acceso(traducido)
			if letra is not None and not re.fullmatch(r"[a-z0-9]", letra):
				problemas.append(f"{traducido!r}: letra de acceso «{letra}» difícil de pulsar")
	assert problemas == []


def test_sin_restos_de_espanol_en_el_catalogo():
	"""Ninguna traducción tiene letras del español, salvo nombres propios y préstamos admitidos."""
	admitidos = re.compile(r"café|piñata|guéridon|Benítez|Héctor|Español", re.IGNORECASE)
	restos = [
		traducido
		for entrada in catalogo_po.leer_po(PO_INGLES).entradas
		if not entrada.obsoleta
		for _original, traducido in _pares(entrada)
		if re.search(r"[ñáéíóú¿¡]", admitidos.sub("", traducido))
	]
	assert restos == []


def test_menus_traducidos_con_su_atajo(ingles):
	from app.ui.menus import MENUS

	titulos = [i18n._(titulo) for titulo, _entradas in MENUS]
	assert titulos == ["&File", "&Edit", "&Insert", "&View", "&Tools", "&Help"]
	assert i18n._("Guardar &como...\tCtrl+Shift+S") == "Save &as...\tCtrl+Shift+S"
	assert i18n.pgettext("tecla", "Inicio") == "Home" and i18n._("Inicio") == "Start"
	assert i18n.separador_decimal() == "."


# ── Teclado en inglés ────────────────────────────────────────────────────────


@pytest.fixture
def catalogo(tmp_path):
	return catalogo_de_prueba(tmp_path)


def test_teclado_de_la_ventana_principal_en_ingles(ingles, app_wx, monkeypatch, catalogo, dialogo_modal):
	ventana = crear_ventana(monkeypatch, catalogo, con_seguimiento=True)
	try:
		barra = ventana.GetMenuBar()
		titulos = [barra.GetMenuLabel(i) for i in range(barra.GetMenuCount())]
		assert titulos == ["&File", "&Edit", "&Insert", "&View", "&Students", "Su&pervision", "&Tools", "&Help"]
		afirmar_teclado_correcto(ventana, teclas_propias=TECLAS_PROPIAS)
		for clase, (entorno, id_elemento) in _un_elemento_de_cada_clase().items():
			ventana.contexto.abrir_documento(entorno)
			ventana.contexto.seleccionar(id_elemento)
			try:
				afirmar_teclado_correcto(ventana, teclas_propias=TECLAS_PROPIAS)
			except AssertionError as error:
				raise AssertionError(f"Con un elemento {clase} seleccionado:\n{error}") from error
		ventana.contexto.seleccionar("")
		afirmar_teclado_correcto(ventana, teclas_propias=TECLAS_PROPIAS)
	finally:
		cerrar_ventana(ventana)


def test_teclado_de_los_dialogos_de_orden_y_propiedades_en_ingles(ingles, app_wx, catalogo):
	contexto = ContextoEstudio(None, Configuracion(), catalogo)
	for clave, definicion in ORDENES.items():
		for entorno in (ejemplos.centro_dos_plantas(), ejemplos.barrio_ejemplo()):
			contexto.abrir_documento(entorno)
			if clave in ("mover", "girar", "medidas"):
				contexto.seleccionar(entorno.plantas[0].espacios[0].id)
			if definicion.requisito(contexto):
				continue
			dialogo = DialogoFormulario(None, definicion.titulo, definicion.campos(contexto), definicion.valores(contexto))
			try:
				afirmar_teclado_correcto(dialogo)
			except AssertionError as error:
				raise AssertionError(f"En el diálogo de «{clave}»:\n{error}") from error
			finally:
				dialogo.Destroy()
			break
	for clase, (entorno, id_elemento) in _un_elemento_de_cada_clase().items():
		_planta, elemento = operaciones.resolver(entorno, id_elemento)
		dialogo = DialogoFormulario(None, "Properties", esquema_de(elemento, entorno, catalogo), operaciones.valores_de(entorno, elemento, catalogo))
		try:
			afirmar_teclado_correcto(dialogo)
		except AssertionError as error:
			raise AssertionError(f"Propiedades de {clase}:\n{error}") from error
		finally:
			dialogo.Destroy()


def test_teclado_de_los_dialogos_de_herramientas_e_importar_en_ingles(ingles, app_wx, catalogo):
	from app.ui import dialogo_catalogo, dialogos_importar

	contexto = ContextoEstudio(None, Configuracion(), catalogo)
	contexto.abrir_documento(piso_minimo()[0])
	dialogos = [
		dialogos_herramientas.DialogoComprobar(None, contexto),
		dialogos_herramientas.DialogoMedir(None, contexto),
		dialogos_herramientas.DialogoBuscar(None, contexto),
		dialogos_herramientas.DialogoPropuesta(None, "Proposal", [("Bed", "1.5 × 2 m", "Against the north wall")]),
		dialogos_importar.DialogoInforme(None, "Report", "Imported:\n- 3 streets", True),
		dialogos_importar.crear_aviso_privacidad(None),
	]
	for dialogo in dialogos:
		try:
			afirmar_teclado_correcto(dialogo)
		except AssertionError as error:
			raise AssertionError(f"{type(dialogo).__name__}:\n{error}") from error
		finally:
			dialogo.Destroy()
	dialogo = dialogo_catalogo.DialogoCatalogo(None, catalogo)
	try:
		afirmar_teclado_correcto(dialogo, teclas_propias=["Ctrl+D"])
	finally:
		dialogo.Destroy()


def test_teclado_de_preferencias_en_ingles(ingles, app_wx, monkeypatch):
	monkeypatch.setattr(esquema, "motores", lambda: [("openal", "Binaural"), ("nulo", "No sound")])
	monkeypatch.setattr(esquema, "dispositivos", lambda: [("", "The Windows default")])
	monkeypatch.setattr(esquema, "segundas_salidas", lambda: [("", "None")])
	monkeypatch.setattr(esquema, "perfiles_hrtf", lambda: [("", "The built-in one")])
	monkeypatch.setattr(esquema, "lista_paquetes", lambda: [])
	monkeypatch.setattr(esquema, "voces_sapi", lambda: [("", "The Windows default")])
	monkeypatch.setattr(esquema, "idiomas", lambda: [("auto", "Windows language"), ("es", "Español"), ("en", "English")])
	dialogo = ui_preferencias.DialogoPreferencias(None, Configuracion())
	try:
		cuaderno = dialogo.cuaderno()
		for pagina in range(cuaderno.GetPageCount()):
			cuaderno.SetSelection(pagina)
			try:
				afirmar_teclado_correcto(dialogo)
			except AssertionError as error:
				raise AssertionError(f"Pestaña «{cuaderno.GetPageText(pagina)}»:\n{error}") from error
		etiquetas = {hijo.GetLabel() for hijo in dialogo.GetChildren() if isinstance(hijo, wx.Button)}
		assert "&OK" in etiquetas and "&Cancel" in etiquetas
	finally:
		dialogo.Destroy()


def test_teclado_de_las_ventanas_de_alumnos_en_ingles(ingles, equipo):
	from app.seguimiento.alumnos import Fichas
	from app.ui.seguimiento import alumnos as ui_alumnos

	base = equipo.abrir_base()
	luna = Fichas(base).alta("Luna")
	ventana = ui_alumnos.VentanaAlumnos(equipo.contexto, equipo.servicio)
	revisar(ventana)
	for dialogo in (ui_alumnos.DialogoAlumno(ventana, Fichas(base), luna), ui_alumnos.DialogoCalcularPaso(ventana)):
		try:
			revisar(dialogo)
		finally:
			dialogo.Destroy()


# ── Ayuda en inglés ──────────────────────────────────────────────────────────


def test_f1_abre_el_manual_del_idioma_de_la_interfaz(ingles):
	docs = ingles / "docs"
	(docs / "en").mkdir(parents=True)
	(docs / "manual.md").write_text("# Manual de EntornoLab\n", encoding="utf-8")
	(docs / "teclas.md").write_text("# Teclas\n", encoding="utf-8")
	(docs / "en" / "manual.md").write_text("# EntornoLab manual\n", encoding="utf-8")
	assert documentacion.ruta_documento(documentacion.MANUAL) == docs / "en" / "manual.md"
	assert documentacion.leer_documento(documentacion.MANUAL).startswith("# EntornoLab manual")
	# Lo que no está traducido se enseña en español; en español, siempre el original.
	assert documentacion.ruta_documento(documentacion.TECLAS) == docs / "teclas.md"
	assert documentacion.ruta_documento(documentacion.MANUAL, idioma="es") == docs / "manual.md"
	assert documentacion.ruta_documento(documentacion.MANUAL, idioma="en_GB") == docs / "en" / "manual.md"


def test_cada_documento_de_usuario_tiene_su_version_inglesa():
	espanoles = sorted(p.name for p in DOCS.glob("*.md"))
	ingleses = sorted(p.name for p in (DOCS / "en").glob("*.md"))
	assert ingleses == espanoles
	for ruta in sorted((DOCS / "en").glob("*.md")) + [RAIZ / "README_en.md"]:
		texto = ruta.read_text(encoding="utf-8")
		lineas = [linea for linea in texto.splitlines() if not linea.startswith("    ")]
		en_codigo = False
		niveles = []
		for linea in lineas:
			if linea.lstrip().startswith("```"):
				en_codigo = not en_codigo
			elif not en_codigo and (coincidencia := re.match(r"^(#{1,6})\s", linea)):
				niveles.append(len(coincidencia.group(1)))
		assert niveles.count(1) == 1, ruta.name
		assert all(b <= a + 1 for a, b in zip(niveles, niveles[1:], strict=False)), f"{ruta.name} salta niveles de encabezado"
		for destino in re.findall(r"(?<!!)\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)", texto):
			if not destino.startswith(("http", "mailto:")):
				assert (ruta.parent / destino).exists(), f"{ruta.name}: enlace roto a {destino}"
	readme = (RAIZ / "README.md").read_text(encoding="utf-8")
	assert "(README_en.md)" in readme.split("\n## ")[0], "el README español enlaza al inglés al principio"
	assert "(README.md)" in (RAIZ / "README_en.md").read_text(encoding="utf-8").split("\n## ")[0]


def test_novedades_en_ingles_se_entienden_como_registro_de_cambios():
	versiones = documentacion.leer_changelog((DOCS / "en" / "novedades.md").read_text(encoding="utf-8"))
	originales = documentacion.leer_changelog((DOCS / "novedades.md").read_text(encoding="utf-8"))
	assert [v.numero for v in versiones] == [v.numero for v in originales]


# ── Arranque en inglés ───────────────────────────────────────────────────────


def _entorno_ingles(carpeta: Path) -> dict[str, str]:
	shutil.copytree(LOCALES / "en", carpeta / "locales" / "en")
	entorno = dict(os.environ)
	entorno.update({"APP_IDIOMA": "en", "APP_DATA_DIR": str(carpeta), "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"})
	return entorno


def _idioma_del_registro(carpeta: Path, prefijo: str) -> list[str]:
	return [
		linea
		for registro in (carpeta / "logs").glob(f"{prefijo}*.log")
		for linea in registro.read_text(encoding="utf-8", errors="replace").splitlines()
		if "Idioma de la interfaz" in linea
	]


@pytest.mark.lento
@pytest.mark.parametrize(("programa", "prefijo"), [("main.py", "sesion_"), ("jugar.py", "jugar_")])
def test_arranque_en_ingles(tmp_path, programa, prefijo):
	carpeta = tmp_path / "datos_en"
	carpeta.mkdir()
	proceso = subprocess.run(
		[sys.executable, str(RAIZ / programa), "--comprobar-arranque"],
		cwd=RAIZ,
		env=_entorno_ingles(carpeta),
		capture_output=True,
		timeout=180,
		check=False,
	)
	assert proceso.returncode == 0, proceso.stderr.decode(errors="replace")[-2000:]
	lineas = _idioma_del_registro(carpeta, prefijo)
	assert lineas and all("Idioma de la interfaz: en" in linea for linea in lineas), lineas


@pytest.mark.lento
def test_el_reproductor_habla_en_ingles(tmp_path):
	"""Guion por el menú principal, la ayuda, «Learn the sounds» y las opciones: nada se dice en español."""
	carpeta = tmp_path / "datos_en"
	carpeta.mkdir()
	abajo = [{"accion": "menu_abajo", "fotogramas": 4}]
	guion = {
		"plazo": 20,
		"pasos": [
			{"fotogramas": 30},
			{"elegir": "Play as a guest", "fotogramas": 20},
			*abajo * 12,
			{"accion": "ayuda", "fotogramas": 10},
			{"elegir": "Learn the sounds", "fotogramas": 20},
			*abajo * 3,
			{"accion": "menu_aceptar", "fotogramas": 20},
			*abajo * 6,
			{"accion": "menu_atras", "fotogramas": 10},
			{"accion": "menu_atras", "fotogramas": 10},
			{"elegir": "Options", "fotogramas": 20},
			{"accion": "menu_aceptar", "fotogramas": 20},
			*abajo * 18,
			{"salir": True},
		],
	}
	ruta_guion = tmp_path / "guion.json"
	ruta_guion.write_text(json.dumps(guion), encoding="utf-8")
	informe = tmp_path / "informe.json"
	proceso = subprocess.run(
		[sys.executable, str(RAIZ / "jugar.py"), "--guion", str(ruta_guion), "--informe", str(informe)],
		cwd=RAIZ,
		env=_entorno_ingles(carpeta),
		capture_output=True,
		timeout=240,
		check=False,
	)
	datos = json.loads(informe.read_text(encoding="utf-8"))
	assert proceso.returncode == 0 and datos["correcto"], datos.get("fallos")
	dicho = [x["texto"] if isinstance(x, dict) else str(x) for x in datos["dicho"]]
	assert any("Main menu" in texto for texto in dicho) and any("Hello, guest" in texto for texto in dicho)
	assert len(dicho) > 30
	assert [texto for texto in dicho if _RE_ESPANOL.search(texto)] == []
