"""Diálogo de Preferencias (Control+coma), generado de ``app/ui/esquema_preferencias.py``.

Recorrido completo de cada preferencia: valor de fábrica en
``app/core/configuracion.py`` → campo en este diálogo → validación con el
foco en el campo que no vale → guardado con ``establecer_varias`` (un solo
guardado, y los suscriptores de la configuración aplican el cambio a las
ventanas abiertas) → lectura en el momento de usarla.

- **Aceptar** guarda y cierra; **Aplicar** guarda sin cerrar; **Cancelar**
  no cambia nada de lo que no se haya aplicado.
- **Valores de fábrica** pone en los campos los valores de serie de la
  pestaña actual o de todas (se pregunta con botones que dicen la acción);
  no se guardan hasta Aceptar o Aplicar.
- El cambio de idioma se aplica al aceptar; si wx sigue en el idioma
  anterior se avisa de que los menús y los botones estándar cambian al reiniciar.
"""

from __future__ import annotations

import copy
import logging
import threading
from collections.abc import Callable
from typing import Any

import wx

from app.core import i18n
from app.core.configuracion import ErrorConfiguracion, ErrorValidacion
from app.core.i18n import _
from app.ui import esquema_preferencias as esquema
from app.ui.accesibilidad.dialogos import DialogoMensaje, crear_botonera, enfocar, mostrar_error, mostrar_mensaje, preparar_dialogo
from app.ui.esquemas import ErrorCampo, con_letra, letra_de, nombre_campo
from app.ui.formulario import Formulario, letras_de_botonera, mostrar_dialogo

log = logging.getLogger(__name__)

ALCANCE_PESTANA = "pestana"
ALCANCE_TODO = "todo"


# ── Muestra de un paquete de sonidos ─────────────────────────────────────────

_motor_muestras: Any = None
_candado_muestras = threading.Lock()


def escuchar_muestra(identificador: str, configuracion: Any = None) -> bool:
	"""Hace sonar una muestra de un paquete de sonidos, sin elegirlo. True si ha podido sonar.

	El Estudio no tiene motor de sonido propio: se crea uno la primera vez que
	se pide una muestra (con el motor y la salida de las preferencias) y se
	conserva hasta ``cerrar_motor_muestras``. Puede tardar un momento, así que
	el diálogo la llama desde un hilo. Lanza la excepción que dé la biblioteca
	de sonido; quien llama la explica.
	"""
	global _motor_muestras
	from app.audio import fabrica, paquetes

	with _candado_muestras:
		if _motor_muestras is None:
			seccion = configuracion.obtener("sonido") if configuracion is not None else None
			_motor_muestras = fabrica.crear_motor(seccion if isinstance(seccion, dict) else None)
		motor = _motor_muestras
		if getattr(motor, "nombre", "") == "nulo":
			return False
		return paquetes.escuchar(identificador, motor) != 0


def cerrar_motor_muestras() -> None:
	"""Cierra el motor de las muestras (al cerrar Preferencias), para soltar la salida de sonido."""
	global _motor_muestras
	with _candado_muestras:
		motor, _motor_muestras = _motor_muestras, None
	if motor is not None:
		try:
			motor.cerrar()
		except Exception:  # noqa: BLE001 - un fallo al cerrar el sonido no debe impedir cerrar el diálogo
			log.warning("No se pudo cerrar el motor de las muestras de sonido.", exc_info=True)


class DialogoPreferencias(wx.Dialog):
	"""Preferencias por pestañas con Aceptar, Cancelar, Aplicar y valores de fábrica."""

	def __init__(
		self,
		padre: wx.Window | None,
		configuracion: Any,
		escuchar: Callable[[str], Any] | None = None,
		anunciar: Callable[[str], Any] | None = None,
		al_aplicar: Callable[[list[str]], Any] | None = None,
	) -> None:
		"""Crea el diálogo.

		:param al_aplicar: se llama con las claves guardadas tras cada Aceptar o
			Aplicar con cambios (el Estudio avisa con ella a los reproductores
			conectados para que relean la configuración compartida).

		:param escuchar: función que hace sonar la muestra de un paquete de
			sonidos (recibe su identificador; devuelve False o 0, o lanza, si
			no puede). Por defecto, ``escuchar_muestra`` en un hilo. Las
			pruebas pasan un doble para no abrir ningún dispositivo.
		:param anunciar: cómo decir un mensaje breve (``contexto.anunciar``);
			por defecto, la voz.
		"""
		super().__init__(padre, title=_("Preferencias"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=_("Preferencias"))
		self._config = configuracion
		self._escuchar = escuchar
		self._anunciar = anunciar
		self._al_aplicar = al_aplicar
		self._escuchando = False
		self.boton_muestra: wx.Button | None = None
		self.campos = esquema.campos_preferencias(configuracion)
		#: True si se guardó algún cambio (con Aceptar o con Aplicar).
		self.cambios_aplicados = False
		self.ultimo_error = ""
		etiqueta_fabrica = _("&Valores de fábrica...")
		usadas = letras_de_botonera(wx.ID_OK, wx.ID_CANCEL, wx.ID_APPLY) | {"v"}
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.formulario = Formulario(
			self, self.campos, esquema.valores_de_formulario(configuracion), letras_usadas=usadas, nombre=_("Preferencias")
		)
		sizer.Add(self.formulario, 1, wx.EXPAND | wx.ALL, self.FromDIP(6))
		fila = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_fabrica = wx.Button(self, label=etiqueta_fabrica)
		self.boton_fabrica.SetHelpText(
			_("Pone en los campos los valores de serie, de esta pestaña o de todas. No se guardan hasta aceptar o aplicar.")
		)
		fila.Add(self.boton_fabrica, 0, wx.ALIGN_CENTER_VERTICAL)
		fila.AddStretchSpacer()
		fila.Add(crear_botonera(self, wx.OK | wx.CANCEL | wx.APPLY), 0)
		sizer.Add(fila, 0, wx.EXPAND | wx.ALL, self.FromDIP(10))
		self.SetSizer(sizer)
		self.SetSize(self.FromDIP(wx.Size(640, 620)))
		self.Bind(wx.EVT_BUTTON, self._al_aceptar, id=wx.ID_OK)
		self.Bind(wx.EVT_BUTTON, lambda _e: self.aplicar(), id=wx.ID_APPLY)
		self.boton_fabrica.Bind(wx.EVT_BUTTON, lambda _e: self._al_fabrica())
		self._preparar_paquete()
		self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)
		# Para reconocer la destrucción propia: en wxPython 4.3 GetEventObject() ya no es self.
		self._id_propio = self.GetId()
		preparar_dialogo(self, foco_inicial=self.cuaderno())
		self.CentreOnParent()

	# ── Paquete de sonidos ───────────────────────────────────────────────────

	def _preparar_paquete(self) -> None:
		"""Añade a la pestaña Sonido el botón «Escuchar una muestra» y enlaza la descripción con la elección.

		El botón no sale de la tabla (no es un dato): se crea aquí, en la misma
		página que la lista de paquetes, con una letra de acceso que no use
		ningún otro control de esa página ni los botones del diálogo, y se
		coloca en el orden de tabulación justo detrás de la descripción.
		"""
		lista = self.formulario.controles.get("sonido.paquete")
		descripcion = self.formulario.controles.get(esquema.NOTA_PAQUETE)
		if lista is None or descripcion is None:
			return
		pagina = lista.GetParent()
		usadas = letras_de_botonera(wx.ID_OK, wx.ID_CANCEL, wx.ID_APPLY) | {"v"}
		for hijo in pagina.GetChildren():
			if isinstance(hijo, (wx.StaticText, wx.CheckBox, wx.Button)):
				letra = letra_de(hijo.GetLabel())
				if letra:
					usadas.add(letra)
		self.boton_muestra = wx.Button(pagina, label=con_letra(_("Escuchar una muestra del paquete"), usadas))
		self.boton_muestra.SetHelpText(_("Hace sonar unos cuantos sonidos del paquete elegido, sin cambiar todavía de paquete."))
		self.boton_muestra.MoveAfterInTabOrder(descripcion)
		sizer = pagina.GetSizer()
		posicion = next((i for i, elemento in enumerate(sizer.GetChildren()) if elemento.GetWindow() is descripcion), -1)
		sizer.Insert(posicion + 1 if posicion >= 0 else sizer.GetItemCount(), self.boton_muestra, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		pagina.Layout()
		self.boton_muestra.Bind(wx.EVT_BUTTON, lambda _e: self.escuchar_muestra())
		# El formulario ya atiende este evento: se le deja seguir con Skip.
		lista.Bind(wx.EVT_CHOICE, self._al_elegir_paquete)

	def paquete_elegido(self) -> str:
		"""Identificador del paquete de sonidos elegido ahora en la lista."""
		return str(self.formulario.crudos().get("sonido.paquete") or "")

	def _al_elegir_paquete(self, evento: wx.CommandEvent) -> None:
		evento.Skip()
		self._actualizar_descripcion()

	def _actualizar_descripcion(self) -> None:
		"""La descripción sigue a la elección (el lector la lee al llegar al campo; no se dice sola)."""
		if esquema.NOTA_PAQUETE in self.formulario.controles:
			self.formulario.fijar({esquema.NOTA_PAQUETE: esquema.descripcion_paquete(self.paquete_elegido())})

	def _decir(self, texto: str) -> None:
		if self._anunciar is not None:
			self._anunciar(texto)
			return
		from app.core import voz

		voz.hablar(texto, False)

	def escuchar_muestra(self) -> None:
		"""Hace sonar la muestra del paquete elegido sin bloquear la interfaz; si no se puede, lo dice y sigue."""
		identificador = self.paquete_elegido()
		if self._escuchar is not None:
			# Función inyectada (pruebas, o quien ya tenga un motor): se llama aquí mismo.
			try:
				sonado = self._escuchar(identificador)
			except Exception:  # noqa: BLE001 - una biblioteca de sonido puede fallar de cualquier forma: se explica y se sigue
				log.warning("No se pudo escuchar la muestra del paquete %s.", identificador, exc_info=True)
				sonado = False
			self._muestra_terminada(sonado is not False and sonado != 0)
			return
		if self._escuchando:
			return
		self._escuchando = True
		config = self._config

		def trabajo() -> None:
			try:
				sonado = escuchar_muestra(identificador, config)
			except Exception:  # noqa: BLE001 - sin motor de sonido o con la salida ocupada: se explica y se sigue
				log.warning("No se pudo escuchar la muestra del paquete %s.", identificador, exc_info=True)
				sonado = False
			wx.CallAfter(self._muestra_terminada, sonado)

		threading.Thread(target=trabajo, name="muestra-paquete", daemon=True).start()

	def _muestra_terminada(self, sonado: bool) -> None:
		if not self:
			return
		self._escuchando = False
		if not sonado:
			self._decir(_("No se puede escuchar la muestra: no hay salida de sonido disponible."))

	def _al_destruir(self, evento: wx.WindowDestroyEvent) -> None:
		"""Cierra el motor de las muestras al cerrar el diálogo (no al destruirse un control hijo)."""
		if evento.GetId() == self._id_propio:
			cerrar_motor_muestras()
		evento.Skip()

	# ── Pestañas ─────────────────────────────────────────────────────────────

	def cuaderno(self) -> wx.Notebook | None:
		"""El cuaderno de pestañas del formulario."""
		return next((hijo for hijo in self.formulario.GetChildren() if isinstance(hijo, wx.Notebook)), None)

	def grupo_actual(self) -> str:
		"""Grupo (pestaña) que se está viendo, tal como figura en la tabla."""
		cuaderno = self.cuaderno()
		grupos: list[str] = []
		for campo in self.campos:
			if campo.grupo not in grupos:
				grupos.append(campo.grupo)
		indice = cuaderno.GetSelection() if cuaderno is not None else 0
		return grupos[indice] if 0 <= indice < len(grupos) else grupos[0]

	def ir_a_grupo(self, grupo: str) -> None:
		"""Abre la pestaña de un grupo."""
		cuaderno = self.cuaderno()
		grupos: list[str] = []
		for campo in self.campos:
			if campo.grupo not in grupos:
				grupos.append(campo.grupo)
		if cuaderno is not None and grupo in grupos:
			cuaderno.SetSelection(grupos.index(grupo))

	# ── Valores ──────────────────────────────────────────────────────────────

	def fijar(self, valores: dict[str, Any]) -> None:
		"""Pone valores en los campos (clave de configuración → valor como lo enseña el formulario)."""
		self.formulario.fijar(valores)
		if "sonido.paquete" in valores and esquema.NOTA_PAQUETE not in valores:
			self._actualizar_descripcion()

	def valores_de_fabrica(self, alcance: str) -> None:
		"""Pone en los campos los valores de serie de la pestaña actual o de todas. No guarda."""
		de_fabrica = esquema.valores_de_formulario(self._config, de_fabrica=True)
		if alcance == ALCANCE_PESTANA:
			grupo = self.grupo_actual()
			claves = {campo.clave for campo in self.campos if campo.grupo == grupo}
			de_fabrica = {clave: valor for clave, valor in de_fabrica.items() if clave in claves}
		self.formulario.fijar(de_fabrica)

	def crear_pregunta_fabrica(self) -> DialogoMensaje:
		"""Pregunta el alcance; ``ids_opciones`` son, por orden, «solo esta pestaña» y «todas»."""
		return DialogoMensaje(
			self,
			_("¿Qué preferencias quiere devolver a sus valores de fábrica? No se guardan hasta que acepte o aplique."),
			_("Valores de fábrica"),
			opciones=[_("&Solo esta pestaña"), _("&Todas las pestañas")],
			icono=wx.ICON_QUESTION,
		)

	def _al_fabrica(self) -> None:
		pregunta = self.crear_pregunta_fabrica()
		ids = list(pregunta.ids_opciones)
		respuesta = mostrar_dialogo(pregunta)
		if respuesta not in ids:
			return
		self.valores_de_fabrica(ALCANCE_PESTANA if ids.index(respuesta) == 0 else ALCANCE_TODO)
		mostrar = _("Valores de fábrica puestos. Pulse Aceptar o Aplicar para guardarlos.")
		from app.core import voz

		voz.hablar(mostrar, False)

	def cambios(self) -> dict[str, Any]:
		"""Lo que hay que guardar: clave de configuración → valor nuevo. Lanza ``ErrorCampo`` si algo no vale."""
		valores = self.formulario.leer()
		por_clave = {campo.clave: campo for campo in self.campos}
		pendientes: dict[str, Any] = {}
		for clave, valor in valores.items():
			campo = por_clave[clave]
			if clave.startswith(esquema.PREFIJO_RESTABLECER):
				if valor:
					destino = clave[len(esquema.PREFIJO_RESTABLECER) :]
					pendientes[destino] = copy.deepcopy(self._config.valor_por_defecto(destino))
				continue
			if not esquema.es_clave_de_configuracion(clave):
				continue
			nuevo = esquema.a_configuracion(campo, valor)
			try:
				self._config.validar(clave, nuevo)
			except ErrorValidacion as error:
				raise ErrorCampo(clave, _mensaje_de_regla(self._config, campo, nuevo)) from error
			if nuevo != self._config.obtener(clave):
				pendientes[clave] = nuevo
		return pendientes

	def aplicar(self) -> bool:
		"""Valida y guarda. False (con el foco en el campo que no vale) si hay algún error."""
		try:
			pendientes = self.cambios()
		except ErrorCampo as error:
			self.ultimo_error = error.mensaje
			mostrar_error(self, error.mensaje, _("Revise las preferencias"))
			self.formulario.enfocar(error.clave)
			return False
		self.ultimo_error = ""
		if not pendientes:
			return True
		try:
			self._config.establecer_varias(pendientes)
		except ErrorConfiguracion as error:
			log.exception("No se pudieron guardar las preferencias")
			self.ultimo_error = str(error)
			mostrar_error(self, _("No se pudieron guardar las preferencias: {error}").format(error=error), _("Preferencias"))
			return False
		self.cambios_aplicados = True
		log.info("Preferencias cambiadas: %s", ", ".join(sorted(pendientes)))
		# Las casillas de «restablecer al aceptar» ya han hecho su trabajo.
		self.formulario.fijar({campo.clave: False for campo in self.campos if campo.clave.startswith(esquema.PREFIJO_RESTABLECER)})
		if "general.idioma" in pendientes:
			self._cambiar_idioma(pendientes["general.idioma"])
		if self._al_aplicar is not None:
			try:
				self._al_aplicar(sorted(pendientes))
			except Exception:  # noqa: BLE001 - las preferencias ya están guardadas; avisar a otros procesos es un extra
				log.exception("No se ha podido avisar del cambio de preferencias")
		return True

	def _cambiar_idioma(self, codigo: str) -> None:
		"""Activa el idioma elegido y avisa de lo que no cambia hasta reiniciar."""
		if not i18n.cambiar_idioma(codigo):
			mostrar_mensaje(self, _("No hay traducción para ese idioma: la aplicación sigue en español."), _("Idioma"))
			return
		if i18n.necesita_reinicio():
			mostrar_mensaje(
				self,
				_(
					"El idioma se ha cambiado. Los menús, las ventanas ya abiertas y los botones estándar cambiarán cuando reinicie la aplicación."
				),
				_("Idioma"),
			)

	def _al_aceptar(self, _evento: wx.CommandEvent) -> None:
		if self.aplicar():
			self.EndModal(wx.ID_OK)

	def enfocar_inicial(self) -> None:
		"""Foco en las pestañas: el lector anuncia en cuál se está."""
		cuaderno = self.cuaderno()
		if cuaderno is not None:
			enfocar(cuaderno)


def _mensaje_de_regla(configuracion: Any, campo: Any, valor: Any) -> str:
	"""Explica por qué un valor no cumple la regla de su clave, nombrando el campo como lo ve la persona."""
	from app.ui.esquemas import texto_numero

	nombre = nombre_campo(campo)
	regla = configuracion.regla(campo.clave)
	if regla is not None and isinstance(valor, (int, float)) and not isinstance(valor, bool):
		escala = campo.extra.get("escala", 1)
		if regla.minimo is not None and valor < regla.minimo:
			return _("«{campo}» no puede ser menor que {limite}.").format(campo=nombre, limite=texto_numero(regla.minimo * escala))
		if regla.maximo is not None and valor > regla.maximo:
			return _("«{campo}» no puede ser mayor que {limite}.").format(campo=nombre, limite=texto_numero(regla.maximo * escala))
	if regla is not None and isinstance(valor, str) and regla.longitud_maxima is not None and len(valor) > regla.longitud_maxima:
		return _("«{campo}» es demasiado largo: admite como mucho {n} caracteres.").format(campo=nombre, n=regla.longitud_maxima)
	return _("El valor de «{campo}» no es válido.").format(campo=nombre)


def avisar_reproductores(contexto: Any, claves: list[str]) -> int:
	"""Pide a los reproductores conectados a la sala que relean ``config.json``, si lo cambiado les afecta.

	Comparten el archivo con el Estudio; sin el aviso, un reproductor en
	marcha no vería el paquete de sonido, los volúmenes o la voz nuevos hasta
	volver a su menú. Solo se usa el servicio del seguimiento si ya existe
	(no se crea uno, ni se abre la sala, para esto). Devuelve a cuántos se avisa.
	"""
	if not any(clave.partition(".")[0] in SECCIONES_DEL_REPRODUCTOR or clave in CLAVES_DEL_REPRODUCTOR for clave in claves):
		return 0
	from app.ui.seguimiento.servicio import servicio_existente

	servicio = servicio_existente(contexto)
	if servicio is None:
		return 0
	return servicio.releer_configuracion_en_reproductores()


# Preferencias que usa el reproductor en marcha (sección entera o clave suelta).
SECCIONES_DEL_REPRODUCTOR: frozenset[str] = frozenset({"sonido", "voz", "juego", "mando", "teclado"})
CLAVES_DEL_REPRODUCTOR: frozenset[str] = frozenset(
	{"general.idioma", "general.tamano_texto", "general.alto_contraste", "supervision.segunda_salida"}
)


def mostrar_preferencias(contexto: Any) -> bool:
	"""Abre Preferencias. True si se aceptó o se aplicó algún cambio."""
	dialogo = DialogoPreferencias(
		contexto.ventana,
		contexto.configuracion,
		anunciar=getattr(contexto, "anunciar", None),
		al_aplicar=lambda claves: avisar_reproductores(contexto, claves),
	)
	foco_previo = wx.Window.FindFocus()
	try:
		respuesta = dialogo.ShowModal()
		# Con un ShowModal sustituido (pruebas, automatización) el botón Aceptar no ha validado todavía.
		if respuesta == wx.ID_OK and not dialogo.cambios_aplicados:
			dialogo.aplicar()
		return dialogo.cambios_aplicados
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()
