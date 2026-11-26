"""Diálogos de «Archivo, Importar»: OpenStreetMap, planos DXF y SVG, imagen de fondo y rutas GPX.

Lo que tienen en común:

- Lo importado es un BORRADOR: al terminar se enseña el informe del
  importador (lo importado, lo deducido, lo que la fuente no dice y lo que
  hay que revisar) en un campo de solo lectura, y la persona decide si usa
  el borrador o lo descarta.
- El trabajo pesado (descargar, leer, convertir) va en el ``GestorTareas``
  del Estudio: la interfaz no se bloquea, el avance se anuncia por hitos y
  se puede cancelar. El entorno ABIERTO solo se toca en el hilo de la
  interfaz, dentro de ``contexto.ejecutar`` (para poder deshacerlo).
- Privacidad: solo OpenStreetMap sale a Internet, solo cuando se pide y
  después de un aviso que explica qué se envía. Los planos, las imágenes y
  las rutas se leen del disco y no salen del equipo.

Cada diálogo se puede manejar sin mostrarlo (``fijar``, ``importar…``,
``trabajando``), que es como lo usan las pruebas.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import wx

from app.core import tareas
from app.core.i18n import N_, _, _n
from app.core.red import ErrorRed
from app.dominio.modelo import Entorno
from app.importar import dxf as importar_dxf
from app.importar import gpx as importar_gpx_mod
from app.importar import imagen as importar_imagen
from app.importar import osm
from app.importar import plano as plano_mod
from app.importar import svg as importar_svg
from app.importar.comun import ErrorImportacion, ImportacionCancelada, ResultadoImportacion, texto_duracion
from app.importar.georef import texto_atribucion
from app.ui.accesibilidad.casillas import CheckListBoxAccesible
from app.ui.accesibilidad.dialogos import DialogoMensaje, enfocar, mostrar_error, mostrar_mensaje, preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.dialogo_progreso import PanelProgreso, cancelado_de_tarea, informar, progreso_de_tarea
from app.ui.esquemas import ErrorCampo, c, leer_numero, texto_numero
from app.ui.formulario import mostrar_dialogo, pedir_formulario

log = logging.getLogger(__name__)

#: Opciones de ``OpcionesOSM`` que se enseñan como casillas: (atributo, texto).
OPCIONES_OSM: tuple[tuple[str, str], ...] = (
	("aceras", N_("Aceras que figuran en el mapa")),
	("deducir_aceras", N_("Deducir aceras donde el mapa no las dibuja")),
	("edificios", N_("Edificios")),
	("lugares", N_("Lugares de interés, comercios y paradas")),
	("obstaculos", N_("Obstáculos y mobiliario urbano")),
	("vias_de_servicio", N_("Vías de servicio y accesos")),
	("terreno_base", N_("Terreno de base para poder andar por todo el recuadro")),
	("interiores", N_("Interiores de edificios, si el mapa los tiene")),
)

#: Unidades frecuentes de un plano: (clave, texto, metros por unidad o None si se escribe).
UNIDADES: tuple[tuple[str, str, float | None], ...] = (
	("mm", N_("Milímetros"), 0.001),
	("cm", N_("Centímetros"), 0.01),
	("m", N_("Metros"), 1.0),
	("in", N_("Pulgadas"), 0.0254),
	("ft", N_("Pies"), 0.3048),
	("otra", N_("Otra (escriba los metros por unidad)"), None),
)

USOS: tuple[tuple[str, str], ...] = (
	(plano_mod.USO_PAREDES, N_("Paredes")),
	(plano_mod.USO_ESPACIOS, N_("Espacios")),
	(plano_mod.USO_PUERTAS, N_("Puertas")),
	(plano_mod.USO_TEXTOS, N_("Textos")),
	(plano_mod.USO_IGNORAR, N_("Ignorar")),
)


def _mensaje_de_error(error: BaseException) -> str:
	"""Frase para la persona a partir de un fallo de importación."""
	if isinstance(error, (ErrorImportacion, ErrorRed, ErrorCampo)):
		return str(error)
	return _("No se pudo completar la importación: {error}. Los detalles están en el registro.").format(error=error)


def _letras_ocupadas(ventana: wx.Window, *siguientes: str) -> set[str]:
	"""Letras de acceso ya puestas en los controles de ``ventana`` y en las etiquetas ``siguientes``.

	Las etiquetas van traducidas, así que las letras dependen del idioma: se
	calculan en lugar de escribirlas a mano. ``siguientes`` son las etiquetas
	de los botones que se crearán después del panel de progreso.
	"""
	from app.ui.accesibilidad.revision_teclado import letra_de_acceso

	etiquetas = [hijo.GetLabel() for hijo in ventana.GetChildren() if not isinstance(hijo, wx.TopLevelWindow)]
	etiquetas += list(siguientes)
	return {letra for letra in map(letra_de_acceso, etiquetas) if letra}


def _es_cancelacion(error: BaseException) -> bool:
	return isinstance(error, (tareas.TareaCancelada, ImportacionCancelada))


# ── Informe ──────────────────────────────────────────────────────────────────


def texto_de_informe(resultado_o_informe: Any, entorno: Entorno | None = None) -> str:
	"""El informe en texto llano, con la atribución de la fuente al final si la licencia la exige."""
	informe = getattr(resultado_o_informe, "informe", resultado_o_informe)
	entorno = entorno or getattr(resultado_o_informe, "entorno", None)
	texto = informe.a_texto()
	atribucion = texto_atribucion(entorno.procedencia) if entorno is not None else ""
	if atribucion and atribucion not in texto:
		texto = f"{texto}\n\n{atribucion}"
	return texto


class DialogoInforme(wx.Dialog):
	"""El informe de una importación en un campo de solo lectura, con la decisión de usar o descartar el borrador."""

	def __init__(self, padre: wx.Window | None, titulo: str, texto: str, con_decision: bool = True) -> None:
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=titulo)
		sizer = wx.BoxSizer(wx.VERTICAL)
		etiqueta = wx.StaticText(self, label=_("&Informe de la importación:"))
		self.campo = wx.TextCtrl(
			self, value=texto, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=self.FromDIP(wx.Size(620, 340))
		)
		self.campo.SetHelpText(
			_(
				"Lo que se ha importado, lo que el programa ha deducido, lo que la fuente no dice y lo que conviene revisar. Recórralo con las flechas."
			)
		)
		sizer.Add(etiqueta, 0, wx.LEFT | wx.RIGHT | wx.TOP, self.FromDIP(10))
		sizer.Add(self.campo, 1, wx.EXPAND | wx.ALL, self.FromDIP(10))
		botones = wx.BoxSizer(wx.HORIZONTAL)
		if con_decision:
			usar = wx.Button(self, wx.ID_OK, _("&Usar este borrador"))
			usar.SetHelpText(_("Abre el borrador en el Estudio para revisarlo y completarlo."))
			usar.SetDefault()
			descartar = wx.Button(self, wx.ID_CANCEL, _("&Descartar"))
			descartar.SetHelpText(_("Tira el borrador: no se cambia nada."))
			botones.Add(usar, 0, wx.RIGHT, self.FromDIP(8))
			botones.Add(descartar, 0)
		else:
			cerrar = wx.Button(self, wx.ID_CANCEL, _("C&errar"))
			cerrar.SetDefault()
			botones.Add(cerrar, 0)
		sizer.Add(botones, 0, wx.ALIGN_RIGHT | wx.ALL, self.FromDIP(10))
		self.SetSizerAndFit(sizer)
		preparar_dialogo(self, foco_inicial=self.campo, ayudas_genericas=False)
		self.CentreOnParent()


def mostrar_informe(padre: wx.Window | None, titulo: str, texto: str, con_decision: bool = True) -> bool:
	"""Enseña el informe. Con ``con_decision`` devuelve True si se eligió usar el borrador."""
	return mostrar_dialogo(DialogoInforme(padre, titulo, texto, con_decision)) == wx.ID_OK


# ── Privacidad ───────────────────────────────────────────────────────────────


def texto_aviso_privacidad() -> str:
	"""Qué sale del equipo al importar de OpenStreetMap, dicho antes de la primera conexión."""
	return "\n".join(
		[
			_("Para importar de OpenStreetMap la aplicación tiene que conectarse a Internet."),
			"",
			_("Qué se envía: solo el texto que escriba para buscar el lugar, o las cuatro coordenadas del recuadro que se descarga."),
			_(
				"A quién: a los servidores públicos de OpenStreetMap (Nominatim para buscar y Overpass para descargar), o a los que haya puesto en Preferencias."
			),
			_(
				"Qué NO se envía: ningún dato de alumnos, de entornos ni de este equipo. La aplicación se identifica solo con su nombre y su versión."
			),
			"",
			_(
				"Los datos de OpenStreetMap tienen licencia ODbL: todo lo que se exporte llevará la atribución «© colaboradores de OpenStreetMap»."
			),
			_("Si no quiere conectarse, puede abrir un fichero .osm que ya tenga descargado."),
		]
	)


def crear_aviso_privacidad(padre: wx.Window | None) -> DialogoMensaje:
	"""El diálogo del aviso, con botones que dicen la acción. ``ids_opciones[0]`` es «Conectar»."""
	return DialogoMensaje(
		padre,
		texto_aviso_privacidad(),
		_("Conexión a OpenStreetMap"),
		opciones=[_("C&onectar"), _("&No conectar")],
		icono=wx.ICON_QUESTION,
	)


def permiso_de_conexion(padre: wx.Window | None, configuracion: Any) -> bool:
	"""True si se puede conectar: ya se aceptó el aviso antes, o se acepta ahora (y se recuerda)."""
	if configuracion is not None and configuracion.obtener("importar.aviso_privacidad_visto", False):
		return True
	dialogo = crear_aviso_privacidad(padre)
	conectar = dialogo.ids_opciones[0]
	if mostrar_dialogo(dialogo) != conectar:
		return False
	if configuracion is not None:
		configuracion.establecer("importar.aviso_privacidad_visto", True)
	return True


# ── OpenStreetMap ────────────────────────────────────────────────────────────


class DialogoOSM(wx.Dialog):
	"""Importar un recuadro de OpenStreetMap: buscar el lugar o dar coordenadas, radio, opciones e informe."""

	def __init__(self, padre: wx.Window | None, contexto: Any, descargar: Callable[..., bytes] | None = None) -> None:
		"""Crea el diálogo.

		:param descargar: función ``descargar(url, datos=None) -> bytes`` que
			sustituye a la red (pruebas). ``None`` usa ``app.core.red``.
		"""
		super().__init__(padre, title=_("Importar de OpenStreetMap"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._contexto = contexto
		self.descargar = descargar
		self.candidatos: list[osm.Candidato] = []
		self.resultado: ResultadoImportacion | None = None
		#: True cuando el borrador ya está abierto en el Estudio.
		self.creado = False
		self.ultimo_error = ""
		config = contexto.configuracion
		radio = config.obtener("importar.radio_m", 150) if config is not None else 150
		borde = self.FromDIP(8)
		sizer = wx.BoxSizer(wx.VERTICAL)

		fila = wx.BoxSizer(wx.HORIZONTAL)
		etiqueta_buscar = wx.StaticText(self, label=_("&Buscar un lugar:"))
		self.buscar_texto = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.buscar_texto.SetHelpText(_("Una dirección o el nombre de un sitio, por ejemplo «Calle Mayor 12, Soria». Intro busca."))
		self.boton_buscar = wx.Button(self, label=_("Bu&scar"))
		self.boton_buscar.SetHelpText(_("Busca el lugar en OpenStreetMap y llena la lista de lugares encontrados."))
		fila.Add(etiqueta_buscar, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, borde)
		fila.Add(self.buscar_texto, 1, wx.RIGHT, borde)
		fila.Add(self.boton_buscar, 0)
		sizer.Add(fila, 0, wx.EXPAND | wx.ALL, borde)

		etiqueta_lista = wx.StaticText(self, label=_("&Lugares encontrados:"))
		self.lista = ListaAccesible(
			self,
			_("Lugares encontrados"),
			[(_("Lugar"), self.FromDIP(240)), (_("Descripción"), self.FromDIP(380))],
		)
		self.lista.SetMinSize(self.FromDIP(wx.Size(640, 110)))
		self.lista.SetHelpText(
			_("Lugares que responden a la búsqueda. Al elegir uno, su latitud y su longitud pasan a los campos de abajo.")
		)
		sizer.Add(etiqueta_lista, 0, wx.LEFT | wx.RIGHT, borde)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, borde)

		rejilla = wx.FlexGridSizer(0, 4, borde, borde)
		rejilla.AddGrowableCol(1, 1)
		rejilla.AddGrowableCol(3, 1)
		etiqueta_lat = wx.StaticText(self, label=_("La&titud:"))
		self.latitud = wx.TextCtrl(self)
		self.latitud.SetHelpText(_("Latitud del centro de la zona, en grados decimales. Por ejemplo 41,7636."))
		etiqueta_lon = wx.StaticText(self, label=_("Lon&gitud:"))
		self.longitud = wx.TextCtrl(self)
		self.longitud.SetHelpText(_("Longitud del centro de la zona, en grados decimales. Al oeste de Greenwich es negativa."))
		etiqueta_radio = wx.StaticText(self, label=_("&Radio en metros:"))
		self.radio = wx.TextCtrl(self, value=texto_numero(radio))
		self.radio.SetHelpText(
			_("Cuánto se importa alrededor del centro, de {minimo} a {maximo} metros. Una zona pequeña se revisa mejor.").format(
				minimo=texto_numero(osm.RADIO_MINIMO_M), maximo=texto_numero(osm.RADIO_MAXIMO_M)
			)
		)
		etiqueta_nombre = wx.StaticText(self, label=_("&Nombre del entorno:"))
		self.nombre = wx.TextCtrl(self)
		self.nombre.SetHelpText(_("Cómo se llamará el borrador. Vacío: el nombre del lugar."))
		for control in (etiqueta_lat, self.latitud, etiqueta_lon, self.longitud, etiqueta_radio, self.radio, etiqueta_nombre, self.nombre):
			rejilla.Add(
				control,
				1 if isinstance(control, wx.TextCtrl) else 0,
				wx.EXPAND if isinstance(control, wx.TextCtrl) else wx.ALIGN_CENTER_VERTICAL,
			)
		sizer.Add(rejilla, 0, wx.EXPAND | wx.ALL, borde)

		etiqueta_opciones = wx.StaticText(self, label=_("&Opciones de la importación:"))
		self.opciones = CheckListBoxAccesible(self, _("Opciones de la importación"), [_(texto) for _clave, texto in OPCIONES_OSM])
		self.opciones.SetMinSize(self.FromDIP(wx.Size(-1, 110)))
		self.opciones.SetHelpText(_("Qué se trae del mapa. La barra espaciadora marca o desmarca cada opción."))
		de_serie = osm.OpcionesOSM()
		self.opciones.SetCheckedItems([i for i, (clave, _texto) in enumerate(OPCIONES_OSM) if getattr(de_serie, clave)])
		self.opciones.SetSelection(0)
		etiqueta_acera = wx.StaticText(self, label=_("Anc&ho de las aceras deducidas, en metros:"))
		self.ancho_acera = wx.TextCtrl(self, value=texto_numero(de_serie.ancho_acera))
		self.ancho_acera.SetHelpText(_("Anchura que se da a las aceras que el mapa no dibuja. Los decimales, con coma o con punto."))
		sizer.Add(etiqueta_opciones, 0, wx.LEFT | wx.RIGHT, borde)
		sizer.Add(self.opciones, 0, wx.EXPAND | wx.ALL, borde)
		fila_acera = wx.BoxSizer(wx.HORIZONTAL)
		fila_acera.Add(etiqueta_acera, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, borde)
		fila_acera.Add(self.ancho_acera, 0)
		sizer.Add(fila_acera, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, borde)

		usadas = _letras_ocupadas(self, _("Descargar e &importar"), _("Abrir un &fichero..."), _("&Cerrar"))
		self.progreso = PanelProgreso(self, contexto.tareas, config, usadas, self._habilitar)
		sizer.Add(self.progreso, 0, wx.EXPAND | wx.ALL, borde)

		botones = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_importar = wx.Button(self, label=_("Descargar e &importar"))
		self.boton_importar.SetHelpText(_("Descarga la zona indicada y la convierte en un borrador de entorno."))
		self.boton_fichero = wx.Button(self, label=_("Abrir un &fichero..."))
		self.boton_fichero.SetHelpText(_("Importa sin conexión un fichero .osm o un JSON de Overpass que ya tenga en el equipo."))
		self.boton_cerrar = wx.Button(self, wx.ID_CANCEL, _("&Cerrar"))
		for boton in (self.boton_importar, self.boton_fichero, self.boton_cerrar):
			botones.Add(boton, 0, wx.LEFT, borde)
		sizer.Add(botones, 0, wx.ALIGN_RIGHT | wx.ALL, borde)
		self.SetSizerAndFit(sizer)

		self.boton_buscar.Bind(wx.EVT_BUTTON, lambda _e: self.buscar())
		self.buscar_texto.Bind(wx.EVT_TEXT_ENTER, lambda _e: self.buscar())
		self.boton_importar.Bind(wx.EVT_BUTTON, lambda _e: self.importar_en_linea())
		self.boton_fichero.Bind(wx.EVT_BUTTON, lambda _e: self._elegir_fichero())
		self.lista.Bind(wx.EVT_LIST_ITEM_SELECTED, self._al_elegir_lugar)
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _e: enfocar(self.radio))
		self.Bind(wx.EVT_CLOSE, self._al_cerrar)
		self.boton_cerrar.Bind(wx.EVT_BUTTON, self._al_boton_cerrar)
		preparar_dialogo(self, foco_inicial=self.buscar_texto)
		self.CentreOnParent()

	# ── Estado ───────────────────────────────────────────────────────────────

	def trabajando(self) -> bool:
		"""True mientras se busca, se descarga o se convierte."""
		return self.progreso.trabajando()

	def _habilitar(self) -> None:
		ocupado = self.trabajando()
		for boton in (self.boton_buscar, self.boton_importar, self.boton_fichero):
			boton.Enable(not ocupado)

	def _al_boton_cerrar(self, evento: wx.CommandEvent) -> None:
		if self.trabajando():
			self.progreso.cancelar()
			return
		evento.Skip()

	def _al_cerrar(self, evento: wx.CloseEvent) -> None:
		if self.trabajando() and evento.CanVeto():
			self.progreso.cancelar()
			evento.Veto()
			return
		evento.Skip()

	def _fallo(self, error: BaseException) -> None:
		if _es_cancelacion(error):
			self.ultimo_error = ""
			self.progreso.decir(_("Importación cancelada."))
			return
		if not isinstance(error, (ErrorImportacion, ErrorRed)):
			log.error("Fallo al importar de OpenStreetMap", exc_info=error)
		self.ultimo_error = _mensaje_de_error(error)
		self.progreso.decir(self.ultimo_error, hablar=False)
		mostrar_error(self, self.ultimo_error, _("Importar de OpenStreetMap"))

	def fijar(self, **valores: Any) -> None:
		"""Rellena campos por nombre: ``buscar``, ``latitud``, ``longitud``, ``radio``, ``nombre``, ``ancho_acera``, ``opciones`` (dict)."""
		campos = {
			"buscar": self.buscar_texto,
			"latitud": self.latitud,
			"longitud": self.longitud,
			"radio": self.radio,
			"nombre": self.nombre,
			"ancho_acera": self.ancho_acera,
		}
		for clave, valor in valores.items():
			if clave == "opciones":
				for indice, (atributo, _texto) in enumerate(OPCIONES_OSM):
					if atributo in valor:
						self.opciones.Check(indice, bool(valor[atributo]))
			else:
				campos[clave].SetValue(texto_numero(valor) if not isinstance(valor, str) else valor)

	# ── Buscar ───────────────────────────────────────────────────────────────

	def buscar(self) -> None:
		"""Busca el lugar escrito (con permiso de conexión) y llena la lista."""
		texto = self.buscar_texto.GetValue().strip()
		if not texto:
			mostrar_error(self, _("Escriba qué lugar quiere buscar."), _("Buscar un lugar"))
			enfocar(self.buscar_texto)
			return
		if self.trabajando() or not permiso_de_conexion(self, self._contexto.configuracion):
			return
		descargar = self.descargar

		def trabajo(tarea: Any) -> list[osm.Candidato]:
			return osm.buscar_lugar(texto, descargar=descargar, cancelado=cancelado_de_tarea(tarea))

		self.progreso.lanzar(trabajo, self._buscado, self._fallo, "buscar lugar", _("Buscando «{texto}»...").format(texto=texto))

	def _buscado(self, candidatos: list[osm.Candidato]) -> None:
		self.candidatos = list(candidatos)
		self.lista.reemplazar_filas([(candidato.nombre, candidato.descripcion) for candidato in self.candidatos], conservar_foco=False)
		if not self.candidatos:
			self.progreso.decir(_("No se ha encontrado ningún lugar con ese texto. Pruebe con otras palabras o escriba las coordenadas."))
			return
		self.lista.enfocar_fila(0)
		self._poner_candidato(0)
		self.progreso.decir(_("{n} lugares encontrados. Elija uno en la lista.").format(n=len(self.candidatos)))
		if self.IsShown():
			self.lista.SetFocus()

	def _al_elegir_lugar(self, evento: wx.ListEvent) -> None:
		self._poner_candidato(evento.GetIndex())
		evento.Skip()

	def _poner_candidato(self, indice: int) -> None:
		if 0 <= indice < len(self.candidatos):
			candidato = self.candidatos[indice]
			self.latitud.SetValue(texto_numero(candidato.lat, 6))
			self.longitud.SetValue(texto_numero(candidato.lon, 6))
			if not self.nombre.GetValue().strip():
				self.nombre.SetValue(candidato.nombre)

	# ── Importar ─────────────────────────────────────────────────────────────

	def _numero(self, control: wx.TextCtrl, nombre: str, minimo: float, maximo: float) -> float:
		try:
			valor = leer_numero(control.GetValue())
		except ValueError:
			valor = None
		if valor is None or not minimo <= valor <= maximo:
			mensaje = _("«{campo}» tiene que ser un número entre {minimo} y {maximo}.").format(
				campo=nombre, minimo=texto_numero(minimo), maximo=texto_numero(maximo)
			)
			self.ultimo_error = mensaje
			mostrar_error(self, mensaje, _("Revise el formulario"))
			enfocar(control)
			raise ErrorCampo(nombre, mensaje)
		return float(valor)

	def opciones_elegidas(self, centro: tuple[float, float] | None = None, radio: float | None = None) -> osm.OpcionesOSM:
		"""Las ``OpcionesOSM`` que corresponden a lo marcado en el diálogo."""
		marcadas = set(self.opciones.GetCheckedItems())
		opciones = osm.OpcionesOSM(nombre=self.nombre.GetValue().strip(), centro=centro, radio_m=radio, catalogo=self._contexto.catalogo)
		for indice, (atributo, _texto) in enumerate(OPCIONES_OSM):
			setattr(opciones, atributo, indice in marcadas)
		opciones.ancho_acera = self._numero(self.ancho_acera, _("Ancho de las aceras"), 0.5, 10.0)
		return opciones

	def importar_en_linea(self) -> None:
		"""Descarga la zona de las coordenadas escritas y la convierte, en segundo plano."""
		if self.trabajando():
			return
		try:
			lat = self._numero(self.latitud, _("Latitud"), -90.0, 90.0)
			lon = self._numero(self.longitud, _("Longitud"), -180.0, 180.0)
			radio = self._numero(self.radio, _("Radio en metros"), osm.RADIO_MINIMO_M, osm.RADIO_MAXIMO_M)
			opciones = self.opciones_elegidas(centro=(lat, lon))
		except ErrorCampo:
			return
		if not permiso_de_conexion(self, self._contexto.configuracion):
			return
		estimacion = osm.estimar_zona(radio)
		if radio > osm.RADIO_AVISO_M and not self.confirmar_zona_grande(estimacion):
			enfocar(self.radio)
			return
		descargar = self.descargar

		def trabajo(tarea: Any) -> ResultadoImportacion:
			# La descarga no sabe cuánto ocupa la zona (Overpass no lo dice): su
			# barra es indeterminada; la de la conversión va de 0 a 100.
			cancelado = cancelado_de_tarea(tarea)
			datos = osm.descargar_zona(lat, lon, radio, descargar=descargar, progreso=progreso_de_tarea(tarea), cancelado=cancelado)
			tarea.comprobar()
			return osm.convertir(datos, opciones, progreso_de_tarea(tarea), cancelado)

		inicio = _("Importando una zona de {lado} por {lado} metros. Descargando el mapa de OpenStreetMap...").format(
			lado=estimacion.lado_m
		)
		self.progreso.lanzar(trabajo, self._importado, self._fallo, "importar osm", inicio)

	def texto_zona_grande(self, estimacion: osm.EstimacionZona) -> str:
		"""El aviso previo a descargar una zona grande: tamaño, tiempo y qué se verá mientras."""
		return "\n\n".join(
			[
				estimacion.texto(),
				_("Una zona más pequeña se descarga antes y se revisa mejor. ¿Quiere descargar esta zona?"),
			]
		)

	def confirmar_zona_grande(self, estimacion: osm.EstimacionZona) -> bool:
		"""Avisa del tamaño y del tiempo aproximados antes de una descarga grande. True si se sigue."""
		dialogo = DialogoMensaje(
			self,
			self.texto_zona_grande(estimacion),
			_("Zona grande"),
			opciones=[_("&Descargar"), _("Cambiar el &radio")],
			icono=wx.ICON_INFORMATION,
		)
		descargar = dialogo.ids_opciones[0]
		return mostrar_dialogo(dialogo) == descargar

	def _elegir_fichero(self) -> None:
		comodin = _("Ficheros de OpenStreetMap (*.osm;*.json;*.xml)|*.osm;*.json;*.xml|Todos los ficheros (*.*)|*.*")
		with wx.FileDialog(
			self, _("Abrir un fichero de OpenStreetMap"), wildcard=comodin, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
		) as dialogo:
			if dialogo.ShowModal() != wx.ID_OK:
				return
			ruta = dialogo.GetPath()
		self.importar_fichero(ruta)

	def importar_fichero(self, ruta: str | Path) -> None:
		"""Importa sin conexión un ``.osm`` o un JSON de Overpass ya descargado."""
		if self.trabajando():
			return
		try:
			opciones = self.opciones_elegidas()
		except ErrorCampo:
			return
		if not opciones.nombre:
			opciones.nombre = Path(ruta).stem

		def trabajo(tarea: Any) -> ResultadoImportacion:
			informar(tarea, _("Leyendo el fichero de OpenStreetMap"))
			datos = osm.importar_fichero_osm(ruta)
			tarea.comprobar()
			return osm.convertir(datos, opciones, progreso_de_tarea(tarea), cancelado_de_tarea(tarea))

		self.progreso.lanzar(trabajo, self._importado, self._fallo, "importar fichero osm", _("Leyendo el fichero de OpenStreetMap..."))

	def _importado(self, resultado: ResultadoImportacion) -> None:
		"""Enseña el informe y, si se acepta, entrega el borrador a la ventana principal."""
		self.resultado = resultado
		self.ultimo_error = ""
		espacios = sum(len(planta.espacios) for planta in resultado.entorno.plantas)
		self.progreso.decir(
			_n(
				"Importación terminada en {tiempo}: {n} espacio. Se abre el informe.",
				"Importación terminada en {tiempo}: {n} espacios. Se abre el informe.",
				espacios,
			).format(tiempo=texto_duracion(self.progreso.duracion_ultima), n=espacios)
		)
		titulo = _("Informe de la importación de OpenStreetMap")
		if not mostrar_informe(self, titulo, texto_de_informe(resultado)):
			self.progreso.decir(_("Borrador descartado."))
			return
		nombre = resultado.entorno.nombre or _("Entorno importado de OpenStreetMap")
		if self._contexto.ventana.adoptar_borrador(resultado.entorno, nombre):
			self.creado = True
			if self.IsModal():
				self.EndModal(wx.ID_OK)


def importar_osm(contexto: Any) -> bool:
	"""Abre el diálogo de OpenStreetMap. True si se creó un borrador."""
	dialogo = DialogoOSM(contexto.ventana, contexto)
	foco_previo = wx.Window.FindFocus()
	try:
		dialogo.ShowModal()
		return dialogo.creado
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()


# ── Planos DXF y SVG ─────────────────────────────────────────────────────────

DESTINO_NUEVO = "nuevo"
DESTINO_PLANTA = "planta"


class DialogoPlano(wx.Dialog):
	"""Importar un plano DXF o SVG: fichero, capas con su uso, escala, destino e informe."""

	def __init__(self, padre: wx.Window | None, contexto: Any, formato: str) -> None:
		titulo = _("Importar un plano DXF") if formato == "dxf" else _("Importar un plano SVG")
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._contexto = contexto
		self.formato = formato
		self.plano: plano_mod.Plano | None = None
		self.capas: list[plano_mod.CapaPlano] = []
		self.usos: dict[str, str] = {}
		self.resultado: ResultadoImportacion | None = None
		self.creado = False
		self.ultimo_error = ""
		borde = self.FromDIP(8)
		sizer = wx.BoxSizer(wx.VERTICAL)

		etiqueta_fichero = wx.StaticText(self, label=_("&Fichero del plano:"))
		self.fichero = wx.TextCtrl(self, style=wx.TE_READONLY)
		self.fichero.SetHelpText(_("El plano elegido. Se lee del disco y no sale del equipo."))
		self.boton_examinar = wx.Button(self, label=_("E&xaminar..."))
		self.boton_examinar.SetHelpText(_("Abre un cuadro de Windows para elegir el fichero del plano."))
		fila = wx.BoxSizer(wx.HORIZONTAL)
		fila.Add(self.fichero, 1, wx.RIGHT, borde)
		fila.Add(self.boton_examinar, 0)
		sizer.Add(etiqueta_fichero, 0, wx.LEFT | wx.RIGHT | wx.TOP, borde)
		sizer.Add(fila, 0, wx.EXPAND | wx.ALL, borde)

		etiqueta_capas = wx.StaticText(self, label=_("Ca&pas del plano:"))
		self.lista = ListaAccesible(
			self,
			_("Capas del plano"),
			[(_("Capa"), self.FromDIP(160)), (_("Uso"), self.FromDIP(100)), (_("Contenido"), self.FromDIP(340))],
		)
		self.lista.SetMinSize(self.FromDIP(wx.Size(620, 130)))
		self.lista.SetHelpText(
			_("Las capas del dibujo, con para qué se va a usar cada una. Elija una capa y cambie su uso en la lista de abajo.")
		)
		etiqueta_uso = wx.StaticText(self, label=_("&Uso de la capa elegida:"))
		self.uso = wx.Choice(self, choices=[_(texto) for _clave, texto in USOS])
		self.uso.SetHelpText(_("Qué son las líneas de la capa elegida: paredes, contornos de espacios, puertas, textos, o nada."))
		sizer.Add(etiqueta_capas, 0, wx.LEFT | wx.RIGHT, borde)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, borde)
		fila_uso = wx.BoxSizer(wx.HORIZONTAL)
		fila_uso.Add(etiqueta_uso, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, borde)
		fila_uso.Add(self.uso, 0)
		sizer.Add(fila_uso, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, borde)

		rejilla = wx.FlexGridSizer(0, 2, borde, borde)
		rejilla.AddGrowableCol(1, 1)
		etiqueta_unidades = wx.StaticText(self, label=_("Uni&dades del dibujo:"))
		self.unidades = wx.Choice(self, choices=[_(texto) for _clave, texto, _factor in UNIDADES])
		self.unidades.SetSelection(len(UNIDADES) - 1)
		self.unidades.SetHelpText(_("En qué está dibujado el plano. Al elegir una unidad se rellenan los metros por unidad."))
		etiqueta_escala = wx.StaticText(self, label=_("&Metros por unidad:"))
		self.escala = wx.TextCtrl(self)
		self.escala.SetHelpText(
			_("Cuántos metros mide una unidad del dibujo. Por ejemplo 0,001 si está en milímetros. Con coma o con punto.")
		)
		etiqueta_propuesta = wx.StaticText(self, label=_("Propue&sta del programa:"))
		self.propuesta = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_MULTILINE, size=self.FromDIP(wx.Size(-1, 44)))
		self.propuesta.SetHelpText(_("Lo que el programa ha podido saber de la escala al leer el fichero."))
		etiqueta_destino = wx.StaticText(self, label=_("D&estino:"))
		destinos = [_("Un entorno nuevo")]
		if contexto.entorno is not None:
			destinos.append(_("Una planta nueva del entorno abierto"))
		self.destino = wx.Choice(self, choices=destinos)
		self.destino.SetSelection(0)
		self.destino.SetHelpText(_("Si el plano se convierte en un entorno nuevo o se añade como una planta más al entorno abierto."))
		etiqueta_nivel = wx.StaticText(self, label=_("Ni&vel de la planta:"))
		self.nivel = wx.TextCtrl(self)
		self.nivel.SetHelpText(_("Número de planta: 0 es la planta baja, 1 la primera, -1 el sótano. Vacío: la siguiente libre."))
		etiqueta_planta = wx.StaticText(self, label=_("Nombre de la p&lanta:"))
		self.nombre_planta = wx.TextCtrl(self)
		self.nombre_planta.SetHelpText(_("Cómo se llamará la planta. Vacío: un nombre según su nivel."))
		etiqueta_nombre = wx.StaticText(self, label=_("&Nombre del entorno:"))
		self.nombre = wx.TextCtrl(self)
		self.nombre.SetHelpText(_("Nombre del entorno nuevo. Vacío: el del fichero."))
		for etiqueta, control in (
			(etiqueta_unidades, self.unidades),
			(etiqueta_escala, self.escala),
			(etiqueta_propuesta, self.propuesta),
			(etiqueta_destino, self.destino),
			(etiqueta_nivel, self.nivel),
			(etiqueta_planta, self.nombre_planta),
			(etiqueta_nombre, self.nombre),
		):
			rejilla.Add(etiqueta, 0, wx.ALIGN_CENTER_VERTICAL)
			rejilla.Add(control, 1, wx.EXPAND)
		sizer.Add(rejilla, 0, wx.EXPAND | wx.ALL, borde)

		usadas = _letras_ocupadas(self, _("&Importar"), _("&Cancelar"))
		self.progreso = PanelProgreso(self, contexto.tareas, contexto.configuracion, usadas, self._habilitar)
		sizer.Add(self.progreso, 0, wx.EXPAND | wx.ALL, borde)
		botones = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_importar = wx.Button(self, label=_("&Importar"))
		self.boton_importar.SetHelpText(_("Convierte el plano con las capas y la escala elegidas."))
		self.boton_cerrar = wx.Button(self, wx.ID_CANCEL, _("&Cancelar"))
		botones.Add(self.boton_importar, 0, wx.RIGHT, borde)
		botones.Add(self.boton_cerrar, 0)
		sizer.Add(botones, 0, wx.ALIGN_RIGHT | wx.ALL, borde)
		self.SetSizerAndFit(sizer)

		self.boton_examinar.Bind(wx.EVT_BUTTON, lambda _e: self._elegir_fichero())
		self.boton_importar.Bind(wx.EVT_BUTTON, lambda _e: self.importar())
		self.lista.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda _e: self._mostrar_uso())
		self.lista.Bind(wx.EVT_LIST_ITEM_FOCUSED, lambda _e: self._mostrar_uso())
		self.uso.Bind(wx.EVT_CHOICE, lambda _e: self._cambiar_uso())
		self.unidades.Bind(wx.EVT_CHOICE, lambda _e: self._al_elegir_unidad())
		self.boton_cerrar.Bind(wx.EVT_BUTTON, self._al_boton_cerrar)
		self.Bind(wx.EVT_CLOSE, self._al_cerrar)
		preparar_dialogo(self, foco_inicial=self.boton_examinar)
		self._habilitar()
		self.CentreOnParent()

	# ── Estado ───────────────────────────────────────────────────────────────

	def trabajando(self) -> bool:
		"""True mientras se lee o se convierte el plano."""
		return self.progreso.trabajando()

	def _habilitar(self) -> None:
		ocupado = self.trabajando()
		self.boton_examinar.Enable(not ocupado)
		self.boton_importar.Enable(not ocupado and self.plano is not None)
		self.uso.Enable(bool(self.capas))

	def _al_boton_cerrar(self, evento: wx.CommandEvent) -> None:
		if self.trabajando():
			self.progreso.cancelar()
			return
		evento.Skip()

	def _al_cerrar(self, evento: wx.CloseEvent) -> None:
		if self.trabajando() and evento.CanVeto():
			self.progreso.cancelar()
			evento.Veto()
			return
		evento.Skip()

	def _fallo(self, error: BaseException) -> None:
		self._habilitar()
		if _es_cancelacion(error):
			self.progreso.decir(_("Importación cancelada."))
			return
		if not isinstance(error, ErrorImportacion):
			log.error("Fallo al importar un plano", exc_info=error)
		self.ultimo_error = _mensaje_de_error(error)
		self.progreso.decir(self.ultimo_error, hablar=False)
		mostrar_error(self, self.ultimo_error, self.GetTitle())

	# ── Fichero y capas ──────────────────────────────────────────────────────

	def _elegir_fichero(self) -> None:
		if self.formato == "dxf":
			comodin = _("Planos DXF (*.dxf)|*.dxf|Todos los ficheros (*.*)|*.*")
		else:
			comodin = _("Dibujos SVG (*.svg)|*.svg|Todos los ficheros (*.*)|*.*")
		with wx.FileDialog(self, self.GetTitle(), wildcard=comodin, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialogo:
			if dialogo.ShowModal() != wx.ID_OK:
				return
			ruta = dialogo.GetPath()
		self.cargar(ruta)

	def cargar(self, ruta: str | Path) -> None:
		"""Lee el plano en segundo plano y enseña sus capas y la escala que se puede proponer."""
		if self.trabajando():
			return
		self.fichero.SetValue(str(ruta))
		lector = importar_dxf.leer_dxf if self.formato == "dxf" else importar_svg.leer_svg

		def trabajo(_tarea: Any) -> plano_mod.Plano:
			return lector(str(ruta))

		self.progreso.lanzar(trabajo, self._cargado, self._fallo, "leer plano", _("Leyendo el plano..."))

	def _cargado(self, plano: plano_mod.Plano) -> None:
		self.plano = plano
		self.capas = plano.capas()
		self.usos = {capa.nombre: capa.sugerencia for capa in self.capas}
		self._pintar_capas()
		metros, explicacion = plano.sugerir_escala()
		self.propuesta.SetValue(explicacion or _("El fichero no dice en qué unidades está dibujado: indíquelo."))
		if metros is not None:
			self.escala.SetValue(texto_numero(metros, 6))
			conocida = next(
				(i for i, (_c, _t, factor) in enumerate(UNIDADES) if factor is not None and abs(factor - metros) < 1e-9), len(UNIDADES) - 1
			)
			self.unidades.SetSelection(conocida)
		self._habilitar()
		self.progreso.decir(_("Plano leído: {n} capas. Revise el uso de cada capa y la escala.").format(n=len(self.capas)))
		if self.capas:
			self.lista.enfocar_fila(0)
			self._mostrar_uso()
			if self.IsShown():
				self.lista.SetFocus()

	def _texto_uso(self, uso: str) -> str:
		return next((_(texto) for clave, texto in USOS if clave == uso), uso)

	def _pintar_capas(self) -> None:
		self.lista.reemplazar_filas([(capa.nombre, self._texto_uso(self.usos[capa.nombre]), capa.descripcion()) for capa in self.capas])

	def _capa_elegida(self) -> plano_mod.CapaPlano | None:
		fila = self.lista.fila_actual()
		return self.capas[fila] if 0 <= fila < len(self.capas) else None

	def _mostrar_uso(self) -> None:
		capa = self._capa_elegida()
		if capa is not None:
			self.uso.SetSelection([clave for clave, _texto in USOS].index(self.usos[capa.nombre]))

	def _cambiar_uso(self) -> None:
		capa = self._capa_elegida()
		if capa is None or self.uso.GetSelection() < 0:
			return
		self.fijar_uso(capa.nombre, USOS[self.uso.GetSelection()][0])

	def fijar_uso(self, capa: str, uso: str) -> None:
		"""Cambia el uso de una capa y lo refleja en la lista (sin releer la fila si no cambia)."""
		if capa not in self.usos or uso not in [clave for clave, _texto in USOS]:
			raise ValueError(f"Capa o uso desconocido: {capa}, {uso}")
		self.usos[capa] = uso
		fila = [c_.nombre for c_ in self.capas].index(capa)
		self.lista.actualizar_celda(fila, 1, self._texto_uso(uso))

	def _al_elegir_unidad(self) -> None:
		factor = UNIDADES[self.unidades.GetSelection()][2]
		if factor is not None:
			self.escala.SetValue(texto_numero(factor, 6))

	def fijar(self, **valores: Any) -> None:
		"""Rellena por nombre: ``escala``, ``nivel``, ``nombre_planta``, ``nombre`` y ``destino`` («nuevo» o «planta»)."""
		campos = {"escala": self.escala, "nivel": self.nivel, "nombre_planta": self.nombre_planta, "nombre": self.nombre}
		for clave, valor in valores.items():
			if clave == "destino":
				self.destino.SetSelection(1 if valor == DESTINO_PLANTA and self.destino.GetCount() > 1 else 0)
			else:
				campos[clave].SetValue(texto_numero(valor, 6) if not isinstance(valor, str) else valor)

	# ── Convertir ────────────────────────────────────────────────────────────

	def _error_de_campo(self, control: wx.Window, mensaje: str) -> None:
		self.ultimo_error = mensaje
		mostrar_error(self, mensaje, _("Revise el formulario"))
		enfocar(control)

	def importar(self) -> None:
		"""Convierte el plano leído con las capas, la escala y el destino elegidos."""
		if self.trabajando() or self.plano is None:
			return
		try:
			escala = leer_numero(self.escala.GetValue())
		except ValueError:
			self._error_de_campo(
				self.escala, _("«Metros por unidad» tiene que ser un número. Puede escribir los decimales con coma o con punto.")
			)
			return
		if escala is None and (self.formato == "svg" or self.plano.sugerir_escala()[0] is None):
			self._error_de_campo(
				self.escala, _("Falta la escala: escriba cuántos metros mide una unidad del dibujo, o elija las unidades.")
			)
			return
		if escala is not None and escala <= 0:
			self._error_de_campo(self.escala, _("«Metros por unidad» tiene que ser mayor que cero."))
			return
		try:
			nivel = leer_numero(self.nivel.GetValue(), decimal=False)
		except ValueError:
			self._error_de_campo(self.nivel, _("«Nivel de la planta» tiene que ser un número entero: 0, 1, -1…"))
			return
		a_planta = self.destino.GetSelection() == 1 and self._contexto.entorno is not None
		# El importador modifica el entorno que recibe: se le da una COPIA, que
		# es lo único que toca el hilo de fondo. El entorno abierto se cambia
		# después, en el hilo de la interfaz y con deshacer.
		copia = Entorno.de_dict(self._contexto.entorno.a_dict()) if a_planta else None
		plantas_previas = {planta.id for planta in copia.plantas} if copia is not None else set()
		opciones = plano_mod.OpcionesPlano(
			nombre=self.nombre.GetValue().strip() or Path(self.fichero.GetValue()).stem,
			metros_por_unidad=float(escala) if escala is not None else None,
			capas_paredes=[n for n, uso in self.usos.items() if uso == plano_mod.USO_PAREDES],
			capas_espacios=[n for n, uso in self.usos.items() if uso in (plano_mod.USO_ESPACIOS, plano_mod.USO_PAREDES)],
			capas_puertas=[n for n, uso in self.usos.items() if uso in (plano_mod.USO_PUERTAS, plano_mod.USO_PAREDES)],
			capas_textos=[n for n, uso in self.usos.items() if uso != plano_mod.USO_IGNORAR],
			nivel=int(nivel) if nivel is not None else None,
			nombre_planta=self.nombre_planta.GetValue().strip(),
			entorno=copia,
		)
		plano = self.plano

		def trabajo(tarea: Any) -> ResultadoImportacion:
			return plano_mod.convertir_plano(plano, opciones, progreso_de_tarea(tarea), cancelado_de_tarea(tarea))

		self.progreso.lanzar(
			trabajo,
			lambda resultado: self._convertido(resultado, plantas_previas if a_planta else None),
			self._fallo,
			"convertir plano",
			_("Convirtiendo el plano..."),
		)

	def _convertido(self, resultado: ResultadoImportacion, plantas_previas: set[str] | None) -> None:
		self.resultado = resultado
		self.ultimo_error = ""
		self._habilitar()
		self.progreso.decir(_("Importación terminada. Se abre el informe."))
		if not mostrar_informe(self, _("Informe de la importación del plano"), texto_de_informe(resultado)):
			self.progreso.decir(_("Borrador descartado."))
			return
		if plantas_previas is None:
			nombre = resultado.entorno.nombre or _("Plano importado")
			hecho = bool(self._contexto.ventana.adoptar_borrador(resultado.entorno, nombre))
		else:
			hecho = self._anadir_plantas(resultado.entorno, plantas_previas)
		if hecho:
			self.creado = True
			if self.IsModal():
				self.EndModal(wx.ID_OK)

	def _anadir_plantas(self, convertido: Entorno, plantas_previas: set[str]) -> bool:
		"""Pasa al entorno abierto las plantas que el importador añadió a la copia."""
		nuevas = [planta for planta in convertido.plantas if planta.id not in plantas_previas]
		if not nuevas:
			return False
		contexto = self._contexto

		def operacion() -> None:
			entorno = contexto.entorno
			entorno.plantas.extend(nuevas)
			entorno.plantas.sort(key=lambda planta: planta.nivel)
			entorno.contador_ids = max(entorno.contador_ids, convertido.contador_ids)

		nombre_planta = nuevas[0].nombre or _("planta importada")
		contexto.ejecutar(
			_("importar la planta {nombre} de un plano").format(nombre=nombre_planta),
			operacion,
			_("Planta {nombre} añadida al entorno.").format(nombre=nombre_planta),
		)
		contexto.ir_a_planta(nuevas[0].id)
		return True


def importar_plano(contexto: Any, formato: str) -> bool:
	"""Abre el diálogo de importar un plano («dxf» o «svg»). True si se creó un borrador o una planta."""
	if formato not in ("dxf", "svg"):
		raise ValueError(f"Formato de plano desconocido: {formato}")
	dialogo = DialogoPlano(contexto.ventana, contexto, formato)
	foco_previo = wx.Window.FindFocus()
	try:
		dialogo.ShowModal()
		return dialogo.creado
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()


# ── Imagen de fondo ──────────────────────────────────────────────────────────


def _plantas_como_opciones(contexto: Any, solo_exteriores: bool = False) -> list[tuple[str, str]]:
	plantas = contexto.entorno.plantas if contexto.entorno is not None else []
	return [(planta.id, planta.nombre or planta.id) for planta in plantas if planta.exterior or not solo_exteriores]


def campos_imagen_fondo(contexto: Any) -> list[Any]:
	"""Esquema del formulario de la imagen de fondo: fichero, planta, dos puntos de calibración y opacidad."""
	ayuda_pixel = N_("Posición del punto en la imagen, en píxeles contados desde la esquina superior izquierda.")
	ayuda_mundo = N_("Posición de ese mismo punto en el entorno.")
	return [
		c(
			"fichero",
			N_("Imagen del plano"),
			"ruta_fichero",
			N_("Un plano escaneado o una foto, en PNG o JPG. Se guarda dentro del entorno y no sale del equipo."),
			obligatorio=True,
			comodin=N_("Imágenes (*.png;*.jpg;*.jpeg)|*.png;*.jpg;*.jpeg|Todos los ficheros (*.*)|*.*"),
		),
		c(
			"planta",
			N_("Planta"),
			"opcion",
			N_("La planta debajo de la cual se pinta la imagen."),
			opciones=_plantas_como_opciones(contexto),
			defecto=contexto.planta_id,
		),
		c("px1", N_("Primer punto: píxel horizontal"), "decimal", ayuda_pixel, obligatorio=True, minimo=0),
		c("py1", N_("Primer punto: píxel vertical"), "decimal", ayuda_pixel, obligatorio=True, minimo=0),
		c("mx1", N_("Primer punto: metros al este"), "metros", ayuda_mundo, obligatorio=True),
		c("my1", N_("Primer punto: metros al norte"), "metros", ayuda_mundo, obligatorio=True),
		c("px2", N_("Segundo punto: píxel horizontal"), "decimal", ayuda_pixel, obligatorio=True, minimo=0),
		c("py2", N_("Segundo punto: píxel vertical"), "decimal", ayuda_pixel, obligatorio=True, minimo=0),
		c("mx2", N_("Segundo punto: metros al este"), "metros", ayuda_mundo, obligatorio=True),
		c("my2", N_("Segundo punto: metros al norte"), "metros", ayuda_mundo, obligatorio=True),
		c(
			"opacidad",
			N_("Opacidad de la imagen"),
			"deslizador",
			N_("Cuánto se ve la imagen debajo del plano: 0 no se ve, 100 se ve del todo."),
			minimo=0,
			maximo=100,
			defecto=50,
			extra={"unidad": N_("por ciento"), "paso_pagina": 10},
		),
	]


def aplicar_imagen_fondo(contexto: Any, valores: dict[str, Any]) -> dict[str, Any]:
	"""Guarda la imagen como recurso del paquete y la asocia a la planta con sus dos puntos de calibración.

	Lanza ``ErrorCampo`` (con el campo que hay que corregir) si la imagen no
	vale o si los dos puntos no sirven para calibrar. Es una operación que se
	puede deshacer; el recurso se queda en el paquete aunque se deshaga.
	"""
	entorno = contexto.entorno
	planta = entorno.planta(valores.get("planta") or "") if entorno is not None else None
	if planta is None:
		raise ErrorCampo("planta", _("Elija la planta sobre la que va la imagen."))
	try:
		nombre_interno, datos = importar_imagen.preparar_recurso(valores["fichero"])
	except ErrorImportacion as error:
		raise ErrorCampo("fichero", str(error)) from error
	punto_imagen_1 = (float(valores["px1"]), float(valores["py1"]))
	punto_imagen_2 = (float(valores["px2"]), float(valores["py2"]))
	punto_mundo_1 = (float(valores["mx1"]), float(valores["my1"]))
	punto_mundo_2 = (float(valores["mx2"]), float(valores["my2"]))
	id_planta = planta.id

	def operacion() -> dict[str, Any]:
		destino = contexto.entorno.planta(id_planta)
		fondo = importar_imagen.definir_fondo(
			contexto.entorno,
			destino,
			nombre_interno,
			punto_imagen_1,
			punto_mundo_1,
			punto_imagen_2,
			punto_mundo_2,
			float(valores.get("opacidad", 50)) / 100.0,
		)
		# Se comprueba ya que los puntos sirven: si no, la operación se anula entera.
		importar_imagen.transformacion(fondo)
		return fondo

	try:
		fondo = contexto.ejecutar(
			_("poner una imagen de fondo en {planta}").format(planta=planta.nombre or planta.id),
			operacion,
			_("Imagen de fondo puesta en {planta}.").format(planta=planta.nombre or planta.id),
		)
	except ErrorImportacion as error:
		raise ErrorCampo("px2", str(error)) from error
	contexto.recursos[nombre_interno] = datos
	return fondo


def importar_imagen_fondo(contexto: Any) -> bool:
	"""Pone una imagen de fondo calibrada en una planta del entorno abierto. True si se puso."""
	if contexto.entorno is None or not contexto.entorno.plantas:
		mostrar_mensaje(
			contexto.ventana,
			_("Abra o cree antes un entorno con una planta: la imagen se pone debajo de una planta."),
			_("Imagen de fondo"),
		)
		return False
	introduccion = _(
		"Elija dos sitios que reconozca en la imagen y cuya posición en el entorno conozca. "
		"Con esos dos puntos quedan fijados la escala, el giro y el lugar de la imagen."
	)
	valores = pedir_formulario(
		contexto.ventana,
		_("Imagen de fondo"),
		campos_imagen_fondo(contexto),
		validar=lambda v: aplicar_imagen_fondo(contexto, v),
		introduccion=introduccion,
	)
	return valores is not None


# ── Rutas GPX y GeoJSON ──────────────────────────────────────────────────────


def campos_gpx(contexto: Any) -> list[Any]:
	"""Esquema del formulario de importar una ruta: fichero, planta de calle y referencias."""
	exteriores = _plantas_como_opciones(contexto, solo_exteriores=True) or _plantas_como_opciones(contexto)
	defecto = (
		contexto.planta_id if contexto.planta_id in [clave for clave, _t in exteriores] else (exteriores[0][0] if exteriores else None)
	)
	return [
		c(
			"fichero",
			N_("Fichero de la ruta"),
			"ruta_fichero",
			N_("Una ruta o unos puntos grabados, en GPX o GeoJSON. Se lee del disco y no sale del equipo."),
			obligatorio=True,
			comodin=N_("Rutas (*.gpx;*.geojson;*.json)|*.gpx;*.geojson;*.json|Todos los ficheros (*.*)|*.*"),
		),
		c(
			"planta",
			N_("Planta de calle"),
			"opcion",
			N_("La planta exterior sobre la que se coloca la ruta."),
			opciones=exteriores,
			defecto=defecto,
		),
		c(
			"referencias",
			N_("Dejar referencias en los vértices de la ruta"),
			"si_no",
			N_("Crea una referencia en cada punto principal de la ruta, que es lo que el alumno encuentra al recorrerla."),
			defecto=True,
		),
	]


def aplicar_gpx(contexto: Any, valores: dict[str, Any]) -> Any:
	"""Coloca la ruta sobre la planta (operación que se puede deshacer) y devuelve el informe."""
	entorno = contexto.entorno
	planta = entorno.planta(valores.get("planta") or "") if entorno is not None else None
	if planta is None:
		raise ErrorCampo("planta", _("Elija la planta de calle sobre la que va la ruta."))
	ruta = Path(valores["fichero"])
	try:
		trazado = importar_gpx_mod.leer_gpx(ruta) if ruta.suffix.lower() == ".gpx" else importar_gpx_mod.leer_geojson(ruta)
	except ErrorImportacion as error:
		raise ErrorCampo("fichero", str(error)) from error
	id_planta = planta.id

	def operacion() -> Any:
		return importar_gpx_mod.anadir_trazado(
			contexto.entorno, contexto.entorno.planta(id_planta), trazado, bool(valores.get("referencias", True))
		)

	try:
		return contexto.ejecutar(
			_("importar la ruta {nombre}").format(nombre=ruta.stem), operacion, _("Ruta {nombre} importada.").format(nombre=ruta.stem)
		)
	except ErrorImportacion as error:
		raise ErrorCampo("fichero", str(error)) from error


def importar_gpx(contexto: Any) -> bool:
	"""Coloca una ruta GPX o GeoJSON sobre un exterior georreferenciado y enseña su informe. True si se importó."""
	titulo = _("Importar una ruta GPX")
	if contexto.entorno is None:
		mostrar_mensaje(contexto.ventana, _("Abra antes el entorno de calle sobre el que quiere colocar la ruta."), titulo)
		return False
	if not contexto.entorno.georef:
		mostrar_mensaje(
			contexto.ventana,
			_(
				"Este entorno no está georreferenciado: no se sabe a qué lugar real corresponde, así que no se puede situar una ruta sobre él. "
				"Las rutas se colocan sobre entornos importados de OpenStreetMap."
			),
			titulo,
		)
		return False
	valores = pedir_formulario(contexto.ventana, titulo, campos_gpx(contexto), validar=lambda v: aplicar_gpx(contexto, v))
	if valores is None:
		return False
	informe = valores.get("_producto")
	if informe is not None:
		mostrar_informe(
			contexto.ventana, _("Informe de la importación de la ruta"), texto_de_informe(informe, contexto.entorno), con_decision=False
		)
	return True
