"""Complementos instalados: verlos, activarlos o desactivarlos, añadir, comprobar y quitar.

Un complemento es una carpeta de datos en ``data/plugins``. Aquí el
profesional decide cuáles salen en el catálogo sin reiniciar nada:

- **Activar o desactivar** solo cambia la preferencia
  ``complementos.desactivados`` y vuelve a cargar el catálogo; los objetos ya
  colocados de un complemento desactivado conservan su forma.
- **Añadir desde un fichero** instala un ``.elabc`` con todas las
  comprobaciones de ``instalar_complemento`` y lo apunta como «del usuario».
- **Quitar** solo se ofrece para los del usuario: los de serie forman parte
  de la aplicación y volverían con la siguiente actualización.

La lista es un ``ListCtrl`` nativo con lectura por columnas; el estado y el
origen se dicen con palabras, nunca solo con un color o un icono. Está
pensada para una veintena de complementos: un campo filtra por nombre o
categoría, una columna resume las categorías principales y los detalles dan
el desglose de objetos por categoría y subcategoría.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import wx

from app.core.i18n import _, _n
from app.dominio.catalogo import EXTENSION_COMPLEMENTO, ErrorComplemento, instalar_complemento, sin_acentos, validar_complemento
from app.services import complementos_en_linea as servicio
from app.ui import complemento_propio
from app.ui.accesibilidad.dialogos import elegir_opcion, mostrar_error, mostrar_mensaje, preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.accesibilidad.nombres import crear_campo
from app.ui.accesibilidad.teclado import vincular_menu_contextual
from app.ui.dialogo_texto import mostrar_texto

log = logging.getLogger(__name__)


def anotar_del_usuario(identificador: str, version: str = "") -> None:
	"""Apunta en ``data/config/complementos.json`` que un complemento lo puso el profesional.

	Sin este apunte, al trabajar desde el código fuente (donde no existe la
	lista ``de_serie.json``) un complemento añadido a mano se tomaría por uno
	de serie y no se podría quitar. La escritura es atómica.
	"""
	registro = servicio.leer_registro()
	registro["instalados"][identificador] = {
		"version": version,
		"origen": "manual",
		"de_serie": False,
		"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
	}
	ruta = servicio.ruta_registro()
	ruta.parent.mkdir(parents=True, exist_ok=True)
	provisional = ruta.with_name(ruta.name + ".tmp")
	provisional.write_text(json.dumps(registro, indent="\t", ensure_ascii=False, sort_keys=True), encoding="utf-8")
	os.replace(provisional, ruta)


def desactivados_de(contexto: Any) -> list[str]:
	"""Ids de los complementos desactivados en las preferencias."""
	if contexto.configuracion is None:
		return []
	return [str(identificador) for identificador in contexto.configuracion.obtener("complementos.desactivados", [])]


def fijar_activo(contexto: Any, identificador: str, activo: bool) -> None:
	"""Activa o desactiva un complemento: guarda la preferencia y recarga el catálogo, sin reiniciar."""
	lista = [otro for otro in desactivados_de(contexto) if otro != identificador]
	if not activo:
		lista.append(identificador)
	contexto.configuracion.establecer("complementos.desactivados", sorted(lista))
	contexto.recargar_catalogo()


CATEGORIAS_EN_COLUMNA = 3
RETARDO_FILTRO_MS = 300


def desglose(local: servicio.ComplementoLocal, catalogo: Any = None) -> list[tuple[str, int, list[tuple[str, int]]]]:
	"""Objetos por categoría, de más a menos: ``[(nombre de categoría, cuántos, [(subcategoría, cuántos)…])…]``.

	Con el catálogo cargado se cuentan las fichas (y sus subcategorías, si el
	dominio ya las tiene); sin él, o si el complemento no se pudo cargar, solo
	se dan los nombres de categoría que constan en disco, sin recuento.
	"""
	complemento = catalogo.complemento(local.id) if catalogo is not None else None
	if complemento is None:
		return [(categoria, 0, []) for categoria in local.categorias]
	cuenta: dict[str, int] = {}
	subcuenta: dict[str, dict[str, int]] = {}
	for definicion in complemento.objetos:
		categoria = definicion.categoria or ""
		cuenta[categoria] = cuenta.get(categoria, 0) + 1
		subcategoria = str(getattr(definicion, "subcategoria", "") or "")
		if subcategoria:
			sub = subcuenta.setdefault(categoria, {})
			sub[subcategoria] = sub.get(subcategoria, 0) + 1
	nombre_sub = getattr(complemento, "nombre_subcategoria", None)
	filas = []
	for categoria, cuantos in sorted(cuenta.items(), key=lambda par: (-par[1], par[0])):
		nombre = (complemento.categorias.get(categoria) or categoria) if categoria else _("Sin categoría")
		subs = [
			(str(nombre_sub(clave)) if callable(nombre_sub) else clave.replace("_", " "), n)
			for clave, n in sorted(subcuenta.get(categoria, {}).items(), key=lambda par: (-par[1], par[0]))
		]
		filas.append((nombre, cuantos, subs))
	return filas


def texto_categorias(local: servicio.ComplementoLocal, catalogo: Any = None) -> str:
	"""Las categorías principales para la columna: «Cocina, Salón, Baño y 4 más»."""
	nombres = [nombre for nombre, _cuantos, _subs in desglose(local, catalogo)]
	if not nombres:
		return _("sin categorías")
	principales = ", ".join(nombres[:CATEGORIAS_EN_COLUMNA])
	resto = len(nombres) - CATEGORIAS_EN_COLUMNA
	return _("{lista} y {n} más").format(lista=principales, n=resto) if resto > 0 else principales


def celdas(local: servicio.ComplementoLocal, desactivados: list[str], catalogo: Any = None) -> tuple[str, str, str, str, str, str]:
	"""Nombre, versión, número de objetos, categorías principales, estado y origen de un complemento, en palabras."""
	return (
		local.nombre,
		local.version or _("sin versión"),
		str(local.objetos),
		texto_categorias(local, catalogo),
		_("Desactivado") if local.id in desactivados else _("Activo"),
		_("De serie") if local.de_serie else _("Del usuario"),
	)


def texto_detalles(local: servicio.ComplementoLocal, desactivados: list[str], catalogo: Any = None) -> str:
	"""Ficha completa de un complemento en texto llano."""
	lineas = [
		_("Nombre: {valor}").format(valor=local.nombre),
		_("Identificador: {valor}").format(valor=local.id),
		_("Versión: {valor}").format(valor=local.version or _("sin versión")),
		_("Autor: {valor}").format(valor=local.autor or _("no consta")),
		_("Licencia: {valor}").format(valor=local.licencia or _("no consta")),
		_n("Contiene {n} objeto.", "Contiene {n} objetos.", local.objetos).format(n=local.objetos),
		_("Categorías: {valor}").format(valor=", ".join(local.categorias) or _("ninguna")),
		_("Estado: {valor}").format(
			valor=_("desactivado; sus objetos no salen en el catálogo") if local.id in desactivados else _("activo")
		),
		_("Origen: {valor}").format(valor=_("viene con la aplicación") if local.de_serie else _("añadido por el usuario")),
		_("Carpeta: {valor}").format(valor=local.carpeta),
	]
	if local.descripcion:
		lineas.insert(1, _("Descripción: {valor}").format(valor=local.descripcion))
	filas = [fila for fila in desglose(local, catalogo) if fila[1]]
	if filas:
		lineas.append("")
		lineas.append(_("Objetos por categoría:"))
		for nombre, cuantos, subs in filas:
			linea = _n("{categoria}: {n} objeto", "{categoria}: {n} objetos", cuantos).format(categoria=nombre, n=cuantos)
			if subs:
				linea += " (" + ", ".join(_("{nombre} {n}").format(nombre=sub, n=n) for sub, n in subs) + ")"
			lineas.append(linea + ".")
	return "\n".join(lineas)


class DialogoComplementos(wx.Dialog):
	"""Lista de complementos instalados con sus acciones."""

	def __init__(self, padre: wx.Window | None, contexto: Any) -> None:
		titulo = _("Complementos instalados")
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=titulo)
		self._contexto = contexto
		self._todos: list[servicio.ComplementoLocal] = []
		self._locales: list[servicio.ComplementoLocal] = []
		# Se guarda el id: en wxPython 4.3 ``evento.GetEventObject()`` de EVT_WINDOW_DESTROY no es ``self``.
		self._id_propio = self.GetId()
		self._temporizador = wx.Timer(self)
		self.ultimo_mensaje = ""

		sizer = wx.BoxSizer(wx.VERTICAL)
		_e, self.campo_filtro = crear_campo(
			self,
			_("Fi&ltrar por nombre:"),
			wx.TextCtrl,
			style=wx.TE_PROCESS_ENTER,
			ayuda=_("Escriba parte del nombre o de una categoría para acortar la lista. Vacío: se enseñan todos los complementos."),
			sizer=sizer,
		)
		etiqueta = wx.StaticText(self, label=_("Co&mplementos instalados:"))
		self.lista = ListaAccesible(
			self,
			_("Complementos instalados"),
			[
				(_("Nombre"), self.FromDIP(190)),
				(_("Versión"), self.FromDIP(70)),
				(_("Objetos"), self.FromDIP(70)),
				(_("Categorías"), self.FromDIP(260)),
				(_("Estado"), self.FromDIP(100)),
				(_("Origen"), self.FromDIP(100)),
			],
		)
		# Alto para unas veinte filas sin tener que desplazar.
		self.lista.SetMinSize(self.FromDIP(wx.Size(820, 420)))
		self.lista.SetHelpText(
			_(
				"Complementos de objetos instalados. Izquierda y derecha leen las columnas; Intro enseña los detalles; la tecla Aplicaciones abre el menú."
			)
		)
		sizer.Add(etiqueta, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
		self.texto_recuento = wx.StaticText(self, label="", name=_("Recuento"))
		sizer.Add(self.texto_recuento, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

		botones = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_activar = wx.Button(self, label=_("&Activar o desactivar"))
		self.boton_activar.SetHelpText(
			_("Hace que los objetos del complemento elegido salgan o dejen de salir en el catálogo, sin reiniciar.")
		)
		self.boton_anadir = wx.Button(self, label=_("Añadir desde &fichero..."))
		self.boton_anadir.SetHelpText(_("Instala un complemento a partir de un fichero .elabc."))
		self.boton_comprobar = wx.Button(self, label=_("Com&probar"))
		self.boton_comprobar.SetHelpText(_("Revisa el complemento elegido: medidas, sonidos e imágenes con descripción."))
		self.boton_quitar = wx.Button(self, label=_("&Quitar"))
		self.boton_quitar.SetHelpText(_("Borra el complemento elegido. Solo los añadidos por el usuario; los de serie no se quitan."))
		self.boton_detalles = wx.Button(self, label=_("&Detalles"))
		self.boton_detalles.SetHelpText(_("Enseña la ficha completa del complemento elegido."))
		self.boton_cerrar = wx.Button(self, wx.ID_CANCEL, _("C&errar"))
		for boton in (
			self.boton_activar,
			self.boton_anadir,
			self.boton_comprobar,
			self.boton_quitar,
			self.boton_detalles,
			self.boton_cerrar,
		):
			botones.Add(boton, 0, wx.ALL, 4)
		sizer.Add(botones, 0, wx.ALIGN_RIGHT | wx.ALL, 4)
		self.SetSizerAndFit(sizer)

		self.boton_activar.Bind(wx.EVT_BUTTON, lambda _e: self.alternar())
		self.boton_anadir.Bind(wx.EVT_BUTTON, lambda _e: self.anadir())
		self.boton_comprobar.Bind(wx.EVT_BUTTON, lambda _e: self.comprobar())
		self.boton_quitar.Bind(wx.EVT_BUTTON, lambda _e: self.quitar())
		self.boton_detalles.Bind(wx.EVT_BUTTON, lambda _e: self.detalles())
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _e: self.detalles())
		self.lista.Bind(wx.EVT_LIST_ITEM_FOCUSED, self._al_cambiar_fila)
		self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla_lista)
		self.campo_filtro.Bind(wx.EVT_TEXT, lambda _e: self._temporizador.StartOnce(RETARDO_FILTRO_MS))
		self.campo_filtro.Bind(wx.EVT_TEXT_ENTER, lambda _e: self.filtrar())
		self.Bind(wx.EVT_TIMER, lambda _e: self.filtrar(), self._temporizador)
		self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)
		vincular_menu_contextual(self.lista, self._crear_menu)
		preparar_dialogo(self, foco_inicial=self.lista)
		self.recargar()
		self.CentreOnParent()

	# ── Lista ────────────────────────────────────────────────────────────────

	def recargar(self, enfocar: str = "") -> None:
		"""Vuelve a leer lo instalado y deja el foco en ``enfocar`` (un id) o donde estaba."""
		anterior = enfocar or (self.actual().id if self.actual() is not None else "")
		try:
			self._todos = sorted(servicio.instalados().values(), key=lambda local: local.nombre.lower())
		except OSError:
			log.exception("No se pudo leer la carpeta de complementos")
			self._todos = []
		if enfocar and enfocar not in [local.id for local in self._filtrados()]:
			# El recién instalado tiene que verse aunque el filtro lo esconda.
			self.campo_filtro.ChangeValue("")
		self._rellenar(anterior)

	def Destroy(self) -> bool:  # noqa: N802 - sobrescribe el método de wx
		"""Para el temporizador antes de destruir: uno vivo tras liberar su dueño cierra el proceso."""
		if self._temporizador.IsRunning():
			self._temporizador.Stop()
		return super().Destroy()

	def _al_destruir(self, evento: wx.WindowDestroyEvent) -> None:
		# Se compara el id: GetEventObject() no es self en wxPython 4.3, y el evento de un hijo también sube hasta aquí.
		if evento.GetId() == self._id_propio and self._temporizador.IsRunning():
			self._temporizador.Stop()
		evento.Skip()

	def _filtrados(self) -> list[servicio.ComplementoLocal]:
		"""Los complementos cuyo nombre, identificador o categorías contienen lo escrito (sin tildes ni mayúsculas)."""
		palabras = sin_acentos(self.campo_filtro.GetValue()).split()
		if not palabras:
			return list(self._todos)
		catalogo = self._contexto.catalogo
		elegidos = []
		for local in self._todos:
			pajar = sin_acentos(
				" ".join([local.nombre, local.id, *local.categorias, *(nombre for nombre, _cuantos, _subs in desglose(local, catalogo))])
			)
			if all(palabra in pajar for palabra in palabras):
				elegidos.append(local)
		return elegidos

	def _rellenar(self, enfocar: str = "") -> None:
		self._locales = self._filtrados()
		desactivados = desactivados_de(self._contexto)
		catalogo = self._contexto.catalogo
		self.lista.reemplazar_filas([celdas(local, desactivados, catalogo) for local in self._locales])
		ids = [local.id for local in self._locales]
		if enfocar in ids:
			self.lista.enfocar_fila(ids.index(enfocar), anunciar=False)
		objetos = sum(local.objetos for local in self._locales)
		self.texto_recuento.SetLabel(
			_n("{n} complemento, {objetos} objetos en total", "{n} complementos, {objetos} objetos en total", len(self._locales)).format(
				n=len(self._locales), objetos=objetos
			)
		)
		self._actualizar_botones()

	def filtrar(self, texto: str | None = None) -> int:
		"""Acorta la lista a los complementos que contienen ``texto`` (o lo escrito en el campo). Devuelve cuántos quedan y lo anuncia."""
		self._temporizador.Stop()
		if texto is not None:
			self.campo_filtro.ChangeValue(texto)
		anterior = self.actual().id if self.actual() is not None else ""
		self._rellenar(anterior)
		self._decir(_n("{n} complemento", "{n} complementos", len(self._locales)).format(n=len(self._locales)))
		return len(self._locales)

	def actual(self) -> servicio.ComplementoLocal | None:
		"""El complemento de la fila enfocada."""
		fila = self.lista.fila_actual() if self._locales else -1
		return self._locales[fila] if 0 <= fila < len(self._locales) else None

	def enfocar(self, identificador: str) -> bool:
		"""Enfoca la fila de un complemento por su id."""
		ids = [local.id for local in self._locales]
		if identificador not in ids:
			return False
		self.lista.enfocar_fila(ids.index(identificador))
		self._actualizar_botones()
		return True

	def _al_cambiar_fila(self, evento: wx.ListEvent) -> None:
		evento.Skip()
		self._actualizar_botones()

	def _actualizar_botones(self) -> None:
		"""«Quitar» solo se ofrece para los complementos del usuario (su ayuda explica por qué)."""
		local = self.actual()
		for boton in (self.boton_activar, self.boton_comprobar, self.boton_detalles):
			boton.Enable(local is not None)
		self.boton_quitar.Enable(local is not None and not local.de_serie)

	def _al_tecla_lista(self, evento: wx.KeyEvent) -> None:
		# atajo: Supr
		if evento.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evento.HasAnyModifiers():
			self.quitar()
			return
		evento.Skip()

	def _crear_menu(self) -> wx.Menu | None:
		if self.actual() is None:
			return None
		menu = wx.Menu()
		for etiqueta, accion, activo in (
			(_("&Activar o desactivar"), self.alternar, True),
			(_("Com&probar"), self.comprobar, True),
			(_("&Detalles"), self.detalles, True),
			(_("&Quitar"), self.quitar, self.boton_quitar.IsEnabled()),
		):
			elemento = menu.Append(wx.ID_ANY, etiqueta)
			elemento.Enable(activo)
			menu.Bind(wx.EVT_MENU, lambda _e, a=accion: a(), elemento)
		return menu

	def _decir(self, texto: str) -> None:
		self.ultimo_mensaje = texto
		self._contexto.anunciar(texto)

	# ── Acciones ─────────────────────────────────────────────────────────────

	def alternar(self) -> None:
		"""Activa el complemento elegido si estaba desactivado, y al revés."""
		local = self.actual()
		if local is None:
			return
		activar = local.id in desactivados_de(self._contexto)
		try:
			fijar_activo(self._contexto, local.id, activar)
		except Exception as error:  # noqa: BLE001 - un fallo al guardar la preferencia se explica y la lista sigue usable
			log.exception("No se pudo cambiar el estado del complemento %s", local.id)
			mostrar_error(
				self,
				_("No se ha podido cambiar el estado de «{nombre}». {detalle}").format(nombre=local.nombre, detalle=error),
				self.GetTitle(),
			)
			return
		self.recargar(local.id)
		self._decir(
			(
				_("«{nombre}» activado: sus objetos vuelven a salir en el catálogo.")
				if activar
				else _("«{nombre}» desactivado: sus objetos ya no salen en el catálogo.")
			).format(nombre=local.nombre)
		)
		self.lista.SetFocus()

	def anadir(self, ruta: str | Path | None = None) -> str | None:
		"""Instala un ``.elabc`` (pregunta cuál si no se pasa) y devuelve el id instalado."""
		if ruta is None:
			dialogo = wx.FileDialog(
				self,
				_("Añadir complemento"),
				wildcard=_("Complementos de EntornoLab (*{ext})|*{ext}|Todos los archivos (*.*)|*.*").format(ext=EXTENSION_COMPLEMENTO),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
			)
			try:
				if dialogo.ShowModal() != wx.ID_OK:
					self.lista.SetFocus()
					return None
				ruta = dialogo.GetPath()
			finally:
				dialogo.Destroy()
		try:
			antes = servicio.instalados()
			identificador = instalar_complemento(ruta)
			de_serie = servicio.ids_de_serie()
			era_de_serie = identificador in antes and antes[identificador].de_serie
			if not era_de_serie and (de_serie is None or identificador not in de_serie):
				# Lo que añade el profesional es suyo y lo puede quitar; uno de serie reinstalado sigue siendo de serie.
				local = servicio.instalados().get(identificador)
				anotar_del_usuario(identificador, local.version if local is not None else "")
		except ErrorComplemento as error:
			mostrar_error(self, _("El complemento no se ha instalado. {motivo}").format(motivo=error), _("Añadir complemento"))
			self.lista.SetFocus()
			return None
		except OSError as error:
			log.exception("No se pudo instalar el complemento %s", ruta)
			mostrar_error(self, _("El complemento no se ha instalado. {motivo}").format(motivo=error), _("Añadir complemento"))
			self.lista.SetFocus()
			return None
		self._contexto.recargar_catalogo()
		self.recargar(identificador)
		instalado = self.actual()
		self._decir(_("Complemento «{nombre}» instalado.").format(nombre=instalado.nombre if instalado is not None else identificador))
		self.lista.SetFocus()
		return identificador

	def comprobar(self) -> str:
		"""Revisa el complemento elegido y enseña el resultado en un campo de solo lectura. Devuelve el texto."""
		local = self.actual()
		if local is None:
			return ""
		try:
			texto = complemento_propio.texto_avisos(validar_complemento(local.carpeta))
		except (ErrorComplemento, OSError) as error:
			texto = _("Error: {texto}").format(texto=error)
		self.ultimo_mensaje = texto
		mostrar_texto(self, _("Comprobación de «{nombre}»").format(nombre=local.nombre), _("&Resultado:"), texto, copiable=True)
		self.lista.SetFocus()
		return texto

	def detalles(self) -> None:
		"""Ficha del complemento elegido, en texto."""
		local = self.actual()
		if local is None:
			return
		mostrar_texto(
			self,
			local.nombre,
			_("&Ficha del complemento:"),
			texto_detalles(local, desactivados_de(self._contexto), self._contexto.catalogo),
			copiable=True,
		)
		self.lista.SetFocus()

	def quitar(self) -> bool:
		"""Quita el complemento elegido si es del usuario, tras confirmarlo. True si se quitó."""
		local = self.actual()
		if local is None:
			return False
		if local.de_serie:
			mostrar_mensaje(
				self,
				_(
					"«{nombre}» viene con la aplicación y no se puede quitar. Puede desactivarlo para que sus objetos no salgan en el catálogo."
				).format(nombre=local.nombre),
				self.GetTitle(),
			)
			self.lista.SetFocus()
			return False
		pregunta = _(
			"Se va a borrar el complemento «{nombre}» de este equipo. Los entornos que lo usen enseñarán sus objetos como cajas con sus medidas."
		).format(nombre=local.nombre)
		if elegir_opcion(self, pregunta, _("Quitar complemento"), [_("&Quitar el complemento"), _("&Conservarlo")]) != 0:
			self.lista.SetFocus()
			return False
		try:
			servicio.desinstalar(local.id)
		except servicio.ErrorComplementoEnLinea as error:
			mostrar_error(self, str(error), _("Quitar complemento"))
			self.lista.SetFocus()
			return False
		if local.id in desactivados_de(self._contexto):
			self._contexto.configuracion.establecer(
				"complementos.desactivados", [i for i in desactivados_de(self._contexto) if i != local.id]
			)
		self._contexto.recargar_catalogo()
		self.recargar()
		self._decir(_("Complemento «{nombre}» quitado.").format(nombre=local.nombre))
		self.lista.SetFocus()
		return True


def mostrar_complementos(contexto: Any) -> None:
	"""Abre «Complementos instalados» (menú Herramientas) de forma modal."""
	dialogo = DialogoComplementos(getattr(contexto, "ventana", None), contexto)
	foco_previo = wx.Window.FindFocus()
	try:
		dialogo.ShowModal()
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()
