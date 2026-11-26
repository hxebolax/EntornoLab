"""Ventana de sesiones: lista filtrable, detalle con notas y marcas, y repetición del recorrido paso a paso."""

from __future__ import annotations

import logging
from typing import Any

import wx

from app.core.i18n import _
from app.seguimiento import sesiones
from app.seguimiento.alumnos import Fichas
from app.seguimiento.base import MODOS, ErrorBase, ErrorDatos
from app.ui.accesibilidad.dialogos import elegir_opcion, mostrar_error, pedir_texto
from app.ui.seguimiento import presentador_registros as pres
from app.ui.seguimiento import textos
from app.ui.seguimiento.comun import (
	DialogoFormulario,
	VentanaSeguimiento,
	crear_boton,
	crear_casilla,
	crear_desplegable,
	crear_lista,
	crear_texto,
	mostrar_modal,
	poner_opciones,
)
from app.ui.seguimiento.contexto import anunciar
from app.ui.seguimiento.plano_simple import PlanoSimple
from app.ui.seguimiento.textos import leer_numero

log = logging.getLogger(__name__)


class DialogoRecorrido(DialogoFormulario):
	"""El recorrido de una sesión narrado paso a paso: cada paso es un elemento de una lista que se recorre con las flechas."""

	def __init__(self, padre: wx.Window | None, base: Any, sesion: dict[str, Any], contexto: Any = None) -> None:
		super().__init__(padre, _("Repetir el recorrido"))
		self.base = base
		self.sesion = sesion
		self.contexto = contexto
		self._unidades = list(textos.UNIDADES)
		self.unidad = crear_desplegable(
			self.panel,
			self.letras.poner(_("Distancias en:")),
			[textos.nombre(textos.UNIDADES, clave) for clave in self._unidades],
			sizer=self.sizer,
			ayuda=_("Las distancias de la narración se dicen en metros o en pasos del alumno, con la longitud de paso de su ficha."),
		)
		self.tiempos = crear_casilla(
			self.panel,
			self.letras.poner(_("Decir el instante de cada paso")),
			False,
			sizer=self.sizer,
			ayuda=_("Antepone a cada paso el momento de la sesión en que ocurrió."),
		)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		columna = wx.BoxSizer(wx.VERTICAL)
		self.etiqueta_pasos = wx.StaticText(self.panel, label=self.letras.poner(_("Pasos del recorrido:")))
		self.pasos = wx.ListBox(self.panel, style=wx.LB_SINGLE, size=wx.Size(520, 320), name=_("Pasos del recorrido"))
		self.pasos.SetHelpText(
			_("Cada elemento es un paso del recorrido. Avance con la flecha abajo para oírlo de principio a fin, como si se repitiera.")
		)
		columna.Add(self.etiqueta_pasos, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		columna.Add(self.pasos, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		fila.Add(columna, 1, wx.EXPAND)
		self.plano = PlanoSimple(self.panel, (280, 240))
		fila.Add(self.plano, 0, wx.ALL, 6)
		self.sizer.Add(fila, 1, wx.EXPAND)
		self.unidad.Bind(wx.EVT_CHOICE, lambda _evento: self.cargar())
		self.tiempos.Bind(wx.EVT_CHECKBOX, lambda _evento: self.cargar())
		self.cargar()
		self._dibujar()
		self.terminar(self.pasos, botones=wx.CLOSE, tamano_minimo=(860, 480))

	def cargar(self) -> None:
		"""Vuelve a narrar el recorrido con la unidad y los instantes elegidos, conservando el paso en el que se está."""
		elegido = self.pasos.GetSelection()
		try:
			pasos = pres.pasos_del_recorrido(
				self.base, self.sesion, self.contexto, self._unidades[max(0, self.unidad.GetSelection())], self.tiempos.GetValue()
			)
		except ErrorDatos as error:
			pasos = [str(error)]
		self.pasos.Set(pasos)
		if pasos:
			self.pasos.SetSelection(min(max(elegido, 0), len(pasos) - 1))

	def _dibujar(self) -> None:
		"""Dibuja el recorrido en el plano si el entorno de la sesión es el que está abierto."""
		try:
			planta, puntos = pres.puntos_del_recorrido(self.base, self.sesion["id"])
		except ErrorDatos:
			log.warning("La traza de una sesión no se puede leer: el plano del recorrido queda vacío")
			return
		entorno = getattr(self.contexto, "entorno", None)
		if entorno is not None and str(getattr(entorno, "id", "")) == str(self.sesion.get("entorno_id") or ""):
			self.plano.poner_planta(entorno, planta)
		self.plano.poner_recorrido(puntos)


class DialogoSesion(DialogoFormulario):
	"""Detalle de una sesión: resumen completo, notas del profesional y marcas."""

	def __init__(self, padre: wx.Window | None, base: Any, sesion: dict[str, Any], contexto: Any = None) -> None:
		super().__init__(padre, _("Sesión del {fecha}").format(fecha=textos.fecha_legible(sesion.get("inicio"))))
		self.base = base
		self.sesion = sesion
		self.contexto = contexto
		configuracion = getattr(contexto, "configuracion", None)
		self.resumen = crear_texto(
			self.panel,
			self.letras.poner(_("Resumen de la sesión:")),
			pres.texto_sesion(base, sesion["id"], contexto),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=230,
			ancho=680,
			proporcion=1,
			ayuda=_(
				"Todas las medidas de la sesión: tiempos, distancia, choques, ayudas, logros, espacios visitados y forma de explorar. Es descriptivo, no un diagnóstico."
			),
		)
		self.notas = crear_texto(
			self.panel,
			self.letras.poner(_("Notas del profesional (se guardan cifradas):")),
			str(sesion.get("notas") or ""),
			sizer=self.sizer,
			multilinea=True,
			alto=70,
			ancho=680,
			ayuda=_("Sus observaciones sobre esta sesión. Se guardan cifradas con su contraseña al pulsar «Guardar las notas»."),
		)
		self.marcas = crear_lista(
			self.panel,
			self.letras.poner(_("Marcas de la sesión:")),
			[(_("Instante"), 90), (_("Lugar"), 220), (_("Nota"), 340)],
			configuracion,
			sizer=self.sizer,
			alto=90,
			proporcion=0,
			ayuda=_("Los momentos que marcó durante la supervisión, o al repasar la sesión, con su nota."),
		)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		crear_boton(self.panel, self.letras.poner(_("Guardar las notas")), self.guardar_notas, _("Guarda las notas escritas arriba."), fila)
		crear_boton(
			self.panel,
			self.letras.poner(_("Añadir una marca...")),
			self.anadir_marca,
			_("Añade una nota en un instante de la sesión."),
			fila,
		)
		crear_boton(
			self.panel, self.letras.poner(_("Repetir el recorrido...")), self.repetir, _("Abre el recorrido narrado paso a paso."), fila
		)
		self.sizer.Add(fila, 0, wx.ALL, 2)
		self._cargar_marcas()
		self.terminar(self.resumen, botones=wx.CLOSE, tamano_minimo=(740, 640))

	def _cargar_marcas(self) -> None:
		self.marcas.reemplazar_filas([pres.fila_marca(marca, self.contexto) for marca in sesiones.marcas(self.base, self.sesion["id"])])

	def guardar_notas(self) -> None:
		"""Guarda las notas del profesional (cifradas)."""
		sesiones.anotar(self.base, self.sesion["id"], self.notas.GetValue())
		self.sesion["notas"] = self.notas.GetValue()
		anunciar(self.contexto, _("Notas guardadas."))

	def anadir_marca(self) -> None:
		"""Pide un instante y una nota y añade la marca."""
		instante = pedir_texto(
			self, _("&Instante de la marca, en segundos desde el principio:"), _("Añadir una marca"), "0", max_caracteres=8
		)
		if instante is None:
			return
		try:
			segundos = leer_numero(instante) or 0.0
		except ValueError:
			mostrar_error(self, _("El instante debe ser un número de segundos."))
			return
		nota = pedir_texto(self, _("&Nota de la marca:"), _("Añadir una marca"), max_caracteres=2000)
		if not nota or not nota.strip():
			return
		try:
			sesiones.anadir_marca(self.base, self.sesion["id"], max(0.0, float(segundos)), nota.strip())
		except ErrorDatos as error:
			mostrar_error(self, str(error))
			return
		self._cargar_marcas()
		anunciar(self.contexto, _("Marca añadida."))

	def repetir(self) -> None:
		"""Abre la narración del recorrido."""
		dialogo = DialogoRecorrido(self, self.base, self.sesion, self.contexto)
		try:
			mostrar_modal(dialogo)
		finally:
			dialogo.Destroy()


class VentanaSesiones(VentanaSeguimiento):
	"""Lista de sesiones con filtros y sus acciones."""

	CLAVE = "sesiones"

	def __init__(self, contexto: Any, servicio: Any, alumno_id: int | None = None) -> None:
		super().__init__(contexto, servicio, _("Sesiones"), (940, 640))
		self.base = servicio.base
		self.sesiones: list[dict[str, Any]] = []
		self._alumnos: list[Any] = []
		self._entornos: list[tuple[str, str]] = []
		self._actividades: list[tuple[str, str]] = []
		self._alias: dict[int, str] = {}
		letras = self.letras
		filtros = wx.FlexGridSizer(cols=3, hgap=8, vgap=0)
		filtros.AddGrowableCol(0)
		filtros.AddGrowableCol(1)
		filtros.AddGrowableCol(2)
		celdas = [wx.BoxSizer(wx.VERTICAL) for _indice in range(6)]
		self.alumno = crear_desplegable(
			self.panel, letras.poner(_("Alumno:")), sizer=celdas[0], ayuda=_("Muestra solo las sesiones de un alumno, o las de todos.")
		)
		self.entorno = crear_desplegable(
			self.panel, letras.poner(_("Entorno:")), sizer=celdas[1], ayuda=_("Muestra solo las sesiones de un entorno.")
		)
		self.actividad = crear_desplegable(
			self.panel, letras.poner(_("Actividad:")), sizer=celdas[2], ayuda=_("Muestra solo las sesiones de una actividad.")
		)
		self.modo = crear_desplegable(
			self.panel,
			letras.poner(_("Modo:")),
			[_("Todos"), *[textos.nombre(textos.MODOS, modo) for modo in MODOS]],
			sizer=celdas[3],
			ayuda=_("Muestra solo los juegos, las prácticas o los exámenes."),
		)
		self.desde = crear_texto(
			self.panel,
			letras.poner(_("Desde la fecha:")),
			sizer=celdas[4],
			ancho=120,
			ayuda=_("Primera fecha, como 2026-11-20 o 20/11/2026. Vacío: sin límite."),
		)
		self.hasta = crear_texto(
			self.panel,
			letras.poner(_("Hasta la fecha:")),
			sizer=celdas[5],
			ancho=120,
			ayuda=_("Última fecha, incluida. Vacío: sin límite."),
		)
		for celda in celdas:
			filtros.Add(celda, 1, wx.EXPAND)
		self.sizer.Add(filtros, 0, wx.EXPAND)
		self.lista = crear_lista(
			self.panel,
			letras.poner(_("Sesiones, de la más reciente a la más antigua:")),
			pres.columnas_sesiones(),
			getattr(contexto, "configuracion", None),
			sizer=self.sizer,
			ayuda=_("Una sesión por fila. Intro abre su detalle; Suprimir pide borrarla. Izquierda y derecha leen las columnas."),
		)
		fila = self.fila_botones()
		crear_boton(
			self.panel,
			letras.poner(_("Buscar con estos filtros")),
			self.buscar,
			_("Vuelve a llenar la lista con los filtros de arriba."),
			fila,
		)
		crear_boton(
			self.panel,
			letras.poner(_("Ver el detalle...")),
			self.detalle,
			_("Abre el resumen completo, las notas y las marcas de la sesión elegida."),
			fila,
		)
		crear_boton(
			self.panel,
			letras.poner(_("Repetir el recorrido...")),
			self.repetir,
			_("Narra paso a paso el recorrido de la sesión elegida."),
			fila,
		)
		crear_boton(self.panel, letras.poner(_("Informes")), self.informes, _("Abre los informes del alumno de la sesión elegida."), fila)
		crear_boton(
			self.panel,
			letras.poner(_("Quitar la sesión...")),
			self.borrar,
			_("Borra la sesión elegida con su recorrido, sus notas y sus marcas."),
			fila,
		)
		crear_boton(self.panel, letras.poner(_("Cerrar")), self.Close, _("Cierra esta ventana."), fila)
		for control in (self.alumno, self.entorno, self.actividad, self.modo):
			control.Bind(wx.EVT_CHOICE, lambda _evento: self.buscar())
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.detalle())
		self.lista.Bind(wx.EVT_KEY_DOWN, self._tecla)
		self.cargar_filtros(alumno_id)
		self.buscar()
		self.terminar(self.lista)

	def _tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_DELETE and evento.GetModifiers() == wx.MOD_NONE:  # atajo: Supr
			self.borrar()
			return
		evento.Skip()

	def cargar_filtros(self, alumno_id: int | None = None) -> None:
		"""Llena los desplegables con los alumnos, entornos y actividades que hay en la base."""
		self._alumnos = Fichas(self.base).buscar(incluir_archivados=True)
		self._alias = {alumno.id: alumno.alias for alumno in self._alumnos}
		self._entornos, self._actividades = pres.valores_de_filtro(self.base)
		poner_opciones(self.alumno, [_("Todos"), *[alumno.alias for alumno in self._alumnos]])
		poner_opciones(self.entorno, [_("Todos"), *[nombre for _id, nombre in self._entornos]])
		poner_opciones(self.actividad, [_("Todas"), *[nombre for _id, nombre in self._actividades]])
		if alumno_id is not None:
			for indice, alumno in enumerate(self._alumnos):
				if alumno.id == alumno_id:
					self.alumno.SetSelection(indice + 1)

	def elegir_alumno(self, alumno_id: int | None) -> None:
		"""Pone el filtro de alumno y busca (cuando la ventana ya estaba abierta)."""
		self.cargar_filtros(alumno_id)
		self.buscar()

	def buscar(self) -> bool:
		"""Llena la lista con los filtros. False si una fecha no vale (se explica y se señala)."""
		try:
			desde = pres.leer_fecha(self.desde.GetValue(), _("Desde la fecha"))
		except ValueError as error:
			mostrar_error(self, str(error))
			self.desde.SetFocus()
			return False
		try:
			hasta = pres.leer_fecha(self.hasta.GetValue(), _("Hasta la fecha"))
		except ValueError as error:
			mostrar_error(self, str(error))
			self.hasta.SetFocus()
			return False
		alumno = self.alumno.GetSelection()
		entorno = self.entorno.GetSelection()
		actividad = self.actividad.GetSelection()
		modo = self.modo.GetSelection()
		self.sesiones = pres.buscar_sesiones(
			self.base,
			self._alumnos[alumno - 1].id if alumno > 0 else None,
			self._entornos[entorno - 1][0] if entorno > 0 else None,
			self._actividades[actividad - 1][0] if actividad > 0 else None,
			MODOS[modo - 1] if modo > 0 else None,
			desde,
			hasta,
		)
		self.lista.reemplazar_filas([pres.fila_sesion(sesion, self._alias.get(sesion["alumno_id"], "")) for sesion in self.sesiones])
		return True

	def elegida(self) -> dict[str, Any] | None:
		"""La sesión de la fila enfocada."""
		fila = self.lista.fila_actual()
		return self.sesiones[fila] if 0 <= fila < len(self.sesiones) else None

	def _exigir(self) -> dict[str, Any] | None:
		sesion = self.elegida()
		if sesion is None:
			anunciar(self.contexto, _("No hay ninguna sesión elegida."))
		return sesion

	def detalle(self) -> None:
		"""Abre el detalle de la sesión elegida."""
		sesion = self._exigir()
		if sesion is None:
			return
		dialogo = DialogoSesion(self, self.base, sesion, self.contexto)
		try:
			mostrar_modal(dialogo)
		finally:
			dialogo.Destroy()
		self.lista.SetFocus()

	def repetir(self) -> None:
		"""Abre la narración del recorrido de la sesión elegida."""
		sesion = self._exigir()
		if sesion is None:
			return
		dialogo = DialogoRecorrido(self, self.base, sesion, self.contexto)
		try:
			mostrar_modal(dialogo)
		finally:
			dialogo.Destroy()
		self.lista.SetFocus()

	def informes(self) -> None:
		"""Abre los informes del alumno de la sesión elegida."""
		from app.ui.seguimiento import integracion

		sesion = self.elegida()
		integracion.mostrar_informes(
			self.contexto, alumno_id=sesion["alumno_id"] if sesion else None, sesion_id=sesion["id"] if sesion else None
		)

	def borrar(self) -> None:
		"""Borra la sesión elegida, tras confirmar."""
		sesion = self._exigir()
		if sesion is None:
			return
		fila = pres.fila_sesion(sesion, self._alias.get(sesion["alumno_id"], ""))
		eleccion = elegir_opcion(
			self,
			_(
				"Va a borrar la sesión de {alias} del {fecha} en {entorno}, con su recorrido, sus notas y sus marcas. No se puede deshacer."
			).format(alias=fila[1], fecha=fila[0], entorno=fila[2]),
			_("Borrar la sesión"),
			[_("&Borrar la sesión")],
		)
		if eleccion != 0:
			self.lista.SetFocus()
			return
		try:
			sesiones.borrar(self.base, sesion["id"])
		except ErrorBase as error:
			mostrar_error(self, str(error))
			return
		posicion = self.lista.fila_actual()
		del self.sesiones[posicion]
		self.lista.eliminar_fila(posicion)
		anunciar(self.contexto, _("Sesión borrada."))
		self.lista.SetFocus()
