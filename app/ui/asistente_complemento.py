"""Asistente «Crear un complemento propio»: definir objetos por formulario, sin programar.

Tres pestañas que se recorren en orden (Control+Tabulador pasa de una a otra):

1. **Ficha**: nombre, identificador, versión, autor, licencia y descripción.
2. **Objetos**: la lista de objetos, con Añadir, Editar, Duplicar y Quitar.
   Cada objeto se define en un formulario generado del esquema de
   ``complemento_propio.esquema_objeto`` (forma, medidas mínima, normal y
   máxima, variantes, dónde se coloca, sonidos, estados, símbolo…).
3. **Guardar**: comprobar el complemento, guardarlo en ``data/plugins`` (con
   la miniatura de la huella de cada objeto y su descripción en texto) y
   exportarlo como ``.elabc`` para compartirlo.

Toda la lógica está en ``app/ui/complemento_propio.py`` (sin wx); aquí solo
se pregunta y se enseña. Un complemento es solo datos: no se ejecuta nada.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import wx
import wx.adv

from app.core import paths
from app.core.i18n import _, _n
from app.dominio.catalogo import EXTENSION_COMPLEMENTO, ErrorComplemento
from app.dominio.modelo import hay_errores
from app.services import complementos_en_linea as servicio
from app.ui import complemento_propio as propio
from app.ui.accesibilidad.dialogos import elegir_opcion, mostrar_error, mostrar_mensaje, preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.accesibilidad.nombres import crear_campo
from app.ui.dialogo_complementos import anotar_del_usuario
from app.ui.esquemas import ErrorCampo, con_letra, letra_de, valores_por_defecto
from app.ui.formulario import DialogoFormulario, Formulario

log = logging.getLogger(__name__)

# El sonido que suena se guarda aquí: si el recolector se lo llevara, se cortaría a media reproducción.
_sonando: list[Any] = []


def _reproducir_wav(ruta: Path) -> bool:
	"""Hace sonar un WAV sin esperar a que termine. Las pruebas sustituyen esta función."""
	sonido = wx.adv.Sound(str(ruta))
	if not sonido.IsOk():
		return False
	_sonando[:] = [sonido]
	return bool(sonido.Play(wx.adv.SOUND_ASYNC))


def escuchar(nombre: str) -> bool:
	"""Hace sonar un sonido de serie. Devuelve False (sin romper nada) si no se pudo."""
	ruta = propio.sonido_a_wav(nombre)
	if ruta is None:
		return False
	try:
		return _reproducir_wav(ruta)
	except Exception:  # noqa: BLE001 - escuchar es una comodidad: un fallo de sonido no debe cerrar el asistente
		log.warning("No se pudo reproducir %s", ruta, exc_info=True)
		return False


class DialogoObjeto(DialogoFormulario):
	"""Formulario de un objeto del complemento, con un botón para escuchar el sonido elegido."""

	def __init__(self, padre: wx.Window | None, valores: dict[str, Any] | None = None, id_objeto: str = "") -> None:
		campos = propio.esquema_objeto()
		iniciales = valores_por_defecto(campos)
		iniciales.update(valores or {})
		super().__init__(
			padre,
			_("Objeto del complemento"),
			campos,
			iniciales,
			validar=lambda leidos: propio.objeto_a_dict(leidos, id_objeto),
		)
		self._campo_sonido = ""
		self.ultimo_aviso = ""
		# La letra del botón se elige cuando ya están repartidas las de todas las pestañas.
		usadas = {
			letra_de(control.GetLabel()) for control in _descendientes(self) if isinstance(control, (wx.StaticText, wx.Button, wx.CheckBox))
		}
		usadas.discard("")
		self.boton_escuchar = wx.Button(self, label=con_letra(_("Escuchar el sonido elegido"), usadas))
		self.boton_escuchar.SetHelpText(
			_("Hace sonar el último sonido que haya elegido en la pestaña de sonidos: el del golpe, el de uso o el propio.")
		)
		sizer = self.GetSizer()
		sizer.Insert(sizer.GetItemCount() - 1, self.boton_escuchar, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
		aceptar = self.FindWindow(wx.ID_OK)
		if aceptar is not None:
			self.boton_escuchar.MoveBeforeInTabOrder(aceptar)
		self.boton_escuchar.Bind(wx.EVT_BUTTON, lambda _e: self.escuchar_elegido())
		self.Bind(wx.EVT_CHOICE, self._al_elegir)
		self.Layout()

	def _al_elegir(self, evento: wx.CommandEvent) -> None:
		"""Recuerda cuál de los tres sonidos se tocó el último: ese es el que suena con «Escuchar»."""
		evento.Skip()
		for clave in propio.CAMPOS_SONIDO:
			if self.formulario.controles.get(clave) is evento.GetEventObject():
				self._campo_sonido = clave

	def sonido_elegido(self) -> str:
		"""Nombre del sonido que sonaría ahora: el último tocado o, si no, el primero que tenga valor."""
		crudos = self.formulario.crudos()
		orden = ([self._campo_sonido] if self._campo_sonido else []) + list(propio.CAMPOS_SONIDO)
		return next((str(crudos[clave]) for clave in orden if crudos.get(clave)), "")

	def escuchar_elegido(self) -> bool:
		"""Hace sonar el sonido elegido; si no hay ninguno o no se puede, lo dice."""
		nombre = self.sonido_elegido()
		if not nombre:
			self.ultimo_aviso = _("No hay ningún sonido elegido. Elija uno en la pestaña de sonidos y acciones.")
		elif escuchar(nombre):
			self.ultimo_aviso = ""
			return True
		else:
			self.ultimo_aviso = _("No se ha podido hacer sonar «{sonido}» en este equipo.").format(sonido=nombre)
		mostrar_mensaje(self, self.ultimo_aviso, _("Escuchar"))
		self.boton_escuchar.SetFocus()
		return False


def _descendientes(ventana: wx.Window):
	for hijo in ventana.GetChildren():
		yield hijo
		yield from _descendientes(hijo)


class AsistenteComplemento(wx.Dialog):
	"""Las tres pestañas del asistente: ficha, objetos y guardar."""

	def __init__(self, padre: wx.Window | None, contexto: Any) -> None:
		titulo = _("Crear un complemento propio")
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=titulo)
		self._contexto = contexto
		self.objetos: list[dict[str, Any]] = []
		#: Id del complemento guardado en este equipo (vacío hasta que se guarda).
		self.id_guardado = ""
		self.carpeta_guardada: Path | None = None
		self.ultimo_error = ""

		sizer = wx.BoxSizer(wx.VERTICAL)
		self.cuaderno = wx.Notebook(self)
		etiqueta_cerrar = _("Ce&rrar")
		fuera = {letra_de(etiqueta_cerrar)}

		# 1. Ficha
		ficha_iniciales = valores_por_defecto(propio.ESQUEMA_FICHA)
		self.ficha = Formulario(self.cuaderno, propio.ESQUEMA_FICHA, ficha_iniciales, letras_usadas=fuera, nombre=_("Ficha"))
		self.cuaderno.AddPage(self.ficha, _("Ficha"))

		# 2. Objetos
		pagina = wx.Panel(self.cuaderno, name=_("Objetos"))
		columna = wx.BoxSizer(wx.VERTICAL)
		etiqueta = wx.StaticText(pagina, label=_("&Objetos del complemento:"))
		self.lista = ListaAccesible(
			pagina,
			_("Objetos del complemento"),
			[
				(_("Nombre"), self.FromDIP(180)),
				(_("Categoría"), self.FromDIP(120)),
				(_("Forma"), self.FromDIP(130)),
				(_("Medidas"), self.FromDIP(150)),
			],
		)
		self.lista.SetMinSize(self.FromDIP(wx.Size(580, 220)))
		self.lista.SetHelpText(_("Objetos definidos. Intro edita el elegido; Suprimir lo quita; izquierda y derecha leen las columnas."))
		columna.Add(etiqueta, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		columna.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_anadir = wx.Button(pagina, label=_("Aña&dir..."))
		self.boton_anadir.SetHelpText(_("Define un objeto nuevo con un formulario."))
		self.boton_editar = wx.Button(pagina, label=_("&Editar..."))
		self.boton_editar.SetHelpText(_("Abre el formulario del objeto elegido."))
		self.boton_duplicar = wx.Button(pagina, label=_("D&uplicar"))
		self.boton_duplicar.SetHelpText(_("Crea una copia del objeto elegido para cambiarle después lo que haga falta."))
		self.boton_quitar = wx.Button(pagina, label=_("&Quitar"))
		self.boton_quitar.SetHelpText(_("Quita de la lista el objeto elegido."))
		for boton in (self.boton_anadir, self.boton_editar, self.boton_duplicar, self.boton_quitar):
			fila.Add(boton, 0, wx.ALL, 4)
		columna.Add(fila, 0, wx.ALL, 4)
		pagina.SetSizer(columna)
		self.cuaderno.AddPage(pagina, _("Objetos"))

		# 3. Guardar
		pagina = wx.Panel(self.cuaderno, name=_("Guardar"))
		columna = wx.BoxSizer(wx.VERTICAL)
		_e, self.campo_resultado = crear_campo(
			pagina,
			_("Resul&tado:"),
			wx.TextCtrl,
			value=_("Todavía no se ha comprobado ni guardado el complemento."),
			style=wx.TE_MULTILINE | wx.TE_READONLY,
			size=self.FromDIP(wx.Size(580, 200)),
			ayuda=_("Lo que dice el comprobador y dónde se ha guardado el complemento."),
			sizer=columna,
		)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_comprobar = wx.Button(pagina, label=_("Com&probar"))
		self.boton_comprobar.SetHelpText(_("Revisa las medidas, las formas, los estados y los sonidos sin guardar nada todavía."))
		self.boton_guardar = wx.Button(pagina, label=_("&Guardar en este equipo"))
		self.boton_guardar.SetHelpText(_("Guarda el complemento en la carpeta de complementos y lo deja disponible en el catálogo."))
		self.boton_exportar = wx.Button(pagina, label=_("E&xportar para compartir..."))
		self.boton_exportar.SetHelpText(_("Crea un fichero .elabc que otra persona puede instalar con «Añadir desde fichero»."))
		for boton in (self.boton_comprobar, self.boton_guardar, self.boton_exportar):
			fila.Add(boton, 0, wx.ALL, 4)
		columna.Add(fila, 0, wx.ALL, 4)
		pagina.SetSizer(columna)
		self.cuaderno.AddPage(pagina, _("Guardar"))

		sizer.Add(self.cuaderno, 1, wx.EXPAND | wx.ALL, 6)
		self.boton_cerrar = wx.Button(self, wx.ID_CANCEL, etiqueta_cerrar)
		sizer.Add(self.boton_cerrar, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizer(sizer)
		self.SetSize(self.FromDIP(wx.Size(680, 520)))

		self.boton_anadir.Bind(wx.EVT_BUTTON, lambda _e: self.anadir_objeto())
		self.boton_editar.Bind(wx.EVT_BUTTON, lambda _e: self.editar_objeto())
		self.boton_duplicar.Bind(wx.EVT_BUTTON, lambda _e: self.duplicar_objeto())
		self.boton_quitar.Bind(wx.EVT_BUTTON, lambda _e: self.quitar_objeto())
		self.boton_comprobar.Bind(wx.EVT_BUTTON, lambda _e: self.comprobar())
		self.boton_guardar.Bind(wx.EVT_BUTTON, lambda _e: self.guardar())
		self.boton_exportar.Bind(wx.EVT_BUTTON, lambda _e: self.exportar())
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _e: self.editar_objeto())
		self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla_lista)
		preparar_dialogo(self, foco_inicial=self.ficha.primer_control())
		self._refrescar()
		self.CentreOnParent()

	# ── Ficha ────────────────────────────────────────────────────────────────

	def fijar_ficha(self, valores: dict[str, Any]) -> None:
		"""Rellena la ficha general (pruebas y automatización)."""
		self.ficha.fijar(valores)

	def _leer_ficha(self) -> dict[str, Any] | None:
		try:
			return self.ficha.leer()
		except ErrorCampo as error:
			self._fallo(error.mensaje)
			self.cuaderno.SetSelection(0)
			self.ficha.enfocar(error.clave)
			return None

	def _fallo(self, mensaje: str) -> None:
		self.ultimo_error = mensaje
		mostrar_error(self, mensaje, self.GetTitle())

	# ── Objetos ──────────────────────────────────────────────────────────────

	def _al_tecla_lista(self, evento: wx.KeyEvent) -> None:
		# atajo: Supr
		if evento.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evento.HasAnyModifiers():
			self.quitar_objeto()
			return
		evento.Skip()

	def _refrescar(self, enfocar: int | None = None) -> None:
		self.lista.reemplazar_filas([propio.resumen_objeto(objeto) for objeto in self.objetos])
		if enfocar is not None and self.objetos:
			self.lista.enfocar_fila(max(0, min(enfocar, len(self.objetos) - 1)), anunciar=False)
		hay = bool(self.objetos)
		for boton in (self.boton_editar, self.boton_duplicar, self.boton_quitar):
			boton.Enable(hay)

	def _fila(self) -> int:
		fila = self.lista.fila_actual() if self.objetos else -1
		return fila if 0 <= fila < len(self.objetos) else -1

	def _id_libre(self, base: str) -> str:
		usados = {objeto["id"] for objeto in self.objetos}
		candidato, numero = base, 2
		while candidato in usados:
			candidato = f"{base}_{numero}"[:64]
			numero += 1
		return candidato

	def _pedir_objeto(self, valores: dict[str, Any] | None, id_objeto: str) -> dict[str, Any] | None:
		"""Abre el formulario de objeto y devuelve su ficha, o None si se cancela o no vale."""
		dialogo = DialogoObjeto(self, valores, id_objeto)
		try:
			if dialogo.ShowModal() != wx.ID_OK:
				return None
			if dialogo.resultado is None and not dialogo.aceptar():
				self.ultimo_error = dialogo.ultimo_error
				return None
			return dialogo.producto
		finally:
			dialogo.Destroy()

	def anadir_objeto(self, valores: dict[str, Any] | None = None) -> dict[str, Any] | None:
		"""Añade un objeto: con ``valores`` (los de su formulario) directamente; sin ellos, preguntando."""
		try:
			if valores is not None:
				ficha = propio.objeto_a_dict({**valores_por_defecto(propio.esquema_objeto()), **valores})
			else:
				ficha = self._pedir_objeto(None, "")
		except ErrorCampo as error:
			self._fallo(error.mensaje)
			return None
		if ficha is None:
			self.lista.SetFocus()
			return None
		ficha["id"] = self._id_libre(ficha["id"])
		self.objetos.append(ficha)
		self._refrescar(len(self.objetos) - 1)
		self._contexto.anunciar(_("Objeto «{nombre}» añadido al complemento.").format(nombre=ficha["nombre"]))
		self.lista.SetFocus()
		return ficha

	def editar_objeto(self) -> dict[str, Any] | None:
		"""Abre el formulario del objeto elegido y guarda los cambios."""
		fila = self._fila()
		if fila < 0:
			return None
		actual = self.objetos[fila]
		ficha = self._pedir_objeto(propio.dict_a_valores(actual), actual["id"])
		if ficha is not None:
			self.objetos[fila] = ficha
			self._refrescar(fila)
		self.lista.SetFocus()
		return ficha

	def duplicar_objeto(self) -> dict[str, Any] | None:
		"""Copia el objeto elegido con otro identificador y «(copia)» en el nombre."""
		fila = self._fila()
		if fila < 0:
			return None
		copia = dict(self.objetos[fila])
		copia["nombre"] = _("{nombre} (copia)").format(nombre=copia["nombre"])
		copia["id"] = self._id_libre(copia["id"])
		self.objetos.insert(fila + 1, copia)
		self._refrescar(fila + 1)
		self._contexto.anunciar(_("Objeto duplicado: {nombre}.").format(nombre=copia["nombre"]))
		self.lista.SetFocus()
		return copia

	def quitar_objeto(self) -> bool:
		"""Quita el objeto elegido tras confirmarlo; el foco pasa al vecino."""
		fila = self._fila()
		if fila < 0:
			return False
		nombre = self.objetos[fila]["nombre"]
		pregunta = _("Se va a quitar «{nombre}» de este complemento.").format(nombre=nombre)
		if elegir_opcion(self, pregunta, _("Quitar objeto"), [_("&Quitar el objeto"), _("&Conservarlo")]) != 0:
			self.lista.SetFocus()
			return False
		del self.objetos[fila]
		self._refrescar(fila)
		self._contexto.anunciar(_("Objeto «{nombre}» quitado.").format(nombre=nombre))
		(self.lista if self.objetos else self.boton_anadir).SetFocus()
		return True

	# ── Comprobar, guardar y exportar ────────────────────────────────────────

	def _construir(self) -> dict[str, Any] | None:
		"""El ``complemento.json`` con lo que hay ahora en el asistente, o None (con el foco donde falta algo)."""
		ficha = self._leer_ficha()
		if ficha is None:
			return None
		try:
			return propio.construir_complemento(ficha, self.objetos)
		except ErrorCampo as error:
			self._fallo(error.mensaje)
			if error.clave == "objetos":
				self.cuaderno.SetSelection(1)
				self.boton_anadir.SetFocus()
			else:
				self.cuaderno.SetSelection(0)
				self.ficha.enfocar(error.clave)
			return None

	def _mostrar_resultado(self, texto: str) -> None:
		self.campo_resultado.ChangeValue(texto)
		self.cuaderno.SetSelection(2)
		self.campo_resultado.SetFocus()
		self.campo_resultado.SetInsertionPoint(0)

	def comprobar(self) -> list | None:
		"""Revisa el complemento sin instalarlo (en una carpeta provisional) y enseña el resultado. Devuelve los avisos."""
		datos = self._construir()
		if datos is None:
			return None
		raiz = paths.ruta_temporales() / "complemento_propio"
		try:
			shutil.rmtree(raiz, ignore_errors=True)
			carpeta = propio.guardar_complemento(datos, raiz)
			avisos = propio.comprobar(carpeta)
		except (OSError, ErrorComplemento) as error:
			log.exception("No se pudo comprobar el complemento propio")
			self._fallo(_("No se ha podido comprobar el complemento. {motivo}").format(motivo=error))
			return None
		finally:
			shutil.rmtree(raiz, ignore_errors=True)
		self._mostrar_resultado(propio.texto_avisos(avisos))
		self._contexto.anunciar(
			_("Comprobación sin problemas.")
			if not avisos
			else _n("Comprobación: {n} aviso.", "Comprobación: {n} avisos.", len(avisos)).format(n=len(avisos))
		)
		return avisos

	def guardar(self) -> Path | None:
		"""Guarda el complemento en ``data/plugins``, lo comprueba y lo deja disponible en el catálogo."""
		datos = self._construir()
		if datos is None:
			return None
		identificador = datos["id"]
		existente = servicio.instalados().get(identificador)
		if existente is not None and identificador != self.id_guardado:
			if existente.de_serie:
				self._fallo(
					_("Ya hay un complemento de serie con el identificador «{id}». Cambie el identificador en la ficha.").format(
						id=identificador
					)
				)
				self.cuaderno.SetSelection(0)
				self.ficha.enfocar("id")
				return None
			pregunta = _("Ya hay un complemento suyo con el identificador «{id}» ({nombre}).").format(
				id=identificador, nombre=existente.nombre
			)
			if elegir_opcion(self, pregunta, self.GetTitle(), [_("&Sustituirlo"), _("&Cambiar el identificador")]) != 0:
				self.cuaderno.SetSelection(0)
				self.ficha.enfocar("id")
				return None
		try:
			carpeta = propio.guardar_complemento(datos)
			avisos = propio.comprobar(carpeta)
			anotar_del_usuario(identificador, datos["version"])
		except (OSError, ErrorComplemento) as error:
			log.exception("No se pudo guardar el complemento propio %s", identificador)
			self._fallo(_("No se ha podido guardar el complemento. {motivo}").format(motivo=error))
			return None
		self.id_guardado = identificador
		self.carpeta_guardada = carpeta
		self._contexto.recargar_catalogo()
		lineas = [
			_("Complemento «{nombre}» guardado en {carpeta}.").format(nombre=datos["nombre"], carpeta=carpeta),
			_n(
				"Contiene {n} objeto, con la miniatura de su huella.",
				"Contiene {n} objetos, cada uno con la miniatura de su huella.",
				len(datos["objetos"]),
			).format(n=len(datos["objetos"])),
			propio.texto_avisos(avisos),
		]
		if hay_errores(avisos):
			lineas.append(_("Hay errores: corríjalos y vuelva a guardar antes de compartirlo."))
		else:
			lineas.append(_("Ya puede usar sus objetos en «Insertar objeto» y exportarlo para compartirlo."))
		self._mostrar_resultado("\n".join(lineas))
		self._contexto.anunciar(_("Complemento «{nombre}» guardado.").format(nombre=datos["nombre"]))
		return carpeta

	def exportar(self, ruta: str | Path | None = None) -> Path | None:
		"""Crea el ``.elabc`` (guardando antes si hace falta). Pregunta dónde si no se pasa la ruta."""
		carpeta = self.guardar()
		if carpeta is None:
			return None
		if ruta is None:
			dialogo = wx.FileDialog(
				self,
				_("Exportar complemento"),
				defaultFile=self.id_guardado + EXTENSION_COMPLEMENTO,
				wildcard=_("Complementos de EntornoLab (*{ext})|*{ext}").format(ext=EXTENSION_COMPLEMENTO),
				style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
			)
			try:
				if dialogo.ShowModal() != wx.ID_OK:
					self.boton_exportar.SetFocus()
					return None
				ruta = dialogo.GetPath()
			finally:
				dialogo.Destroy()
		try:
			destino = propio.exportar(carpeta, ruta)
		except (OSError, ErrorComplemento) as error:
			log.exception("No se pudo exportar el complemento %s", self.id_guardado)
			self._fallo(_("No se ha podido exportar el complemento. {motivo}").format(motivo=error))
			return None
		self._mostrar_resultado(self.campo_resultado.GetValue() + "\n" + _("Exportado para compartir en {ruta}.").format(ruta=destino))
		self._contexto.anunciar(_("Complemento exportado."))
		return Path(destino)


def mostrar_asistente_complemento(contexto: Any) -> str | None:
	"""Abre el asistente (menú Herramientas) y devuelve el id del complemento guardado, o None."""
	dialogo = AsistenteComplemento(getattr(contexto, "ventana", None), contexto)
	foco_previo = wx.Window.FindFocus()
	try:
		dialogo.ShowModal()
		return dialogo.id_guardado or None
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()
