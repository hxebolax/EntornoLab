"""Ventana de alumnos: lista, ficha, archivar, recompensas, lista de trabajo, exportar y borrar.

Trata datos de salud, a menudo de menores: el nombre real y las notas se
guardan cifrados, el borrado es completo (incluidas las copias de seguridad)
y exige escribir el alias, y nada de esto se escribe en los registros.
"""

from __future__ import annotations

import logging
from typing import Any

import wx

from app.core.i18n import _
from app.seguimiento import recompensas
from app.seguimiento.alumnos import ALIAS_MAXIMO, Alumno, Fichas
from app.seguimiento.base import ESTILOS, PERFILES, TIPOS_RECOMPENSA, ErrorBase, ErrorDatos
from app.ui.accesibilidad.dialogos import enfocar, mostrar_error, mostrar_mensaje
from app.ui.accesibilidad.teclado import vincular_menu_contextual
from app.ui.seguimiento import dialogos_acceso, textos
from app.ui.seguimiento import presentador_alumnos as pres
from app.ui.seguimiento.comun import (
	DialogoFormulario,
	Problema,
	VentanaSeguimiento,
	crear_boton,
	crear_casilla,
	crear_desplegable,
	crear_lista,
	crear_texto,
	mostrar_modal,
	pedir_ruta_guardar,
	poner_texto,
)
from app.ui.seguimiento.contexto import anunciar
from app.ui.seguimiento.textos import fecha_legible, texto_numero

log = logging.getLogger(__name__)


class DialogoCalcularPaso(DialogoFormulario):
	"""Calcula la longitud del paso a partir de «camina 10 metros y cuenta los pasos»."""

	def __init__(self, padre: wx.Window | None) -> None:
		super().__init__(padre, _("Calcular la longitud del paso"))
		self.paso: float | None = None
		crear_texto(
			self.panel,
			self.letras.poner(_("Instrucciones:")),
			_(
				"Pida al alumno que camine en línea recta una distancia conocida, por ejemplo 10 metros, a su ritmo "
				"normal, y cuente sus pasos. Escriba aquí los metros y los pasos: el programa divide unos entre otros."
			),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=80,
			ancho=460,
		)
		self.metros = crear_texto(
			self.panel,
			self.letras.poner(_("Metros caminados:")),
			"10",
			sizer=self.sizer,
			ayuda=_("La distancia que ha caminado el alumno, en metros. Admite decimales con coma."),
		)
		self.pasos = crear_texto(
			self.panel,
			self.letras.poner(_("Pasos contados:")),
			sizer=self.sizer,
			ayuda=_("Cuántos pasos ha dado para recorrer esa distancia."),
		)
		self.terminar(self.pasos)

	def validar(self) -> Problema | None:
		try:
			self.paso = pres.calcular_paso(self.metros.GetValue(), self.pasos.GetValue())
		except ValueError as error:
			return str(error), self.pasos
		return None


class DialogoAlumno(DialogoFormulario):
	"""Alta o edición de la ficha de un alumno, en dos pestañas: la ficha y sus ajustes de juego."""

	def __init__(self, padre: wx.Window | None, fichas: Fichas, alumno: Alumno | None = None, configuracion: Any = None) -> None:
		titulo = _("Nuevo alumno") if alumno is None else _("Ficha de {alias}").format(alias=alumno.alias)
		super().__init__(padre, titulo)
		self.fichas = fichas
		self.alumno = alumno
		self.resultado: Alumno | None = None
		self._datos: pres.DatosFicha | None = None
		self.cuaderno = wx.Notebook(self.panel, name=_("Apartados de la ficha"))
		self.sizer.Add(self.cuaderno, 1, wx.EXPAND | wx.ALL, 6)
		self._pagina_ficha(alumno)
		self._pagina_ajustes(pres.ajustes_completos(alumno.ajustes if alumno else None, configuracion))
		self.terminar(self.alias, tamano_minimo=(620, 560))

	def _pagina(self, titulo: str) -> tuple[wx.Panel, wx.BoxSizer]:
		pagina = wx.Panel(self.cuaderno, name=titulo)
		columna = wx.BoxSizer(wx.VERTICAL)
		pagina.SetSizer(columna)
		self.cuaderno.AddPage(pagina, titulo)
		return pagina, columna

	def _pagina_ficha(self, alumno: Alumno | None) -> None:
		pagina, columna = self._pagina(_("Ficha"))
		letras = self.letras.copia()
		self.alias = crear_texto(
			pagina,
			letras.poner(_("Alias (obligatorio):")),
			alumno.alias if alumno else "",
			sizer=columna,
			ayuda=_(
				"Nombre corto o apodo con el que se identifica al alumno en las listas, los informes y la supervisión. "
				"Es obligatorio, no se cifra y no debe ser su nombre completo."
			),
		)
		self.alias.SetMaxLength(ALIAS_MAXIMO)
		self.nombre_real = crear_texto(
			pagina,
			letras.poner(_("Nombre real (opcional, se guarda cifrado):")),
			alumno.nombre_real if alumno else "",
			sizer=columna,
			ayuda=_("Puede dejarlo vacío. Si lo escribe, se guarda cifrado con su contraseña y nunca viaja por la red."),
		)
		self.ano = crear_texto(
			pagina,
			letras.poner(_("Año de nacimiento (opcional):")),
			texto_numero(alumno.ano_nacimiento) if alumno else "",
			sizer=columna,
			ayuda=_("Solo el año, con cuatro cifras. Puede dejarlo vacío. Se guarda sin cifrar: no escriba la fecha completa."),
		)
		self.perfil = crear_desplegable(
			pagina,
			letras.poner(_("Perfil de movilidad:")),
			[textos.nombre(textos.PERFILES, clave) for clave in PERFILES],
			sizer=columna,
			seleccion=PERFILES.index(alumno.perfil) if alumno and alumno.perfil in PERFILES else PERFILES.index("otro"),
			ayuda=_("Cómo se desplaza el alumno habitualmente. Sirve para describirlo en los informes."),
		)
		self.estilo = crear_desplegable(
			pagina,
			letras.poner(_("Estilo de presentación:")),
			[textos.nombre(textos.ESTILOS, clave) for clave in ESTILOS],
			sizer=columna,
			seleccion=ESTILOS.index(alumno.estilo) if alumno and alumno.estilo in ESTILOS else ESTILOS.index("adulto"),
			ayuda=_(
				"Infantil: personajes y mucha celebración. Juvenil: misiones y retos. Adulto: sobrio, con objetivos prácticos. El contenido que se aprende es el mismo."
			),
		)
		self.notas = crear_texto(
			pagina,
			letras.poner(_("Notas (opcionales, se guardan cifradas):")),
			alumno.notas if alumno else "",
			sizer=columna,
			multilinea=True,
			alto=110,
			proporcion=1,
			ayuda=_("Observaciones sobre el alumno. Se guardan cifradas con su contraseña."),
		)

	def _pagina_ajustes(self, ajustes: dict[str, Any]) -> None:
		pagina, columna = self._pagina(_("Ajustes de juego"))
		letras = self.letras.copia()
		self._otros_ajustes = {clave: valor for clave, valor in ajustes.items() if clave not in pres.AJUSTES_DE_SERIE}
		self._modos = list(textos.MODOS_MOVIMIENTO)
		self.modo = crear_desplegable(
			pagina,
			letras.poner(_("Modo de movimiento:")),
			[textos.nombre(textos.MODOS_MOVIMIENTO, clave) for clave in self._modos],
			sizer=columna,
			seleccion=self._modos.index(ajustes["modo_movimiento"]) if ajustes["modo_movimiento"] in self._modos else 0,
			ayuda=_("Cómo se mueve el alumno con las flechas o el mando."),
		)
		self.paso = crear_texto(
			pagina,
			letras.poner(_("Longitud de su paso, en metros:")),
			texto_numero(float(ajustes["paso_m"])),
			sizer=columna,
			ayuda=_(
				"Lo que avanza el alumno con cada paso, entre {minimo} y {maximo} metros. Con su paso real, las distancias "
				"dichas en pasos coinciden con las del lugar de verdad. El botón siguiente lo calcula."
			).format(minimo=textos.decimal(pres.PASO_MINIMO, 2), maximo=textos.decimal(pres.PASO_MAXIMO, 2)),
		)
		self.boton_paso = crear_boton(
			pagina,
			letras.poner(_("Calcular el paso...")),
			self.calcular_paso,
			sizer=columna,
			ayuda=_("Calcula la longitud del paso a partir de una prueba sencilla: caminar 10 metros y contar los pasos."),
		)
		self.giro = crear_texto(
			pagina,
			letras.poner(_("Giro por pulsación, en grados:")),
			texto_numero(float(ajustes["giro_grados"])),
			sizer=columna,
			ayuda=_("Cuánto gira con cada pulsación, de 0 a 180 grados. Con 0 gira mientras mantiene la tecla."),
		)
		self.velocidad = crear_texto(
			pagina,
			letras.poner(_("Velocidad en modo continuo, en metros por segundo:")),
			texto_numero(float(ajustes["velocidad_ms"])),
			sizer=columna,
			ayuda=_("Entre 0,3 y 3 metros por segundo. Andar despacio son unos 0,8; a paso normal, 1,2."),
		)
		self._formatos = list(textos.FORMATOS_DIRECCION)
		self.formato = crear_desplegable(
			pagina,
			letras.poner(_("Formato de las direcciones:")),
			[textos.nombre(textos.FORMATOS_DIRECCION, clave) for clave in self._formatos],
			sizer=columna,
			seleccion=self._formatos.index(ajustes["formato_direccion"]) if ajustes["formato_direccion"] in self._formatos else 0,
			ayuda=_("Cómo se le dicen las direcciones: por las horas del reloj, por lados, por puntos cardinales o en grados."),
		)
		self._unidades = list(textos.UNIDADES)
		self.unidad = crear_desplegable(
			pagina,
			letras.poner(_("Unidad de las distancias:")),
			[textos.nombre(textos.UNIDADES, clave) for clave in self._unidades],
			sizer=columna,
			seleccion=self._unidades.index(ajustes["unidad"]) if ajustes["unidad"] in self._unidades else 0,
			ayuda=_("Las distancias se le dicen en metros o en pasos suyos."),
		)
		self._detalles = list(textos.DETALLES)
		detalle = ajustes["detalle"] if ajustes["detalle"] in self._detalles else 2
		self.detalle = crear_desplegable(
			pagina,
			letras.poner(_("Nivel de detalle de lo que se le cuenta:")),
			[textos.nombre(textos.DETALLES, clave) for clave in self._detalles],
			sizer=columna,
			seleccion=self._detalles.index(detalle),
			ayuda=_("De 0, solo sonidos, a 3, todos los avisos y descripciones."),
		)

	def ir_a(self, control: wx.Window) -> None:
		for indice in range(self.cuaderno.GetPageCount()):
			if control.GetParent() is self.cuaderno.GetPage(indice):
				self.cuaderno.SetSelection(indice)
				break
		enfocar(control)

	def calcular_paso(self) -> None:
		"""Abre el cálculo del paso y, si se acepta, escribe el resultado en el campo."""
		dialogo = DialogoCalcularPaso(self)
		try:
			mostrar_modal(dialogo)
			paso = dialogo.paso if dialogo.aceptado else None
		finally:
			dialogo.Destroy()
		if paso is not None:
			self.paso.SetValue(texto_numero(paso))
			enfocar(self.paso)

	def validar(self) -> Problema | None:
		alias = " ".join(self.alias.GetValue().split())
		if not alias:
			return _("El alias es obligatorio."), self.alias
		pasos = (
			(self.ano, 1900, pres.ano_actual(), _("Año de nacimiento"), True, True),
			(self.paso, pres.PASO_MINIMO, pres.PASO_MAXIMO, _("Longitud de su paso"), False, False),
			(self.giro, pres.GIRO_MINIMO, pres.GIRO_MAXIMO, _("Giro por pulsación"), False, False),
			(self.velocidad, pres.VELOCIDAD_MINIMA, pres.VELOCIDAD_MAXIMA, _("Velocidad en modo continuo"), False, False),
		)
		valores: list[Any] = []
		for campo, minimo, maximo, nombre, entero, vacio in pasos:
			try:
				valores.append(pres.leer_en_rango(campo.GetValue(), minimo, maximo, nombre, entero=entero, vacio=vacio))
			except ValueError as error:
				return str(error), campo
		ajustes = dict(self._otros_ajustes)
		ajustes.update(
			{
				"modo_movimiento": self._modos[self.modo.GetSelection()],
				"paso_m": float(valores[1]),
				"giro_grados": float(valores[2]),
				"velocidad_ms": float(valores[3]),
				"formato_direccion": self._formatos[self.formato.GetSelection()],
				"unidad": self._unidades[self.unidad.GetSelection()],
				"detalle": self._detalles[self.detalle.GetSelection()],
			}
		)
		self._datos = pres.DatosFicha(
			alias=alias,
			nombre_real=self.nombre_real.GetValue().strip(),
			notas=self.notas.GetValue(),
			ano_nacimiento=valores[0],
			perfil=PERFILES[self.perfil.GetSelection()],
			estilo=ESTILOS[self.estilo.GetSelection()],
			ajustes=ajustes,
		)
		return None

	def aplicar(self) -> Problema | None:
		datos = self._datos
		assert datos is not None
		campos = {
			"nombre_real": datos.nombre_real,
			"notas": datos.notas,
			"ano_nacimiento": datos.ano_nacimiento,
			"perfil": datos.perfil,
			"estilo": datos.estilo,
			"ajustes": datos.ajustes,
		}
		try:
			if self.alumno is None:
				self.resultado = self.fichas.alta(datos.alias, **campos)
			else:
				self.resultado = self.fichas.editar(self.alumno.id, alias=datos.alias, **campos)
		except ErrorDatos as error:
			return str(error), self.alias
		except ErrorBase as error:
			log.exception("No se ha podido guardar una ficha")
			return _("No se ha podido guardar la ficha: {error}").format(error=error), self.alias
		return None


class DialogoBorrarAlumno(DialogoFormulario):
	"""Confirmación fuerte del borrado completo: hay que escribir el alias."""

	def __init__(self, padre: wx.Window | None, alumno: Alumno, resumen: str) -> None:
		super().__init__(padre, _("Borrar por completo a {alias}").format(alias=alumno.alias))
		self.alumno = alumno
		etiqueta_borrar = self.letras.poner(_("Borrar por completo"))
		self.aviso = crear_texto(
			self.panel,
			self.letras.poner(_("Qué se va a borrar:")),
			resumen,
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=230,
			ancho=560,
			proporcion=1,
			ayuda=_("Lea con las flechas todo lo que se va a borrar. No se puede deshacer."),
		)
		self.confirmacion = crear_texto(
			self.panel,
			self.letras.poner(_("Para confirmar, escriba el alias del alumno:")),
			sizer=self.sizer,
			ayuda=_("Escriba «{alias}» tal cual. Es una protección contra un borrado por error.").format(alias=alumno.alias),
		)
		# Intro es «Cancelar»: una pulsación accidental no borra nada.
		self.terminar(self.aviso, etiqueta_aceptar=etiqueta_borrar, predeterminado=wx.ID_CANCEL, tamano_minimo=(600, 440))

	def validar(self) -> Problema | None:
		if not pres.alias_coincide(self.confirmacion.GetValue(), self.alumno.alias):
			return _("Lo escrito no coincide con el alias «{alias}». No se ha borrado nada.").format(
				alias=self.alumno.alias
			), self.confirmacion
		return None


class DialogoRecompensas(DialogoFormulario):
	"""Colección de recompensas de un alumno: resumen, lista, añadir una a mano y quitar una apuntada por error."""

	def __init__(self, padre: wx.Window | None, base: Any, alumno: Alumno, configuracion: Any = None) -> None:
		super().__init__(padre, _("Recompensas de {alias}").format(alias=alumno.alias))
		self.base = base
		self.alumno = alumno
		self.recompensas: list[Any] = []
		self.resumen = crear_texto(
			self.panel,
			self.letras.poner(_("Colección:")),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=110,
			ancho=520,
			ayuda=_("Cuántas estrellas, medallas y objetos tiene el alumno. Las recompensas motivan; no son una medida del aprendizaje."),
		)
		self.lista = crear_lista(
			self.panel,
			self.letras.poner(_("Recompensas ganadas:")),
			[(_("Fecha"), 110), (_("Tipo"), 100), (_("Nombre"), 280)],
			configuracion,
			sizer=self.sizer,
			ayuda=_("Todas las recompensas, de la más antigua a la más reciente."),
		)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		self._tipos = list(TIPOS_RECOMPENSA)
		nombres = {"estrella": _("Estrella"), "medalla": _("Medalla"), "objeto": _("Objeto")}
		self.tipo = crear_desplegable(
			self.panel,
			self.letras.poner(_("Tipo de la recompensa nueva:")),
			[nombres.get(t, t) for t in self._tipos],
			sizer=self.sizer,
			ayuda=_("Para dar una recompensa a mano: elija el tipo, escriba el nombre y pulse «Dar la recompensa»."),
		)
		self.nombre = crear_texto(
			self.panel,
			self.letras.poner(_("Nombre de la recompensa nueva:")),
			sizer=self.sizer,
			ayuda=_("Por ejemplo «Medalla del explorador»."),
		)
		crear_boton(
			self.panel,
			self.letras.poner(_("Dar la recompensa")),
			self.dar,
			_("Apunta una recompensa nueva con el tipo y el nombre escritos."),
			fila,
		)
		crear_boton(
			self.panel,
			self.letras.poner(_("Quitar la elegida")),
			self.quitar,
			_("Quita la recompensa elegida en la lista, por si se apuntó por error."),
			fila,
		)
		self.sizer.Add(fila, 0, wx.ALL, 2)
		self.recargar()
		self.terminar(self.resumen, botones=wx.CLOSE, tamano_minimo=(580, 560))

	def recargar(self) -> None:
		"""Vuelve a leer la colección y la lista."""
		self.recompensas = recompensas.de_alumno(self.base, self.alumno.id)
		nombres = {"estrella": _("Estrella"), "medalla": _("Medalla"), "objeto": _("Objeto")}
		self.lista.reemplazar_filas(
			[[fecha_legible(r.fecha, con_hora=False), nombres.get(r.tipo, r.tipo), r.nombre] for r in self.recompensas]
		)
		poner_texto(self.resumen, pres.texto_coleccion(self.base, self.alumno.id))

	def dar(self) -> None:
		"""Apunta la recompensa escrita."""
		try:
			recompensas.registrar(self.base, self.alumno.id, self._tipos[self.tipo.GetSelection()], self.nombre.GetValue())
		except ErrorDatos as error:
			mostrar_error(self, str(error))
			return
		self.nombre.SetValue("")
		self.recargar()
		self.lista.enfocar_fila(self.lista.numero_filas() - 1, anunciar=False)

	def quitar(self) -> None:
		"""Quita la recompensa elegida."""
		fila = self.lista.fila_actual()
		if not 0 <= fila < len(self.recompensas):
			return
		recompensas.borrar(self.base, self.recompensas[fila].id)
		self.recargar()


class DialogoListaTrabajo(DialogoFormulario):
	"""Actividades asignadas a un alumno, con la posibilidad de quitar una."""

	def __init__(self, padre: wx.Window | None, fichas: Fichas, alumno: Alumno, configuracion: Any = None) -> None:
		super().__init__(padre, _("Lista de trabajo de {alias}").format(alias=alumno.alias))
		self.fichas = fichas
		self.alumno = alumno
		self.lista = crear_lista(
			self.panel,
			self.letras.poner(_("Actividades asignadas:")),
			[(_("Actividad"), 240), (_("Entorno"), 200), (_("Asignada el"), 110)],
			configuracion,
			sizer=self.sizer,
			ayuda=_("Las actividades que este alumno tiene pendientes. Se asignan desde la pestaña Actividades del entorno."),
		)
		crear_boton(
			self.panel,
			self.letras.poner(_("Quitar de la lista")),
			self.quitar,
			_("Quita de la lista de trabajo la actividad elegida. No borra la actividad."),
			self.sizer,
		)
		self.recargar()
		self.terminar(self.lista, botones=wx.CLOSE, tamano_minimo=(600, 380))

	def recargar(self) -> None:
		"""Vuelve a pintar la lista."""
		self.lista.reemplazar_filas([pres.fila_trabajo(entrada) for entrada in pres.lista_de_trabajo(self.alumno)])

	def quitar(self) -> None:
		"""Quita la entrada elegida."""
		fila = self.lista.fila_actual()
		if fila == wx.NOT_FOUND:
			return
		self.alumno = pres.quitar_de_lista(self.fichas, self.alumno, fila)
		self.recargar()


class VentanaAlumnos(VentanaSeguimiento):
	"""Lista de alumnos con todas sus acciones."""

	CLAVE = "alumnos"

	def __init__(self, contexto: Any, servicio: Any) -> None:
		super().__init__(contexto, servicio, _("Alumnos"), (860, 620))
		self.alumnos: list[Alumno] = []
		letras = self.letras
		self.buscar = crear_texto(
			self.panel,
			letras.poner(_("Buscar por alias:")),
			sizer=self.sizer,
			ayuda=_("Escriba parte del alias para acortar la lista. Solo se busca en el alias: el nombre real está cifrado."),
		)
		self.archivados = crear_casilla(
			self.panel,
			letras.poner(_("Mostrar también los archivados")),
			sizer=self.sizer,
			ayuda=_("Los alumnos archivados no salen en las listas, pero conservan todos sus datos."),
		)
		self.lista = crear_lista(
			self.panel,
			letras.poner(_("Alumnos:")),
			pres.columnas(),
			getattr(contexto, "configuracion", None),
			sizer=self.sizer,
			ayuda=_(
				"Lista de alumnos. Arriba y abajo cambian de alumno; izquierda y derecha leen las columnas. Intro abre la ficha, "
				"Suprimir pide borrarlo y la tecla Aplicaciones abre el menú con todas las acciones."
			),
		)
		fila = self.fila_botones()
		acciones = (
			(_("Nuevo..."), self.nuevo, _("Crea la ficha de un alumno nuevo.")),
			(_("Editar la ficha..."), self.editar, _("Abre la ficha y los ajustes de juego del alumno elegido.")),
			(
				_("Archivar o recuperar"),
				self.archivar,
				_("Archiva al alumno elegido para que no salga en las listas, o lo recupera si estaba archivado. No borra nada."),
			),
			(_("Recompensas..."), self.recompensas, _("Muestra las estrellas, medallas y objetos que ha ganado.")),
			(_("Lista de trabajo..."), self.lista_trabajo, _("Muestra las actividades que tiene asignadas.")),
			(_("Sesiones"), lambda: self.abrir("sesiones"), _("Abre las sesiones del alumno elegido.")),
			(_("Informes"), lambda: self.abrir("informes"), _("Abre los informes del alumno elegido.")),
			(_("Cuaderno real"), lambda: self.abrir("cuaderno"), _("Abre el cuaderno de evaluación en el lugar real del alumno elegido.")),
			(_("Exportar datos..."), self.exportar, _("Guarda en un archivo ZIP todos los datos del alumno elegido, para entregárselos.")),
			(
				_("Borrar por completo..."),
				self.borrar,
				_("Borra al alumno elegido con todo lo suyo. Pide escribir su alias. No se puede deshacer."),
			),
			(_("Cambiar contraseña..."), self.cambiar_contrasena, _("Cambia la contraseña con la que se cifran los datos.")),
			(_("Bloquear los datos"), self.bloquear, _("Cierra los datos de alumnos: la próxima vez se pedirá la contraseña.")),
			(_("Cerrar"), self.Close, _("Cierra esta ventana. Los datos siguen desbloqueados hasta que los bloquee o cierre el programa.")),
		)
		self.botones: dict[str, wx.Button] = {}
		for etiqueta, accion, ayuda in acciones:
			self.botones[etiqueta] = crear_boton(self.panel, letras.poner(etiqueta), accion, ayuda, fila)
		self.buscar.Bind(wx.EVT_TEXT, lambda _evento: self.recargar())
		self.archivados.Bind(wx.EVT_CHECKBOX, lambda _evento: self.recargar())
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.editar())
		self.lista.Bind(wx.EVT_KEY_DOWN, self._tecla_lista)
		vincular_menu_contextual(self.lista, self._menu)
		self.recargar()
		self.terminar(self.lista)

	# ── Lista ────────────────────────────────────────────────────────────────

	@property
	def fichas(self) -> Fichas:
		"""Fichas de la base abierta."""
		return self.servicio.fichas()

	def recargar(self, alias: str | None = None) -> None:
		"""Vuelve a leer la lista; deja elegido el alumno ``alias`` si se indica."""
		base = self.servicio.base
		if base is None:
			return
		filas = pres.filas_alumnos(base, self.buscar.GetValue(), self.archivados.GetValue())
		self.alumnos = [alumno for alumno, _fila in filas]
		self.lista.reemplazar_filas([fila for _alumno, fila in filas])
		if alias is not None:
			for indice, alumno in enumerate(self.alumnos):
				if alumno.alias == alias:
					self.lista.enfocar_fila(indice, anunciar=False)
					break

	def elegido(self) -> Alumno | None:
		"""El alumno de la fila enfocada, o ``None``."""
		fila = self.lista.fila_actual()
		return self.alumnos[fila] if 0 <= fila < len(self.alumnos) else None

	def _exigir(self) -> Alumno | None:
		alumno = self.elegido()
		if alumno is None:
			anunciar(self.contexto, _("No hay ningún alumno elegido."))
		return alumno

	def _tecla_lista(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_DELETE and evento.GetModifiers() == wx.MOD_NONE:  # atajo: Supr
			self.borrar()
			return
		evento.Skip()

	def _menu(self) -> wx.Menu | None:
		if self.elegido() is None:
			return None
		menu = wx.Menu()
		letras = textos.Letras()
		for etiqueta, accion in (
			(_("Editar la ficha..."), self.editar),
			(_("Archivar o recuperar"), self.archivar),
			(_("Recompensas..."), self.recompensas),
			(_("Lista de trabajo..."), self.lista_trabajo),
			(_("Sesiones"), lambda: self.abrir("sesiones")),
			(_("Informes"), lambda: self.abrir("informes")),
			(_("Cuaderno real"), lambda: self.abrir("cuaderno")),
			(_("Exportar datos..."), self.exportar),
			(_("Borrar por completo..."), self.borrar),
		):
			elemento = menu.Append(wx.ID_ANY, letras.poner(etiqueta))
			self.Bind(wx.EVT_MENU, lambda _evento, a=accion: a(), elemento)
		return menu

	# ── Acciones ─────────────────────────────────────────────────────────────

	def _ficha(self, alumno: Alumno | None) -> Alumno | None:
		dialogo = DialogoAlumno(self, self.fichas, alumno, getattr(self.contexto, "configuracion", None))
		try:
			mostrar_modal(dialogo)
			return dialogo.resultado if dialogo.aceptado else None
		finally:
			dialogo.Destroy()

	def nuevo(self) -> None:
		"""Da de alta un alumno."""
		creado = self._ficha(None)
		if creado is not None:
			self.recargar(creado.alias)
			anunciar(self.contexto, _("Alumno {alias} creado.").format(alias=creado.alias))
			self._enviar_al_reproductor(creado)
		self.lista.SetFocus()

	def editar(self) -> None:
		"""Edita la ficha del alumno elegido."""
		alumno = self._exigir()
		if alumno is None:
			return
		cambiado = self._ficha(alumno)
		if cambiado is not None:
			self.recargar(cambiado.alias)
			anunciar(self.contexto, _("Ficha de {alias} guardada.").format(alias=cambiado.alias))
			self._enviar_al_reproductor(cambiado)
		self.lista.SetFocus()

	def archivar(self) -> None:
		"""Archiva al alumno elegido, o lo recupera si ya estaba archivado."""
		alumno = self._exigir()
		if alumno is None:
			return
		self.fichas.archivar(alumno.id, not alumno.archivado)
		self.recargar(alumno.alias)
		if alumno.archivado:
			anunciar(self.contexto, _("{alias} recuperado.").format(alias=alumno.alias))
		else:
			anunciar(
				self.contexto,
				_("{alias} archivado. Sus datos se conservan; para verlo, marque «Mostrar también los archivados».").format(
					alias=alumno.alias
				),
			)

	def recompensas(self) -> None:
		"""Abre la colección de recompensas del alumno elegido."""
		alumno = self._exigir()
		if alumno is None:
			return
		dialogo = DialogoRecompensas(self, self.servicio.base, alumno, getattr(self.contexto, "configuracion", None))
		try:
			mostrar_modal(dialogo)
		finally:
			dialogo.Destroy()

	def lista_trabajo(self) -> None:
		"""Abre la lista de trabajo del alumno elegido."""
		alumno = self._exigir()
		if alumno is None:
			return
		dialogo = DialogoListaTrabajo(self, self.fichas, alumno, getattr(self.contexto, "configuracion", None))
		try:
			mostrar_modal(dialogo)
			actual = dialogo.alumno
		finally:
			dialogo.Destroy()
		if actual is not alumno:
			self._enviar_al_reproductor(actual)
		self.recargar(alumno.alias)

	def _enviar_al_reproductor(self, alumno: Alumno) -> None:
		"""Si el alumno está conectado a la sala, su reproductor recibe al momento la ficha cambiada."""
		enviar = getattr(self.servicio, "enviar_ficha", None)
		if callable(enviar) and enviar(alumno):
			anunciar(self.contexto, _("Cambios enviados al reproductor de {alias}.").format(alias=alumno.alias))

	def abrir(self, cual: str) -> None:
		"""Abre las sesiones, los informes o el cuaderno del alumno elegido."""
		from app.ui.seguimiento import integracion

		alumno = self.elegido()
		alumno_id = alumno.id if alumno is not None else None
		if cual == "sesiones":
			integracion.mostrar_sesiones(self.contexto, alumno_id=alumno_id)
		elif cual == "informes":
			integracion.mostrar_informes(self.contexto, alumno_id=alumno_id)
		else:
			integracion.mostrar_cuaderno(self.contexto, alumno_id=alumno_id)

	def exportar(self) -> None:
		"""Guarda todos los datos del alumno elegido en un ZIP."""
		alumno = self._exigir()
		if alumno is None:
			return
		ruta = pedir_ruta_guardar(
			self, _("Exportar los datos de {alias}").format(alias=alumno.alias), _("Archivo ZIP (*.zip)|*.zip"), f"{alumno.alias}.zip"
		)
		if ruta is None:
			return
		try:
			destino = self.fichas.exportar(alumno.id, ruta)
		except (ErrorBase, OSError) as error:
			log.exception("No se han podido exportar los datos de un alumno")
			mostrar_error(self, _("No se han podido exportar los datos: {error}").format(error=error))
			return
		mostrar_mensaje(
			self,
			_(
				"Datos de {alias} exportados en:\n{ruta}\n\nEl archivo contiene todos sus datos y NO está cifrado: "
				"entréguelo o guárdelo con cuidado."
			).format(alias=alumno.alias, ruta=destino),
			_("Datos exportados"),
		)

	def borrar(self) -> None:
		"""Borra por completo al alumno elegido, tras escribir su alias."""
		alumno = self._exigir()
		base = self.servicio.base
		if alumno is None or base is None:
			return
		dialogo = DialogoBorrarAlumno(self, alumno, pres.resumen_de_borrado(base, alumno))
		try:
			mostrar_modal(dialogo)
			confirmado = dialogo.aceptado
		finally:
			dialogo.Destroy()
		if not confirmado:
			anunciar(self.contexto, _("No se ha borrado nada."))
			self.lista.SetFocus()
			return
		try:
			cuenta = self.fichas.borrar(alumno.id, carpeta_sesiones=self.servicio.acceso.carpeta_sesiones)
		except (ErrorBase, OSError) as error:
			log.exception("No se ha podido borrar un alumno")
			mostrar_error(self, _("No se ha podido completar el borrado: {error}").format(error=error))
			return
		self.recargar()
		anunciar(
			self.contexto,
			_(
				"Alumno borrado por completo: {sesiones} sesiones, {evaluaciones} evaluaciones y {copias} copias de seguridad eliminadas."
			).format(sesiones=cuenta["sesiones"], evaluaciones=cuenta["evaluaciones"], copias=cuenta["copias"]),
		)
		self.lista.SetFocus()

	def cambiar_contrasena(self) -> None:
		"""Abre el cambio de contraseña."""
		dialogos_acceso.cambiar_contrasena(self.contexto, self.servicio, self)

	def bloquear(self) -> None:
		"""Bloquea los datos y cierra las ventanas que los muestran (esta incluida)."""
		# Destroy de una ventana de nivel superior es diferido: se puede pedir desde su propio botón.
		dialogos_acceso.bloquear(self.contexto, self.servicio)
