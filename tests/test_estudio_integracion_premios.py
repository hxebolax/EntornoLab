"""Integración del Estudio con las actividades: premios en el plano, audios en «Comprobar» y recursos al guardar.

- El plano dibuja los premios de la actividad elegida (``contexto.actividad_actual``)
  y se repinta al cambiar de actividad o de premios; lo mismo se lee en texto
  en la página «Descripción» y en la ayuda del plano (nada queda solo en el lienzo).
- «Comprobar el entorno» (F5) incluye los avisos de las actividades, con el
  audio de cada premio comprobado contra los recursos del paquete.
- Los recursos de audio añadidos al paquete sobreviven a guardar, abrir y
  volver a guardar.
"""

from __future__ import annotations

import pytest

from app.dominio.formato import cargar_paquete, guardar_paquete
from app.ui import dialogos_herramientas
from app.ui import modelo_plano as mp
from app.ui.contexto import ContextoEstudio
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo

from ._ui_estudio_util import cerrar_ventana, crear_ventana

AUDIO = b"RIFF\x24\x00\x00\x00WAVEfmt "


def _piso_con_cama(catalogo):
	"""Piso mínimo con una cama en el salón (para esconder un premio dentro)."""
	entorno, planta, salon, cocina = piso_minimo()
	cama = catalogo.crear_objeto("prueba/cama", 1.5, 1.5)
	cama.id = "cama-1"
	cama.nombre = "Cama"
	planta.objetos.append(cama)
	return entorno, planta, salon, cocina, cama


def _actividad(planta_id: str, audio: str | None = "sonidos/llaves.wav") -> dict:
	return {
		"id": "busca",
		"nombre": "Busca las llaves",
		"tipo": "busqueda",
		"premios": [
			{"id": "p1", "nombre": "Llaves", "planta": planta_id, "x": 4.0, "y": 3.0, "audio": audio},
			{"id": "p2", "nombre": "Cartera", "dentro_de": "cama-1"},
		],
	}


@pytest.fixture
def catalogo(tmp_path):
	return catalogo_de_prueba(tmp_path)


# ── Sin ventana ──────────────────────────────────────────────────────────────


def test_figuras_de_los_premios_sueltos_y_escondidos(catalogo):
	entorno, planta, _salon, _cocina, cama = _piso_con_cama(catalogo)
	figuras = [f for f in mp.figuras_de_planta(entorno, planta, catalogo, _actividad(planta.id)) if f.clase == "premio"]
	assert [(f.rotulo, f.puntos, f.tipo) for f in figuras] == [("Llaves", [(4.0, 3.0)], ""), ("Cartera", [(cama.x, cama.y)], "dentro")]
	# El que está dentro de un objeto que ya no existe no se dibuja (ni rompe el plano).
	planta.objetos.remove(cama)
	assert [f.rotulo for f in mp.figuras_de_planta(entorno, planta, catalogo, _actividad(planta.id)) if f.clase == "premio"] == ["Llaves"]


def test_describir_actividad_dice_donde_esta_cada_premio(catalogo):
	entorno, planta, _salon, _cocina, _cama = _piso_con_cama(catalogo)
	texto = mp.describir_actividad(entorno, _actividad(planta.id))
	lineas = texto.splitlines()
	assert lineas[0] == "Actividad elegida: «Busca las llaves»."
	assert "2 premios:" in lineas
	assert "Premio «Llaves»: planta Planta baja, en Salón, x 4 m, y 3 m." in lineas
	assert "Premio «Cartera»: dentro de Cama, planta Planta baja." in lineas
	assert mp.describir_actividad(entorno, None) == "" and mp.describir_actividad(None, _actividad(planta.id)) == ""


def test_comprobar_incluye_las_actividades_y_sus_audios(catalogo):
	entorno, planta, _salon, _cocina, _cama = _piso_con_cama(catalogo)
	contexto = ContextoEstudio(catalogo=catalogo)
	contexto.abrir_documento(entorno, actividades=[_actividad(planta.id)])
	avisos = dialogos_herramientas.avisos_del_documento(contexto)
	audio = [a for a in avisos if a.codigo == "audio_no_existe"]
	assert len(audio) == 1 and audio[0].mensaje.startswith("Actividad «Busca las llaves»: ") and "sonidos/llaves.wav" in audio[0].mensaje
	assert audio[0].elemento_id == "", "un premio no es un elemento del plano: «Ir al elemento» no promete nada"
	# Con el audio en el paquete el aviso desaparece.
	contexto.anadir_recurso("sonidos/llaves.wav", AUDIO)
	assert "audio_no_existe" not in {a.codigo for a in dialogos_herramientas.avisos_del_documento(contexto)}


def test_comprobar_con_una_validacion_antigua_sin_recursos(catalogo, monkeypatch):
	"""Si la validación instalada no admite ``recursos`` se llama sin ellos: se pierde solo esa comprobación."""
	import app.actividades as actividades

	original = actividades.validar_actividad
	llamadas: list[int] = []

	def antigua(datos, entorno, catalogo=None):
		llamadas.append(1)
		return original(datos, entorno, catalogo)

	monkeypatch.setattr(actividades, "validar_actividad", antigua)
	entorno, planta, _salon, _cocina, _cama = _piso_con_cama(catalogo)
	contexto = ContextoEstudio(catalogo=catalogo)
	contexto.abrir_documento(entorno, actividades=[_actividad(planta.id)])
	avisos = dialogos_herramientas.avisos_del_documento(contexto)
	assert llamadas == [1] and "audio_no_existe" not in {a.codigo for a in avisos}


def test_los_recursos_de_audio_sobreviven_a_guardar_abrir_y_volver_a_guardar(tmp_path, catalogo):
	entorno, planta, _salon, _cocina, _cama = _piso_con_cama(catalogo)
	ruta = tmp_path / "piso.elab"
	contexto = ContextoEstudio(catalogo=catalogo)
	contexto.abrir_documento(entorno, actividades=[_actividad(planta.id)])
	contexto.anadir_recurso("sonidos/llaves.wav", AUDIO)
	assert contexto.guardar(ruta)
	paquete = cargar_paquete(ruta)
	assert paquete.recursos == {"sonidos/llaves.wav": AUDIO}
	# Se abre otra vez, se cambia algo del entorno y se vuelve a guardar: el audio sigue.
	otro = ContextoEstudio(catalogo=catalogo)
	otro.abrir_documento(paquete.entorno, ruta, paquete.actividades, paquete.recursos)
	otro.ejecutar("renombrar", lambda: setattr(otro.entorno, "nombre", "Piso renombrado"))
	otro.deshacer()
	otro.rehacer()
	assert otro.guardar()
	again = cargar_paquete(ruta)
	assert again.recursos == {"sonidos/llaves.wav": AUDIO} and again.entorno.nombre == "Piso renombrado"
	assert again.actividades[0]["premios"][0]["audio"] == "sonidos/llaves.wav"


# ── Con la ventana principal ─────────────────────────────────────────────────


@pytest.fixture
def ventana(app_wx, monkeypatch, catalogo, dialogo_modal, voz_simulada):
	marco = crear_ventana(monkeypatch, catalogo)
	yield marco
	cerrar_ventana(marco)


def test_el_plano_pinta_y_describe_los_premios_de_la_actividad_elegida(ventana, catalogo):
	entorno, planta, _salon, _cocina, _cama = _piso_con_cama(catalogo)
	actividad = _actividad(planta.id)
	otra = {"id": "otra", "nombre": "Sin premios", "tipo": "exploracion", "premios": []}
	contexto = ventana.contexto
	contexto.abrir_documento(entorno, actividades=[actividad, otra])
	assert ventana.plano.premios_dibujados() == []
	# El panel de actividades elige una: el plano se repinta con sus premios.
	contexto.actividad_actual = actividad
	contexto.emitir("actividades_cambiadas")
	assert [f.rotulo for f in ventana.plano.premios_dibujados()] == ["Llaves", "Cartera"]
	assert "Premio «Llaves»" in ventana.plano.GetHelpText(), "Control+H en el plano lee también los premios"
	# Cambian los premios (el panel edita en el sitio y avisa): se repinta.
	actividad["premios"].append({"id": "p3", "nombre": "Gafas", "planta": planta.id, "x": 6.0, "y": 2.0})
	contexto.marcar_modificado("añadir un premio")
	assert [f.rotulo for f in ventana.plano.premios_dibujados()] == ["Llaves", "Cartera", "Gafas"]
	# La página «Descripción» (lo mismo en texto) también los dice, y se pone al día al cambiar.
	ventana.cuaderno.SetSelection(1)
	ventana._actualizar_descripcion()
	assert "Premio «Gafas»" in ventana.texto_descripcion.GetValue()
	contexto.actividad_actual = otra
	contexto.emitir("actividades_cambiadas")
	assert ventana.plano.premios_dibujados() == []
	assert "Gafas" not in ventana.texto_descripcion.GetValue() and "No tiene premios." in ventana.texto_descripcion.GetValue()
	# Al cerrar el documento no queda nada dibujado.
	contexto.cerrar_documento()
	assert ventana.plano.premios_dibujados() == [] and "Premio" not in ventana.plano.GetHelpText()


def test_ventana_abre_y_reguarda_sin_perder_el_audio(ventana, catalogo, tmp_path):
	entorno, planta, _salon, _cocina, _cama = _piso_con_cama(catalogo)
	ruta = tmp_path / "con-audio.elab"
	guardar_paquete(ruta, entorno, [_actividad(planta.id)], {"sonidos/llaves.wav": AUDIO})
	assert ventana.abrir_paquete(ruta)
	contexto = ventana.contexto
	contexto.anadir_recurso("sonidos/nuevo.ogg", b"OggS")
	contexto.ejecutar("renombrar", lambda: setattr(contexto.entorno, "nombre", "Otro nombre"))
	assert ventana.guardar()
	assert set(cargar_paquete(ruta).recursos) == {"sonidos/llaves.wav", "sonidos/nuevo.ogg"}
	# Abrir de nuevo y guardar sin cambios tampoco pierde nada.
	assert ventana.abrir_paquete(ruta)
	assert ventana.guardar()
	assert cargar_paquete(ruta).recursos == {"sonidos/llaves.wav": AUDIO, "sonidos/nuevo.ogg": b"OggS"}
	assert cargar_paquete(ruta).actividades[0]["premios"][0]["audio"] == "sonidos/llaves.wav"
