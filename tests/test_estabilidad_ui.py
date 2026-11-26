"""Cierre nativo de las pruebas de interfaz: temporizadores que sobreviven a su ventana.

Historia: una vez se vio «Windows fatal exception: code 0xc0000374» (corrupción del montículo) al
cerrar una prueba de interfaz. En las repeticiones salía siempre al destruir la ventana de
``test_sincronia_arbol_lista_plano_y_propiedades``, y solo si antes se había abierto el catálogo de
objetos. Con cdb la pila nativa era ``WM_TIMER`` → ``wxTimerImpl::SendEvent`` →
``SafelyProcessEvent`` sobre un dueño ya liberado (a veces «access violation», a veces 0xc0000374).

Causa: ``DialogoCatalogo`` arranca ``_temporizador_miniatura`` (250 ms, una vez) al enfocar una fila
y lo para en su manejador de ``EVT_WINDOW_DESTROY`` solo ``if evento.GetEventObject() is self``.
Esa comparación NUNCA es cierta al destruir una ventana creada desde Python: sip desliga la
envoltura antes de que wx envíe ``wxEVT_DESTROY`` y ``GetEventObject()`` devuelve una envoltura nueva
(``wx.Window``). El temporizador sigue en marcha con el diálogo ya liberado y, en cuanto alguien
procesa mensajes (la siguiente prueba al cerrar su ventana), wx llama a memoria liberada. Si la
envoltura de Python del diálogo la recoge antes el recolector, el temporizador se borra y no pasa
nada: por eso era intermitente. El mismo patrón está en ``dialogo_complementos.py`` y en
``accesibilidad/progreso.py``.
"""

from __future__ import annotations

import os
import traceback
import warnings

import pytest

wx = pytest.importorskip("wx")

from tests import _ui_estudio_util as util  # noqa: E402
from tests import test_ui_estudio_ventana as pv  # noqa: E402
from tests.conftest import procesar_eventos  # noqa: E402
from tests.test_ui_estudio_ventana import catalogo, ventana  # noqa: E402,F401 - fixtures de la ventana principal

VECES = int(os.environ.get("APP_ESTRES_VECES", "2"))
SECUENCIA = ("vivienda", "error", "no_cabe", "sincronia")


# ── Lo que hace wxPython (la raíz del fallo) ─────────────────────────────────


def test_en_evt_window_destroy_el_objeto_del_evento_no_es_self(app_wx):
	"""Documenta el comportamiento de wxPython 4.3 que rompe la guarda ``GetEventObject() is self``.

	Si una versión futura lo cambia, esta prueba lo dirá; la forma segura de reconocer la
	destrucción propia es comparar el identificador (``evento.GetId() == id guardado``).
	"""
	vistos: list[tuple[bool, bool]] = []

	class Dialogo(wx.Dialog):
		def __init__(self) -> None:
			super().__init__(None, title="prueba")
			self.id_propio = self.GetId()
			self.Bind(wx.EVT_WINDOW_DESTROY, self.al_destruir)

		def al_destruir(self, evento: wx.WindowDestroyEvent) -> None:
			vistos.append((evento.GetEventObject() is self, evento.GetId() == self.id_propio))
			evento.Skip()

	dialogo = Dialogo()
	dialogo.Destroy()
	procesar_eventos(lambda: bool(vistos), 2)
	assert vistos, "no llegó EVT_WINDOW_DESTROY"
	es_self, por_id = vistos[0]
	assert por_id is True
	assert es_self is False, "wxPython ya devuelve la propia envoltura: la guarda «is self» vuelve a funcionar"


def test_el_catalogo_para_sus_temporizadores_al_destruirse(app_wx, catalogo, dialogo_modal):  # noqa: F811
	from app.ui.contexto import ContextoEstudio
	from app.ui.dialogo_catalogo import DialogoCatalogo

	marco = wx.Frame(None)
	contexto = ContextoEstudio(ventana=marco, catalogo=catalogo)
	dialogo = DialogoCatalogo(marco, catalogo, None, contexto)
	temporizadores = [dialogo._temporizador, dialogo._temporizador_miniatura]
	try:
		# Abrir el catálogo ya enfoca una fila y arranca la miniatura (250 ms).
		if not any(t.IsRunning() for t in temporizadores):
			temporizadores[1].StartOnce(250)
		dialogo.Destroy()
		marco.Destroy()
		procesar_eventos(lambda: not dialogo and not marco, 2)
		assert not dialogo, "el diálogo debería estar destruido"
		en_marcha = [t for t in temporizadores if t.IsRunning()]
		assert not en_marcha, "un temporizador del catálogo sigue en marcha con el diálogo ya liberado"
	finally:
		# Se paran aquí en cualquier caso: si no, dispararían más tarde sobre memoria liberada y
		# cerrarían el proceso de pruebas.
		for temporizador in temporizadores:
			temporizador.Stop()


# ── Estrés: la secuencia en la que se vio el cierre ──────────────────────────


class VigilanciaTemporizadores:
	"""Conserva cada ``wx.Timer`` con dueño y detecta los que siguen en marcha con el dueño destruido.

	Se guardan referencias fuertes a propósito: así el recolector no puede esconder el fallo
	borrando el temporizador antes de tiempo.
	"""

	def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
		self.creados: list[tuple[object, object, str]] = []
		clase_original = wx.Timer
		vigilancia = self

		class TimerVigilado(clase_original):  # type: ignore[misc, valid-type]
			"""Igual que ``wx.Timer``, pero apunta su dueño y dónde se creó."""

			def __init__(temporizador, *args, **kwargs) -> None:
				super().__init__(*args, **kwargs)
				dueno = args[0] if args else kwargs.get("owner")
				vigilancia.creados.append((temporizador, dueno, "".join(traceback.format_stack(limit=8)[:-1])))

		monkeypatch.setattr(wx, "Timer", TimerVigilado)

	def parar_huerfanos(self) -> list[str]:
		"""Para los temporizadores en marcha cuyo dueño ya no existe y dice dónde se crearon."""
		huerfanos = []
		for temporizador, dueno, pila in self.creados:
			if isinstance(dueno, wx.Window) and not dueno and temporizador.IsRunning():
				temporizador.Stop()
				huerfanos.append(f"{type(dueno).__name__}; creado en:\n{pila}")
		return huerfanos


@pytest.fixture
def vigilancia(monkeypatch: pytest.MonkeyPatch):
	"""Tras cada ronda de eventos del cierre, ningún temporizador puede quedar con su ventana liberada."""
	vigilancia = VigilanciaTemporizadores(monkeypatch)
	original = util.procesar_eventos
	encontrados: list[str] = []

	def procesar_vigilado(condicion=lambda: False, segundos: float = 3.0) -> bool:
		encontrados.extend(vigilancia.parar_huerfanos())
		resultado = original(condicion, segundos)
		encontrados.extend(vigilancia.parar_huerfanos())
		return resultado

	monkeypatch.setattr(util, "procesar_eventos", procesar_vigilado)
	yield vigilancia
	encontrados.extend(vigilancia.parar_huerfanos())
	for temporizador, _dueno, _pila in vigilancia.creados:
		temporizador.Stop()
	if encontrados:
		# El fallo en sí lo marca test_el_catalogo_para_sus_temporizadores_al_destruirse; aquí se avisa
		# y se garantiza que el proceso no se cierra (que es lo que prueba esta secuencia).
		warnings.warn("Temporizador en marcha con su ventana liberada; se ha parado. " + encontrados[0], stacklevel=1)


@pytest.mark.lento
@pytest.mark.parametrize("paso", SECUENCIA)
@pytest.mark.parametrize("vuelta", range(VECES))
def test_secuencia_que_cerraba_con_el_monticulo_corrupto(vigilancia, ventana, dialogo_modal, voz_simulada, tmp_path, paso, vuelta):  # noqa: F811
	"""Las cuatro primeras pruebas de la ventana principal, en bucle, sin que el proceso se cierre.

	Antes de vigilar los temporizadores, 15 vueltas cerraban el proceso en las 4 de 4 ejecuciones
	(en la tercera o cuarta vuelta). La vigilancia los para y lo apunta.
	"""
	if paso == "vivienda":
		pv.test_crear_vivienda_solo_con_menus_deshacer_guardar_y_reabrir(ventana, dialogo_modal, voz_simulada, tmp_path)
	elif paso == "error":
		pv.test_un_error_de_edicion_deja_el_dialogo_y_el_entorno_como_estaban(ventana, dialogo_modal)
	elif paso == "no_cabe":
		pv.test_objeto_que_no_cabe_no_se_coloca(ventana, dialogo_modal)
	else:
		pv.test_sincronia_arbol_lista_plano_y_propiedades(ventana)
