"""Ventana de informes: de una sesión, comparación, evolución, examen y evaluación real frente a virtual.

La vista previa es texto en un campo de solo lectura (lo que mejor se lee
con un lector de pantalla); el mismo informe se guarda en texto, HTML o CSV,
que dicen lo mismo. Todos terminan con el aviso de que son descriptivos.
"""

from __future__ import annotations

import logging
import webbrowser
from typing import Any

import wx

from app.core.i18n import _
from app.seguimiento import informes
from app.seguimiento.alumnos import Alumno, Fichas
from app.seguimiento.base import ErrorBase
from app.ui.accesibilidad.dialogos import mostrar_error
from app.ui.seguimiento import presentador_registros as pres
from app.ui.seguimiento import textos
from app.ui.seguimiento.comun import (
	VentanaSeguimiento,
	crear_boton,
	crear_desplegable,
	crear_lista,
	crear_texto,
	pedir_ruta_guardar,
	poner_opciones,
)
from app.ui.seguimiento.contexto import anunciar

log = logging.getLogger(__name__)


class VentanaInformes(VentanaSeguimiento):
	"""Elige el informe, lo enseña en texto y lo guarda en el formato que se quiera."""

	CLAVE = "informes"

	def __init__(self, contexto: Any, servicio: Any, alumno_id: int | None = None, sesion_id: str | None = None) -> None:
		super().__init__(contexto, servicio, _("Informes"), (940, 720))
		self.base = servicio.base
		self.informe: informes.Informe | None = None
		self._alumnos: list[Alumno] = []
		self._sesiones: list[dict[str, Any]] = []
		self._tipos = list(pres.TIPOS_INFORME)
		letras = self.letras
		self.tipo = crear_desplegable(
			self.panel,
			letras.poner(_("Tipo de informe:")),
			[textos.nombre(pres.TIPOS_INFORME, tipo) for tipo in self._tipos],
			sizer=self.sizer,
			ayuda=_(
				"De una sesión: todas sus medidas. Comparación: varias sesiones marcadas, una junto a otra. Evolución: todas las del alumno "
				"en el tiempo. Examen: las puntuaciones primero. Real frente a virtual: el cuaderno de evaluación real junto a las sesiones."
			)
			+ " "
			+ _(pres.AYUDA_INFORMES),
		)
		self.alumno = crear_desplegable(self.panel, letras.poner(_("Alumno:")), sizer=self.sizer, ayuda=_("El alumno del informe."))
		self.lista = crear_lista(
			self.panel,
			letras.poner(_("Sesiones del alumno:")),
			pres.columnas_sesiones(),
			getattr(contexto, "configuracion", None),
			sizer=self.sizer,
			alto=140,
			proporcion=0,
			con_casillas=True,
			estilo=wx.LC_REPORT | wx.LC_SINGLE_SEL,
			ayuda=_(
				"Para el informe de una sesión o de un examen se usa la sesión elegida. Para la comparación, marque con la barra "
				"espaciadora las sesiones que quiere comparar. La evolución y el informe real frente a virtual usan todas."
			),
		)
		fila = self.fila_botones()
		crear_boton(
			self.panel,
			letras.poner(_("Generar la vista previa")),
			self.generar,
			_("Construye el informe elegido y lo enseña debajo, en texto."),
			fila,
		)
		self.vista = crear_texto(
			self.panel,
			letras.poner(_("Vista previa del informe:")),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=260,
			ancho=880,
			proporcion=1,
			ayuda=_("El informe en texto. Recórralo con las flechas; puede seleccionarlo y copiarlo.") + " " + _(pres.AYUDA_INFORMES),
		)
		fila = self.fila_botones()
		crear_boton(
			self.panel,
			letras.poner(_("Guardar en texto...")),
			lambda: self.guardar("texto"),
			_("Guarda el informe en un fichero de texto."),
			fila,
		)
		crear_boton(
			self.panel,
			letras.poner(_("Guardar en HTML...")),
			lambda: self.guardar("html"),
			_("Guarda el informe como página web, con encabezados y tablas accesibles."),
			fila,
		)
		crear_boton(
			self.panel,
			letras.poner(_("Guardar en CSV...")),
			lambda: self.guardar("csv"),
			_("Guarda las tablas del informe para abrirlas en una hoja de cálculo."),
			fila,
		)
		crear_boton(
			self.panel,
			letras.poner(_("Abrir en el navegador")),
			self.abrir_en_navegador,
			_("Abre el informe en HTML en su navegador, donde se recorre por encabezados y tablas."),
			fila,
		)
		crear_boton(self.panel, letras.poner(_("Cerrar")), self.Close, _("Cierra esta ventana."), fila)
		self.alumno.Bind(wx.EVT_CHOICE, lambda _evento: self._cargar_sesiones())
		self.cargar_alumnos(alumno_id, sesion_id)
		self.terminar(self.tipo)

	# ── Datos ────────────────────────────────────────────────────────────────

	def cargar_alumnos(self, alumno_id: int | None = None, sesion_id: str | None = None) -> None:
		"""Llena el desplegable de alumnos y deja elegidos el alumno y la sesión que se indiquen."""
		self._alumnos = Fichas(self.base).buscar(incluir_archivados=True)
		poner_opciones(self.alumno, [alumno.alias for alumno in self._alumnos])
		if alumno_id is not None:
			for indice, alumno in enumerate(self._alumnos):
				if alumno.id == alumno_id:
					self.alumno.SetSelection(indice)
		self._cargar_sesiones(sesion_id)

	def alumno_elegido(self) -> Alumno | None:
		"""El alumno del desplegable."""
		indice = self.alumno.GetSelection()
		return self._alumnos[indice] if 0 <= indice < len(self._alumnos) else None

	def _cargar_sesiones(self, sesion_id: str | None = None) -> None:
		alumno = self.alumno_elegido()
		self._sesiones = pres.buscar_sesiones(self.base, alumno.id) if alumno is not None else []
		alias = alumno.alias if alumno is not None else ""
		self.lista.reemplazar_filas([pres.fila_sesion(sesion, alias) for sesion in self._sesiones], conservar_foco=False)
		if sesion_id is not None:
			for indice, sesion in enumerate(self._sesiones):
				if sesion["id"] == sesion_id:
					self.lista.enfocar_fila(indice, anunciar=False)

	def ids_elegidos(self, tipo: str) -> list[str]:
		"""Sesiones que usa el informe: las marcadas en la comparación; la elegida en los de una sesión."""
		if tipo == "comparacion":
			return [self._sesiones[fila]["id"] for fila in self.lista.filas_marcadas() if fila < len(self._sesiones)]
		fila = self.lista.fila_actual()
		return [self._sesiones[fila]["id"]] if 0 <= fila < len(self._sesiones) else []

	# ── Acciones ─────────────────────────────────────────────────────────────

	def generar(self) -> bool:
		"""Construye el informe elegido y lo enseña. False si faltan datos (se explica)."""
		tipo = self._tipos[max(0, self.tipo.GetSelection())]
		try:
			self.informe = pres.construir_informe(self.base, tipo, self.alumno_elegido(), self.ids_elegidos(tipo), self.contexto)
		except ValueError as error:
			mostrar_error(self, str(error))
			(self.lista if tipo in ("sesion", "comparacion", "examen") else self.alumno).SetFocus()
			return False
		except ErrorBase as error:
			log.exception("No se ha podido construir un informe")
			mostrar_error(self, _("No se ha podido construir el informe: {error}").format(error=error))
			return False
		self.vista.ChangeValue(informes.a_texto(self.informe))
		self.vista.SetInsertionPoint(0)
		anunciar(self.contexto, _("Informe generado: {titulo}. Está en la vista previa.").format(titulo=self.informe.titulo))
		return True

	def _informe_o_generar(self) -> informes.Informe | None:
		if self.informe is None and not self.generar():
			return None
		return self.informe

	def guardar(self, formato: str) -> None:
		"""Guarda el informe de la vista previa en texto, HTML o CSV."""
		informe = self._informe_o_generar()
		if informe is None:
			return
		alumno = self.alumno_elegido()
		nombre = pres.nombre_de_fichero(informe, alumno.alias if alumno else "", formato)
		ruta = pedir_ruta_guardar(self, _("Guardar el informe"), _(pres.COMODINES[formato]), nombre)
		if ruta is None:
			return
		try:
			destino = pres.guardar_informe(informe, ruta, formato)
		except OSError as error:
			log.exception("No se ha podido guardar un informe")
			mostrar_error(self, _("No se ha podido guardar el informe: {error}").format(error=error))
			return
		anunciar(self.contexto, _("Informe guardado en {nombre}. No está cifrado: guárdelo con cuidado.").format(nombre=destino.name))

	def abrir_en_navegador(self) -> None:
		"""Escribe el informe en HTML en la carpeta temporal y lo abre en el navegador."""
		informe = self._informe_o_generar()
		if informe is None:
			return
		try:
			ruta = pres.html_temporal(informe)
		except OSError as error:
			log.exception("No se ha podido preparar el informe para el navegador")
			mostrar_error(self, _("No se ha podido preparar el informe: {error}").format(error=error))
			return
		# Se borra al cerrar el Estudio: contiene el alias y las medidas, sin cifrar.
		self.servicio.temporales.append(ruta)
		if abrir_navegador(ruta.as_uri()):
			anunciar(self.contexto, _("Informe abierto en el navegador."))
		else:
			mostrar_error(self, _("No se ha podido abrir el navegador. El informe está en {ruta}.").format(ruta=ruta))


def abrir_navegador(direccion: str) -> bool:
	"""Abre una dirección en el navegador predeterminado. Aparte, para poder sustituirla en las pruebas."""
	try:
		return bool(webbrowser.open(direccion))
	except webbrowser.Error:
		log.warning("No se ha podido abrir el navegador", exc_info=True)
		return False
