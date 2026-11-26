"""Abrir un paquete dañado o grande nunca deja el Estudio esperando.

Por qué: ``EntornoLab.exe --comprobar-arranque <paquete dañado>`` se quedaba
para siempre con un diálogo modal que nadie podía cerrar. En la comprobación
no se abre ningún diálogo y se sale con el código 3 (como el reproductor); en
uso normal el error se explica en un diálogo accesible que ofrece la copia
``.bak``, y un paquete grande se lee en segundo plano con progreso.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import wx

from app.dominio import ejemplos
from app.dominio.formato import guardar_paquete
from app.ui import ventana_principal as vp

from ._ui_estudio_util import boton, cerrar_ventana, crear_ventana

RAIZ = Path(__file__).resolve().parent.parent


def _roto(carpeta: Path) -> Path:
	ruta = carpeta / "roto.elab"
	ruta.write_bytes(b"PK\x03\x04 esto no es un paquete")
	return ruta


def test_sin_interaccion_no_abre_ningun_dialogo(app_wx, monkeypatch, data_temporal: Path) -> None:
	# Sin la fixture dialogo_modal, cualquier ShowModal hace fallar la prueba al momento.
	ventana = crear_ventana(monkeypatch)
	try:
		assert ventana.abrir_archivos([_roto(data_temporal)], interactivo=False) is False
		assert ventana.contexto.entorno is None
	finally:
		cerrar_ventana(ventana)


def test_danado_con_copia_ofrece_abrirla(app_wx, monkeypatch, dialogo_modal, data_temporal: Path) -> None:
	ruta = data_temporal / "casa.elab"
	guardar_paquete(ruta, ejemplos.vivienda_ejemplo())
	guardar_paquete(ruta, ejemplos.vivienda_ejemplo())  # la segunda vez deja la copia .bak
	ruta.write_bytes(b"PK\x03\x04 roto")
	ventana = crear_ventana(monkeypatch)
	try:
		dialogo_modal.responder(boton(0))
		assert ventana.abrir_paquete(ruta) is True
		assert "copia de seguridad" in dialogo_modal.ultimo.mensaje
		assert ventana.contexto.entorno is not None
	finally:
		cerrar_ventana(ventana)


def test_un_paquete_grande_se_lee_en_segundo_plano(app_wx, monkeypatch, dialogo_modal, data_temporal: Path) -> None:
	ruta = data_temporal / "casa.elab"
	guardar_paquete(ruta, ejemplos.vivienda_ejemplo())
	monkeypatch.setattr(vp, "TAMANO_PAQUETE_EN_SEGUNDO_PLANO", 1)
	ventana = crear_ventana(monkeypatch)
	try:
		assert ventana.abrir_paquete(ruta) is True
		assert any(mostrado.titulo == "Abrir" for mostrado in dialogo_modal.mostrados), "se esperó con el diálogo de progreso"
		assert ventana.contexto.entorno is not None
	finally:
		cerrar_ventana(ventana)
	assert wx.GetApp() is not None


@pytest.mark.lento
def test_comprobar_arranque_con_paquete_danado_sale_con_tres(data_temporal: Path) -> None:
	entorno = {**os.environ, "APP_DATA_DIR": str(data_temporal)}
	resultado = subprocess.run(
		[sys.executable, str(RAIZ / "main.py"), str(_roto(data_temporal)), "--comprobar-arranque"],
		capture_output=True,
		text=True,
		encoding="utf-8",
		errors="replace",
		timeout=120,
		env=entorno,
		cwd=str(RAIZ),
		check=False,
	)
	assert resultado.returncode == 3, resultado.stderr
	texto = "".join(ruta.read_text(encoding="utf-8") for ruta in sorted((data_temporal / "logs").glob("sesion_*.log")))
	assert "no se pudo abrir" in texto.lower()
