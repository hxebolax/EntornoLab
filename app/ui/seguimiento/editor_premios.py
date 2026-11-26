"""Editor de los premios que el profesional esconde para que el alumno los encuentre.

Es la parte más usada del editor de actividades. Un premio se coloca de tres
formas, las tres sin plano:

- eligiendo el lugar en palabras (planta, espacio y «dentro del armario»,
  «junto a la mesa», «en una esquina»...);
- pidiendo que el programa reparta varios por el entorno, con vista previa;
- recorriendo el entorno con el reproductor y diciendo «aquí».

En la lista, el lugar de cada premio se lee siempre en palabras.
"""

from __future__ import annotations

import copy
import logging
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import wx

from app.core.i18n import _
from app.supervision.sala import ErrorSala
from app.ui.accesibilidad.dialogos import mostrar_error, mostrar_mensaje
from app.ui.seguimiento import actividades_api as api
from app.ui.seguimiento import lugares, sonidos, textos
from app.ui.seguimiento import presentador_actividades as pres
from app.ui.seguimiento.comun import (
	DialogoFormulario,
	Problema,
	Reloj,
	cerrar_dialogo,
	crear_boton,
	crear_casilla,
	crear_casillas,
	crear_desplegable,
	crear_lista,
	crear_texto,
	mostrar_modal,
	pedir_ruta_abrir,
	poner_texto,
)
from app.ui.seguimiento.contexto import anunciar, guardar_recurso
from app.ui.seguimiento.selector_lugar import ErrorLugar, PanelLugar
from app.ui.seguimiento.textos import Letras

log = logging.getLogger(__name__)

INTERVALO_SONDEO_MS = 250


class DialogoPremio(DialogoFormulario):
	"""Un premio: nombre, lugar, sonido, visibilidad, mensaje, pista y audio grabado."""

	def __init__(self, padre: wx.Window | None, contexto: Any, servicio: Any, premio: dict[str, Any] | None = None) -> None:
		super().__init__(padre, _("Premio escondido"))
		self.contexto = contexto
		self.servicio = servicio
		self._original = copy.deepcopy(premio) if premio else {}
		self.premio: dict[str, Any] = {}
		self._audio: str | None = self._original.get("audio") or None
		self._audio_nuevo: tuple[str, bytes] | None = None
		entorno = getattr(contexto, "entorno", None)
		self.nombre = crear_texto(
			self.panel,
			self.letras.poner(_("Nombre del premio:")),
			str(self._original.get("nombre") or ""),
			sizer=self.sizer,
			ayuda=_("Cómo se llama el premio: «Llave dorada», «El osito». Se le dice al alumno al encontrarlo."),
		)
		self.lugar = PanelLugar(self.panel, entorno, getattr(contexto, "catalogo", None), self.letras, con_contenedores=True)
		self.sizer.Add(self.lugar, 0, wx.EXPAND | wx.ALL, 2)
		self._sonidos = [("", _("El de serie")), *sonidos.listar_sonidos()]
		actual = str(self._original.get("sonido") or "")
		if actual and actual not in [clave for clave, _nombre in self._sonidos]:
			self._sonidos.append((actual, actual))
		fila_sonido = wx.BoxSizer(wx.HORIZONTAL)
		columna_sonido = wx.BoxSizer(wx.VERTICAL)
		self.sonido = crear_desplegable(
			self.panel,
			self.letras.poner(_("Sonido del premio:")),
			[nombre for _clave, nombre in self._sonidos],
			sizer=columna_sonido,
			seleccion=[clave for clave, _nombre in self._sonidos].index(actual),
			ayuda=_("El sonido que hace el premio para que el alumno lo localice. El botón Escuchar lo reproduce."),
		)
		fila_sonido.Add(columna_sonido, 1, wx.EXPAND)
		self.boton_escuchar = crear_boton(
			self.panel,
			self.letras.poner(_("Escuchar")),
			self.escuchar,
			_("Reproduce el sonido elegido, para saber cómo suena."),
			fila_sonido,
		)
		self.sizer.Add(fila_sonido, 0, wx.EXPAND)
		self._visibilidades = list(textos.VISIBILIDADES)
		visibilidad = self._original.get("visibilidad") if self._original.get("visibilidad") in self._visibilidades else "cerca"
		self.visibilidad = crear_desplegable(
			self.panel,
			self.letras.poner(_("Visibilidad:")),
			[textos.nombre(textos.VISIBILIDADES, clave) for clave in self._visibilidades],
			sizer=self.sizer,
			seleccion=self._visibilidades.index(visibilidad),
			ayuda=_(
				"«Se oye de lejos»: suena desde cualquier punto del espacio. «Solo de cerca»: hay que acercarse. "
				"«Oculto»: no suena hasta abrir o usar el objeto que lo esconde."
			),
		)
		self.mensaje = crear_texto(
			self.panel,
			self.letras.poner(_("Mensaje al encontrarlo (opcional):")),
			str(self._original.get("mensaje") or ""),
			sizer=self.sizer,
			multilinea=True,
			alto=54,
			ancho=460,
			ayuda=_("Texto que se le dice al alumno cuando encuentra el premio."),
		)
		self.pista = crear_texto(
			self.panel,
			self.letras.poner(_("Pista para encontrarlo (opcional):")),
			str(self._original.get("pista") or ""),
			sizer=self.sizer,
			ayuda=_("Se usa en las pistas encadenadas y cuando el alumno pide una pista. Vacío: la redacta el programa."),
		)
		self.audio = crear_texto(
			self.panel,
			self.letras.poner(_("Audio grabado (opcional):")),
			sizer=self.sizer,
			lectura=True,
			ayuda=_(
				"Un mensaje de voz grabado por usted o por la familia, que suena al encontrar el premio. Se guarda dentro del entorno."
			),
		)
		fila_audio = wx.BoxSizer(wx.HORIZONTAL)
		crear_boton(
			self.panel,
			self.letras.poner(_("Buscar un fichero de audio...")),
			self.elegir_audio,
			_("Elige un fichero WAV, OGG o FLAC grabado con cualquier programa."),
			fila_audio,
		)
		crear_boton(
			self.panel, self.letras.poner(_("Quitar el audio")), self.quitar_audio, _("El premio deja de tener audio grabado."), fila_audio
		)
		self.sizer.Add(fila_audio, 0, wx.ALL, 2)
		self.lugar.poner(self._original if self._original else None)
		self._pintar_audio()
		self.terminar(self.nombre, tamano_minimo=(540, 640))

	def _pintar_audio(self) -> None:
		poner_texto(self.audio, self._audio or _("Sin audio grabado"))

	def escuchar(self) -> None:
		"""Reproduce el sonido elegido, si el equipo puede."""
		clave = self._sonidos[max(0, self.sonido.GetSelection())][0] or "premio/cerca"
		if self.servicio.escucha is None:
			self.servicio.escucha = sonidos.Escucha(
				getattr(self.contexto, "configuracion", None), lambda: getattr(self.contexto, "recursos", None)
			)
		if not self.servicio.escucha.escuchar(clave):
			anunciar(self.contexto, sonidos.mensaje_sin_sonido())

	def elegir_audio(self) -> None:
		"""Elige un fichero de audio; se añadirá al paquete al aceptar."""
		ruta = pedir_ruta_abrir(self, _("Audio grabado del premio"), _("Audio (*.wav;*.ogg;*.flac)|*.wav;*.ogg;*.flac"))
		if ruta is None:
			return
		self.poner_audio(ruta)

	def poner_audio(self, ruta: Path) -> bool:
		"""Lee el fichero y lo deja listo para añadirlo al paquete. False si no vale (se explica)."""
		try:
			datos = pres.leer_audio(ruta)
		except ValueError as error:
			mostrar_error(self, str(error))
			return False
		existentes = list(pres.recursos_del_paquete(self.contexto))
		nombre = pres.nombre_recurso_audio(ruta, existentes)
		self._audio_nuevo = (nombre, datos)
		self._audio = nombre
		self._pintar_audio()
		return True

	def quitar_audio(self) -> None:
		"""Deja el premio sin audio grabado."""
		self._audio = None
		self._audio_nuevo = None
		self._pintar_audio()

	def validar(self) -> Problema | None:
		nombre = self.nombre.GetValue().strip()
		if not nombre:
			return _("Escriba el nombre del premio."), self.nombre
		try:
			lugar = self.lugar.leer()
		except ErrorLugar as error:
			return str(error), error.control
		premio = dict(self._original)
		premio.update(
			{
				"nombre": nombre,
				"planta": lugar["planta"],
				"x": lugar["x"],
				"y": lugar["y"],
				"dentro_de": lugar.get("dentro_de"),
				"sonido": self._sonidos[max(0, self.sonido.GetSelection())][0],
				"visibilidad": self._visibilidades[max(0, self.visibilidad.GetSelection())],
				"mensaje": self.mensaje.GetValue().strip(),
				"pista": self.pista.GetValue().strip(),
				"audio": self._audio,
			}
		)
		self.premio = premio
		return None

	def aplicar(self) -> Problema | None:
		if self._audio_nuevo is not None:
			nombre, datos = self._audio_nuevo
			if not guardar_recurso(self.contexto, nombre, datos):
				self.premio["audio"] = None
				return _(
					"En esta versión el Estudio no puede guardar audios dentro del entorno. Quite el audio para continuar."
				), self.audio
		return None


class DialogoRepartir(DialogoFormulario):
	"""Reparte premios automáticamente, con vista previa antes de aceptar."""

	def __init__(self, padre: wx.Window | None, contexto: Any, hay_premios: bool = False) -> None:
		super().__init__(padre, _("Repartir premios automáticamente"))
		self.contexto = contexto
		self.premios: list[dict[str, Any]] = []
		self.sustituir = False
		self._semilla = random.randrange(1, 2**31 - 1)
		entorno = getattr(contexto, "entorno", None)
		self._plantas = lugares.plantas(entorno)
		espacios = sum(len(lugares.espacios(planta)) for planta in self._plantas)
		etiqueta_cuantos = wx.StaticText(self.panel, label=self.letras.poner(_("Cuántos premios:")))
		self.cuantos = wx.SpinCtrl(self.panel, min=1, max=50, initial=max(1, min(espacios, 50)), name=_("Cuántos premios"))
		self.cuantos.SetHelpText(
			_("Número de premios que se reparten, de 1 a 50. Por defecto, uno por espacio, para que haya que recorrerlos todos.")
		)
		self.sizer.Add(etiqueta_cuantos, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		self.sizer.Add(self.cuantos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.plantas = crear_casillas(
			self.panel,
			self.letras.poner(_("Plantas en las que se esconden:")),
			[lugares.nombre_de(planta) for planta in self._plantas],
			sizer=self.sizer,
			ayuda=_("Solo se esconden premios en las plantas marcadas."),
		)
		for indice in range(self.plantas.GetCount()):
			self.plantas.Check(indice, True)
		self._visibilidades = list(textos.VISIBILIDADES)
		self.visibilidad = crear_desplegable(
			self.panel,
			self.letras.poner(_("Visibilidad de los premios:")),
			[textos.nombre(textos.VISIBILIDADES, clave) for clave in self._visibilidades],
			sizer=self.sizer,
			seleccion=self._visibilidades.index("cerca"),
			ayuda=_("Si se oyen de lejos, solo de cerca o están ocultos."),
		)
		self.dentro = crear_casilla(
			self.panel,
			self.letras.poner(_("Esconder algunos dentro de objetos (armarios, cajones)")),
			True,
			sizer=self.sizer,
			ayuda=_("Si en un espacio hay un objeto que se puede abrir, el premio puede ir dentro."),
		)
		self.casilla_sustituir = crear_casilla(
			self.panel,
			self.letras.poner(_("Quitar antes los premios que ya hay")),
			False,
			sizer=self.sizer,
			ayuda=_("Marcada: la lista de premios se sustituye por estos. Sin marcar: estos se añaden a los que ya hay."),
		)
		self.casilla_sustituir.Enable(hay_premios)
		crear_boton(
			self.panel,
			self.letras.poner(_("Generar la vista previa")),
			self.generar,
			_("Reparte los premios con las opciones de arriba y los enseña en la lista. Cada pulsación da un reparto distinto."),
			self.sizer,
		)
		self.lista = crear_lista(
			self.panel,
			self.letras.poner(_("Vista previa del reparto:")),
			[(_("Premio"), 130), (_("Dónde está"), 300), (_("Visibilidad"), 150)],
			getattr(contexto, "configuracion", None),
			sizer=self.sizer,
			ayuda=_(
				"Dónde quedaría cada premio. Si no le convence, pulse otra vez «Generar la vista previa». Aceptar los pone en la actividad."
			),
		)
		self.terminar(self.cuantos, tamano_minimo=(640, 620))

	def generar(self) -> None:
		"""Calcula un reparto nuevo y lo enseña."""
		self._semilla += 1
		entorno = getattr(self.contexto, "entorno", None)
		plantas = [self._plantas[indice].id for indice in self.plantas.GetCheckedItems()]
		try:
			self.premios = api.repartir_premios(
				entorno,
				int(self.cuantos.GetValue()),
				getattr(self.contexto, "catalogo", None),
				semilla=self._semilla,
				plantas=plantas or None,
				visibilidad=self._visibilidades[max(0, self.visibilidad.GetSelection())],
				dentro_de_objetos=self.dentro.GetValue(),
			)
		except Exception as error:  # noqa: BLE001 - el reparto depende del entorno entero; cualquier fallo se explica y no se pierde nada
			log.exception("Ha fallado el reparto automático de premios")
			mostrar_error(self, _("No se han podido repartir los premios: {error}").format(error=error))
			self.premios = []
		filas = [pres.fila_premio(premio, entorno)[:3] for premio in self.premios]
		self.lista.reemplazar_filas(filas)
		anunciar(
			self.contexto,
			textos.contar(
				len(self.premios), "{n} premio repartido. Repase la vista previa.", "{n} premios repartidos. Repase la vista previa."
			),
		)

	def validar(self) -> Problema | None:
		if not self.plantas.GetCheckedItems() and self._plantas:
			return _("Marque al menos una planta."), self.plantas
		if not self.premios:
			self.generar()
		if not self.premios:
			return _("No se ha podido colocar ningún premio con esas opciones."), self.cuantos
		self.sustituir = self.casilla_sustituir.GetValue()
		return None


class DialogoColocarRecorriendo(DialogoFormulario):
	"""Espera a que el profesional, recorriendo el entorno con el reproductor, diga «aquí».

	El reproductor en modo recorrido envía una petición («marcar este punto»
	o «colocar aquí») con su posición; se toma como lugar del premio y se le
	contesta para que lo oiga confirmado.

	Con ``sesion`` (lo normal) usa el mismo mecanismo que «Recorrer el
	entorno» del Estudio (``app.ui.recorrido.SesionRecorrido``): la sala única
	del servicio, el reproductor vigilado y, si ya había un recorrido abierto,
	ese mismo. Sin ``sesion`` escucha la sala del servicio directamente.
	"""

	def __init__(self, padre: wx.Window | None, contexto: Any, servicio: Any, sesion: Any = None) -> None:
		super().__init__(padre, _("Colocar el premio recorriendo"))
		self.contexto = contexto
		self.servicio = servicio
		self.sesion = sesion
		self.posicion: dict[str, Any] | None = None
		#: Por qué se cerró sin posición (el reproductor se cerró, por ejemplo); vacío si se canceló o se colocó.
		self.motivo = ""
		self._listo = False
		self.estado = crear_texto(
			self.panel,
			self.letras.poner(_("Estado:")),
			_(
				"Se está abriendo el reproductor en modo recorrido. Camine hasta el sitio donde quiere esconder el premio y, "
				"en el menú de edición del reproductor, elija «Marcar este punto». Esta ventana se cerrará sola y podrá "
				"completar el nombre y el sonido del premio. Escape cancela."
			),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=120,
			ancho=480,
			ayuda=_("Explica qué hay que hacer y dice si el reproductor ya se ha conectado."),
		)
		if sesion is not None:
			self._dejar: Callable[[], None] = lambda: None
			sesion.al_pedir = self._capturar
			if getattr(sesion, "listo", False):
				self._poner_listo()
		else:
			self._dejar = servicio.sala.escuchar(self._suceso)
		self._reloj = Reloj(self, self.sondear)
		self.terminar(self.estado, botones=wx.CANCEL)
		self._reloj.Start(INTERVALO_SONDEO_MS)

	def Destroy(self) -> bool:  # noqa: N802 - API de wx
		"""Para el temporizador y deja de escuchar la sala antes de destruirse."""
		self._reloj.Stop()
		self._dejar()
		if self.sesion is not None and getattr(self.sesion, "al_pedir", None) == self._capturar:
			self.sesion.al_pedir = None
		return super().Destroy()

	def sondear(self) -> None:
		"""Lee los sucesos de la sala (lo llama el temporizador; las pruebas, a mano)."""
		if self.sesion is None:
			self.servicio.sala.sondear()
			return
		for frase in self.sesion.atender():
			anunciar(self.contexto, frase)
		if not self:
			return
		if getattr(self.sesion, "listo", False) and not self._listo:
			self._poner_listo()
		if not self.sesion.activa and self.posicion is None:
			# El reproductor se ha cerrado (o ha muerto) sin decir «aquí»: no tiene sentido seguir esperando.
			self.motivo = _("El reproductor se ha cerrado antes de marcar el sitio del premio.")
			self._reloj.Stop()
			cerrar_dialogo(self, wx.ID_CANCEL)

	def _poner_listo(self) -> None:
		self._listo = True
		poner_texto(self.estado, _("El reproductor está conectado. Camine hasta el sitio y elija «Marcar este punto»."))
		anunciar(self.contexto, _("Reproductor conectado. Camine hasta el sitio del premio."))

	def _capturar(self, _alumno: str, datos: dict[str, Any]) -> Any:
		"""Toma la posición de una petición «marcar este punto» o «colocar aquí» como lugar del premio.

		Devuelve la ``Respuesta`` que oirá el profesional, o None para que la
		resuelva el recorrido normal (una medida, por ejemplo).
		"""
		from app.ui.recorrido import COLOCAR, INICIO, MARCAR, PREMIO, Respuesta, normalizar_accion

		if self.posicion is not None or not self:
			return None
		if normalizar_accion(str(datos.get("accion", "")), dict(datos.get("datos") or {})) not in (COLOCAR, PREMIO, MARCAR, INICIO):
			return None
		planta, x, y = datos.get("planta"), datos.get("x"), datos.get("y")
		if not planta or isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
			return Respuesta(False, _("No se sabe en qué punto está."))
		self.posicion = {"planta": str(planta), "x": round(float(x), 2), "y": round(float(y), 2), "dentro_de": None}
		lugar = lugares.describir_punto(getattr(self.contexto, "entorno", None), str(planta), x, y)
		wx.CallAfter(self._aceptar_si_sigue)
		return Respuesta(True, _("Premio colocado aquí: {lugar}.").format(lugar=lugar))

	def _aceptar_si_sigue(self) -> None:
		if self and not self.aceptado:
			self.aceptar()

	def _suceso(self, suceso: dict[str, Any]) -> None:
		"""Un suceso de la sala (sin sesión de recorrido) o una petición entregada a mano."""
		if not self:
			# El diálogo se destruyó sin pasar por Destroy de Python: deja de escuchar.
			self._dejar()
			return
		tipo, datos = suceso.get("tipo"), suceso.get("datos") or {}
		if tipo in ("conectado", "reconectado") and datos.get("recorrido"):
			self._poner_listo()
			return
		if tipo != "peticion" or self.posicion is not None:
			return
		alumno = str(suceso.get("alumno") or "")
		respuesta = self._capturar(alumno, {"accion": "marcar_punto", **datos})
		if respuesta is None:
			return
		self.servicio.sala.responder(alumno, int(datos.get("id", 0)), respuesta.aceptada, respuesta.texto)
		if self.posicion is not None:
			self.aceptar()


class PanelPremios(wx.Panel):
	"""Lista de premios con sus botones: añadir, editar, quitar, ordenar, repartir y colocar recorriendo."""

	def __init__(
		self,
		padre: wx.Window,
		contexto: Any,
		servicio: Any,
		letras: Letras,
		premios: list[dict[str, Any]] | None = None,
		etiqueta: str = "",
		al_cambiar: Callable[[], None] | None = None,
	) -> None:
		super().__init__(padre, name=_("Premios"))
		self.contexto = contexto
		self.servicio = servicio
		self._al_cambiar = al_cambiar
		self.premios: list[dict[str, Any]] = []
		self._nombres_sonido = dict(sonidos.listar_sonidos())
		columna = wx.BoxSizer(wx.VERTICAL)
		self.lista = crear_lista(
			self,
			letras.poner(etiqueta or _("Premios escondidos:")),
			pres.columnas_premios(),
			getattr(contexto, "configuracion", None),
			sizer=columna,
			alto=190,
			ayuda=_(
				"Cada fila es un premio: su nombre, dónde está dicho en palabras, si se oye de lejos, de cerca o está oculto, "
				"su sonido y su mensaje. Intro lo edita y Suprimir lo quita. Izquierda y derecha leen las columnas."
			),
		)
		fila = wx.WrapSizer(wx.HORIZONTAL)
		crear_boton(
			self, letras.poner(_("Añadir premio...")), self.anadir, _("Esconde un premio nuevo eligiendo el lugar con listas."), fila
		)
		crear_boton(self, letras.poner(_("Editar premio...")), self.editar, _("Cambia el premio elegido."), fila)
		crear_boton(self, letras.poner(_("Quitar premio")), self.quitar, _("Quita el premio elegido."), fila)
		crear_boton(
			self, letras.poner(_("Subir premio")), lambda: self.mover(-1), _("Mueve el premio elegido un puesto hacia arriba."), fila
		)
		crear_boton(self, letras.poner(_("Bajar premio")), lambda: self.mover(1), _("Mueve el premio elegido un puesto hacia abajo."), fila)
		crear_boton(
			self,
			letras.poner(_("Repartir automáticamente...")),
			self.repartir,
			_("El programa reparte varios premios por el entorno, de modo que haya que recorrerlo entero, y enseña una vista previa."),
			fila,
		)
		crear_boton(
			self,
			letras.poner(_("Colocar recorriendo...")),
			self.colocar_recorriendo,
			_(
				"Abre el reproductor en modo recorrido: camine hasta el sitio y elija «Marcar este punto» para esconder ahí el premio. "
				"Necesita que el entorno esté guardado."
			),
			fila,
		)
		columna.Add(fila, 0, wx.ALL, 2)
		self.SetSizer(columna)
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.editar())
		self.lista.Bind(wx.EVT_KEY_DOWN, self._tecla)
		self.poner(premios)

	def _tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_DELETE and evento.GetModifiers() == wx.MOD_NONE:  # atajo: Supr
			self.quitar()
			return
		evento.Skip()

	# ── Valor ────────────────────────────────────────────────────────────────

	def poner(self, premios: list[dict[str, Any]] | None) -> None:
		"""Carga una lista de premios (se copian)."""
		self.premios = [copy.deepcopy(premio) for premio in (premios or []) if isinstance(premio, dict)]
		self.recargar()

	def leer(self) -> list[dict[str, Any]]:
		"""Los premios, en orden."""
		return [copy.deepcopy(premio) for premio in self.premios]

	def recargar(self, fila: int | None = None) -> None:
		"""Vuelve a pintar la lista y avisa de que ha cambiado."""
		entorno = getattr(self.contexto, "entorno", None)
		self.lista.reemplazar_filas([pres.fila_premio(premio, entorno, self._nombres_sonido) for premio in self.premios])
		if fila is not None:
			self.lista.enfocar_fila(fila, anunciar=False)
		if self._al_cambiar is not None:
			self._al_cambiar()

	# ── Acciones ─────────────────────────────────────────────────────────────

	def _pedir(self, premio: dict[str, Any] | None) -> dict[str, Any] | None:
		dialogo = DialogoPremio(self.GetTopLevelParent(), self.contexto, self.servicio, premio)
		try:
			mostrar_modal(dialogo)
			return dialogo.premio if dialogo.aceptado else None
		finally:
			dialogo.Destroy()

	def _anadir(self, premio: dict[str, Any]) -> None:
		premio["id"] = pres.id_premio_unico(self.premios, str(premio.get("id") or "premio"))
		self.premios.append(premio)
		self.recargar(len(self.premios) - 1)
		fila = pres.fila_premio(premio, getattr(self.contexto, "entorno", None))
		anunciar(self.contexto, _("Premio {nombre} escondido: {lugar}.").format(nombre=fila[0], lugar=fila[1]))

	def anadir(self) -> None:
		"""Esconde un premio nuevo."""
		if getattr(self.contexto, "entorno", None) is None:
			mostrar_mensaje(self.GetTopLevelParent(), _("Abra antes un entorno: los premios se esconden en sus espacios."), _("Premios"))
			return
		premio = self._pedir(None)
		if premio is not None:
			self._anadir(premio)
		self.lista.SetFocus()

	def editar(self) -> None:
		"""Edita el premio elegido."""
		fila = self.lista.fila_actual()
		if not 0 <= fila < len(self.premios):
			return
		premio = self._pedir(self.premios[fila])
		if premio is not None:
			self.premios[fila] = premio
			self.recargar(fila)
		self.lista.SetFocus()

	def quitar(self) -> None:
		"""Quita el premio elegido."""
		fila = self.lista.fila_actual()
		if 0 <= fila < len(self.premios):
			nombre = self.premios[fila].get("nombre", "")
			del self.premios[fila]
			self.recargar(min(fila, len(self.premios) - 1) if self.premios else None)
			anunciar(self.contexto, _("Premio {nombre} quitado.").format(nombre=nombre))

	def mover(self, delta: int) -> None:
		"""Sube o baja el premio elegido."""
		self.recargar(pres.mover(self.premios, self.lista.fila_actual(), delta))

	def repartir(self) -> None:
		"""Reparte premios automáticamente y los pone en la lista."""
		if getattr(self.contexto, "entorno", None) is None:
			mostrar_mensaje(self.GetTopLevelParent(), _("Abra antes un entorno: los premios se reparten por sus espacios."), _("Premios"))
			return
		dialogo = DialogoRepartir(self.GetTopLevelParent(), self.contexto, hay_premios=bool(self.premios))
		try:
			mostrar_modal(dialogo)
			if not dialogo.aceptado:
				return
			nuevos, sustituir = dialogo.premios, dialogo.sustituir
		finally:
			dialogo.Destroy()
		if sustituir:
			self.premios = []
		primero = len(self.premios)
		self.premios.extend(pres.renumerar_premios(nuevos, self.premios))
		self.recargar(primero if self.premios else None)
		anunciar(self.contexto, textos.contar(len(nuevos), "{n} premio añadido a la lista.", "{n} premios añadidos a la lista."))
		self.lista.SetFocus()

	def motivo_sin_recorrido(self) -> str:
		"""Por qué no se puede colocar recorriendo ahora mismo; cadena vacía si se puede."""
		if getattr(self.contexto, "entorno", None) is None:
			return _("No hay ningún entorno abierto.")
		if getattr(self.contexto, "ruta_paquete", None) is None:
			return _(
				"El entorno todavía no se ha guardado nunca. Guárdelo (Control+S) y vuelva a intentarlo: el reproductor lo abre desde su fichero."
			)
		if not callable(getattr(self.contexto, "lanzar_reproductor", None)):
			return _("Esta versión del Estudio todavía no puede abrir el reproductor.")
		return ""

	def colocar_recorriendo(self) -> None:
		"""Lanza el modo recorrido y esconde un premio donde el profesional diga «aquí»."""
		padre = self.GetTopLevelParent()
		motivo = self.motivo_sin_recorrido()
		if motivo:
			mostrar_mensaje(padre, _("Ahora no se puede colocar recorriendo. {motivo}").format(motivo=motivo), _("Colocar recorriendo"))
			return
		from app.core.procesos import ErrorProceso
		from app.ui.recorrido import ErrorRecorrido, SesionRecorrido

		sala = self.servicio.sala
		# Un solo recorrido por Estudio: si ya hay uno abierto («Recorrer el entorno»), se usa ese mismo reproductor.
		existente = getattr(sala, "recorrido", None)
		propia: SesionRecorrido | None = None
		posicion: dict[str, Any] | None = None
		motivo = ""
		try:
			if existente is not None and getattr(existente, "activa", False):
				sesion = existente
				anunciar(self.contexto, _("Ya hay un reproductor recorriendo el entorno: se usa ese."))
			else:
				sesion = propia = SesionRecorrido(self.contexto, sala, lanzar=self.servicio.lanzar)
				sesion.iniciar()
			dialogo = DialogoColocarRecorriendo(padre, self.contexto, self.servicio, sesion=sesion)
			try:
				mostrar_modal(dialogo)
				posicion = dialogo.posicion if dialogo.aceptado else None
				motivo = dialogo.motivo
			finally:
				dialogo.Destroy()
		except (ErrorRecorrido, ErrorSala, ErrorProceso) as error:
			log.warning("No se ha podido iniciar el modo recorrido para colocar un premio: %s", error)
			mostrar_error(padre, str(error))
			return
		except Exception as error:  # noqa: BLE001 - lo que pueda fallar al lanzar: se explica y no se pierde la actividad
			log.exception("No se ha podido iniciar el modo recorrido para colocar un premio")
			mostrar_error(padre, _("No se ha podido abrir el reproductor: {error}").format(error=error))
			return
		finally:
			if propia is not None:
				try:
					propia.detener()
				except Exception:  # noqa: BLE001 - es limpieza: si falla, al cerrar el Estudio se termina todo igualmente
					log.warning("No se ha podido cerrar del todo el modo recorrido", exc_info=True)
		if posicion is None:
			anunciar(self.contexto, motivo or _("No se ha colocado ningún premio."))
			return
		premio = self._pedir({"nombre": _("Premio {n}").format(n=len(self.premios) + 1), "visibilidad": "cerca", **posicion})
		if premio is not None:
			self._anadir(premio)
		self.lista.SetFocus()
