"""Cuaderno de evaluación real: lo que el profesional anota en el lugar físico, por alumno.

El programa solo guarda y enseña lo anotado, y lo pone junto a las sesiones
del simulador: no puntúa ni interpreta la evaluación.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import wx

from app.core.i18n import _
from app.seguimiento import cuaderno, informes, sesiones
from app.seguimiento.alumnos import Alumno, Fichas
from app.seguimiento.base import ErrorBase, ErrorDatos
from app.ui.accesibilidad.dialogos import elegir_opcion, mostrar_mensaje
from app.ui.seguimiento import presentador_registros as pres
from app.ui.seguimiento.comun import (
	DialogoFormulario,
	Problema,
	VentanaSeguimiento,
	crear_boton,
	crear_desplegable,
	crear_lista,
	crear_texto,
	mostrar_modal,
	mostrar_texto,
	poner_opciones,
	poner_texto,
)
from app.ui.seguimiento.contexto import anunciar

log = logging.getLogger(__name__)


class DialogoRuta(DialogoFormulario):
	"""Una ruta hecha en el lugar real: su nombre, cómo salió y unas notas."""

	def __init__(self, padre: wx.Window | None, ruta: dict[str, Any] | None = None) -> None:
		super().__init__(padre, _("Ruta en el lugar real"))
		ruta = ruta or {}
		self.ruta: dict[str, str] = {}
		self._resultados = list(cuaderno.RESULTADOS_RUTA)
		self.nombre = crear_texto(
			self.panel,
			self.letras.poner(_("Ruta:")),
			str(ruta.get("nombre") or ""),
			sizer=self.sizer,
			ayuda=_("De dónde a dónde: «De la entrada a la cocina»."),
		)
		resultado = ruta.get("resultado") if ruta.get("resultado") in self._resultados else "conseguida"
		self.resultado = crear_desplegable(
			self.panel,
			self.letras.poner(_("Resultado:")),
			[_(cuaderno.RESULTADOS_RUTA[clave]) for clave in self._resultados],
			sizer=self.sizer,
			seleccion=self._resultados.index(resultado),
			ayuda=_("Cómo salió la ruta en el lugar real."),
		)
		self.notas = crear_texto(
			self.panel,
			self.letras.poner(_("Notas de la ruta (opcional):")),
			str(ruta.get("notas") or ""),
			sizer=self.sizer,
			multilinea=True,
			alto=60,
			ancho=420,
			ayuda=_("Lo que quiera recordar de esta ruta. Se guarda sin cifrar: no escriba datos personales."),
		)
		self.terminar(self.nombre)

	def validar(self) -> Problema | None:
		nombre = self.nombre.GetValue().strip()
		if not nombre:
			return _("Escriba qué ruta es."), self.nombre
		self.ruta = {
			"nombre": nombre,
			"resultado": self._resultados[max(0, self.resultado.GetSelection())],
			"notas": self.notas.GetValue().strip(),
		}
		return None


class DialogoEvaluacion(DialogoFormulario):
	"""Anota una prueba en el lugar físico."""

	def __init__(self, padre: wx.Window | None, base: Any, alumno: Alumno, contexto: Any = None) -> None:
		super().__init__(padre, _("Evaluación en el lugar real de {alias}").format(alias=alumno.alias))
		self.base = base
		self.alumno = alumno
		self.rutas: list[dict[str, str]] = []
		self.evaluacion_id: int | None = None
		self._datos: dict[str, Any] = {}
		configuracion = getattr(contexto, "configuracion", None)
		self._entornos = pres.entornos_para_evaluar(base, contexto)
		abierto = str(getattr(getattr(contexto, "entorno", None), "id", "") or "")
		self.fecha = crear_texto(
			self.panel,
			self.letras.poner(_("Fecha de la prueba:")),
			date.today().isoformat(),
			sizer=self.sizer,
			ayuda=_("Como 2026-11-20 o 20/11/2026. Por defecto, hoy."),
		)
		self.lugar = crear_texto(
			self.panel,
			self.letras.poner(_("Lugar:")),
			sizer=self.sizer,
			ayuda=_("El lugar físico de la prueba: «Colegio, planta baja»."),
		)
		ids = [ident for ident, _nombre in self._entornos]
		self.entorno = crear_desplegable(
			self.panel,
			self.letras.poner(_("Entorno del simulador relacionado:")),
			[_("Ninguno"), *[nombre for _id, nombre in self._entornos]],
			sizer=self.sizer,
			seleccion=ids.index(abierto) + 1 if abierto in ids else 0,
			ayuda=_("El entorno del simulador que representa ese lugar. Sirve para comparar la prueba con las sesiones jugadas en él."),
		)
		self.dias = crear_texto(
			self.panel,
			self.letras.poner(_("Días desde el último entrenamiento (se calcula):")),
			sizer=self.sizer,
			lectura=True,
			ayuda=_(
				"Cuántos días han pasado entre la última sesión del alumno en el simulador y la fecha de la prueba. Lo calcula el programa."
			),
		)
		self.lista = crear_lista(
			self.panel,
			self.letras.poner(_("Rutas hechas:")),
			[(_("Ruta"), 230), (_("Resultado"), 170), (_("Notas"), 200)],
			configuracion,
			sizer=self.sizer,
			alto=110,
			ayuda=_("Las rutas que se probaron, con su resultado. Intro edita la elegida."),
		)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		crear_boton(self.panel, self.letras.poner(_("Nueva ruta...")), self.nueva_ruta, _("Añade una ruta con su resultado."), fila)
		crear_boton(self.panel, self.letras.poner(_("Modificar la ruta...")), self.editar_ruta, _("Cambia la ruta elegida."), fila)
		crear_boton(self.panel, self.letras.poner(_("Quitar la ruta")), self.quitar_ruta, _("Quita la ruta elegida."), fila)
		self.sizer.Add(fila, 0, wx.ALL, 2)
		self._niveles = list(cuaderno.NIVELES_AYUDA)
		self.nivel = crear_desplegable(
			self.panel,
			self.letras.poner(_("Nivel de ayuda:")),
			[_(cuaderno.NIVELES_AYUDA[clave]) for clave in self._niveles],
			sizer=self.sizer,
			ayuda=_("Cuánta ayuda necesitó en conjunto."),
		)
		self._tipos = list(cuaderno.TIPOS_RECORRIDO)
		self.tipo = crear_desplegable(
			self.panel,
			self.letras.poner(_("Tipo de recorrido:")),
			[_(cuaderno.TIPOS_RECORRIDO[clave]) for clave in self._tipos],
			sizer=self.sizer,
			ayuda=_("Si el recorrido se había entrenado en el simulador, o era nuevo, inverso o alternativo."),
		)
		self.ayudas = crear_texto(
			self.panel,
			self.letras.poner(_("Ayudas de movilidad usadas, separadas por comas:")),
			sizer=self.sizer,
			ayuda=_("Por ejemplo: bastón largo, perro guía."),
		)
		self.observaciones = crear_texto(
			self.panel,
			self.letras.poner(_("Observaciones (se guardan cifradas):")),
			sizer=self.sizer,
			multilinea=True,
			alto=70,
			ancho=520,
			ayuda=_("Lo que observó durante la prueba. Se guarda cifrado con su contraseña."),
		)
		self.fecha.Bind(wx.EVT_TEXT, lambda _evento: self._pintar_dias())
		self.entorno.Bind(wx.EVT_CHOICE, lambda _evento: self._pintar_dias())
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.editar_ruta())
		self._pintar_dias()
		self.terminar(self.fecha, tamano_minimo=(620, 700))

	def _entorno_elegido(self) -> tuple[str, str]:
		indice = self.entorno.GetSelection()
		return self._entornos[indice - 1] if indice > 0 else ("", "")

	def _pintar_dias(self) -> None:
		try:
			fecha = pres.leer_fecha(self.fecha.GetValue(), _("Fecha de la prueba"))
		except ValueError:
			fecha = None
		poner_texto(self.dias, pres.texto_dias(self.base, self.alumno.id, fecha, self._entorno_elegido()[0]))

	def _pedir_ruta(self, ruta: dict[str, Any] | None) -> dict[str, str] | None:
		dialogo = DialogoRuta(self, ruta)
		try:
			mostrar_modal(dialogo)
			return dialogo.ruta if dialogo.aceptado else None
		finally:
			dialogo.Destroy()

	def _pintar_rutas(self, fila: int | None = None) -> None:
		self.lista.reemplazar_filas([pres.fila_ruta(ruta) for ruta in self.rutas])
		if fila is not None:
			self.lista.enfocar_fila(fila, anunciar=False)

	def nueva_ruta(self) -> None:
		"""Añade una ruta."""
		ruta = self._pedir_ruta(None)
		if ruta is not None:
			self.rutas.append(ruta)
			self._pintar_rutas(len(self.rutas) - 1)
		self.lista.SetFocus()

	def editar_ruta(self) -> None:
		"""Cambia la ruta elegida."""
		fila = self.lista.fila_actual()
		if not 0 <= fila < len(self.rutas):
			return
		ruta = self._pedir_ruta(self.rutas[fila])
		if ruta is not None:
			self.rutas[fila] = ruta
			self._pintar_rutas(fila)
		self.lista.SetFocus()

	def quitar_ruta(self) -> None:
		"""Quita la ruta elegida."""
		fila = self.lista.fila_actual()
		if 0 <= fila < len(self.rutas):
			del self.rutas[fila]
			self._pintar_rutas(min(fila, len(self.rutas) - 1) if self.rutas else None)

	def validar(self) -> Problema | None:
		try:
			fecha = pres.leer_fecha(self.fecha.GetValue(), _("Fecha de la prueba"))
		except ValueError as error:
			return str(error), self.fecha
		if fecha is None:
			return _("Escriba la fecha de la prueba."), self.fecha
		if not self.lugar.GetValue().strip() and not self._entorno_elegido()[0]:
			return _("Escriba el lugar de la prueba o elija el entorno relacionado."), self.lugar
		entorno_id, entorno_nombre = self._entorno_elegido()
		self._datos = {
			"fecha": fecha,
			"lugar": self.lugar.GetValue().strip(),
			"entorno_id": entorno_id,
			"entorno_nombre": entorno_nombre,
			"rutas": list(self.rutas),
			"nivel_ayuda": self._niveles[max(0, self.nivel.GetSelection())],
			"tipo_recorrido": self._tipos[max(0, self.tipo.GetSelection())],
			"ayudas_movilidad": pres.separar_ayudas(self.ayudas.GetValue()),
			"observaciones": self.observaciones.GetValue().strip(),
		}
		return None

	def aplicar(self) -> Problema | None:
		try:
			self.evaluacion_id = cuaderno.anotar(self.base, self.alumno.id, **self._datos)
		except ErrorDatos as error:
			return str(error), self.fecha
		except ErrorBase as error:
			log.exception("No se ha podido guardar una evaluación real")
			return _("No se ha podido guardar la evaluación: {error}").format(error=error), self.fecha
		return None


class VentanaCuaderno(VentanaSeguimiento):
	"""Evaluaciones reales de un alumno y su comparación con las sesiones del simulador."""

	CLAVE = "cuaderno"

	def __init__(self, contexto: Any, servicio: Any, alumno_id: int | None = None) -> None:
		super().__init__(contexto, servicio, _("Cuaderno de evaluación real"), (900, 600))
		self.base = servicio.base
		self._alumnos: list[Alumno] = []
		self.evaluaciones: list[cuaderno.EvaluacionReal] = []
		letras = self.letras
		self.alumno = crear_desplegable(
			self.panel,
			letras.poner(_("Alumno:")),
			sizer=self.sizer,
			ayuda=_("El alumno cuyas pruebas en el lugar real se muestran."),
		)
		self.lista = crear_lista(
			self.panel,
			letras.poner(_("Evaluaciones en el lugar real:")),
			pres.columnas_evaluaciones(),
			getattr(contexto, "configuracion", None),
			sizer=self.sizer,
			ayuda=_("Una prueba por fila, de la más antigua a la más reciente. Intro la abre para leerla entera; Suprimir pide borrarla."),
		)
		fila = self.fila_botones()
		crear_boton(self.panel, letras.poner(_("Nueva evaluación...")), self.nueva, _("Anota una prueba hecha en el lugar físico."), fila)
		crear_boton(self.panel, letras.poner(_("Ver entera...")), self.ver, _("Enseña la evaluación elegida completa, en texto."), fila)
		crear_boton(
			self.panel,
			letras.poner(_("Comparar con el simulador...")),
			self.comparar,
			_("Pone las evaluaciones reales junto a las sesiones del simulador del mismo entorno, sin interpretarlas."),
			fila,
		)
		crear_boton(self.panel, letras.poner(_("Borrar la evaluación...")), self.borrar, _("Borra la evaluación elegida."), fila)
		crear_boton(self.panel, letras.poner(_("Cerrar")), self.Close, _("Cierra esta ventana."), fila)
		self.alumno.Bind(wx.EVT_CHOICE, lambda _evento: self.recargar())
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.ver())
		self.lista.Bind(wx.EVT_KEY_DOWN, self._tecla)
		self.cargar_alumnos(alumno_id)
		self.terminar(self.alumno)

	def _tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_DELETE and evento.GetModifiers() == wx.MOD_NONE:  # atajo: Supr
			self.borrar()
			return
		evento.Skip()

	def cargar_alumnos(self, alumno_id: int | None = None) -> None:
		"""Llena el desplegable de alumnos y deja elegido el indicado."""
		self._alumnos = Fichas(self.base).buscar()
		poner_opciones(self.alumno, [alumno.alias for alumno in self._alumnos])
		if alumno_id is not None:
			for indice, alumno in enumerate(self._alumnos):
				if alumno.id == alumno_id:
					self.alumno.SetSelection(indice)
		self.recargar()

	def alumno_elegido(self) -> Alumno | None:
		"""El alumno del desplegable."""
		indice = self.alumno.GetSelection()
		return self._alumnos[indice] if 0 <= indice < len(self._alumnos) else None

	def recargar(self, fila: int | None = None) -> None:
		"""Vuelve a leer las evaluaciones del alumno elegido."""
		alumno = self.alumno_elegido()
		self.evaluaciones = cuaderno.listar(self.base, alumno.id) if alumno is not None else []
		self.lista.reemplazar_filas([pres.fila_evaluacion(evaluacion) for evaluacion in self.evaluaciones])
		if fila is not None:
			self.lista.enfocar_fila(fila, anunciar=False)

	def elegida(self) -> cuaderno.EvaluacionReal | None:
		"""La evaluación de la fila enfocada."""
		fila = self.lista.fila_actual()
		return self.evaluaciones[fila] if 0 <= fila < len(self.evaluaciones) else None

	def _exigir_alumno(self) -> Alumno | None:
		alumno = self.alumno_elegido()
		if alumno is None:
			mostrar_mensaje(self, _("Todavía no hay alumnos. Créelos en la ventana de alumnos."), _("Cuaderno de evaluación real"))
		return alumno

	def nueva(self) -> None:
		"""Anota una evaluación nueva del alumno elegido."""
		alumno = self._exigir_alumno()
		if alumno is None:
			return
		dialogo = DialogoEvaluacion(self, self.base, alumno, self.contexto)
		try:
			mostrar_modal(dialogo)
			guardada = dialogo.aceptado
		finally:
			dialogo.Destroy()
		if guardada:
			self.recargar(len(cuaderno.listar(self.base, alumno.id)) - 1)
			anunciar(self.contexto, _("Evaluación de {alias} guardada.").format(alias=alumno.alias))
		self.lista.SetFocus()

	def ver(self) -> None:
		"""Enseña la evaluación elegida completa."""
		evaluacion, alumno = self.elegida(), self.alumno_elegido()
		if evaluacion is None or alumno is None:
			anunciar(self.contexto, _("No hay ninguna evaluación elegida."))
			return
		mostrar_texto(self, _("Evaluación en el lugar real"), _("&Evaluación:"), pres.texto_evaluacion(evaluacion, alumno.alias))
		self.lista.SetFocus()

	def comparar(self) -> None:
		"""Pone las evaluaciones reales del alumno junto a sus sesiones del simulador."""
		alumno = self._exigir_alumno()
		if alumno is None:
			return
		informe = informes.informe_real_frente_virtual(
			self.evaluaciones, sesiones.listar(self.base, alumno.id, incluir_parciales=False), alias=alumno.alias
		)
		mostrar_texto(self, informe.titulo, _("&Comparación:"), informes.a_texto(informe))
		self.lista.SetFocus()

	def borrar(self) -> None:
		"""Borra la evaluación elegida, tras confirmar."""
		evaluacion = self.elegida()
		if evaluacion is None:
			anunciar(self.contexto, _("No hay ninguna evaluación elegida."))
			return
		fila = pres.fila_evaluacion(evaluacion)
		eleccion = elegir_opcion(
			self,
			_("Va a borrar la evaluación del {fecha} en {lugar}. No se puede deshacer.").format(
				fecha=fila[0], lugar=fila[1] or fila[2] or _("un lugar sin indicar")
			),
			_("Borrar la evaluación"),
			[_("&Borrar la evaluación")],
		)
		if eleccion != 0:
			self.lista.SetFocus()
			return
		posicion = self.lista.fila_actual()
		cuaderno.borrar(self.base, evaluacion.id)
		self.recargar(min(posicion, len(self.evaluaciones) - 2) if len(self.evaluaciones) > 1 else None)
		anunciar(self.contexto, _("Evaluación borrada."))
		self.lista.SetFocus()
