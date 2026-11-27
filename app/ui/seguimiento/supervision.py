"""Ventana de supervisión en vivo.

Sigue el patrón del panel de servidor del autor: la sala vive en su hilo y
la ventana NUNCA espera por ella. Un temporizador lee su «foto» y sus
sucesos y pone la pantalla al día sin molestar:

- las listas no se reconstruyen: se actualizan las celdas que cambian y se
  añaden filas al final, de modo que el foco y la fila elegida no se mueven;
- los campos de solo lectura solo se reescriben cuando su texto cambia, y
  conservan la posición del cursor de quien los está leyendo;
- la voz dice solo los tipos de suceso que el profesional ha elegido, en
  frases breves, sin interrumpir y resumiendo si llegan muchos a la vez. Lo
  que se dice queda también en la lista de sucesos, para repasarlo.

Las órdenes (pausar, mensaje, pista, recolocar...) se envían con
``Sala.pedir``, que vuelve al momento.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import wx

from app.core.i18n import _
from app.seguimiento.alumnos import Fichas
from app.supervision.sala import ErrorSala
from app.ui.accesibilidad.dialogos import elegir_opcion, mostrar_error, mostrar_mensaje, pedir_texto
from app.ui.seguimiento import presentador_actividades, textos
from app.ui.seguimiento import presentador_supervision as pres
from app.ui.seguimiento.comun import (
	DialogoFormulario,
	Problema,
	Reloj,
	VentanaSeguimiento,
	anadir_linea,
	crear_boton,
	crear_casilla,
	crear_casillas,
	crear_desplegable,
	crear_lista,
	crear_texto,
	en_segundo_plano,
	mostrar_modal,
	poner_opciones,
	poner_texto,
)
from app.ui.seguimiento.contexto import anunciar
from app.ui.seguimiento.dialogos_acceso import asegurar_base
from app.ui.seguimiento.editor_ayudas import DialogoAyudas
from app.ui.seguimiento.editor_premios import DialogoPremio
from app.ui.seguimiento.plano_simple import PlanoSimple
from app.ui.seguimiento.selector_lugar import DialogoLugar

log = logging.getLogger(__name__)

INTERVALO_MS = 500
MAXIMO_REGISTRO = 500
_BALIZAS: tuple[int, ...] = (0, 10, 20, 30, 60)


class DialogoPista(DialogoFormulario):
	"""Una pista para el alumno: un texto que se le dice y, si se quiere, una baliza durante unos segundos."""

	def __init__(self, padre: wx.Window | None, alias: str) -> None:
		super().__init__(padre, _("Dar una pista a {alias}").format(alias=alias))
		self.texto_pista = ""
		self.baliza_s = 0
		self.campo = crear_texto(
			self.panel,
			self.letras.poner(_("Texto de la pista (opcional):")),
			sizer=self.sizer,
			multilinea=True,
			alto=70,
			ancho=440,
			ayuda=_("Lo que se le dice al alumno. Si lo deja vacío, la actividad redacta la pista del objetivo actual."),
		)
		self.baliza = crear_desplegable(
			self.panel,
			self.letras.poner(_("Baliza sonora hacia el objetivo:")),
			[_("Sin baliza")] + [_("Durante {n} segundos").format(n=segundos) for segundos in _BALIZAS[1:]],
			sizer=self.sizer,
			ayuda=_("Además del texto, puede hacer sonar un momento una baliza en el lugar al que tiene que ir."),
		)
		self.terminar(self.campo, etiqueta_aceptar=self.letras.poner(_("Dar la pista")))

	def validar(self) -> Problema | None:
		self.texto_pista = self.campo.GetValue().strip()
		self.baliza_s = _BALIZAS[max(0, self.baliza.GetSelection())]
		return None


class DialogoAnuncios(DialogoFormulario):
	"""Qué sucesos del alumno se le dicen por voz al profesional."""

	def __init__(self, padre: wx.Window | None, configuracion: Any) -> None:
		super().__init__(padre, _("Anuncios por voz de la supervisión"))
		self.configuracion = configuracion
		self._tipos = list(textos.EVENTOS_ANUNCIABLES)
		self.activados = crear_casilla(
			self.panel,
			self.letras.poner(_("Decir por voz lo que le ocurre al alumno")),
			pres.anuncios_activados(configuracion),
			sizer=self.sizer,
			ayuda=_("Interruptor general. Apagado, la ventana no dice nada por voz: todo sigue en las listas, para leerlo cuando quiera."),
		)
		self.lista = crear_casillas(
			self.panel,
			self.letras.poner(_("Qué se anuncia:")),
			[textos.nombre(textos.EVENTOS_ANUNCIABLES, tipo) for tipo in self._tipos],
			sizer=self.sizer,
			alto=210,
			proporcion=1,
			ayuda=_("Marque solo lo que quiera oír mientras trabaja. Los anuncios son breves y no cortan lo que esté diciendo su lector."),
		)
		elegidos = pres.leer_tipos(configuracion)
		for indice, tipo in enumerate(self._tipos):
			self.lista.Check(indice, tipo in elegidos)
		self.terminar(self.activados, tamano_minimo=(480, 420))

	def aplicar(self) -> Problema | None:
		tipos = [self._tipos[indice] for indice in self.lista.GetCheckedItems()]
		try:
			pres.guardar_anuncios(self.configuracion, self.activados.GetValue(), tipos)
		except ValueError as error:
			return _("No se han podido guardar las preferencias: {error}").format(error=error), self.lista
		return None


class DialogoSesionLocal(DialogoFormulario):
	"""Elige alumno, entorno y actividad para empezar una sesión en este mismo ordenador."""

	def __init__(self, padre: wx.Window | None, contexto: Any, alias: list[str], entornos: list[tuple[str, Path]]) -> None:
		super().__init__(padre, _("Empezar sesión en este ordenador"))
		self.contexto = contexto
		self._alias = alias
		self._entornos = entornos
		self._actividades: list[dict[str, Any]] = []
		self.alias = ""
		self.ruta: Path | None = None
		self.actividad_id = ""
		self.alumno = crear_desplegable(
			self.panel,
			self.letras.poner(_("Alumno:")),
			[_("Invitado (sin ficha)"), *alias],
			sizer=self.sizer,
			ayuda=_("El alumno que va a jugar. La sesión se guardará con su alias. «Invitado» juega sin ficha."),
		)
		self.entorno = crear_desplegable(
			self.panel,
			self.letras.poner(_("Entorno:")),
			[nombre for nombre, _ruta in entornos],
			sizer=self.sizer,
			ayuda=_("El entorno en el que va a jugar: el que tiene abierto, los suyos y los de ejemplo."),
		)
		self.actividad = crear_desplegable(
			self.panel,
			self.letras.poner(_("Actividad:")),
			sizer=self.sizer,
			ayuda=_("La actividad de ese entorno. «Sin actividad» deja al alumno explorar con libertad."),
		)
		self.entorno.Bind(wx.EVT_CHOICE, lambda _evento: self._cargar_actividades())
		self._cargar_actividades()
		self.terminar(self.alumno, etiqueta_aceptar=self.letras.poner(_("Empezar")))

	def _cargar_actividades(self) -> None:
		indice = self.entorno.GetSelection()
		self._actividades = pres.actividades_de(self.contexto, self._entornos[indice][1]) if 0 <= indice < len(self._entornos) else []
		nombres = [_("Sin actividad: exploración libre"), *[str(a.get("nombre") or a.get("id") or "") for a in self._actividades]]
		poner_opciones(self.actividad, nombres)
		self.actividad.SetSelection(1 if self._actividades else 0)

	def validar(self) -> Problema | None:
		indice = self.entorno.GetSelection()
		if not 0 <= indice < len(self._entornos):
			return _("Elija un entorno."), self.entorno
		self.ruta = self._entornos[indice][1]
		elegido = self.alumno.GetSelection()
		self.alias = self._alias[elegido - 1] if elegido > 0 else ""
		actividad = self.actividad.GetSelection()
		self.actividad_id = str(self._actividades[actividad - 1].get("id", "")) if actividad > 0 else ""
		return None


class VentanaSupervision(VentanaSeguimiento):
	"""Sala, alumnos conectados, lo que oye el elegido, sus sucesos y las órdenes del profesional."""

	CLAVE = "supervision"

	def __init__(self, contexto: Any, servicio: Any) -> None:
		super().__init__(contexto, servicio, _("Supervisión en vivo"), (1000, 780))
		self.configuracion = getattr(contexto, "configuracion", None)
		# Lo ocurrido antes de abrir la ventana se toma de la foto; lo de después llega como sucesos.
		# Por eso se vacía antes la cola: si no, lo que ya está en la foto se apuntaría dos veces.
		servicio.sala.sondear()
		self.foto: dict[str, Any] = servicio.sala.foto()
		self._ids: list[str] = []
		self._eventos: dict[str, list[dict[str, Any]]] = {}
		self._voces: dict[str, list[str]] = {}
		for alumno in self.foto.get("alumnos") or []:
			ident = str(alumno.get("id"))
			self._eventos[ident] = [dict(evento) for evento in alumno.get("eventos") or [] if isinstance(evento, Mapping)]
			self._voces[ident] = [pres.linea_voz(voz) for voz in alumno.get("voces") or [] if isinstance(voz, Mapping)]
		self._mostrado: str | None = None
		self._abriendo = False
		self._error = ""
		self._por_anunciar: list[dict[str, Any]] = []
		self._premios_extra = 0
		self._construir()
		self._dejar = servicio.sala.escuchar(self._suceso)
		self._reloj = Reloj(self, self.refrescar)
		self.terminar(
			self.estado,
			[
				(wx.ACCEL_CTRL, ord("P"), self.pausar),
				(wx.ACCEL_CTRL, ord("M"), self.mensaje),
				(wx.ACCEL_CTRL, ord("I"), self.pista),
				(wx.ACCEL_CTRL, ord("R"), self.recolocar),
				(wx.ACCEL_CTRL, ord("U"), self.ayudas),
				(wx.ACCEL_CTRL, ord("E"), self.premio),
				(wx.ACCEL_CTRL, ord("K"), self.marca),
				(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("R"), self.reiniciar),
				(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("T"), self.terminar_sesion),
				(wx.ACCEL_NORMAL, wx.WXK_F6, self.decir_estado),
			],
		)
		self.refrescar()
		self._reloj.Start(INTERVALO_MS)

	# ── Construcción ─────────────────────────────────────────────────────────

	def _construir(self) -> None:
		letras = self.letras
		panel = self.panel
		self.estado = crear_texto(
			panel,
			letras.poner(_("Estado de la sala:")),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=96,
			ancho=900,
			ayuda=_(
				"Si la sala está abierta, cuántos alumnos hay, el código de emparejamiento, el modo, la dirección de este "
				"ordenador para dictarla y la huella para compararla. Una cosa por línea. Se pone al día solo cuando cambia."
			),
		)
		self.modo = crear_desplegable(
			panel,
			letras.poner(_("Modo de conexión:")),
			[_("Solo este ordenador"), _("Red local, con conexión cifrada")],
			sizer=self.sizer,
			ayuda=_(
				"«Solo este ordenador»: el alumno juega aquí mismo, con mando y auriculares. «Red local»: el alumno juega en otro "
				"ordenador de la misma red y se conecta con la dirección y el código."
			)
			+ " "
			+ _(pres.AVISO_CORTAFUEGOS),
		)
		fila = self.fila_botones()
		self.botones: dict[str, wx.Button] = {}

		def boton(clave: str, etiqueta: str, accion: Callable[[], Any], ayuda: str, donde: wx.Sizer) -> None:
			self.botones[clave] = crear_boton(panel, letras.poner(etiqueta), accion, ayuda, donde)

		boton(
			"abrir", _("Abrir la sala"), self.abrir_sala, _("Abre la sala con el modo elegido y un código de emparejamiento nuevo."), fila
		)
		boton(
			"cerrar_sala",
			_("Cerrar la sala"),
			self.cerrar_sala,
			_("Cierra la sala y desconecta a los alumnos. Sus sesiones se guardan."),
			fila,
		)
		boton("copiar", _("Copiar el código"), self.copiar_codigo, _("Copia al portapapeles el código de emparejamiento."), fila)
		boton(
			"local",
			_("Empezar sesión en este ordenador..."),
			self.empezar_sesion,
			_("Elige alumno, entorno y actividad y abre el reproductor en este ordenador, ya conectado a la sala."),
			fila,
		)
		boton("anuncios", _("Anuncios por voz..."), self.anuncios, _("Elige qué sucesos del alumno se le dicen por voz."), fila)
		self.segunda = crear_casilla(
			panel,
			letras.poner(_("Enviar el sonido del alumno a la segunda salida de audio")),
			self._leer_segunda(),
			sizer=self.sizer,
			ayuda=_(pres.EXPLICACION_SEGUNDA_SALIDA),
		)
		self.segunda.Bind(wx.EVT_CHECKBOX, lambda _evento: self._guardar_segunda())
		self.lista = crear_lista(
			panel,
			letras.poner(_("Alumnos conectados:")),
			pres.columnas(),
			self.configuracion,
			sizer=self.sizer,
			alto=120,
			ayuda=_(
				"Un alumno por fila: alias, estado, entorno, actividad, dónde está, rumbo, tiempo activo, choques, ayudas y objetivos. "
				"Se actualiza sola sin mover el foco. Izquierda y derecha leen las columnas; F6 dice el estado del elegido."
			),
		)
		self.posicion = crear_texto(
			panel,
			letras.poner(_("Posición del alumno elegido:")),
			sizer=self.sizer,
			lectura=True,
			ayuda=_("Dónde está el alumno elegido, hacia dónde mira y qué tiene delante. Se actualiza sola."),
		)
		self.ultimo = crear_texto(
			panel,
			letras.poner(_("Lo último que ha oído:")),
			sizer=self.sizer,
			lectura=True,
			ayuda=_("La última frase que el juego le ha dicho al alumno elegido."),
		)
		centro = wx.BoxSizer(wx.HORIZONTAL)
		izquierda = wx.BoxSizer(wx.VERTICAL)
		self.historial = crear_texto(
			panel,
			letras.poner(_("Historial de lo que ha oído:")),
			sizer=izquierda,
			multilinea=True,
			lectura=True,
			alto=100,
			ancho=620,
			proporcion=1,
			ayuda=_(
				"Todo lo que ha oído el alumno elegido, lo más nuevo al final. Se añade sin mover el cursor si está leyendo más arriba."
			),
		)
		self.sucesos = crear_lista(
			panel,
			letras.poner(_("Sucesos del alumno:")),
			[(_("Instante"), 90), (_("Qué ha pasado"), 480)],
			self.configuracion,
			sizer=izquierda,
			alto=110,
			ayuda=_("Choques, ayudas pedidas, premios encontrados, objetivos cumplidos, cruces inseguros y sus intervenciones, por orden."),
		)
		centro.Add(izquierda, 1, wx.EXPAND)
		self.plano = PlanoSimple(panel)
		centro.Add(self.plano, 0, wx.ALL, 6)
		self.sizer.Add(centro, 1, wx.EXPAND)
		fila = self.fila_botones()
		boton(
			"pausar",
			_("Pausar o reanudar"),
			self.pausar,
			_("Pausa la sesión del alumno elegido, o la reanuda si estaba en pausa. Control+P."),
			fila,
		)
		boton(
			"mensaje", _("Enviar mensaje..."), self.mensaje, _("Escribe una frase que el juego le dice al alumno elegido. Control+M."), fila
		)
		boton("pista", _("Dar una pista..."), self.pista, _("Le da una pista, con un texto o con una baliza un momento. Control+I."), fila)
		boton(
			"recolocar",
			_("Recolocar..."),
			self.recolocar,
			_("Lleva al alumno elegido a un punto del entorno, elegido por planta y espacio. Control+R."),
			fila,
		)
		boton(
			"ayudas", _("Cambiar ayudas..."), self.ayudas, _("Permite o prohíbe ayudas al alumno elegido sobre la marcha. Control+U."), fila
		)
		boton(
			"premio",
			_("Añadir un premio..."),
			self.premio,
			_("Esconde ahora un premio nuevo en la sesión del alumno elegido. Control+E."),
			fila,
		)
		boton("marca", _("Marcar este momento..."), self.marca, _("Deja una nota en este instante de la sesión grabada. Control+K."), fila)
		boton(
			"reiniciar",
			_("Reiniciar..."),
			self.reiniciar,
			_("Vuelve a empezar la actividad del alumno elegido. Control+Mayúsculas+R."),
			fila,
		)
		boton(
			"terminar",
			_("Terminar..."),
			self.terminar_sesion,
			_("Termina la sesión del alumno elegido y la guarda. Control+Mayúsculas+T."),
			fila,
		)
		boton("olvidar", _("Quitar de la lista"), self.olvidar, _("Quita de la lista a un alumno que ya no está conectado."), fila)
		boton("cerrar", _("Cerrar ventana"), self.Close, _("Cierra esta ventana. Si la sala está abierta, pregunta si cerrarla."), fila)
		self.lista.Bind(wx.EVT_LIST_ITEM_FOCUSED, lambda evento: (evento.Skip(), self._pintar_elegido()))
		self.lista.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda evento: (evento.Skip(), self._pintar_elegido()))

	def _leer_segunda(self) -> bool:
		if self.configuracion is None:
			return False
		try:
			return bool(self.configuracion.obtener(pres.CLAVE_SEGUNDA_SALIDA, False))
		except KeyError, TypeError, ValueError:
			log.debug("No se ha podido leer %s", pres.CLAVE_SEGUNDA_SALIDA, exc_info=True)
			return False

	def _guardar_segunda(self) -> None:
		if self.configuracion is None:
			return
		try:
			self.configuracion.establecer(pres.CLAVE_SEGUNDA_SALIDA, bool(self.segunda.GetValue()))
		except ValueError:
			log.warning("No se ha podido guardar la preferencia de la segunda salida", exc_info=True)
			return
		anunciar(self.contexto, _("Se aplicará a los reproductores que se abran a partir de ahora en este ordenador."))

	# ── Refresco ─────────────────────────────────────────────────────────────

	def refrescar(self) -> None:
		"""Lee la sala y pone la ventana al día. Lo llama el temporizador; no espera a nada."""
		if not self:
			return
		self.servicio.sala.sondear()
		self.foto = self.servicio.sala.foto()
		self._pintar()
		pendientes, self._por_anunciar = self._por_anunciar, []
		for frase in pres.frases_a_anunciar(pendientes, pres.anuncios_activados(self.configuracion), pres.leer_tipos(self.configuracion)):
			anunciar(self.contexto, frase)

	def _suceso(self, suceso: dict[str, Any]) -> None:
		"""Un suceso de la sala (lo entrega ``GestorSala.sondear``, lo llame quien lo llame)."""
		if not self:
			self._dejar()
			return
		self._por_anunciar.append(suceso)
		ident = str(suceso.get("alumno") or "")
		tipo = suceso.get("tipo")
		datos = suceso.get("datos") if isinstance(suceso.get("datos"), Mapping) else {}
		if not ident:
			return
		if tipo == "voz":
			self._apuntar_voz(ident, pres.linea_voz(datos))
		elif tipo == "evento":
			self._apuntar_evento(ident, {"t": datos.get("t"), "tipo": datos.get("tipo"), "datos": datos.get("datos") or {}})
		elif tipo == "fin":
			self._apuntar_evento(
				ident,
				{"t": None, "tipo": _("Fin de la sesión") if datos.get("completada") else _("Fin de la sesión sin completar"), "datos": {}},
			)
		elif tipo == "proceso_terminado":
			# Queda también en la lista de sucesos del alumno (el anuncio por voz ya va en ``_por_anunciar``).
			self._apuntar_evento(ident, {"t": None, "tipo": pres.frase_suceso(suceso), "datos": {}})

	def _registro_de(self, ident: str) -> tuple[list[dict[str, Any]], list[str]]:
		"""Sucesos y frases oídas que la ventana guarda de un alumno (vacíos la primera vez que se le ve)."""
		return self._eventos.setdefault(ident, []), self._voces.setdefault(ident, [])

	def _apuntar_voz(self, ident: str, linea: str) -> None:
		_eventos, voces = self._registro_de(ident)
		voces.append(linea)
		del voces[:-MAXIMO_REGISTRO]
		if ident == self._mostrado:
			anadir_linea(self.historial, linea)

	def _apuntar_evento(self, ident: str, evento: dict[str, Any]) -> None:
		eventos, _voces = self._registro_de(ident)
		eventos.append(evento)
		del eventos[:-MAXIMO_REGISTRO]
		if ident == self._mostrado:
			# Al final: añadir una fila no mueve el foco ni la fila que el profesional está leyendo.
			self.sucesos.agregar_fila(pres.fila_evento(evento))

	def _alumno(self, ident: str | None) -> dict[str, Any] | None:
		for alumno in self.foto.get("alumnos") or []:
			if str(alumno.get("id")) == ident:
				return alumno
		return None

	def elegido(self) -> dict[str, Any] | None:
		"""El alumno de la fila enfocada, tal como está en la última foto."""
		fila = self.lista.fila_actual()
		return self._alumno(self._ids[fila]) if 0 <= fila < len(self._ids) else None

	def _sincronizar_alumnos(self) -> None:
		alumnos = list(self.foto.get("alumnos") or [])
		ids = [str(alumno.get("id")) for alumno in alumnos]
		if ids != self._ids:
			# Primero se quitan las filas de quienes ya no están; después se añaden al final los nuevos.
			for fila in reversed(range(len(self._ids))):
				if self._ids[fila] not in ids:
					self.lista.eliminar_fila(fila)
					del self._ids[fila]
			if ids[: len(self._ids)] == self._ids:
				for alumno in alumnos[len(self._ids) :]:
					self.lista.agregar_fila(pres.fila_alumno(alumno))
			else:
				self.lista.reemplazar_filas([pres.fila_alumno(alumno) for alumno in alumnos])
			self._ids = ids
		for fila, alumno in enumerate(alumnos):
			self.lista.actualizar_fila(fila, pres.fila_alumno(alumno))

	def _pintar(self) -> None:
		activa = bool(self.foto.get("activa"))
		poner_texto(self.estado, pres.texto_sala(self.foto, self.segunda.GetValue(), self._abriendo, self._error))
		self._sincronizar_alumnos()
		self._pintar_elegido()
		alumno = self.elegido()
		conectado = bool(alumno and alumno.get("conectado"))
		self.botones["abrir"].Enable(not activa and not self._abriendo)
		self.modo.Enable(not activa and not self._abriendo)
		self.botones["cerrar_sala"].Enable(activa)
		self.botones["copiar"].Enable(activa)
		for clave in ("pausar", "mensaje", "pista", "recolocar", "ayudas", "premio", "marca", "reiniciar", "terminar"):
			self.botones[clave].Enable(conectado)
		self.botones["olvidar"].Enable(bool(alumno) and not conectado)

	def _pintar_elegido(self) -> None:
		"""Pone al día el detalle del alumno elegido; si ha cambiado de alumno, rehace su historial y sus sucesos."""
		alumno = self.elegido()
		ident = str(alumno.get("id")) if alumno else None
		if ident != self._mostrado:
			self._mostrado = ident
			if ident is None:
				self.historial.ChangeValue("")
				self.sucesos.limpiar()
			else:
				eventos, voces = self._registro_de(ident)
				self.historial.ChangeValue("".join(linea + "\n" for linea in voces))
				self.historial.SetInsertionPointEnd()
				self.sucesos.reemplazar_filas([pres.fila_evento(evento) for evento in eventos], conservar_foco=False)
		poner_texto(self.posicion, pres.texto_posicion(alumno))
		poner_texto(self.ultimo, str(alumno.get("ultimo_texto") or "") if alumno else "")
		entorno = getattr(self.contexto, "entorno", None)
		if alumno and entorno is not None:
			self.plano.poner_planta(entorno, str(alumno.get("planta") or ""), getattr(self.contexto, "version", 0))
			self.plano.poner_posicion(alumno.get("x"), alumno.get("y"), alumno.get("rumbo"))
		else:
			self.plano.poner_posicion(None, None)

	# ── Sala ─────────────────────────────────────────────────────────────────

	def abrir_sala(self) -> None:
		"""Abre la sala con el modo elegido. En red se hace en segundo plano (crea el certificado)."""
		sala = self.servicio.sala
		if sala.activa or self._abriendo:
			return
		self._error = ""
		if self.modo.GetSelection() != 1:
			try:
				sala.abrir(red=False)
			except ErrorSala as error:
				self._fallo_al_abrir(error)
				return
			self._sala_abierta(None)
			return
		self._abriendo = True
		self._pintar()
		anunciar(self.contexto, _("Abriendo la sala en red..."))
		en_segundo_plano(lambda: sala.abrir(red=True), self._sala_abierta, self._fallo_al_abrir)

	def _sala_abierta(self, _resultado: Any) -> None:
		if not self:
			return
		self._abriendo = False
		self.foto = self.servicio.sala.foto()
		self._pintar()
		codigo = " ".join(str(self.foto.get("codigo") or ""))
		if self.foto.get("red"):
			anunciar(
				self.contexto,
				_("Sala abierta en red local. Código {codigo}. La dirección y la huella están en el estado de la sala.").format(
					codigo=codigo
				),
			)
		else:
			anunciar(self.contexto, _("Sala abierta solo para este ordenador. Código {codigo}.").format(codigo=codigo))

	def _fallo_al_abrir(self, error: BaseException) -> None:
		if not self:
			return
		self._abriendo = False
		self._error = str(error)
		self._pintar()
		mostrar_error(self, str(error), _("No se ha podido abrir la sala"))

	def cerrar_sala(self) -> None:
		"""Cierra la sala; si hay alumnos conectados, confirma antes."""
		if not self.servicio.sala.activa:
			return
		conectados = sum(1 for alumno in self.foto.get("alumnos") or [] if alumno.get("conectado"))
		if conectados:
			eleccion = elegir_opcion(
				self,
				textos.contar(
					conectados,
					"Hay {n} alumno conectado. Al cerrar la sala se corta su supervisión; su sesión sigue y se guarda en su ordenador.",
					"Hay {n} alumnos conectados. Al cerrar la sala se corta su supervisión; sus sesiones siguen y se guardan en sus ordenadores.",
				),
				_("Cerrar la sala"),
				[_("&Cerrar la sala"), _("&Dejarla abierta")],
			)
			if eleccion != 0:
				return
		self.servicio.sala.cerrar()
		self.foto = self.servicio.sala.foto()
		self._pintar()
		anunciar(self.contexto, _("Sala cerrada."))

	def copiar_codigo(self) -> None:
		"""Copia el código de emparejamiento al portapapeles."""
		codigo = str(self.foto.get("codigo") or "")
		if not codigo:
			return
		if wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(codigo))
			finally:
				wx.TheClipboard.Close()
			anunciar(self.contexto, _("Código copiado al portapapeles."))
		else:
			anunciar(self.contexto, _("No se ha podido usar el portapapeles. El código es {codigo}.").format(codigo=" ".join(codigo)))

	def anuncios(self) -> None:
		"""Abre las preferencias de los anuncios por voz."""
		dialogo = DialogoAnuncios(self, self.configuracion)
		try:
			mostrar_modal(dialogo)
		finally:
			dialogo.Destroy()

	def empezar_sesion(self) -> None:
		"""Elige alumno, entorno y actividad y lanza el reproductor conectado a la sala por el puerto local."""
		entornos = pres.entornos_disponibles(self.contexto)
		if not entornos:
			mostrar_mensaje(
				self, _("No hay ningún entorno guardado que se pueda jugar. Guarde antes el entorno abierto."), _("Empezar sesión")
			)
			return
		base = asegurar_base(self.contexto, self.servicio, self)
		alias = [alumno.alias for alumno in Fichas(base).buscar()] if base is not None else []
		dialogo = DialogoSesionLocal(self, self.contexto, alias, entornos)
		try:
			mostrar_modal(dialogo)
			if not dialogo.aceptado or dialogo.ruta is None:
				return
			ruta, alumno, actividad = dialogo.ruta, dialogo.alias, dialogo.actividad_id
		finally:
			dialogo.Destroy()
		abierto = getattr(self.contexto, "ruta_paquete", None)
		if abierto is not None and Path(abierto) == ruta and getattr(self.contexto, "modificado", False) and not self.contexto.guardar():
			mostrar_error(self, _("No se ha podido guardar el entorno abierto, así que el alumno jugaría con una versión antigua."))
			return
		sala = self.servicio.sala
		try:
			sala.asegurar_local()
			argumentos = [str(ruta)]
			if actividad:
				argumentos += ["--actividad", actividad]
			if alumno:
				argumentos += ["--alumno", alumno]
			self.servicio.lanzar([*argumentos, *sala.argumentos_conexion()])
		except ErrorSala as error:
			mostrar_error(self, str(error))
			return
		except Exception as error:  # noqa: BLE001 - ErrorProceso u otro fallo al arrancar: se explica
			log.exception("No se ha podido lanzar el reproductor para una sesión local")
			mostrar_error(self, _("No se ha podido abrir el reproductor: {error}").format(error=error))
			return
		self.refrescar()
		anunciar(self.contexto, _("Reproductor abierto. El alumno aparecerá en la lista cuando se conecte."))

	# ── Órdenes al alumno elegido ────────────────────────────────────────────

	def _exigir(self) -> dict[str, Any] | None:
		alumno = self.elegido()
		if alumno is None:
			anunciar(self.contexto, _("No hay ningún alumno elegido."))
			return None
		if not alumno.get("conectado"):
			anunciar(self.contexto, _("{alias} no está conectado.").format(alias=alumno.get("alias", "")))
			return None
		return alumno

	def _pedir(self, alumno: Mapping[str, Any], orden: str, dicho: str, **datos: Any) -> bool:
		"""Envía una orden y dice el resultado (el foco no se mueve, así que el lector no lo sabría)."""
		ident = str(alumno.get("id"))
		try:
			enviado = self.servicio.sala.pedir(ident, orden, **datos)
		except ValueError as error:
			log.warning("Orden de supervisión rechazada por el protocolo: %s", orden)
			mostrar_error(self, _("No se ha podido enviar: {error}").format(error=error))
			return False
		if not enviado:
			anunciar(self.contexto, _("No se ha podido enviar: {alias} ya no está conectado.").format(alias=alumno.get("alias", "")))
			return False
		self._apuntar_evento(ident, {"t": alumno.get("tiempo_activo"), "tipo": "intervencion", "datos": {"orden": orden}})
		anunciar(self.contexto, dicho)
		return True

	def pausar(self) -> None:
		"""Pausa la sesión del alumno elegido, o la reanuda."""
		alumno = self._exigir()
		if alumno is None:
			return
		alias = alumno.get("alias", "")
		if alumno.get("pausado"):
			self._pedir(alumno, "reanudar", _("Sesión de {alias} reanudada.").format(alias=alias))
		else:
			self._pedir(alumno, "pausa", _("Sesión de {alias} en pausa.").format(alias=alias))

	def mensaje(self) -> None:
		"""Envía una frase que el juego le dice al alumno."""
		alumno = self._exigir()
		if alumno is None:
			return
		texto = pedir_texto(
			self, _("&Mensaje para {alias}:").format(alias=alumno.get("alias", "")), _("Enviar mensaje"), max_caracteres=1000
		)
		if texto and texto.strip():
			self._pedir(alumno, "mensaje", _("Mensaje enviado."), texto=texto.strip())

	def pista(self) -> None:
		"""Da una pista al alumno, con texto y/o baliza."""
		alumno = self._exigir()
		if alumno is None:
			return
		dialogo = DialogoPista(self, str(alumno.get("alias", "")))
		try:
			mostrar_modal(dialogo)
			if not dialogo.aceptado:
				return
			datos: dict[str, Any] = {}
			if dialogo.texto_pista:
				datos["texto"] = dialogo.texto_pista
			if dialogo.baliza_s:
				datos["baliza_s"] = dialogo.baliza_s
		finally:
			dialogo.Destroy()
		self._pedir(alumno, "pista", _("Pista enviada."), **datos)

	def _entorno_o_aviso(self) -> Any | None:
		entorno = getattr(self.contexto, "entorno", None)
		if entorno is None:
			mostrar_mensaje(
				self,
				_("Para elegir un lugar hace falta tener abierto en el Estudio el entorno en el que está el alumno."),
				_("Supervisión"),
			)
		return entorno

	def recolocar(self) -> None:
		"""Lleva al alumno a un punto elegido por planta y espacio."""
		alumno = self._exigir()
		entorno = self._entorno_o_aviso() if alumno is not None else None
		if alumno is None or entorno is None:
			return
		actual = None
		if isinstance(alumno.get("x"), (int, float)) and isinstance(alumno.get("y"), (int, float)):
			actual = {"planta": alumno.get("planta"), "x": alumno.get("x"), "y": alumno.get("y"), "rumbo": alumno.get("rumbo")}
		dialogo = DialogoLugar(
			self,
			entorno,
			getattr(self.contexto, "catalogo", None),
			_("Recolocar a {alias}").format(alias=alumno.get("alias", "")),
			actual,
			con_rumbo=True,
		)
		try:
			mostrar_modal(dialogo)
			if not dialogo.aceptado or dialogo.valor is None:
				return
			lugar = dialogo.valor
			dicho = dialogo.lugar.describir(lugar)
		finally:
			dialogo.Destroy()
		self._pedir(
			alumno,
			"recolocar",
			_("{alias} recolocado: {lugar}").format(alias=alumno.get("alias", ""), lugar=dicho),
			planta=lugar["planta"],
			x=lugar["x"],
			y=lugar["y"],
			rumbo=lugar.get("rumbo"),
		)

	def ayudas(self) -> None:
		"""Cambia las ayudas permitidas del alumno sobre la marcha."""
		alumno = self._exigir()
		if alumno is None:
			return
		dialogo = DialogoAyudas(self, {}, _("Ayudas de {alias}").format(alias=alumno.get("alias", "")), self.configuracion)
		try:
			mostrar_modal(dialogo)
			reglas = dialogo.reglas if dialogo.aceptado else {}
		finally:
			dialogo.Destroy()
		if reglas:
			self._pedir(alumno, "ayudas", textos.contar(len(reglas), "{n} ayuda cambiada.", "{n} ayudas cambiadas."), ayudas=reglas)

	def premio(self) -> None:
		"""Esconde un premio nuevo en la sesión del alumno."""
		alumno = self._exigir()
		entorno = self._entorno_o_aviso() if alumno is not None else None
		if alumno is None or entorno is None:
			return
		dialogo = DialogoPremio(self, self.contexto, self.servicio)
		try:
			mostrar_modal(dialogo)
			premio = dialogo.premio if dialogo.aceptado else None
		finally:
			dialogo.Destroy()
		if premio is None:
			return
		self._premios_extra += 1
		fila = presentador_actividades.fila_premio(premio, entorno)
		self._pedir(
			alumno,
			"premio",
			_("Premio {nombre} escondido: {lugar}.").format(nombre=fila[0], lugar=fila[1]),
			id=f"extra-{self._premios_extra}",
			nombre=premio["nombre"],
			planta=premio["planta"],
			x=premio["x"],
			y=premio["y"],
			sonido=premio.get("sonido") or "",
			mensaje=premio.get("mensaje") or "",
			visibilidad=premio.get("visibilidad") or "cerca",
		)

	def marca(self) -> None:
		"""Marca este momento de la sesión con una nota."""
		alumno = self._exigir()
		if alumno is None:
			return
		texto = pedir_texto(
			self,
			_("&Nota para este momento de la sesión de {alias}:").format(alias=alumno.get("alias", "")),
			_("Marcar este momento"),
			max_caracteres=2000,
		)
		if texto is None:
			return
		texto = texto.strip()
		if self.servicio.sala.marcar(dict(alumno), texto):
			self._apuntar_evento(str(alumno.get("id")), {"t": alumno.get("tiempo_activo"), "tipo": "marca", "datos": {"texto": texto}})
			anunciar(self.contexto, _("Momento marcado. La nota quedará en la sesión grabada."))
		else:
			anunciar(self.contexto, _("No se ha podido marcar: {alias} ya no está conectado.").format(alias=alumno.get("alias", "")))

	def _confirmar(self, texto: str, titulo: str, accion: str) -> bool:
		return elegir_opcion(self, texto, titulo, [accion]) == 0

	def reiniciar(self) -> None:
		"""Vuelve a empezar la actividad del alumno, tras confirmar."""
		alumno = self._exigir()
		if alumno is None:
			return
		alias = alumno.get("alias", "")
		if self._confirmar(
			_("La actividad de {alias} volverá a empezar desde el principio.").format(alias=alias),
			_("Reiniciar la actividad"),
			_("&Reiniciar"),
		):
			self._pedir(alumno, "reiniciar", _("Actividad de {alias} reiniciada.").format(alias=alias))

	def terminar_sesion(self) -> None:
		"""Termina la sesión del alumno, tras confirmar."""
		alumno = self._exigir()
		if alumno is None:
			return
		alias = alumno.get("alias", "")
		if self._confirmar(
			_("La sesión de {alias} terminará ahora y se guardará.").format(alias=alias), _("Terminar la sesión"), _("&Terminar la sesión")
		):
			self._pedir(alumno, "terminar", _("Sesión de {alias} terminada.").format(alias=alias))

	def olvidar(self) -> None:
		"""Quita de la lista a un alumno que ya no está conectado."""
		alumno = self.elegido()
		if alumno is None or alumno.get("conectado") or self.servicio.sala.sala is None:
			return
		ident = str(alumno.get("id"))
		if self.servicio.sala.sala.olvidar(ident):
			self._eventos.pop(ident, None)
			self._voces.pop(ident, None)
			self.refrescar()

	def decir_estado(self) -> None:
		"""Dice por voz el estado del alumno elegido, sin mover el foco."""
		anunciar(self.contexto, pres.resumen_hablado(self.elegido()))

	# ── Cierre ───────────────────────────────────────────────────────────────

	def puede_cerrar(self) -> bool:
		if not self.servicio.sala.activa:
			return True
		eleccion = elegir_opcion(
			self,
			_(
				"La sala de supervisión está abierta. Puede cerrarla ahora o dejarla abierta y volver a esta ventana más tarde desde el menú Supervisión."
			),
			_("Cerrar la ventana de supervisión"),
			[_("Cerrar también la &sala"), _("&Dejar la sala abierta")],
		)
		if eleccion is None:
			return False
		if eleccion == 0:
			self.servicio.sala.cerrar()
			anunciar(self.contexto, _("Sala cerrada."))
		else:
			anunciar(self.contexto, _("La sala sigue abierta."))
		return True

	def al_cerrar(self) -> None:
		self._reloj.Stop()
		self._dejar()
