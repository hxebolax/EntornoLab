"""Utilidades compartidas por las pruebas de ``app/ui/seguimiento`` (no es un fichero de pruebas).

- ``sin_voz``: sustituye la voz de ``app.ui.accesibilidad`` (la que usan las
  listas y Ctrl+H) para que las pruebas no hablen con un lector abierto.
- ``equipo``: contexto de prueba con su servicio, con la base, el fichero de
  acceso y la sala en la carpeta temporal de la prueba.
- ``casa()``: un entorno pequeño con un armario (contenedor) y un catálogo
  mínimo que lo declara.
- ``responder_con``: respuesta para ``dialogo_modal`` que rellena un diálogo
  de formulario y lo acepta.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

wx = pytest.importorskip("wx")

from app.dominio import edicion as ed  # noqa: E402
from app.dominio.catalogo import Catalogo, Complemento, DefObjeto  # noqa: E402
from app.dominio.modelo import Entorno, Objeto  # noqa: E402
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto  # noqa: E402
from app.ui.seguimiento import comun  # noqa: E402
from app.ui.seguimiento import servicio as mod_servicio  # noqa: E402
from app.ui.seguimiento.acceso import AccesoDatos  # noqa: E402
from app.ui.seguimiento.contexto import ContextoDePrueba  # noqa: E402
from app.ui.seguimiento.sala import GestorSala  # noqa: E402
from app.ui.seguimiento.servicio import ServicioSeguimiento  # noqa: E402

CONTRASENA = "clave de prueba 1"


@pytest.fixture
def sin_voz(monkeypatch: pytest.MonkeyPatch) -> list[str]:
	"""Lo que habría dicho la voz de la interfaz (listas, Ctrl+H), sin decirlo."""
	dicho: list[str] = []
	from app.ui.accesibilidad import voz

	monkeypatch.setattr(voz, "hablar", lambda texto, *args, **kwargs: dicho.append(str(texto)))
	monkeypatch.setattr(comun, "mostrar_al_abrir", False)
	return dicho


def casa() -> tuple[Entorno, Catalogo]:
	"""Vivienda de dos habitaciones con un armario (contenedor) y una mesa en el dormitorio."""
	entorno = ed.crear_entorno("Casa de prueba", "Para las pruebas del seguimiento.", "pruebas")
	planta = ed.crear_planta(entorno, "Planta baja")
	dormitorio = ed.crear_habitacion_rectangular(entorno, planta, "Dormitorio", 0.0, 0.0, 4.0, 4.0)
	cocina = ed.crear_habitacion_rectangular(entorno, planta, "Cocina", 4.0, 0.0, 4.0, 4.0)
	ed.anadir_puerta_entre(entorno, planta, dormitorio, cocina, ancho=0.9, estado="abierta")
	ed.anadir_puerta(entorno, planta, cocina, "este", ancho=0.9, nombre="Puerta de la calle", es_salida=True)
	armario = Objeto(id=entorno.nuevo_id("obj"), nombre="Armario", tipo="prueba/armario", x=0.6, y=3.4, ancho=1.0, fondo=0.6, alto=2.0)
	mesa = Objeto(id=entorno.nuevo_id("obj"), nombre="Mesa", tipo="prueba/mesa", x=2.0, y=1.0, ancho=1.2, fondo=0.8, alto=0.75)
	planta.objetos.extend([armario, mesa])
	ed.anadir_referencia(entorno, planta, "Felpudo", 7.5, 2.0, tipo="tactil")
	ed.fijar_inicio(entorno, planta, 6.0, 2.0, 270.0)
	catalogo = Catalogo()
	catalogo.anadir(
		Complemento(
			id="prueba",
			nombre="Prueba",
			objetos=[
				DefObjeto(id="armario", complemento="prueba", nombre="Armario", contenedor=True, estados=["cerrado", "abierto"]),
				DefObjeto(id="mesa", complemento="prueba", nombre="Mesa"),
			],
		)
	)
	return entorno, catalogo


@dataclass
class Equipo:
	"""Lo que necesita una prueba de interfaz del seguimiento."""

	contexto: ContextoDePrueba
	servicio: ServicioSeguimiento
	carpeta: Path

	def abrir_base(self):
		"""Crea la contraseña de prueba (o desbloquea) y devuelve la base."""
		acceso = self.servicio.acceso
		if acceso.base is not None:
			return acceso.base
		if acceso.hay_contrasena():
			return acceso.desbloquear(CONTRASENA)
		return acceso.crear_contrasena(CONTRASENA)


@pytest.fixture
def equipo(marco, tmp_path: Path, sin_voz, dialogo_modal) -> Iterator[Equipo]:
	"""Contexto de prueba con ventana, entorno de ejemplo y servicio en la carpeta temporal."""
	entorno, catalogo = casa()
	contexto = ContextoDePrueba(ventana=marco, entorno=entorno, catalogo=catalogo)
	acceso = AccesoDatos(
		contexto.configuracion,
		ruta_base=tmp_path / "db" / "entornolab.db",
		ruta_acceso=tmp_path / "config" / "seguimiento_acceso.json",
		carpeta_sesiones=tmp_path / "sessions",
	)
	sala = GestorSala(contexto.configuracion, carpeta_config=tmp_path / "config")
	servicio = ServicioSeguimiento(contexto, acceso=acceso, sala=sala)
	mod_servicio.poner_servicio(contexto, servicio)
	yield Equipo(contexto, servicio, tmp_path)
	mod_servicio.cerrar_servicio(contexto)


def responder_con(rellenar: Callable[[Any], None] | None = None) -> Callable[[Any], int]:
	"""Respuesta para ``dialogo_modal.responder``: rellena el diálogo y pulsa Aceptar.

	Devuelve ``wx.ID_OK`` si el diálogo aceptó y ``wx.ID_CANCEL`` si la
	validación lo impidió (como si después se hubiera cancelado).
	"""

	def respuesta(dialogo: Any) -> int:
		if rellenar is not None:
			rellenar(dialogo)
		return wx.ID_OK if dialogo.aceptar() else wx.ID_CANCEL

	return respuesta


def revisar(ventana: Any, teclas: tuple[str, ...] = ()) -> None:
	"""``afirmar_teclado_correcto`` con las teclas propias que declare la ventana."""
	propias = list(getattr(ventana, "teclas_propias", ())) + list(teclas)
	afirmar_teclado_correcto(ventana, teclas_propias=propias)


def elegir(control: Any, texto: str) -> None:
	"""Elige en un desplegable la opción que contiene ``texto`` y avisa como si lo hiciera el usuario."""
	for indice, opcion in enumerate(control.GetStrings()):
		if texto in opcion:
			control.SetSelection(indice)
			evento = wx.CommandEvent(wx.wxEVT_CHOICE, control.GetId())
			evento.SetEventObject(control)
			evento.SetInt(indice)
			control.GetEventHandler().ProcessEvent(evento)
			return
	raise AssertionError(f"No hay ninguna opción con «{texto}» en {control.GetStrings()}")
