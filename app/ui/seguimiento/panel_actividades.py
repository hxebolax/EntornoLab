"""Pestaña «Actividades» del entorno abierto: lista de actividades del paquete y lo que se hace con ellas.

Edita en el sitio ``contexto.actividades`` y, tras cada cambio, llama a
``contexto.marcar_modificado``. No guarda referencias al entorno entre
eventos: lo lee del contexto cada vez (el Estudio lo sustituye al deshacer).
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Sequence
from typing import Any

import wx

from app.core.i18n import _
from app.seguimiento.alumnos import Alumno, Fichas
from app.supervision.sala import ErrorSala
from app.ui.accesibilidad.dialogos import elegir_opcion, mostrar_error, mostrar_mensaje
from app.ui.accesibilidad.teclado import vincular_menu_contextual
from app.ui.seguimiento import actividades_api as api
from app.ui.seguimiento import presentador_actividades as pres
from app.ui.seguimiento import presentador_alumnos, presentador_supervision, textos
from app.ui.seguimiento.comun import (
	DialogoFormulario,
	Problema,
	Reloj,
	crear_boton,
	crear_casillas,
	crear_desplegable,
	crear_lista,
	crear_texto,
	letras_de_menus,
	mostrar_modal,
	mostrar_texto,
	pedir_ruta_guardar,
	poner_texto,
)
from app.ui.seguimiento.contexto import anunciar
from app.ui.seguimiento.dialogos_acceso import asegurar_base
from app.ui.seguimiento.formulario_actividad import editar_actividad
from app.ui.seguimiento.textos import Letras

log = logging.getLogger(__name__)

# Cada cuánto se lee la sala mientras haya un reproductor lanzado desde «Probar ahora».
INTERVALO_SONDEO_MS = 500


def _vivo(proceso: Any) -> bool:
	"""Si un reproductor lanzado sigue abierto (un doble sin ``vivo`` cuenta como cerrado)."""
	try:
		return bool(proceso.vivo())
	except AttributeError, OSError:
		log.debug("No se ha podido saber si un reproductor sigue vivo", exc_info=True)
		return False


class DialogoTipoActividad(DialogoFormulario):
	"""Elige el tipo de la actividad nueva, por grupos (juegos, prácticas y exámenes), con su descripción."""

	def __init__(self, padre: wx.Window | None) -> None:
		super().__init__(padre, _("Nueva actividad"))
		self.tipo = ""
		todos = api.tipos()
		self._grupos = [grupo for grupo in textos.GRUPOS_TIPO if any(getattr(info, "grupo", "") == grupo for info in todos.values())]
		self._grupos.extend(sorted({str(getattr(info, "grupo", "")) for info in todos.values()} - set(self._grupos) - {""}))
		self._tipos: list[str] = []
		self.grupo = crear_desplegable(
			self.panel,
			self.letras.poner(_("Grupo:")),
			[textos.nombre(textos.GRUPOS_TIPO, grupo) for grupo in self._grupos],
			sizer=self.sizer,
			ayuda=_(
				"Juegos: aprender jugando. Prácticas: ejercicios con ayuda. Exámenes: pruebas sin pistas, que se pueden repetir idénticas otro día."
			),
		)
		self.etiqueta_lista = wx.StaticText(self.panel, label=self.letras.poner(_("Tipo de actividad:")))
		self.lista = wx.ListBox(self.panel, style=wx.LB_SINGLE, size=wx.Size(460, 190), name=_("Tipo de actividad"))
		self.lista.SetHelpText(_("Elija el tipo con las flechas. Debajo se describe el que está elegido. Intro lo acepta."))
		self.sizer.Add(self.etiqueta_lista, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		self.sizer.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.descripcion = crear_texto(
			self.panel,
			self.letras.poner(_("Descripción del tipo elegido:")),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=80,
			ancho=460,
			ayuda=_("En qué consiste el tipo de actividad elegido en la lista."),
		)
		self.grupo.Bind(wx.EVT_CHOICE, lambda _evento: self._cargar())
		self.lista.Bind(wx.EVT_LISTBOX, lambda _evento: self._describir())
		self.lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda _evento: self.aceptar())
		self._cargar()
		self.terminar(self.grupo, tamano_minimo=(520, 480))

	def _cargar(self) -> None:
		indice = self.grupo.GetSelection()
		grupo = self._grupos[indice] if 0 <= indice < len(self._grupos) else ""
		todos = api.tipos()
		self._tipos = [ident for ident, info in todos.items() if getattr(info, "grupo", "") == grupo]
		self.lista.Set([api.nombre_tipo(ident) for ident in self._tipos])
		if self._tipos:
			self.lista.SetSelection(0)
		self._describir()

	def _describir(self) -> None:
		indice = self.lista.GetSelection()
		poner_texto(self.descripcion, api.descripcion_tipo(self._tipos[indice]) if 0 <= indice < len(self._tipos) else "")

	def validar(self) -> Problema | None:
		indice = self.lista.GetSelection()
		if not 0 <= indice < len(self._tipos):
			return _("Elija un tipo de actividad."), self.lista
		self.tipo = self._tipos[indice]
		return None


class DialogoAsignar(DialogoFormulario):
	"""Marca a qué alumnos se les pone una actividad en su lista de trabajo."""

	def __init__(self, padre: wx.Window | None, actividad: dict[str, Any], alumnos: Sequence[Alumno], entorno_id: str) -> None:
		super().__init__(padre, _("Asignar la actividad «{nombre}»").format(nombre=actividad.get("nombre") or actividad.get("id") or ""))
		self.alumnos = list(alumnos)
		self.marcados: list[bool] = []
		self.lista = crear_casillas(
			self.panel,
			self.letras.poner(_("Alumnos que tienen que hacerla:")),
			[alumno.alias for alumno in self.alumnos],
			sizer=self.sizer,
			alto=220,
			proporcion=1,
			ayuda=_("Marque los alumnos a los que se asigna. La actividad aparecerá en su lista de trabajo, en su ficha."),
		)
		for indice, alumno in enumerate(self.alumnos):
			self.lista.Check(indice, presentador_alumnos.tiene_asignada(alumno, entorno_id, str(actividad.get("id", ""))))
		self.terminar(self.lista, tamano_minimo=(420, 380))

	def validar(self) -> Problema | None:
		marcados = set(self.lista.GetCheckedItems())
		self.marcados = [indice in marcados for indice in range(len(self.alumnos))]
		return None


class DialogoProbarComo(DialogoFormulario):
	"""Elige con qué alumno se prueba la actividad: el reproductor recibe sus ajustes, su nivel y su lista de trabajo."""

	def __init__(self, padre: wx.Window | None, alias: Sequence[str]) -> None:
		super().__init__(padre, _("Probar la actividad"))
		self._alias = list(alias)
		self.alias = ""
		self.alumno = crear_desplegable(
			self.panel,
			self.letras.poner(_("Probar como:")),
			[_("Sin alumno (invitado)"), *self._alias],
			sizer=self.sizer,
			ayuda=_(
				"Con un alumno, el reproductor usa los ajustes de juego de su ficha y el nivel en que va en esta actividad, "
				"y la sesión se guarda con su alias. «Sin alumno» la prueba usted, sin ficha."
			),
		)
		self.terminar(self.alumno, etiqueta_aceptar=self.letras.poner(_("Probar")))

	def validar(self) -> Problema | None:
		elegido = self.alumno.GetSelection()
		self.alias = self._alias[elegido - 1] if 0 < elegido <= len(self._alias) else ""
		return None


class DialogoExportarPaquete(DialogoFormulario):
	"""Elige qué actividades lleva el «Paquete para el alumno»."""

	def __init__(self, padre: wx.Window | None, actividades: Sequence[dict[str, Any]], elegida: int = -1) -> None:
		super().__init__(padre, _("Paquete para el alumno"))
		self._ids = [str(actividad.get("id", "")) for actividad in actividades]
		self.ids: list[str] = []
		crear_texto(
			self.panel,
			self.letras.poner(_("Qué es:")),
			_(
				"Un fichero de entorno que lleva solo las actividades que marque, para copiarlo al ordenador del alumno y abrirlo con el "
				"reproductor. No contiene datos de ningún alumno."
			),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=64,
			ancho=460,
		)
		self.lista = crear_casillas(
			self.panel,
			self.letras.poner(_("Actividades que lleva el paquete:")),
			[str(a.get("nombre") or a.get("id") or "") for a in actividades],
			sizer=self.sizer,
			alto=200,
			proporcion=1,
			ayuda=_("Marque las actividades que debe llevar el paquete."),
		)
		for indice in range(self.lista.GetCount()):
			self.lista.Check(indice, elegida < 0 or indice == elegida)
		self.terminar(self.lista, etiqueta_aceptar=self.letras.poner(_("Guardar el paquete...")), tamano_minimo=(500, 440))

	def validar(self) -> Problema | None:
		self.ids = [self._ids[indice] for indice in self.lista.GetCheckedItems()]
		if not self.ids:
			return _("Marque al menos una actividad."), self.lista
		return None


class PanelActividades(wx.Panel):
	"""Lista de actividades del paquete abierto con sus acciones."""

	def __init__(self, padre: wx.Window, contexto: Any, servicio: Any) -> None:
		super().__init__(padre, name=_("Actividades"))
		self.contexto = contexto
		self.servicio = servicio
		self._cambiando = False
		self._cancelar: list[Callable[[], Any]] = []
		# Las letras preferidas van escritas en cada etiqueta; ``Letras`` solo las cambia si la ventana
		# principal ya usa alguna. Alt+1 a Alt+5 son atajos suyos: tampoco se usan como letra de reserva.
		letras = Letras(self._letras_ocupadas() | set("12345"))
		columna = wx.BoxSizer(wx.VERTICAL)
		self.lista = crear_lista(
			self,
			letras.poner(_("A&ctividades de este entorno:")),
			pres.columnas(),
			getattr(contexto, "configuracion", None),
			sizer=columna,
			ayuda=_(
				"Juegos, prácticas y exámenes preparados para este entorno. Arriba y abajo cambian de actividad; izquierda y derecha "
				"leen las columnas. Intro la edita, Suprimir la borra y la tecla Aplicaciones abre el menú de acciones. "
				"Si la lista está vacía, abra o cree un entorno y use «Nueva»."
			),
		)
		fila = wx.WrapSizer(wx.HORIZONTAL)
		self.botones: dict[str, wx.Button] = {}
		self._acciones: list[tuple[str, str, Callable[[], None], str, bool]] = [
			("nueva", _("&Nueva actividad..."), self.nueva, _("Crea una actividad eligiendo su tipo: juego, práctica o examen."), False),
			("editar", _("E&ditar..."), self.editar, _("Abre el formulario de la actividad elegida."), True),
			("duplicar", _("Du&plicar"), self.duplicar, _("Crea una copia de la actividad elegida, para hacer una variante."), True),
			("borrar", _("&Borrar..."), self.borrar, _("Borra la actividad elegida. Pide confirmación."), True),
			(
				"subir",
				_("Subi&r"),
				lambda: self.mover(-1),
				_("Mueve la actividad elegida un puesto hacia arriba. El alumno las ve en este orden."),
				True,
			),
			("bajar", _("Ba&jar"), lambda: self.mover(1), _("Mueve la actividad elegida un puesto hacia abajo."), True),
			("comprobar", _("Co&mprobar"), self.comprobar, _("Revisa la actividad elegida y dice los problemas encontrados."), True),
			(
				"probar",
				_("Pr&obar ahora"),
				self.probar,
				_("Abre el reproductor con la actividad elegida, para jugarla como el alumno. Guarda antes el entorno."),
				True,
			),
			(
				"asignar",
				_("Asi&gnar a alumnos..."),
				self.asignar,
				_("Pone la actividad elegida en la lista de trabajo de uno o varios alumnos."),
				True,
			),
			(
				"exportar",
				_("Paque&te para el alumno..."),
				self.exportar,
				_("Guarda un fichero de entorno con solo las actividades que elija, para llevarlo al ordenador del alumno."),
				True,
			),
		]
		for clave, etiqueta, accion, ayuda, _necesita in self._acciones:
			self.botones[clave] = crear_boton(self, letras.poner(etiqueta), accion, ayuda, fila)
		columna.Add(fila, 0, wx.EXPAND | wx.ALL, 2)
		self.SetSizer(columna)
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.editar())
		self.lista.Bind(wx.EVT_LIST_ITEM_FOCUSED, self._al_elegir)
		self.lista.Bind(wx.EVT_KEY_DOWN, self._tecla)
		vincular_menu_contextual(self.lista, self._menu)
		for evento in ("entorno_abierto", "entorno_cerrado", "actividades_cambiadas"):
			try:
				self._cancelar.append(contexto.suscribir(evento, self._al_cambio_externo))
			except ValueError, AttributeError:
				log.warning("El contexto no admite la suscripción al evento %s", evento)
		# Tras «Probar ahora», alguien tiene que leer la sala aunque la ventana de supervisión esté cerrada:
		# así llega la ficha al reproductor que se conecta y se sabe si el reproductor se cierra.
		escuchar = getattr(getattr(servicio, "sala", None), "escuchar", None)
		if callable(escuchar):
			self._cancelar.append(escuchar(self._suceso_sala))
		self._sondeo = Reloj(self, self._sondear)
		self._vueltas_sin_vivos = 0
		self.recargar()

	def _letras_ocupadas(self) -> set[str]:
		"""Letras que no puede usar el panel: las de los menús de la ventana principal."""
		ocupadas: set[str] = set()
		obtener = getattr(self.contexto, "letras_ocupadas", None)
		if callable(obtener):
			try:
				ocupadas |= {str(letra).lower() for letra in obtener()}
			except Exception:  # noqa: BLE001 - la ventana principal puede estar a medio construir; se cae al recuento directo
				log.debug("No se han podido pedir las letras ocupadas al contexto", exc_info=True)
		ventana = getattr(self.contexto, "ventana", None)
		if ventana is not None:
			ocupadas |= letras_de_menus(ventana)
		return ocupadas

	def _darse_de_baja(self) -> None:
		"""Cancela las suscripciones al contexto y a la sala (el panel ya no existe)."""
		for cancelar in self._cancelar:
			if callable(cancelar):
				cancelar()
		self._cancelar.clear()

	# ── Sala: reproductores lanzados desde aquí ──────────────────────────────

	def _sondear(self) -> None:
		"""Lee la sala mientras quede algún reproductor lanzado vivo; después se para."""
		sala = getattr(self.servicio, "sala", None)
		if sala is not None:
			sala.sondear()
		if any(_vivo(proceso) for proceso in getattr(self.servicio, "procesos", [])):
			self._vueltas_sin_vivos = 0
			return
		# Una vuelta más tras cerrarse el último: el aviso de su cierre puede llegar en el sondeo siguiente.
		self._vueltas_sin_vivos += 1
		if self._vueltas_sin_vivos >= 2 and self._sondeo.IsRunning():
			self._sondeo.Stop()

	def _suceso_sala(self, suceso: dict[str, Any]) -> None:
		"""Dice que el reproductor se ha cerrado, si nadie más lo va a decir (la ventana de supervisión ya lo anuncia)."""
		if not self:
			self._darse_de_baja()
			return
		if suceso.get("tipo") != "proceso_terminado":
			return
		if getattr(self.servicio, "ventanas", {}).get("supervision"):
			return
		anunciar(self.contexto, presentador_supervision.frase_suceso(suceso))

	# ── Lista ────────────────────────────────────────────────────────────────

	@property
	def actividades(self) -> list[dict[str, Any]]:
		"""La lista de actividades del paquete abierto (la del contexto: se edita en el sitio)."""
		return self.contexto.actividades

	def _al_cambio_externo(self, *_args: Any) -> None:
		if not self:
			# El panel se destruyó con la ventana: en vez de atender su destrucción
			# (momento delicado para ejecutar Python), se da de baja al primer aviso.
			self._darse_de_baja()
			return
		if self._cambiando:
			return
		self.recargar()

	def recargar(self, fila: int | None = None) -> None:
		"""Pone la lista al día. Si no cambia el número de filas, solo se actualizan las celdas."""
		entorno = getattr(self.contexto, "entorno", None)
		filas = [pres.fila_actividad(actividad, entorno) for actividad in self.actividades] if entorno is not None else []
		if len(filas) == self.lista.numero_filas():
			for indice, valores in enumerate(filas):
				self.lista.actualizar_fila(indice, valores)
		else:
			self.lista.reemplazar_filas(filas)
		if fila is not None and filas:
			self.lista.enfocar_fila(max(0, min(fila, len(filas) - 1)), anunciar=False)
		hay_entorno = entorno is not None
		hay_elegida = hay_entorno and self.elegida() is not None
		for clave, _etiqueta, _accion, _ayuda, necesita in self._acciones:
			self.botones[clave].Enable(hay_elegida if necesita else hay_entorno)

	def indice(self) -> int:
		"""Posición de la actividad elegida, o -1."""
		fila = self.lista.fila_actual()
		return fila if 0 <= fila < len(self.actividades) else -1

	def elegida(self) -> dict[str, Any] | None:
		"""La actividad elegida, o ``None``."""
		indice = self.indice()
		return self.actividades[indice] if indice >= 0 else None

	def _al_elegir(self, evento: wx.ListEvent) -> None:
		"""Deja la actividad elegida en el contexto, para que el plano dibuje sus premios y su inicio."""
		evento.Skip()
		if not hasattr(self.contexto, "actividad_actual") or self._cambiando:
			return
		elegida = self.elegida()
		if self.contexto.actividad_actual is elegida:
			return
		self.contexto.actividad_actual = elegida
		self._avisar()

	def _avisar(self) -> None:
		emitir = getattr(self.contexto, "emitir", None)
		if not callable(emitir):
			return
		self._cambiando = True
		try:
			emitir("actividades_cambiadas")
		finally:
			self._cambiando = False

	def _modificado(self, operacion: str, fila: int | None = None) -> None:
		"""Tras tocar la lista: avisa al Estudio y repinta."""
		self._cambiando = True
		try:
			self.contexto.marcar_modificado(operacion)
		finally:
			self._cambiando = False
		self.recargar(fila)

	def _tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_DELETE and evento.GetModifiers() == wx.MOD_NONE:  # atajo: Supr
			self.borrar()
			return
		evento.Skip()

	def _menu(self) -> wx.Menu | None:
		if getattr(self.contexto, "entorno", None) is None:
			return None
		menu = wx.Menu()
		letras = Letras()
		hay = self.elegida() is not None
		for _clave, etiqueta, accion, _ayuda, necesita in self._acciones:
			elemento = menu.Append(wx.ID_ANY, letras.poner(textos.sin_marca(etiqueta)))
			elemento.Enable(hay or not necesita)
			self.Bind(wx.EVT_MENU, lambda _evento, a=accion: a(), elemento)
		return menu

	def _exigir(self) -> dict[str, Any] | None:
		if getattr(self.contexto, "entorno", None) is None:
			anunciar(self.contexto, _("No hay ningún entorno abierto."))
			return None
		actividad = self.elegida()
		if actividad is None:
			anunciar(self.contexto, _("No hay ninguna actividad elegida."))
		return actividad

	# ── Acciones ─────────────────────────────────────────────────────────────

	def nueva(self) -> None:
		"""Crea una actividad eligiendo su tipo y abre su formulario."""
		entorno = getattr(self.contexto, "entorno", None)
		if entorno is None:
			anunciar(self.contexto, _("Abra o cree antes un entorno."))
			return
		dialogo = DialogoTipoActividad(self.GetTopLevelParent())
		try:
			mostrar_modal(dialogo)
			tipo = dialogo.tipo if dialogo.aceptado else ""
		finally:
			dialogo.Destroy()
		if not tipo:
			self.lista.SetFocus()
			return
		try:
			datos = api.nueva_actividad(tipo, entorno, getattr(self.contexto, "catalogo", None))
		except Exception as error:  # noqa: BLE001 - crear una actividad recorre el entorno; un fallo se explica y no se añade nada
			log.exception("No se ha podido crear una actividad nueva")
			mostrar_error(self.GetTopLevelParent(), _("No se ha podido crear la actividad: {error}").format(error=error))
			return
		datos["id"] = pres.id_unico(self.actividades, str(datos.get("id") or tipo))
		resultado = editar_actividad(self.GetTopLevelParent(), self.contexto, self.servicio, datos)
		if resultado is not None:
			self.actividades.append(resultado)
			self._modificado(_("nueva actividad"), len(self.actividades) - 1)
			anunciar(self.contexto, _("Actividad {nombre} creada.").format(nombre=resultado.get("nombre", "")))
		self.lista.SetFocus()

	def editar(self) -> None:
		"""Abre el formulario de la actividad elegida."""
		actividad = self._exigir()
		if actividad is None:
			return
		indice = self.indice()
		resultado = editar_actividad(self.GetTopLevelParent(), self.contexto, self.servicio, actividad)
		if resultado is not None:
			self.actividades[indice] = resultado
			if getattr(self.contexto, "actividad_actual", None) is actividad:
				self.contexto.actividad_actual = resultado
			self._modificado(_("editar la actividad"), indice)
			anunciar(self.contexto, _("Actividad {nombre} guardada.").format(nombre=resultado.get("nombre", "")))
		self.lista.SetFocus()

	def duplicar(self) -> None:
		"""Duplica la actividad elegida."""
		actividad = self._exigir()
		if actividad is None:
			return
		copia = pres.duplicar(actividad, self.actividades)
		posicion = self.indice() + 1
		self.actividades.insert(posicion, copia)
		self._modificado(_("duplicar la actividad"), posicion)
		anunciar(self.contexto, _("{nombre}: creada.").format(nombre=copia["nombre"]))

	def borrar(self) -> None:
		"""Borra la actividad elegida, tras confirmar."""
		actividad = self._exigir()
		if actividad is None:
			return
		nombre = str(actividad.get("nombre") or actividad.get("id") or "")
		eleccion = elegir_opcion(
			self.GetTopLevelParent(),
			_("Va a borrar la actividad «{nombre}» de este entorno. Las sesiones ya jugadas con ella se conservan.").format(nombre=nombre),
			_("Borrar la actividad"),
			[_("&Borrar la actividad")],
		)
		if eleccion != 0:
			self.lista.SetFocus()
			return
		indice = self.indice()
		del self.actividades[indice]
		if getattr(self.contexto, "actividad_actual", None) is actividad:
			self.contexto.actividad_actual = None
		self._modificado(_("borrar la actividad"), indice)
		anunciar(self.contexto, _("Actividad {nombre} borrada.").format(nombre=nombre))
		self.lista.SetFocus()

	def mover(self, delta: int) -> None:
		"""Sube o baja la actividad elegida."""
		if self._exigir() is None:
			return
		indice = self.indice()
		destino = pres.mover(self.actividades, indice, delta)
		if destino != indice:
			self._modificado(_("ordenar las actividades"), destino)
			anunciar(self.contexto, _("Puesto {n} de {total}.").format(n=destino + 1, total=len(self.actividades)))

	def comprobar(self) -> None:
		"""Comprueba la actividad elegida y enseña el resultado."""
		actividad = self._exigir()
		if actividad is None:
			return
		try:
			avisos = api.validar_actividad(
				copy.deepcopy(actividad),
				self.contexto.entorno,
				getattr(self.contexto, "catalogo", None),
				recursos=getattr(self.contexto, "recursos", None),
			)
		except Exception as error:  # noqa: BLE001 - la validación recorre el entorno entero; su fallo se enseña como tal
			log.exception("Ha fallado la comprobación de una actividad")
			mostrar_error(self.GetTopLevelParent(), _("No se ha podido comprobar la actividad: {error}").format(error=error))
			return
		mostrar_texto(
			self.GetTopLevelParent(),
			_("Comprobación de «{nombre}»").format(nombre=actividad.get("nombre", "")),
			_("&Resultado:"),
			pres.texto_avisos(avisos),
		)
		self.lista.SetFocus()

	def _guardar_para_jugar(self) -> bool:
		"""Deja el paquete guardado en disco (el reproductor lo abre desde su fichero). False si no se pudo."""
		padre = self.GetTopLevelParent()
		if getattr(self.contexto, "ruta_paquete", None) is None or getattr(self.contexto, "modificado", True):
			eleccion = elegir_opcion(
				padre,
				_("El reproductor abre el entorno desde su fichero, así que antes hay que guardarlo con los últimos cambios."),
				_("Probar la actividad"),
				[_("&Guardar y probar")],
			)
			if eleccion != 0:
				return False
			if not self.contexto.guardar():
				mostrar_error(padre, _("No se ha podido guardar el entorno."))
				return False
		if getattr(self.contexto, "ruta_paquete", None) is None:
			mostrar_mensaje(
				padre, _("El entorno sigue sin fichero: guárdelo con Archivo, Guardar como, y vuelva a probar."), _("Probar la actividad")
			)
			return False
		return True

	def _alumno_para_probar(self) -> str | None:
		"""Con qué alumno se prueba: «» sin alumno, None si se cancela.

		Solo se pregunta si los datos de alumnos ya están desbloqueados y hay
		alguno: probar una actividad no debe pedir la contraseña.
		"""
		base = getattr(self.servicio, "base", None)
		if base is None:
			return ""
		try:
			alias = [alumno.alias for alumno in Fichas(base).buscar()]
		except Exception:  # noqa: BLE001 - sin la lista de alumnos se prueba sin alumno, como antes
			log.exception("No se ha podido leer la lista de alumnos para probar una actividad")
			return ""
		if not alias:
			return ""
		dialogo = DialogoProbarComo(self.GetTopLevelParent(), alias)
		try:
			mostrar_modal(dialogo)
			return dialogo.alias if dialogo.aceptado else None
		finally:
			dialogo.Destroy()

	def probar(self) -> None:
		"""Lanza el reproductor con la actividad elegida (y, si se elige, con un alumno: recibe su ficha por la sala)."""
		actividad = self._exigir()
		if actividad is None or not self._guardar_para_jugar():
			return
		alias = self._alumno_para_probar()
		if alias is None:
			self.lista.SetFocus()
			return
		sala = self.servicio.sala
		try:
			if alias:
				# Los ajustes de la ficha llegan por la sala: hace falta una, aunque sea solo para este ordenador.
				sala.asegurar_local()
			conexion = sala.argumentos_conexion() if sala.activa else []
		except ErrorSala as error:
			mostrar_error(self.GetTopLevelParent(), str(error))
			return
		argumentos = pres.argumentos_probar(self.contexto.ruta_paquete, str(actividad.get("id", "")), alumno=alias, conexion=conexion)
		try:
			self.servicio.lanzar(argumentos)
		except Exception as error:  # noqa: BLE001 - ErrorProceso u otro fallo al arrancar: se explica
			log.exception("No se ha podido lanzar el reproductor para probar una actividad")
			mostrar_error(self.GetTopLevelParent(), _("No se ha podido abrir el reproductor: {error}").format(error=error))
			return
		if sala.activa and not self._sondeo.IsRunning():
			self._vueltas_sin_vivos = 0
			self._sondeo.Start(INTERVALO_SONDEO_MS)
		if alias:
			anunciar(
				self.contexto,
				_("Reproductor abierto con la actividad {nombre}, como {alias}.").format(nombre=actividad.get("nombre", ""), alias=alias),
			)
		else:
			anunciar(self.contexto, _("Reproductor abierto con la actividad {nombre}.").format(nombre=actividad.get("nombre", "")))

	def asignar(self) -> None:
		"""Asigna la actividad elegida a uno o varios alumnos."""
		actividad = self._exigir()
		if actividad is None:
			return
		padre = self.GetTopLevelParent()
		base = asegurar_base(self.contexto, self.servicio, padre)
		if base is None:
			return
		fichas = Fichas(base)
		alumnos = fichas.buscar()
		if not alumnos:
			mostrar_mensaje(padre, _("Todavía no hay alumnos. Créelos en el menú Alumnos."), _("Asignar la actividad"))
			return
		entorno = self.contexto.entorno
		dialogo = DialogoAsignar(padre, actividad, alumnos, str(entorno.id))
		try:
			mostrar_modal(dialogo)
			if not dialogo.aceptado:
				return
			marcados = dialogo.marcados
		finally:
			dialogo.Destroy()
		paquete = getattr(self.contexto, "ruta_paquete", None)
		cambios = 0
		enviar = getattr(self.servicio, "enviar_ficha", None)
		for alumno, marcado in zip(alumnos, marcados, strict=True):
			if marcado != presentador_alumnos.tiene_asignada(alumno, str(entorno.id), str(actividad.get("id", ""))):
				cambiado = presentador_alumnos.asignar(
					fichas, alumno, entorno, actividad, paquete.name if paquete is not None else "", asignada=marcado
				)
				cambios += 1
				if callable(enviar):
					# Si el alumno está jugando conectado, su lista de trabajo cambia al momento.
					enviar(cambiado)
		anunciar(
			self.contexto,
			textos.contar(cambios, "Lista de trabajo cambiada para {n} alumno.", "Lista de trabajo cambiada para {n} alumnos."),
		)
		self.lista.SetFocus()

	def exportar(self) -> None:
		"""Guarda un «Paquete para el alumno» con las actividades que se elijan."""
		if self._exigir() is None:
			return
		padre = self.GetTopLevelParent()
		dialogo = DialogoExportarPaquete(padre, self.actividades, self.indice())
		try:
			mostrar_modal(dialogo)
			if not dialogo.aceptado:
				return
			ids = dialogo.ids
		finally:
			dialogo.Destroy()
		nombre = str(getattr(self.contexto.entorno, "nombre", "") or "entorno")
		ruta = pedir_ruta_guardar(
			padre, _("Guardar el paquete para el alumno"), _("Entorno de EntornoLab (*.elab)|*.elab"), f"{nombre} (alumno).elab"
		)
		if ruta is None:
			return
		try:
			cuantas = pres.exportar_paquete_alumno(self.contexto, ids, ruta)
		except Exception as error:  # noqa: BLE001 - ErrorFormato, disco lleno, ruta imposible: se explica
			log.exception("No se ha podido exportar el paquete para el alumno")
			mostrar_error(padre, _("No se ha podido guardar el paquete: {error}").format(error=error))
			return
		anunciar(self.contexto, textos.contar(cuantas, "Paquete guardado con {n} actividad.", "Paquete guardado con {n} actividades."))
		self.lista.SetFocus()
