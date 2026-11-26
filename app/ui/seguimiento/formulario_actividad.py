"""Formulario de una actividad, generado a partir del esquema de su tipo.

No hay un formulario escrito por cada tipo de actividad: ``campos_de(tipo)``
dice qué campos tiene y este diálogo los reparte en pestañas (una por
``grupo``), crea para cada uno su editor (``campos.EDITORES``), atenúa los que
dependen de una casilla apagada (``depende_de``) y, al aceptar, valida campo a
campo y con ``validar_actividad``, llevando el foco al campo que hay que
corregir.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import wx

from app.core.i18n import _
from app.ui.accesibilidad.dialogos import elegir_opcion, enfocar, mostrar_error
from app.ui.seguimiento import actividades_api as api
from app.ui.seguimiento import presentador_actividades as pres
from app.ui.seguimiento import textos
from app.ui.seguimiento.campos import EditorCampo, ErrorCampo, crear_editor
from app.ui.seguimiento.comun import DialogoFormulario, cerrar_dialogo, crear_boton, crear_desplegable, mostrar_modal, mostrar_texto
from app.ui.seguimiento.contexto import anunciar
from app.ui.seguimiento.reserva_actividades import Campo

log = logging.getLogger(__name__)


class DialogoActividad(DialogoFormulario):
	"""Edita una actividad. Tras aceptar, ``resultado`` tiene la actividad cambiada (una copia)."""

	def __init__(self, padre: wx.Window | None, contexto: Any, servicio: Any, datos: dict[str, Any]) -> None:
		self.tipo = str(datos.get("tipo") or "")
		super().__init__(padre, _("Actividad: {tipo}").format(tipo=api.nombre_tipo(self.tipo)))
		self.contexto = contexto
		self.servicio = servicio
		self.datos: dict[str, Any] = copy.deepcopy(datos)
		self.resultado: dict[str, Any] | None = None
		self.editores: list[EditorCampo] = []
		self._por_clave: dict[str, EditorCampo] = {}
		self._campos = self._campos_del_tipo()
		self._claves = [str(campo.clave) for campo in self._campos]
		etiqueta_comprobar = self.letras.poner(_("Comprobar"))
		self.cuaderno = wx.Notebook(self.panel, name=_("Apartados de la actividad"))
		self.sizer.Add(self.cuaderno, 1, wx.EXPAND | wx.ALL, 6)
		self._paginas: dict[str, tuple[wx.ScrolledWindow, wx.BoxSizer, textos.Letras]] = {}
		self.modo: wx.Choice | None = None
		self._modos = list(textos.MODOS)
		for campo in self._campos:
			pagina, columna, letras = self._pagina(str(getattr(campo, "grupo", "") or "general"))
			editor = crear_editor(pagina, campo, letras, self)
			columna.Add(editor.sizer, 1 if editor.expande else 0, wx.EXPAND)
			self.editores.append(editor)
			self._por_clave[editor.clave] = editor
			if editor.clave == "descripcion":
				self._crear_modo(pagina, columna, letras)
		if self.modo is None and "general" in self._paginas:
			pagina, columna, letras = self._paginas["general"]
			self._crear_modo(pagina, columna, letras)
		for pagina, _columna, _letras in self._paginas.values():
			pagina.SetScrollRate(0, 12)
		for editor in self.editores:
			editor.cargar(self.datos)
		self.boton_comprobar = crear_boton(
			self.panel,
			etiqueta_comprobar,
			self.comprobar,
			_("Revisa la actividad tal como está ahora en el formulario y dice los problemas encontrados, sin guardar nada."),
			self.sizer,
		)
		self._aplicar_dependencias()
		primero = self._por_clave.get("nombre") or (self.editores[0] if self.editores else None)
		self.terminar(primero.principal if primero is not None else None, tamano_minimo=(760, 640))

	# ── Construcción ─────────────────────────────────────────────────────────

	def _campos_del_tipo(self) -> list[Any]:
		"""Campos del esquema; si no trae el nombre de la actividad, se añade delante."""
		campos = api.campos_de(self.tipo)
		if not any(str(campo.clave) == "nombre" for campo in campos):
			campos.insert(0, Campo("nombre", _("Nombre"), "texto", _("Nombre de la actividad."), defecto=api.nombre_tipo(self.tipo)))
		return campos

	def _pagina(self, grupo: str) -> tuple[wx.ScrolledWindow, wx.BoxSizer, textos.Letras]:
		if grupo not in self._paginas:
			titulo = pres.titulo_grupo(grupo)
			pagina = wx.ScrolledWindow(self.cuaderno, name=titulo, style=wx.TAB_TRAVERSAL | wx.VSCROLL)
			columna = wx.BoxSizer(wx.VERTICAL)
			pagina.SetSizer(columna)
			self.cuaderno.AddPage(pagina, titulo)
			# Cada pestaña reparte sus letras por separado, sin repetir las de los botones de fuera.
			self._paginas[grupo] = (pagina, columna, self.letras.copia())
		return self._paginas[grupo]

	def _crear_modo(self, pagina: wx.Window, columna: wx.BoxSizer, letras: textos.Letras) -> None:
		"""El modo (juego, práctica o examen) no viene en el esquema: lo fija el tipo y aquí se puede cambiar."""
		if self.modo is not None or self.tiene_campo("modo"):
			return
		modo = self.datos.get("modo") if self.datos.get("modo") in self._modos else "practica"
		self.modo = crear_desplegable(
			pagina,
			letras.poner(_("Modo:")),
			[textos.nombre(textos.MODOS, clave) for clave in self._modos],
			sizer=columna,
			seleccion=self._modos.index(modo),
			ayuda=_(
				"Juego: con premios y celebraciones. Práctica: con pistas y sin puntuación. Examen: sin pistas ni celebraciones intermedias. "
				"Los tipos de examen son siempre examen."
			),
		)
		info = api.tipos().get(self.tipo)
		if getattr(info, "grupo", "") == "examen":
			self.modo.SetSelection(self._modos.index("examen"))
			self.modo.Enable(False)

	# ── Lo que usan los editores ─────────────────────────────────────────────

	def tiene_campo(self, clave: str) -> bool:
		"""True si el esquema del tipo tiene un campo con esa clave."""
		return clave in self._claves

	def editor(self, clave: str) -> EditorCampo | None:
		"""El editor del campo con esa clave."""
		return self._por_clave.get(clave)

	def premios_actuales(self) -> list[dict[str, Any]]:
		"""Los premios tal como están ahora en el formulario (los objetivos pueden referirse a ellos)."""
		editor = self._por_clave.get("premios")
		if editor is None:
			return [premio for premio in self.datos.get("premios") or [] if isinstance(premio, dict)]
		return list(editor.leer())

	def al_cambiar_campo(self, clave: str) -> None:
		"""Un campo ha cambiado: se revisan los que dependen de él."""
		self._aplicar_dependencias()

	def _valores_para_dependencias(self) -> dict[str, Any]:
		datos = copy.deepcopy(self.datos)
		for editor in self.editores:
			if getattr(editor.campo, "tipo", "") in ("si_no", "opcion"):
				try:
					api.poner_campo(datos, editor.clave, editor.leer())
				except ErrorCampo:
					continue
		return datos

	def _aplicar_dependencias(self) -> None:
		datos = self._valores_para_dependencias()
		for editor in self.editores:
			depende = getattr(editor.campo, "depende_de", None)
			if depende:
				editor.activar(pres.condicion_cumplida(depende, datos))

	def ir_a(self, control: wx.Window) -> None:
		"""Cambia a la pestaña del control y le da el foco."""
		ventana: wx.Window | None = control
		while ventana is not None and ventana.GetParent() is not self.cuaderno:
			ventana = ventana.GetParent()
		if ventana is not None:
			for indice in range(self.cuaderno.GetPageCount()):
				if self.cuaderno.GetPage(indice) is ventana:
					self.cuaderno.SetSelection(indice)
					break
		enfocar(control)

	# ── Validación ───────────────────────────────────────────────────────────

	def recoger(self) -> dict[str, Any]:
		"""La actividad con lo escrito en el formulario. Lanza ``ErrorCampo`` si un campo no vale."""
		nuevo = copy.deepcopy(self.datos)
		for editor in self.editores:
			if editor.activo:
				editor.volcar(nuevo)
		if self.modo is not None:
			nuevo["modo"] = self._modos[max(0, self.modo.GetSelection())]
		if not str(nuevo.get("nombre") or "").strip():
			editor_nombre = self._por_clave.get("nombre")
			raise ErrorCampo(_("Escriba el nombre de la actividad."), editor_nombre.principal if editor_nombre is not None else None)
		return nuevo

	def _control_de(self, aviso: Any, datos: dict[str, Any]) -> wx.Window | None:
		"""Control al que hay que llevar el foco por un aviso; en una lista, deja además elegida la fila que falla."""
		clave = pres.campo_de_aviso(aviso, self._claves, datos)
		editor = self._por_clave.get(clave) if clave else None
		if editor is None:
			return None
		lista = api.leer_campo(datos, editor.clave)
		fila = pres.indice_de_aviso(aviso, lista) if isinstance(lista, list) else -1
		if fila >= 0 and hasattr(editor.principal, "enfocar_fila"):
			editor.principal.enfocar_fila(fila, anunciar=False)
		return editor.principal

	def comprobar(self) -> None:
		"""Comprueba la actividad sin guardar y enseña el resultado en un campo de solo lectura."""
		try:
			nuevo = self.recoger()
		except ErrorCampo as error:
			mostrar_error(self, str(error))
			if error.control is not None:
				self.ir_a(error.control)
			return
		avisos = api.validar_actividad(
			nuevo,
			getattr(self.contexto, "entorno", None),
			getattr(self.contexto, "catalogo", None),
			recursos=getattr(self.contexto, "recursos", None),
		)
		mostrar_texto(self, _("Comprobación de la actividad"), _("&Resultado:"), pres.texto_avisos(avisos))

	def aceptar(self) -> bool:
		"""Valida los campos y la actividad entera; si hay errores, deja corregirlos o guardar de todos modos."""
		try:
			nuevo = self.recoger()
		except ErrorCampo as error:
			mostrar_error(self, str(error))
			if error.control is not None:
				self.ir_a(error.control)
			return False
		try:
			avisos = api.validar_actividad(
				nuevo,
				getattr(self.contexto, "entorno", None),
				getattr(self.contexto, "catalogo", None),
				recursos=getattr(self.contexto, "recursos", None),
			)
		except Exception:  # noqa: BLE001 - la validación recorre el entorno entero; si falla no debe impedir guardar el trabajo
			log.exception("Ha fallado la validación de una actividad")
			avisos = []
		errores = [aviso for aviso in avisos if getattr(aviso, "gravedad", "") == "error"]
		if errores:
			eleccion = elegir_opcion(
				self,
				pres.texto_avisos(avisos) + "\n\n" + _("Puede corregirlo ahora o guardar la actividad así y terminarla más tarde."),
				_("La actividad tiene errores"),
				[_("C&orregir"), _("&Guardar de todos modos")],
			)
			if eleccion != 1:
				control = self._control_de(errores[0], nuevo)
				if control is not None:
					self.ir_a(control)
				return False
		elif avisos:
			anunciar(
				self.contexto,
				textos.contar(
					len(avisos),
					"Actividad guardada con {n} aviso. Use «Comprobar» para leerlo.",
					"Actividad guardada con {n} avisos. Use «Comprobar» para leerlos.",
				),
			)
		self.resultado = nuevo
		self.aceptado = True
		cerrar_dialogo(self, wx.ID_OK)
		return True


def editar_actividad(padre: wx.Window | None, contexto: Any, servicio: Any, datos: dict[str, Any]) -> dict[str, Any] | None:
	"""Abre el formulario de una actividad. Devuelve la actividad cambiada, o ``None`` si se cancela."""
	dialogo = DialogoActividad(padre, contexto, servicio, datos)
	try:
		mostrar_modal(dialogo)
		return dialogo.resultado if dialogo.aceptado else None
	finally:
		dialogo.Destroy()
