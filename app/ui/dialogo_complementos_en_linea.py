"""Diálogo accesible del catálogo en línea de complementos.

Lo abre «Herramientas, Catálogo en línea de complementos». Enseña en una
lista lo instalado y lo que ofrece el catálogo (nombre, estado, versión
instalada, versión disponible y tamaño) y permite instalar, actualizar uno o
todos, desinstalar, volver a la versión anterior y ver los detalles, con
búsqueda, filtro por categoría, progreso y cancelación.

Accesibilidad:

- Lista nativa (``wx.ListCtrl`` en modo informe): el lector de pantalla lee la
  fila con sus columnas; la aplicación no la repite por voz. Siempre hay una
  fila enfocada si la lista tiene filas, y al refrescar se conserva el
  complemento en el que estaba el usuario.
- Cada campo tiene su etiqueta creada justo antes y todas las letras de acceso
  son distintas. La búsqueda es un ``wx.TextCtrl`` (``wx.SearchCtrl`` no dice
  su etiqueta al tabular).
- Todo lo que se hace con el ratón se hace con el teclado: Intro abre los
  detalles, F5 refresca, la tecla Aplicaciones o Mayús+F10 abre el menú de la
  fila, Escape cierra (o cancela la descarga en curso).
- El progreso se anuncia por hitos y el resultado queda en el campo «Estado»,
  que se puede releer.

La red y el disco van en tareas de fondo: la ventana nunca se bloquea.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import wx

from app.core import tareas, voz
from app.core.i18n import _, _n, separador_decimal
from app.services import complementos_en_linea as servicio
from app.ui.dialogo_actualizacion import confirmar, gestor_de_red

log = logging.getLogger(__name__)

COLUMNAS = (
	# Traductores: cabeceras de las columnas de la lista de complementos.
	(lambda: _("Nombre"), 240),
	(lambda: _("Estado"), 170),
	(lambda: _("Versión instalada"), 120),
	(lambda: _("Versión disponible"), 120),
	(lambda: _("Tamaño"), 90),
)


def texto_tamano(tamano: int) -> str:
	"""Tamaño legible: «340 KB», «1,2 MB». Vacío si no se conoce."""
	if tamano <= 0:
		return ""
	if tamano < 1_048_576:
		return _("{kilos} KB").format(kilos=max(1, round(tamano / 1024)))
	return _("{megas} MB").format(megas=f"{tamano / 1_048_576:.1f}".replace(".", separador_decimal()))


def celdas(fila: servicio.EstadoComplemento) -> tuple[str, str, str, str, str]:
	"""Texto de cada columna para una fila. Separado para probarlo sin ventana."""
	estado = servicio.nombre_estado(fila.estado)
	if fila.de_serie:
		estado = _("{estado} (de serie)").format(estado=estado)
	return (
		fila.nombre,
		estado,
		fila.version_instalada or _("No instalado"),
		fila.version_disponible or _("No está en el catálogo"),
		texto_tamano(fila.tamano),
	)


def texto_detalles(fila: servicio.EstadoComplemento) -> str:
	"""Ficha completa de un complemento, en texto, para el diálogo de detalles."""
	remoto, local = fila.en_linea, fila.local
	lineas = [
		_("Nombre: {valor}").format(valor=fila.nombre),
		_("Identificador: {valor}").format(valor=fila.id),
		_("Estado: {valor}").format(valor=servicio.nombre_estado(fila.estado)),
		_("Versión instalada: {valor}").format(valor=fila.version_instalada or _("no instalado")),
		_("Versión disponible: {valor}").format(valor=fila.version_disponible or _("no está en el catálogo")),
	]
	autor = (remoto.autor if remoto else "") or (local.autor if local else "")
	licencia = (remoto.licencia if remoto else "") or (local.licencia if local else "")
	objetos = (remoto.objetos if remoto else 0) or (local.objetos if local else 0)
	if autor:
		lineas.append(_("Autor: {valor}").format(valor=autor))
	if licencia:
		lineas.append(_("Licencia: {valor}").format(valor=licencia))
	if fila.categorias:
		lineas.append(_("Categorías: {valor}").format(valor=", ".join(fila.categorias)))
	if objetos:
		lineas.append(_n("Contiene {n} objeto.", "Contiene {n} objetos.", objetos).format(n=objetos))
	if remoto:
		lineas.append(_("Tamaño de la descarga: {valor}").format(valor=texto_tamano(remoto.tamano)))
		if remoto.fecha:
			lineas.append(_("Fecha de publicación: {valor}").format(valor=remoto.fecha))
		if remoto.version_minima_app:
			lineas.append(_("Versión mínima de la aplicación: {valor}").format(valor=remoto.version_minima_app))
	if local:
		procedencias = {
			"serie": _("viene con la aplicación"),
			"catalogo": _("instalado o actualizado desde el catálogo en línea"),
			"manual": _("instalado a mano por el usuario"),
		}
		lineas.append(_("Procedencia: {valor}").format(valor=procedencias.get(local.origen, local.origen)))
		if local.de_serie:
			lineas.append(_("Es un complemento de serie: no se puede desinstalar."))
	if fila.hay_anterior:
		lineas.append(_("Se guarda la versión anterior: se puede volver a ella."))
	descripcion = (remoto.descripcion if remoto else "") or (local.descripcion if local else "")
	if descripcion:
		lineas.extend(["", _("Descripción:"), descripcion])
	return "\n".join(lineas)


class DialogoComplementosEnLinea(wx.Dialog):
	"""Lista de complementos instalados y disponibles, con sus acciones."""

	def __init__(
		self,
		padre: wx.Window | None,
		al_cambiar: Callable[[], Any] | None = None,
		gestor: tareas.GestorTareas | None = None,
	) -> None:
		super().__init__(padre, title=_("Catálogo en línea de complementos"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._al_cambiar = al_cambiar
		self._gestor = gestor or gestor_de_red()
		self._tarea: tareas.Tarea | None = None
		self._hitos = tareas.HitosProgreso(25)
		self.indice: servicio.Indice | None = None
		self._todas: list[servicio.EstadoComplemento] = []
		self.filas: list[servicio.EstadoComplemento] = []
		self._categorias: list[str] = []
		self.cambios = 0
		self._crear_controles()
		self._recalcular()
		self.CentreOnParent()

	# ── Construcción ─────────────────────────────────────────────────────────

	def _crear_controles(self) -> None:
		borde = self.FromDIP(10)
		principal = wx.BoxSizer(wx.VERTICAL)

		filtros = wx.BoxSizer(wx.HORIZONTAL)
		etiqueta_buscar = wx.StaticText(self, label=_("&Buscar:"))
		self.buscar = wx.TextCtrl(self, size=self.FromDIP(wx.Size(220, -1)))
		self.buscar.SetHelpText(_("Escriba parte del nombre o de la descripción; la lista se filtra al escribir."))
		etiqueta_categoria = wx.StaticText(self, label=_("Cate&goría:"))
		self.categoria = wx.Choice(self, choices=[_("Todas")])
		self.categoria.SetSelection(0)
		for control, proporcion in ((etiqueta_buscar, 0), (self.buscar, 1), (etiqueta_categoria, 0), (self.categoria, 0)):
			filtros.Add(control, proporcion, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(8))
		principal.Add(filtros, 0, wx.ALL | wx.EXPAND, borde)

		etiqueta_lista = wx.StaticText(self, label=_("Co&mplementos:"))
		self.lista = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=self.FromDIP(wx.Size(780, 300)))
		for indice, (titulo, ancho) in enumerate(COLUMNAS):
			self.lista.InsertColumn(indice, titulo(), width=self.FromDIP(ancho))
		self.lista.SetHelpText(
			_("Lista de complementos. Intro abre los detalles, F5 refresca y la tecla Aplicaciones abre el menú de acciones.")
		)
		principal.Add(etiqueta_lista, 0, wx.LEFT | wx.RIGHT, borde)
		principal.Add(self.lista, 1, wx.ALL | wx.EXPAND, borde)

		etiqueta_estado = wx.StaticText(self, label=_("Es&tado:"))
		self.estado = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=self.FromDIP(wx.Size(-1, 54)))
		self.barra = wx.Gauge(self, range=100)
		self.barra.SetName(_("Progreso de la descarga"))
		principal.Add(etiqueta_estado, 0, wx.LEFT | wx.RIGHT, borde)
		principal.Add(self.estado, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, borde)
		principal.Add(self.barra, 0, wx.ALL | wx.EXPAND, borde)

		botones = wx.WrapSizer(wx.HORIZONTAL)
		self.boton_instalar = wx.Button(self, label=_("&Instalar"))
		self.boton_actualizar = wx.Button(self, label=_("&Actualizar"))
		self.boton_todos = wx.Button(self, label=_("Actualizar t&odos"))
		self.boton_desinstalar = wx.Button(self, label=_("&Desinstalar"))
		self.boton_anterior = wx.Button(self, label=_("Versió&n anterior"))
		self.boton_detalles = wx.Button(self, label=_("D&etalles"))
		self.boton_refrescar = wx.Button(self, label=_("&Refrescar"))
		self.boton_cerrar = wx.Button(self, wx.ID_CANCEL, label=_("&Cerrar"))
		self._botones_accion = (
			(self.boton_instalar, self.instalar),
			(self.boton_actualizar, self.actualizar),
			(self.boton_todos, self.actualizar_todos),
			(self.boton_desinstalar, self.desinstalar),
			(self.boton_anterior, self.volver_a_anterior),
			(self.boton_detalles, self.detalles),
			(self.boton_refrescar, self.refrescar),
		)
		for boton, accion in self._botones_accion:
			botones.Add(boton, 0, wx.ALL, self.FromDIP(4))
			boton.Bind(wx.EVT_BUTTON, lambda _evento, accion=accion: accion())
		botones.Add(self.boton_cerrar, 0, wx.ALL, self.FromDIP(4))
		principal.Add(botones, 0, wx.ALL | wx.EXPAND, self.FromDIP(6))
		self.SetSizerAndFit(principal)

		self.SetEscapeId(wx.ID_CANCEL)
		self.boton_cerrar.Bind(wx.EVT_BUTTON, self._al_boton_cerrar)
		self.buscar.Bind(wx.EVT_TEXT, lambda _evento: self._filtrar())
		self.categoria.Bind(wx.EVT_CHOICE, lambda _evento: self._filtrar())
		self.lista.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda _evento: self._habilitar())
		self.lista.Bind(wx.EVT_LIST_ITEM_FOCUSED, lambda _evento: self._habilitar())
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.detalles())
		self.lista.Bind(wx.EVT_CONTEXT_MENU, self._al_menu_contextual)
		self.Bind(wx.EVT_CHAR_HOOK, self._al_teclear)
		self.Bind(wx.EVT_CLOSE, self._al_cerrar)

	# ── Datos y lista ────────────────────────────────────────────────────────

	def trabajando(self) -> bool:
		"""True mientras hay una descarga o una operación en curso."""
		return self._tarea is not None and not self._tarea.terminada

	def seleccionado(self) -> servicio.EstadoComplemento | None:
		"""La fila enfocada (la que el lector de pantalla está leyendo)."""
		indice = self.lista.GetFirstSelected()
		if indice < 0:
			indice = self.lista.GetFocusedItem()
		return self.filas[indice] if 0 <= indice < len(self.filas) else None

	def _recalcular(self, enfocar: str | None = None) -> None:
		"""Vuelve a cruzar el catálogo con lo instalado y repinta la lista."""
		try:
			self._todas = servicio.comparar(self.indice)
		except OSError:
			log.exception("No se pudo leer la carpeta de complementos")
			self._todas = []
		categorias = sorted({categoria for fila in self._todas for categoria in fila.categorias}, key=str.casefold)
		if categorias != self._categorias:
			elegida = self._categoria_elegida()
			self._categorias = categorias
			self.categoria.Set([_("Todas"), *categorias])
			self.categoria.SetSelection(categorias.index(elegida) + 1 if elegida in categorias else 0)
		self._filtrar(enfocar)

	def _categoria_elegida(self) -> str:
		indice = self.categoria.GetSelection()
		return self._categorias[indice - 1] if 0 < indice <= len(self._categorias) else ""

	def _filtrar(self, enfocar: str | None = None) -> None:
		"""Aplica la búsqueda y la categoría conservando el complemento en el que estaba el usuario."""
		anterior = self.seleccionado()
		enfocar = enfocar or (anterior.id if anterior else None)
		texto = self.buscar.GetValue().strip().casefold()
		categoria = self._categoria_elegida()

		def visible(fila: servicio.EstadoComplemento) -> bool:
			if categoria and categoria not in fila.categorias:
				return False
			if not texto:
				return True
			descripcion = (fila.en_linea.descripcion if fila.en_linea else "") or (fila.local.descripcion if fila.local else "")
			return texto in f"{fila.nombre} {fila.id} {descripcion}".casefold()

		self.filas = [fila for fila in self._todas if visible(fila)]
		self.lista.Freeze()
		try:
			self.lista.DeleteAllItems()
			for indice, fila in enumerate(self.filas):
				textos = celdas(fila)
				self.lista.InsertItem(indice, textos[0])
				for columna, valor in enumerate(textos[1:], start=1):
					self.lista.SetItem(indice, columna, valor)
		finally:
			self.lista.Thaw()
		if self.filas:
			destino = next((indice for indice, fila in enumerate(self.filas) if fila.id == enfocar), 0)
			self.lista.Select(destino)
			self.lista.Focus(destino)
			self.lista.EnsureVisible(destino)
		self._habilitar()

	def _habilitar(self) -> None:
		ocupado = self.trabajando()
		fila = self.seleccionado()
		self.boton_instalar.Enable(not ocupado and fila is not None and fila.instalable)
		self.boton_actualizar.Enable(not ocupado and fila is not None and fila.actualizable)
		self.boton_todos.Enable(not ocupado and bool(servicio.actualizables(self._todas)))
		self.boton_desinstalar.Enable(not ocupado and fila is not None and fila.desinstalable)
		self.boton_anterior.Enable(not ocupado and fila is not None and fila.hay_anterior)
		self.boton_detalles.Enable(fila is not None)
		self.boton_refrescar.Enable(not ocupado)
		self.boton_cerrar.SetLabel(_("&Cancelar") if ocupado else _("&Cerrar"))

	def _poner_estado(self, texto: str, decir: bool = True) -> None:
		self.estado.SetValue(texto)
		if decir and texto:
			voz.hablar(texto)

	def _resumen(self) -> str:
		"""Frase de estado tras cargar el catálogo: cuántos hay y cuántos tienen actualización."""
		total = len(self._todas)
		con_novedad = len(servicio.actualizables(self._todas))
		nuevos = sum(1 for fila in self._todas if fila.instalable)
		partes = [_n("{n} complemento.", "{n} complementos.", total).format(n=total)]
		if con_novedad:
			partes.append(_n("{n} tiene actualización.", "{n} tienen actualización.", con_novedad).format(n=con_novedad))
		if nuevos:
			partes.append(_n("{n} se puede instalar.", "{n} se pueden instalar.", nuevos).format(n=nuevos))
		if not con_novedad and not nuevos and self.indice is not None:
			partes.append(_("Todo está al día."))
		return " ".join(partes)

	# ── Tareas ───────────────────────────────────────────────────────────────

	def _lanzar(self, trabajo: Callable[[tareas.Tarea], Any], al_terminar: Callable[[Any], Any], nombre: str) -> None:
		self._hitos.reiniciar()
		self.barra.SetValue(0)
		self._tarea = self._gestor.enviar(
			trabajo, al_terminar=al_terminar, al_fallar=self._al_fallar, al_progresar=self._al_progresar, nombre=nombre
		)
		self._habilitar()

	def _al_progresar(self, progreso: tareas.Progreso) -> None:
		if not self:
			return
		porcentaje = progreso.porcentaje or 0
		self.barra.SetValue(porcentaje)
		hito = self._hitos.nuevo_hito(porcentaje)
		if hito is not None and hito < 100:
			texto = _("{nombre}: {porcentaje} %.").format(nombre=progreso.texto, porcentaje=hito) if progreso.texto else f"{hito} %"
			self._poner_estado(texto)

	def _al_fallar(self, error: BaseException) -> None:
		if not self:
			return
		self._tarea = None
		self.barra.SetValue(0)
		if isinstance(error, (tareas.TareaCancelada, servicio.OperacionCancelada)):
			mensaje = _("Cancelado.")
		elif isinstance(error, servicio.ErrorComplementoEnLinea):
			mensaje = str(error)
		else:
			log.error("Fallo inesperado en el catálogo de complementos", exc_info=error)
			mensaje = _("Se ha producido un error inesperado. Los detalles están en el registro.")
		self._recalcular()
		self._poner_estado(mensaje)
		# El foco va al estado para que el lector lea el error y se pueda releer.
		self.estado.SetFocus()

	def _avisar_cambio(self) -> None:
		"""Avisa a quien abrió el diálogo de que los complementos instalados han cambiado."""
		self.cambios += 1
		if self._al_cambiar is None:
			return
		try:
			self._al_cambiar()
		except Exception:  # noqa: BLE001 - un fallo de quien escucha no debe romper el diálogo
			log.exception("Falló el aviso de cambio de complementos")

	# ── Acciones ─────────────────────────────────────────────────────────────

	def refrescar(self) -> None:
		"""Descarga el catálogo y vuelve a comparar con lo instalado."""
		if self.trabajando():
			return
		self._poner_estado(_("Descargando el catálogo de complementos..."))
		self._lanzar(
			lambda tarea: servicio.descargar_catalogo(cancelacion=tarea.token), self._al_recibir_catalogo, "catálogo de complementos"
		)

	def _al_recibir_catalogo(self, indice: servicio.Indice) -> None:
		if not self:
			return
		self._tarea = None
		self.indice = indice
		self.barra.SetValue(0)
		self._recalcular()
		self._poner_estado(self._resumen())

	def _instalar(self, complementos: list[servicio.ComplementoEnLinea]) -> None:
		if self.trabajando() or not complementos:
			return
		if len(complementos) == 1:
			self._poner_estado(_("Descargando «{nombre}»...").format(nombre=complementos[0].nombre))
		else:
			self._poner_estado(
				_n("Actualizando {n} complemento...", "Actualizando {n} complementos...", len(complementos)).format(n=len(complementos))
			)

		def trabajo(tarea: tareas.Tarea) -> list[servicio.ResultadoInstalacion]:
			tamano_total = sum(complemento.tamano for complemento in complementos) or 1
			hechos = [0] * len(complementos)

			def progreso(indice: int, _cuantos: int, complemento: servicio.ComplementoEnLinea, hecho: int, _total: int) -> None:
				hechos[indice - 1] = hecho
				tarea.progresar(sum(hechos), tamano_total, complemento.nombre)

			return servicio.instalar_varios(complementos, al_progresar=progreso, cancelacion=tarea.token)

		self._lanzar(trabajo, self._al_instalar, "instalar complementos")
		self.boton_cerrar.SetFocus()  # «Cancelar»

	def _al_instalar(self, resultados: list[servicio.ResultadoInstalacion]) -> None:
		if not self:
			return
		self._tarea = None
		self.barra.SetValue(0)
		bien = [resultado for resultado in resultados if resultado.correcto]
		mal = [resultado for resultado in resultados if resultado.error]
		cancelados = [resultado for resultado in resultados if resultado.cancelado]
		lineas: list[str] = []
		for resultado in bien:
			if resultado.version_anterior:
				lineas.append(
					_("«{nombre}» actualizado de la versión {anterior} a la {version}.").format(
						nombre=resultado.nombre, anterior=resultado.version_anterior, version=resultado.version
					)
				)
			else:
				lineas.append(_("«{nombre}» instalado, versión {version}.").format(nombre=resultado.nombre, version=resultado.version))
		lineas.extend(resultado.error for resultado in mal)
		if cancelados:
			lineas.append(
				_n(
					"{n} complemento sin procesar por la cancelación.", "{n} complementos sin procesar por la cancelación.", len(cancelados)
				).format(n=len(cancelados))
			)
		self._recalcular(enfocar=resultados[0].id if resultados else None)
		self._poner_estado("\n".join(lineas))
		if bien:
			self._avisar_cambio()
		(self.estado if mal else self.lista).SetFocus()

	def instalar(self) -> None:
		"""Instala el complemento seleccionado."""
		fila = self.seleccionado()
		if fila is not None and fila.instalable and fila.en_linea is not None:
			self._instalar([fila.en_linea])

	def actualizar(self) -> None:
		"""Actualiza el complemento seleccionado."""
		fila = self.seleccionado()
		if fila is not None and fila.actualizable and fila.en_linea is not None:
			self._instalar([fila.en_linea])

	def actualizar_todos(self) -> None:
		"""Actualiza todos los complementos instalados que tienen versión nueva."""
		self._instalar(servicio.actualizables(self._todas))

	def desinstalar(self) -> None:
		"""Quita el complemento seleccionado, tras confirmarlo."""
		fila = self.seleccionado()
		if self.trabajando() or fila is None or not fila.desinstalable:
			return
		aceptado = confirmar(
			self,
			_(
				"¿Desinstalar «{nombre}»?\n\nLos entornos que lo usan seguirán abriéndose, pero sus objetos se mostrarán como cajas "
				"hasta que vuelva a instalarlo."
			).format(nombre=fila.nombre),
			_("Desinstalar complemento"),
			_("&Desinstalar"),
			_("&No desinstalar"),
		)
		if not aceptado:
			return
		nombre, identificador = fila.nombre, fila.id

		def hecho(_resultado: Any) -> None:
			if not self:
				return
			self._tarea = None
			self._recalcular()
			self._poner_estado(_("«{nombre}» desinstalado.").format(nombre=nombre))
			self._avisar_cambio()
			self.lista.SetFocus()

		self._lanzar(lambda _tarea: servicio.desinstalar(identificador), hecho, "desinstalar complemento")

	def volver_a_anterior(self) -> None:
		"""Vuelve a la versión anterior guardada del complemento seleccionado."""
		fila = self.seleccionado()
		if self.trabajando() or fila is None or not fila.hay_anterior:
			return
		aceptado = confirmar(
			self,
			_(
				"¿Volver a la versión anterior de «{nombre}»? La versión {version} se quitará; podrá instalarla otra vez desde el catálogo."
			).format(nombre=fila.nombre, version=fila.version_instalada),
			_("Versión anterior"),
			_("&Volver a la versión anterior"),
			_("&No cambiar nada"),
		)
		if not aceptado:
			return
		nombre, identificador = fila.nombre, fila.id

		def hecho(version: str) -> None:
			if not self:
				return
			self._tarea = None
			self._recalcular(enfocar=identificador)
			self._poner_estado(_("«{nombre}» ha vuelto a la versión {version}.").format(nombre=nombre, version=version))
			self._avisar_cambio()
			self.lista.SetFocus()

		self._lanzar(lambda _tarea: servicio.volver_a_anterior(identificador), hecho, "versión anterior de complemento")

	def detalles(self) -> None:
		"""Abre la ficha completa del complemento seleccionado en un campo de solo lectura."""
		fila = self.seleccionado()
		if fila is None:
			return
		from app.ui import dialogo_texto

		dialogo_texto.mostrar_texto(
			self,
			_("Detalles de «{nombre}»").format(nombre=fila.nombre),
			_("&Detalles del complemento:"),
			texto_detalles(fila),
			copiable=True,
		)

	# ── Teclado, menú y cierre ───────────────────────────────────────────────

	def _al_teclear(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_F5 and not evento.HasAnyModifiers():  # atajo: F5
			self.refrescar()
			return
		evento.Skip()

	def _al_menu_contextual(self, _evento: wx.ContextMenuEvent) -> None:
		"""Menú de la fila (tecla Aplicaciones, Mayús+F10 o botón derecho) con las mismas acciones que los botones."""
		if self.seleccionado() is None:
			return
		menu = wx.Menu()
		for boton, accion in self._botones_accion:
			elemento = menu.Append(wx.ID_ANY, boton.GetLabel())
			elemento.Enable(boton.IsEnabled())
			self.Bind(wx.EVT_MENU, lambda _e, accion=accion: accion(), elemento)
		try:
			self.lista.PopupMenu(menu)
		finally:
			menu.Destroy()

	def cancelar_trabajo(self) -> None:
		"""Pide cancelar la operación en curso."""
		if self._tarea is not None and self.trabajando():
			self._tarea.cancelar()
			self._poner_estado(_("Cancelando..."))

	def _al_boton_cerrar(self, _evento: wx.CommandEvent) -> None:
		if self.trabajando():
			self.cancelar_trabajo()
			return
		self._terminar()

	def _al_cerrar(self, evento: wx.CloseEvent) -> None:
		if self.trabajando():
			self.cancelar_trabajo()
			if evento.CanVeto():
				evento.Veto()
				return
		self._terminar()

	def _terminar(self) -> None:
		if self.IsModal():
			self.EndModal(wx.ID_CANCEL)
		else:
			self.Hide()


def mostrar_complementos_en_linea(padre: wx.Window | None, al_cambiar: Callable[[], Any] | None = None, buscar: str = "") -> int:
	"""Abre el catálogo en línea de complementos (menú Herramientas).

	Abrirlo es una acción explícita del usuario: por eso descarga enseguida el
	catálogo. Mientras llega, y si no hay conexión, se ve lo instalado.

	:param al_cambiar: se llama (en el hilo de la interfaz, sin argumentos)
		cada vez que se instala, actualiza, quita o revierte un complemento,
		para que la ventana principal recargue su catálogo de objetos.
	:param buscar: texto que se deja ya escrito en «Buscar» (el identificador
		de un complemento que le falta al entorno abierto), para que la lista
		salga filtrada.
	:return: el número de cambios hechos.
	"""
	dialogo = DialogoComplementosEnLinea(padre, al_cambiar=al_cambiar)
	if buscar:
		dialogo.buscar.ChangeValue(buscar)
		dialogo._filtrar()  # noqa: SLF001 - ChangeValue no lanza EVT_TEXT; se aplica el filtro como al escribir
	try:
		wx.CallAfter(dialogo.lista.SetFocus)
		wx.CallAfter(dialogo.refrescar)
		dialogo.ShowModal()
		return dialogo.cambios
	finally:
		dialogo.Destroy()


def buscar_actualizaciones_en_segundo_plano(
	al_encontrar: Callable[[int], Any] | None = None, gestor: tareas.GestorTareas | None = None
) -> tareas.Tarea | None:
	"""Mira el catálogo sin abrir nada y avisa si hay complementos con versión nueva.

	Pensada para ``dialogo_actualizacion.al_arrancar(..., al_haber_permiso=...)``:
	solo se llama cuando el usuario dio permiso para comprobar al arrancar. No
	instala nada y no molesta si no hay novedades ni si falla la conexión.

	:param al_encontrar: recibe cuántos complementos tienen actualización; por
		defecto se anuncia por el lector de pantalla.
	"""
	if not servicio.comprobar_con_la_aplicacion():
		return None

	def trabajo(tarea: tareas.Tarea) -> int:
		return len(servicio.actualizables(servicio.comparar(servicio.descargar_catalogo(cancelacion=tarea.token))))

	def terminado(cuantos: int) -> None:
		if cuantos <= 0:
			return
		if al_encontrar is not None:
			al_encontrar(cuantos)
			return
		voz.hablar(
			_n(
				"Hay {n} complemento con actualización. Ábralo en Herramientas, Catálogo en línea de complementos.",
				"Hay {n} complementos con actualización. Ábralos en Herramientas, Catálogo en línea de complementos.",
				cuantos,
			).format(n=cuantos)
		)

	def fallido(error: BaseException) -> None:
		if isinstance(error, (servicio.ErrorComplementoEnLinea, tareas.ErrorTarea)):
			log.info("No se pudo mirar el catálogo de complementos: %s", error)
		else:
			log.error("Fallo inesperado al mirar el catálogo de complementos", exc_info=error)

	return (gestor or gestor_de_red()).enviar(
		trabajo,
		al_terminar=terminado,
		al_fallar=fallido,
		clave_unica="complementos:automatica",
		nombre="catálogo de complementos automático",
	)
