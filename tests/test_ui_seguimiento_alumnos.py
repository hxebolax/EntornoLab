"""Ventana de alumnos: alta y edición con campos cifrados de verdad, borrado con confirmación, recompensas y exportación."""

# ruff: noqa: F811 - las fixtures importadas de _ui_seguimiento_util se usan como parámetros
from __future__ import annotations

import zipfile

import pytest

wx = pytest.importorskip("wx")

from app.seguimiento import recompensas, sesiones  # noqa: E402
from app.seguimiento.alumnos import Fichas  # noqa: E402
from app.ui.seguimiento import alumnos as ui  # noqa: E402
from app.ui.seguimiento import presentador_alumnos as pres  # noqa: E402
from tests._seguimiento_util import documento_sesion  # noqa: E402
from tests._ui_seguimiento_util import equipo, responder_con, revisar, sin_voz  # noqa: E402, F401


# ── Lógica ───────────────────────────────────────────────────────────────────


def test_calcular_paso():
	assert pres.calcular_paso("10", "14") == 0.71
	assert pres.calcular_paso("7,5", "10") == 0.75
	for metros, pasos in (("", "10"), ("10", "0"), ("10", "abc"), ("10", "2"), ("10", "100"), ("10", "12,5")):
		with pytest.raises(ValueError):
			pres.calcular_paso(metros, pasos)


def test_leer_en_rango_da_mensajes_concretos():
	assert pres.leer_en_rango("0,7", 0.25, 1.5, "Paso") == 0.7
	assert pres.leer_en_rango("", 1900, 2100, "Año", entero=True, vacio=True) is None
	with pytest.raises(ValueError, match="entre"):
		pres.leer_en_rango("3", 0.25, 1.5, "Paso")
	with pytest.raises(ValueError, match="número"):
		pres.leer_en_rango("dos", 0.25, 1.5, "Paso")


def test_alias_coincide_sin_mayusculas_ni_espacios():
	assert pres.alias_coincide("  luna  ", "Luna")
	assert not pres.alias_coincide("lun", "Luna")


def test_lista_de_trabajo_se_guarda_en_los_ajustes(equipo):
	base = equipo.abrir_base()
	fichas = Fichas(base)
	luna = fichas.alta("Luna", ajustes={"paso_m": 0.6})
	actividad = {"id": "buscar", "nombre": "Buscar la llave"}
	luna = pres.asignar(fichas, luna, equipo.contexto.entorno, actividad, "casa.elab")
	assert pres.tiene_asignada(luna, equipo.contexto.entorno.id, "buscar")
	assert luna.ajustes["paso_m"] == 0.6
	luna = pres.asignar(fichas, luna, equipo.contexto.entorno, actividad, "casa.elab")
	assert len(pres.lista_de_trabajo(luna)) == 1
	luna = pres.quitar_de_lista(fichas, luna, 0)
	assert pres.lista_de_trabajo(luna) == []


# ── Ficha ────────────────────────────────────────────────────────────────────


def test_teclado_de_la_ventana_y_sus_dialogos(equipo):
	base = equipo.abrir_base()
	fichas = Fichas(base)
	luna = fichas.alta("Luna")
	ventana = ui.VentanaAlumnos(equipo.contexto, equipo.servicio)
	revisar(ventana)
	for dialogo in (
		ui.DialogoAlumno(ventana, fichas, luna),
		ui.DialogoAlumno(ventana, fichas, None),
		ui.DialogoCalcularPaso(ventana),
		ui.DialogoBorrarAlumno(ventana, luna, pres.resumen_de_borrado(base, luna)),
		ui.DialogoRecompensas(ventana, base, luna),
		ui.DialogoListaTrabajo(ventana, fichas, luna),
	):
		try:
			revisar(dialogo)
		finally:
			dialogo.Destroy()
	menu = ventana._menu()
	assert menu is not None and menu.GetMenuItemCount() == 9
	menu.Destroy()


def test_alta_guarda_cifrado_el_nombre_real_y_las_notas(equipo, dialogo_modal):
	base = equipo.abrir_base()
	ventana = ui.VentanaAlumnos(equipo.contexto, equipo.servicio)

	def rellenar(dialogo):
		dialogo.alias.SetValue("  Luna ")
		dialogo.nombre_real.SetValue("Nombre Reservadísimo")
		dialogo.notas.SetValue("Nota confidencial")
		dialogo.ano.SetValue("2015")
		dialogo.perfil.SetSelection(0)
		dialogo.estilo.SetSelection(0)
		dialogo.paso.SetValue("0,55")
		dialogo.giro.SetValue("45")
		dialogo.unidad.SetSelection(1)

	dialogo_modal.responder(responder_con(rellenar))
	ventana.nuevo()
	luna = Fichas(base).por_alias("Luna")
	assert luna is not None
	assert (luna.nombre_real, luna.notas, luna.ano_nacimiento) == ("Nombre Reservadísimo", "Nota confidencial", 2015)
	assert (luna.perfil, luna.estilo) == ("baston", "infantil")
	assert luna.ajustes["paso_m"] == 0.55 and luna.ajustes["giro_grados"] == 45.0 and luna.ajustes["unidad"] == "pasos"
	assert ventana.lista.valores_fila(0)[:3] == ["Luna", "Bastón", "Infantil"]
	assert any("Luna creado" in texto for texto in equipo.contexto.anunciados)
	# En el fichero, el alias está en claro y lo personal no.
	equipo.servicio.acceso.bloquear()
	crudo = (equipo.carpeta / "db" / "entornolab.db").read_bytes()
	assert b"Luna" in crudo
	assert "Nombre Reservadísimo".encode() not in crudo and b"Nota confidencial" not in crudo


def test_validacion_de_la_ficha_lleva_el_foco_al_campo_erroneo(equipo, dialogo_modal):
	base = equipo.abrir_base()
	dialogo = ui.DialogoAlumno(equipo.contexto.ventana, Fichas(base))
	assert dialogo.validar()[1] is dialogo.alias
	dialogo.alias.SetValue("Sol")
	dialogo.paso.SetValue("7")
	problema = dialogo.validar()
	assert problema is not None and problema[1] is dialogo.paso and "entre" in problema[0]
	# Aceptar con el error: se muestra el mensaje y se cambia a la pestaña del campo.
	dialogo.cuaderno.SetSelection(0)
	assert dialogo.aceptar() is False
	assert dialogo.cuaderno.GetSelection() == 1
	assert Fichas(base).por_alias("Sol") is None
	dialogo.paso.SetValue("0,7")
	dialogo.ano.SetValue("1800")
	assert dialogo.validar()[1] is dialogo.ano
	dialogo.ano.SetValue("")
	assert dialogo.aceptar() is True
	assert Fichas(base).por_alias("Sol").ano_nacimiento is None
	dialogo.Destroy()


def test_editar_conserva_la_lista_de_trabajo_y_rechaza_un_alias_repetido(equipo, dialogo_modal):
	base = equipo.abrir_base()
	fichas = Fichas(base)
	fichas.alta("Sol")
	luna = fichas.alta("Luna", nombre_real="Ana")
	luna = pres.asignar(fichas, luna, equipo.contexto.entorno, {"id": "a1", "nombre": "Actividad"})
	dialogo = ui.DialogoAlumno(equipo.contexto.ventana, fichas, luna)
	assert dialogo.nombre_real.GetValue() == "Ana"
	dialogo.alias.SetValue("Sol")
	assert dialogo.aceptar() is False
	dialogo.alias.SetValue("Luna llena")
	assert dialogo.aceptar() is True
	cambiada = fichas.por_alias("Luna llena")
	assert cambiada.nombre_real == "Ana" and len(pres.lista_de_trabajo(cambiada)) == 1
	dialogo.Destroy()


def test_calcular_paso_escribe_el_resultado_en_la_ficha(equipo, dialogo_modal):
	base = equipo.abrir_base()
	dialogo = ui.DialogoAlumno(equipo.contexto.ventana, Fichas(base))
	dialogo_modal.responder(responder_con(lambda d: d.pasos.SetValue("16")))
	dialogo.calcular_paso()
	assert dialogo.paso.GetValue() == "0,62"
	dialogo.Destroy()


# ── Lista ────────────────────────────────────────────────────────────────────


def test_buscar_archivar_y_columnas_de_sesiones(equipo):
	base = equipo.abrir_base()
	fichas = Fichas(base)
	luna = fichas.alta("Luna")
	fichas.alta("Sol")
	sesiones.guardar_sesion(base, luna.id, documento_sesion("c" * 32, "Luna"))
	ventana = ui.VentanaAlumnos(equipo.contexto, equipo.servicio)
	assert ventana.lista.numero_filas() == 2
	assert ventana.lista.valores_fila(0)[4] == "1" and ventana.lista.valores_fila(1)[3] == "Ninguna"
	ventana.buscar.SetValue("so")
	assert [a.alias for a in ventana.alumnos] == ["Sol"]
	ventana.archivar()
	assert ventana.alumnos == []
	ventana.archivados.SetValue(True)
	ventana.recargar()
	assert ventana.lista.valores_fila(0)[5] == "Archivado"
	ventana.archivar()
	assert fichas.por_alias("Sol").archivado is False


def test_borrar_exige_escribir_el_alias_y_borra_todo(equipo, dialogo_modal):
	base = equipo.abrir_base()
	fichas = Fichas(base)
	luna = fichas.alta("Luna", nombre_real="Ana")
	sesiones.guardar_sesion(base, luna.id, documento_sesion("d" * 32, "Luna"))
	base.copia_seguridad("prueba")
	ventana = ui.VentanaAlumnos(equipo.contexto, equipo.servicio)

	def mal(dialogo):
		assert "NO SE PUEDE DESHACER" in dialogo.aviso.GetValue()
		assert "copia de seguridad" in dialogo.aviso.GetValue()
		dialogo.confirmacion.SetValue("otro alias")

	dialogo_modal.responder(responder_con(mal), wx.ID_OK)
	ventana.borrar()
	assert fichas.por_alias("Luna") is not None
	assert any("No se ha borrado nada" in texto for texto in equipo.contexto.anunciados)

	dialogo_modal.responder(responder_con(lambda d: d.confirmacion.SetValue("luna")))
	ventana.borrar()
	assert fichas.por_alias("Luna") is None
	assert sesiones.listar(base) == []
	assert ventana.lista.numero_filas() == 0
	assert all("prueba" not in copia.name for copia in base.copias())
	assert any("borrado por completo" in texto for texto in equipo.contexto.anunciados)


def test_recompensas_dar_y_quitar(equipo):
	base = equipo.abrir_base()
	luna = Fichas(base).alta("Luna")
	recompensas.registrar(base, luna.id, "estrella", "Primera estrella")
	dialogo = ui.DialogoRecompensas(equipo.contexto.ventana, base, luna)
	assert "1 estrella." in dialogo.resumen.GetValue()
	dialogo.tipo.SetSelection(1)
	dialogo.nombre.SetValue("Medalla del explorador")
	dialogo.dar()
	assert dialogo.lista.numero_filas() == 2
	assert "Medalla del explorador" in dialogo.resumen.GetValue()
	dialogo.lista.enfocar_fila(0, anunciar=False)
	dialogo.quitar()
	assert [r.tipo for r in recompensas.de_alumno(base, luna.id)] == ["medalla"]
	dialogo.Destroy()


def test_exportar_escribe_un_zip_con_todo(equipo, dialogo_modal, monkeypatch):
	base = equipo.abrir_base()
	luna = Fichas(base).alta("Luna", nombre_real="Ana")
	sesiones.guardar_sesion(base, luna.id, documento_sesion("e" * 32, "Luna"))
	ventana = ui.VentanaAlumnos(equipo.contexto, equipo.servicio)
	destino = equipo.carpeta / "luna.zip"
	monkeypatch.setattr(ui, "pedir_ruta_guardar", lambda *args, **kwargs: destino)
	ventana.exportar()
	with zipfile.ZipFile(destino) as paquete:
		nombres = set(paquete.namelist())
	assert {"LEEME.txt", "alumno.json", "sesiones.csv"} <= nombres
	assert "NO está cifrado" in dialogo_modal.ultimo.textos[0] or any("NO está cifrado" in t for t in dialogo_modal.ultimo.textos)


def test_bloquear_cierra_la_base_y_la_ventana(equipo, ayudas_wx):
	equipo.abrir_base()
	ventana = ui.VentanaAlumnos(equipo.contexto, equipo.servicio)
	equipo.servicio.ventanas["alumnos"] = ventana
	ventana.bloquear()
	assert equipo.servicio.acceso.base is None
	assert "alumnos" not in equipo.servicio.ventanas
