"""Pruebas del generador de formularios y de las utilidades de esquema (números, letras de acceso, validación)."""

from __future__ import annotations

import pytest
import wx

from app.ui import esquemas
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto
from app.ui.esquemas import ErrorCampo, c
from app.ui.formulario import DialogoFormulario, Formulario, pedir_formulario

CAMPOS = [
	c("nombre", "Nombre", obligatorio=True, ayuda="Como se llamará."),
	c("ancho", "Ancho", "metros", minimo=0.5, maximo=50, defecto=4.0),
	c("fondo", "Fondo", "metros", minimo=0.5, maximo=50, defecto=3.0),
	c(
		"tipo",
		"Tipo de espacio",
		"opcion",
		opciones=[("habitacion", "Habitación"), ("pasillo", "Pasillo")],
		defecto="habitacion",
		recarga=True,
	),
	c("largo", "Longitud del pasillo", "metros", si=lambda v: v.get("tipo") == "pasillo"),
	c("cerrado", "Con paredes", "si_no", defecto=True),
	c("notas", "Notas", "largo"),
	c("peldanos", "Peldaños", "entero", minimo=0, grupo="Más"),
	c("volumen", "Volumen", "deslizador", minimo=0, maximo=100, defecto=70, grupo="Más"),
	c("usos", "Usos", "casillas", opciones=[("a", "Aula"), ("b", "Baño")], grupo="Más"),
	c("fichero", "Fichero", "ruta_fichero", grupo="Más"),
	c("resumen", "Resumen", "solo_lectura", defecto="Texto fijo", grupo="Más"),
]


def test_numeros_con_coma_y_punto():
	assert esquemas.leer_numero("1,20") == pytest.approx(1.2)
	assert esquemas.leer_numero("1.20") == pytest.approx(1.2)
	assert esquemas.leer_numero(" 3,5 m ") == pytest.approx(3.5)
	assert esquemas.leer_numero("2 metros") == 2
	assert esquemas.leer_numero("") is None
	assert esquemas.leer_numero("7", decimal=False) == 7
	with pytest.raises(ValueError):
		esquemas.leer_numero("7,5", decimal=False)
	with pytest.raises(ValueError):
		esquemas.leer_numero("dos")
	assert esquemas.texto_numero(1.2) == "1,2"
	assert esquemas.texto_numero(3.0) == "3"
	assert esquemas.texto_numero(None) == ""


def test_letras_de_acceso_sin_repetir():
	usadas = {"a", "c"}
	etiquetas = [esquemas.con_letra(texto, usadas) for texto in ("Ancho", "Alto", "Acústica", "Con paredes")]
	letras = [esquemas.letra_de(etiqueta) for etiqueta in etiquetas]
	assert all(letras), etiquetas
	assert len(set(letras)) == len(letras)
	assert not {"a", "c"} & set(letras)
	assert esquemas.con_letra("&Suelo", usadas) == "&Suelo" and "s" in usadas


def test_validacion_de_campos():
	ancho = CAMPOS[1]
	assert esquemas.convertir_valor(ancho, "4,25") == pytest.approx(4.25)
	with pytest.raises(ErrorCampo) as error:
		esquemas.convertir_valor(ancho, "0,1")
	assert error.value.clave == "ancho" and "menor" in error.value.mensaje
	with pytest.raises(ErrorCampo):
		esquemas.convertir_valor(ancho, "ancho")
	with pytest.raises(ErrorCampo) as falta:
		esquemas.convertir_valor(CAMPOS[0], "  ")
	assert "Falta" in falta.value.mensaje


def test_formulario_etiquetas_antes_de_cada_control(marco):
	formulario = Formulario(marco, CAMPOS, {"nombre": "Cocina"})
	for clave, control in formulario.controles.items():
		if isinstance(control, (wx.TextCtrl, wx.Choice, wx.Slider, wx.CheckListBox)):
			hermanos = list(control.GetParent().GetChildren())
			anterior = hermanos[hermanos.index(control) - 1]
			assert isinstance(anterior, wx.StaticText), clave
			assert "&" in anterior.GetLabel(), clave
		assert control.GetHelpText(), f"{clave} no tiene ayuda para Control+H"
		assert not isinstance(control, (wx.SpinCtrlDouble, wx.SearchCtrl))
	valores = formulario.leer()
	assert valores["nombre"] == "Cocina" and valores["ancho"] == 4.0 and valores["cerrado"] is True
	assert "largo" not in valores, "un campo condicionado que no procede no se devuelve"


def test_formulario_campo_condicionado_y_recarga(marco, ayudas_wx):
	formulario = Formulario(marco, CAMPOS)
	assert "largo" not in formulario.controles
	formulario.fijar({"nombre": "Pasillo", "tipo": "pasillo", "largo": 6.5})
	assert "largo" in formulario.controles
	assert formulario.leer()["largo"] == pytest.approx(6.5)


def test_dialogo_formulario_teclado_y_validacion(app_wx, dialogo_modal):
	creados = []

	def validar(valores):
		if valores["nombre"] == "Repetido":
			raise ValueError("Ya existe.")
		creados.append(valores)
		return "producto"

	dialogo = DialogoFormulario(None, "Insertar habitación", CAMPOS, validar=validar)
	try:
		afirmar_teclado_correcto(dialogo)
		assert dialogo.GetEscapeId() == wx.ID_CANCEL
		assert dialogo.aceptar() is False, "falta el nombre"
		assert "Falta" in dialogo.ultimo_error
		dialogo.fijar({"nombre": "Repetido"})
		assert dialogo.aceptar() is False and dialogo.ultimo_error == "Ya existe."
		dialogo.fijar({"nombre": "Salón", "ancho": 5.5})
		assert dialogo.aceptar() is True
		assert dialogo.resultado["ancho"] == pytest.approx(5.5) and dialogo.producto == "producto"
	finally:
		dialogo.Destroy()
	assert creados and creados[0]["nombre"] == "Salón"


def test_pedir_formulario_con_dialogo_simulado(marco, dialogo_modal):
	dialogo_modal.responder(lambda d: (d.fijar({"nombre": "Baño", "fondo": "2,10"}), wx.ID_OK)[1])
	valores = pedir_formulario(marco, "Insertar", CAMPOS)
	assert valores is not None and valores["nombre"] == "Baño" and valores["fondo"] == pytest.approx(2.1)
	dialogo_modal.responder(wx.ID_CANCEL)
	assert pedir_formulario(marco, "Insertar", CAMPOS) is None
