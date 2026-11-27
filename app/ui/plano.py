"""Plano gráfico de la planta actual, dibujado a escala.

Es la vista para el profesional que ve o tiene resto visual: espacios con su
nombre, paredes, puertas con su arco, objetos con su huella real, fuentes,
referencias, conectores, calles y la actividad elegida. Se maneja con el
ratón (seleccionar, arrastrar, dibujar) y, con el foco dentro, con las flechas.

Un lienzo dibujado a mano NO es accesible para un lector de pantalla: no
tiene hijos, ni nombres, ni estados. Por eso este panel es un COMPLEMENTO y
nunca la única vía: todo lo que se hace aquí se hace también desde el árbol,
la lista y los menús (ver «Equivalencias» en ``docs/estudio.md``). Lo que sí
hace por quien no ve: anuncia por voz cada movimiento con las flechas y deja
el resultado en la barra de estado.

Reglas visuales que cumple:

- nada depende solo del color: cada tipo de espacio lleva su trama y su
  rótulo, cada clase de punto su letra y su forma, y la selección se marca
  con trazo grueso y asas;
- con un tema de alto contraste (o la preferencia ``general.alto_contraste``)
  solo se usan los colores del sistema;
- las medidas en píxeles pasan por ``FromDIP``; el dibujo usa doble búfer.

La geometría (coordenadas, selección por punto, arrastre) está en
``app/ui/modelo_plano.py``, sin wx, donde se prueba sin ventana.
"""

from __future__ import annotations

import io
import logging
import math
from collections.abc import Callable
from typing import Any

import wx

from app.core.i18n import _
from app.dominio import edicion
from app.dominio import geometria as geo
from app.dominio.diferencias import Afectados
from app.ui import modelo_plano as mp
from app.ui.accesibilidad.visual import alto_contraste_activo, color_sistema
from app.ui.contexto import ContextoEstudio
from app.ui.esquemas import texto_numero

log = logging.getLogger(__name__)

HERRAMIENTAS = ("seleccion", "habitacion", "pared", "objeto")
FACTOR_ZOOM = 1.25
#: Píxeles (antes de FromDIP) que hay que mover el ratón para que un clic pase a ser un arrastre.
UMBRAL_ARRASTRE = 4
#: Lado mínimo, en metros, de una habitación dibujada con el ratón (menos es un clic que se fue).
LADO_MINIMO_HABITACION = 0.3

# Con más figuras que estas a la vista, el plano se dibuja simplificado (sin letras ni símbolos menudos).
LIMITE_DETALLE = 1500

# Trama de cada tipo de espacio: lo que lo distingue aunque no se perciba el color.
_TRAMAS: dict[str, int] = {
	"calzada": wx.BRUSHSTYLE_CROSS_HATCH,
	"paso_peatones": wx.BRUSHSTYLE_VERTICAL_HATCH,
	"acera": wx.BRUSHSTYLE_HORIZONTAL_HATCH,
	"edificio": wx.BRUSHSTYLE_BDIAGONAL_HATCH,
	"parque": wx.BRUSHSTYLE_CROSSDIAG_HATCH,
	"plaza": wx.BRUSHSTYLE_FDIAGONAL_HATCH,
	"sendero": wx.BRUSHSTYLE_FDIAGONAL_HATCH,
}
# Color de relleno por tipo (solo fuera del alto contraste). Tonos claros: el texto negro se lee encima.
_COLORES_ESPACIO: dict[str, str] = {
	"habitacion": "#FBF3DC",
	"pasillo": "#EDEDED",
	"vestibulo": "#E6F0E0",
	"escalera": "#E3E3F4",
	"cabina": "#DCDCEB",
	"exterior": "#F2F2EA",
	"acera": "#8C8C8C",
	"calzada": "#6E6E6E",
	"paso_peatones": "#3C3C3C",
	"plaza": "#B7A27A",
	"parque": "#5E9A56",
	"sendero": "#A0875A",
	"edificio": "#7A6A5A",
}


class PanelPlano(wx.Panel):
	"""El plano gráfico de ``contexto.planta_actual()``."""

	def __init__(self, padre: wx.Window, contexto: ContextoEstudio) -> None:
		super().__init__(padre, style=wx.BORDER_THEME, name=_("Plano gráfico"))
		self.contexto = contexto
		# Devoluciones de llamada que fija la ventana principal.
		self.al_editar: Callable[[str], None] | None = None
		self.al_menu: Callable[[], wx.Menu | None] | None = None
		self.al_dibujar_habitacion: Callable[[float, float, float, float], None] | None = None
		self.al_dibujar_pared: Callable[[tuple[float, float], tuple[float, float]], None] | None = None
		self.al_colocar_objeto: Callable[[float, float], None] | None = None

		self.herramienta = "seleccion"
		self.vista = mp.VistaPlano()
		self.figuras: list[mp.Figura] = []
		self.cuadricula_visible = bool(self._preferencia("editor.cuadricula", True))
		self.ajuste = bool(self._preferencia("editor.cuadricula", True))
		self._planta_vista = ""
		# ``contexto.version`` de lo que enseñan las figuras: si es la anterior, basta con el parche para ponerse al día.
		self._version_vista = -1
		self._encajado = False
		# Gesto en curso: None o {"tipo": mover|desplazar|rectangulo, "inicio": (px, py), "actual": (px, py), "id": str, "activo": bool}
		self._gesto: dict[str, Any] | None = None
		self._primer_punto_pared: tuple[float, float] | None = None
		self._raton: tuple[int, int] = (0, 0)
		self._espacio_pulsado = False
		self._fondos: dict[str, wx.Bitmap | None] = {}
		# Parte fija ya pintada (ver ``_pintar_base``), la clave con la que se pintó y las cajas de las figuras.
		self._base: wx.Bitmap | None = None
		self._clave_base: tuple[Any, ...] | None = None
		self._cajas_figuras: list[tuple[float, float, float, float]] | None = None
		self._simplificado = False

		self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
		self.SetMinSize(self.FromDIP(wx.Size(240, 180)))
		self.SetLabel(_("Plano gráfico"))
		self._ayuda_base = _(
			"Plano gráfico de la planta, a escala. Con el ratón: clic selecciona, arrastrar mueve, la rueda amplía, "
			"el botón central desplaza y el doble clic abre las propiedades. Con el teclado: las flechas mueven el elemento "
			"seleccionado un paso de cuadrícula, y con Mayúsculas un paso fino. Todo lo que se hace en el plano se puede hacer "
			"también desde el árbol, la lista y los menús Editar e Insertar."
		)
		self.SetHelpText(self._ayuda_base)

		self.Bind(wx.EVT_PAINT, self._al_pintar)
		self.Bind(wx.EVT_SIZE, self._al_cambiar_tamano)
		self.Bind(wx.EVT_LEFT_DOWN, self._al_pulsar_izquierdo)
		self.Bind(wx.EVT_LEFT_UP, self._al_soltar_izquierdo)
		self.Bind(wx.EVT_LEFT_DCLICK, self._al_doble_clic)
		self.Bind(wx.EVT_MIDDLE_DOWN, self._al_pulsar_central)
		self.Bind(wx.EVT_MIDDLE_UP, self._al_soltar_central)
		self.Bind(wx.EVT_MOTION, self._al_mover_raton)
		self.Bind(wx.EVT_MOUSEWHEEL, self._al_rueda)
		self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._al_perder_captura)
		self.Bind(wx.EVT_CONTEXT_MENU, self._al_menu_contextual)
		# EVT_CHAR_HOOK y no EVT_KEY_DOWN: en un panel dentro de una ventana con
		# tabulación, Windows usa las flechas para cambiar de control antes de
		# que llegue EVT_KEY_DOWN. El gancho llega primero al control enfocado;
		# así se atienden las flechas sin wx.WANTS_CHARS (que se quedaría también
		# con el tabulador y encerraría el foco en el plano).
		self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
		self.Bind(wx.EVT_KEY_UP, self._al_soltar_tecla)
		self.Bind(wx.EVT_SET_FOCUS, self._al_cambiar_foco)
		self.Bind(wx.EVT_KILL_FOCUS, self._al_cambiar_foco)
		self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)
		# Para reconocer la destrucción propia: en wxPython 4.3 GetEventObject() ya no es self.
		self._id_propio = self.GetId()

		self._bajas = [
			contexto.suscribir(evento, self._al_cambiar_contexto)
			for evento in ("entorno_abierto", "entorno_cerrado", "planta_cambiada", "actividades_cambiadas", "catalogo_cambiado")
		]
		self._bajas.append(contexto.suscribir("entorno_cambiado", self._al_cambiar_entorno))
		self._bajas.append(contexto.suscribir("seleccion_cambiada", self._al_cambiar_seleccion))
		self.refrescar()

	# ── Foco ─────────────────────────────────────────────────────────────────

	def AcceptsFocus(self) -> bool:  # noqa: N802 - API de wx
		"""El plano recibe el foco (F6, Alt+4, clic) para poder mover con las flechas."""
		return True

	def AcceptsFocusFromKeyboard(self) -> bool:  # noqa: N802 - API de wx
		return True

	def _al_cambiar_foco(self, evento: wx.FocusEvent) -> None:
		self._espacio_pulsado = False
		self.Refresh()
		evento.Skip()

	def _al_destruir(self, evento: wx.WindowDestroyEvent) -> None:
		"""Se da de baja del contexto para que sus avisos no lleguen a un plano ya destruido."""
		# Se compara el id: el destroy de un hijo también sube hasta aquí y
		# GetEventObject() no es self en wxPython 4.3 (sip suelta antes la envoltura).
		if evento.GetId() == self._id_propio:
			for baja in self._bajas:
				baja()
			self._bajas = []
		evento.Skip()

	# ── Preferencias ─────────────────────────────────────────────────────────

	def _preferencia(self, clave: str, defecto: Any) -> Any:
		configuracion = self.contexto.configuracion
		if configuracion is None:
			return defecto
		return configuracion.obtener(clave, defecto)

	def paso_cuadricula(self) -> float:
		"""Separación de la cuadrícula, en metros."""
		return float(self._preferencia("editor.paso_cuadricula", 0.5))

	def paso_fino(self) -> float:
		"""Desplazamiento más fino con el teclado, en metros."""
		return float(self._preferencia("editor.paso_minimo_m", 0.05))

	def _paso_de_ajuste(self) -> float:
		return self.paso_cuadricula() if self.ajuste else 0.0

	def alto_contraste(self) -> bool:
		"""True si hay que pintar solo con los colores del sistema."""
		return bool(self._preferencia("general.alto_contraste", False)) or alto_contraste_activo()

	# ── API para la ventana principal ────────────────────────────────────────

	def refrescar(self, afectados: Afectados | None = None) -> None:
		"""Vuelve a leer el contexto y repinta. Encaja la vista si ha cambiado la planta.

		Con ``afectados`` (lo que cambió en la última edición, deshacer o
		rehacer) solo se rehacen las figuras de esos elementos; las demás se
		reutilizan. Sin ellos, se rehacen todas.
		"""
		if not self:
			return
		entorno = self.contexto.entorno
		planta = self.contexto.planta_actual() if entorno is not None else None
		self._version_vista = self.contexto.version
		if entorno is None or planta is None:
			self.figuras = []
			self._planta_vista = ""
			self._gesto = None
			self._primer_punto_pared = None
		else:
			previas = self.figuras if afectados is not None and planta.id == self._planta_vista else None
			self.figuras = mp.figuras_de_planta(
				entorno, planta, self.contexto.catalogo, self.contexto.actividad_actual, previas=previas, afectados=afectados
			)
			if planta.id != self._planta_vista:
				self._planta_vista = planta.id
				self._encajado = False
		# Figuras nuevas: la parte fija ya pintada no vale.
		self._base = None
		self._cajas_figuras = None
		# Ctrl+H en el plano lee también lo que dibuja de la actividad: nada queda solo en el lienzo.
		actividad = self.descripcion_actividad()
		self.SetHelpText(f"{self._ayuda_base}\n\n{actividad}" if actividad else self._ayuda_base)
		if not self._encajado:
			self._encajar_si_hay_tamano()
		self.Refresh()

	def premios_dibujados(self) -> list[mp.Figura]:
		"""Premios de la actividad elegida que se ven en la planta actual (para las pruebas y la ayuda)."""
		return [figura for figura in self.figuras if figura.clase == "premio"]

	def descripcion_actividad(self) -> str:
		"""En frases, lo que el plano dibuja de la actividad elegida (su inicio y sus premios); «» si no hay."""
		return mp.describir_actividad(self.contexto.entorno, self.contexto.actividad_actual)

	def acercar(self) -> None:
		"""Amplía el plano alrededor de su centro."""
		ancho, alto = self.GetClientSize()
		self.vista.zoom(FACTOR_ZOOM, ancho / 2, alto / 2)
		self.Refresh()

	def alejar(self) -> None:
		"""Reduce el plano alrededor de su centro."""
		ancho, alto = self.GetClientSize()
		self.vista.zoom(1 / FACTOR_ZOOM, ancho / 2, alto / 2)
		self.Refresh()

	def encajar(self) -> None:
		"""Ajusta la vista para que quepa la planta entera."""
		self._encajado = False
		self._encajar_si_hay_tamano(forzar=True)
		self.Refresh()

	def fijar_cuadricula(self, visible: bool) -> None:
		"""Muestra u oculta la cuadrícula."""
		self.cuadricula_visible = bool(visible)
		self.Refresh()

	def fijar_ajuste(self, ajustar: bool) -> None:
		"""Activa o desactiva el redondeo a la cuadrícula al mover y dibujar."""
		self.ajuste = bool(ajustar)

	def fijar_herramienta(self, nombre: str) -> None:
		"""Elige qué hace el ratón: ``seleccion``, ``habitacion``, ``pared`` u ``objeto``."""
		if nombre not in HERRAMIENTAS:
			raise ValueError(f"Herramienta desconocida: {nombre}")
		self._cancelar_gesto()
		self.herramienta = nombre
		self.SetCursor(wx.Cursor(wx.CURSOR_ARROW if nombre == "seleccion" else wx.CURSOR_CROSS))
		self.Refresh()

	# ── Reacción al contexto ─────────────────────────────────────────────────

	def _al_cambiar_contexto(self) -> None:
		if self:
			self.refrescar()

	def _al_cambiar_entorno(self) -> None:
		"""Tras editar, deshacer o rehacer: solo las figuras de lo que dice el parche, si el plano enseñaba el estado anterior."""
		if not self:
			return
		cambio = self.contexto.cambio
		if cambio is not None and self._version_vista == self.contexto.version - 1:
			self.refrescar(cambio.afectados())
		else:
			self.refrescar()

	def _al_cambiar_seleccion(self) -> None:
		if self:
			self.Refresh()

	def _encajar_si_hay_tamano(self, forzar: bool = False) -> None:
		ancho, alto = self.GetClientSize()
		if ancho < 20 or alto < 20:
			if forzar:
				self.vista.encajar(mp.caja_de_figuras(self.figuras), max(ancho, 400), max(alto, 300))
			return
		self.vista.encajar(mp.caja_de_figuras(self.figuras), ancho, alto)
		self._encajado = True

	def _al_cambiar_tamano(self, evento: wx.SizeEvent) -> None:
		ancho, alto = self.GetClientSize()
		if not self._encajado:
			self._encajar_si_hay_tamano()
		else:
			self.vista.redimensionar(ancho, alto)
		self.Refresh()
		evento.Skip()

	# ── Ratón ────────────────────────────────────────────────────────────────

	def _tolerancia_m(self) -> float:
		"""Margen del clic en metros: unos pocos píxeles, sea cual sea el zoom."""
		return self.FromDIP(6) / self.vista.escala

	def elemento_en_pixel(self, px: float, py: float) -> str:
		"""Id del elemento que hay bajo un píxel del plano («» si no hay)."""
		x, y = self.vista.a_mundo(px, py)
		return mp.elemento_en(self.figuras, x, y, self._tolerancia_m())

	def _capturar(self) -> None:
		if not self.HasCapture() and self.IsShownOnScreen():
			self.CaptureMouse()

	def _soltar(self) -> None:
		if self.HasCapture():
			self.ReleaseMouse()

	def _al_perder_captura(self, _evento: wx.MouseCaptureLostEvent) -> None:
		self._gesto = None
		self.Refresh()

	def _cancelar_gesto(self) -> bool:
		"""Abandona el arrastre o el dibujo a medias. True si había algo que cancelar."""
		habia = self._gesto is not None or self._primer_punto_pared is not None
		self._gesto = None
		self._primer_punto_pared = None
		self._soltar()
		if habia:
			self.Refresh()
		return habia

	def _al_pulsar_izquierdo(self, evento: wx.MouseEvent) -> None:
		self.SetFocus()
		punto = (evento.GetX(), evento.GetY())
		self._raton = punto
		if self._espacio_pulsado:
			self._gesto = {"tipo": "desplazar", "inicio": punto, "actual": punto, "id": "", "activo": True}
			self._capturar()
			return
		if self.contexto.entorno is None:
			return
		if self.herramienta == "seleccion":
			elegido = self.elemento_en_pixel(*punto)
			self.contexto.seleccionar(elegido)
			if elegido:
				self._gesto = {"tipo": "mover", "inicio": punto, "actual": punto, "id": elegido, "activo": False}
				self._capturar()
			self.Refresh()
		elif self.herramienta == "habitacion":
			self._gesto = {"tipo": "rectangulo", "inicio": punto, "actual": punto, "id": "", "activo": True}
			self._capturar()
		elif self.herramienta == "pared":
			x, y = self._punto_ajustado(*punto)
			if self._primer_punto_pared is None:
				self._primer_punto_pared = (x, y)
				self.contexto.anunciar(_("Primer extremo de la pared. Haga clic en el segundo."))
			else:
				primero, self._primer_punto_pared = self._primer_punto_pared, None
				if geo.distancia(primero, (x, y)) > 0.05 and self.al_dibujar_pared is not None:
					self.al_dibujar_pared(primero, (x, y))
			self.Refresh()
		elif self.herramienta == "objeto":
			x, y = self._punto_ajustado(*punto)
			if self.al_colocar_objeto is not None:
				self.al_colocar_objeto(x, y)

	def _punto_ajustado(self, px: float, py: float) -> tuple[float, float]:
		"""Punto del entorno bajo un píxel, redondeado a la cuadrícula si el ajuste está activo."""
		x, y = self.vista.a_mundo(px, py)
		paso = self._paso_de_ajuste()
		return mp.ajustar_a_cuadricula(x, paso), mp.ajustar_a_cuadricula(y, paso)

	def _al_mover_raton(self, evento: wx.MouseEvent) -> None:
		punto = (evento.GetX(), evento.GetY())
		anterior, self._raton = self._raton, punto
		gesto = self._gesto
		if gesto is None:
			if self._primer_punto_pared is not None:
				self.Refresh()
			evento.Skip()
			return
		if gesto["tipo"] == "desplazar":
			self.vista.desplazar(punto[0] - anterior[0], punto[1] - anterior[1])
		elif gesto["tipo"] == "mover" and not gesto["activo"]:
			umbral = self.FromDIP(UMBRAL_ARRASTRE)
			if abs(punto[0] - gesto["inicio"][0]) >= umbral or abs(punto[1] - gesto["inicio"][1]) >= umbral:
				gesto["activo"] = True
		gesto["actual"] = punto
		self.Refresh()

	def _al_soltar_izquierdo(self, evento: wx.MouseEvent) -> None:
		gesto, self._gesto = self._gesto, None
		self._soltar()
		if gesto is None:
			evento.Skip()
			return
		fin = (evento.GetX(), evento.GetY())
		if gesto["tipo"] == "mover" and gesto["activo"]:
			dx, dy = mp.desplazamiento_de_arrastre(self.vista, gesto["inicio"], fin, self._paso_de_ajuste())
			self.mover_elemento(gesto["id"], dx, dy)
		elif gesto["tipo"] == "rectangulo":
			x, y, ancho, fondo = mp.rectangulo_de_arrastre(self.vista, gesto["inicio"], fin, self._paso_de_ajuste())
			if ancho >= LADO_MINIMO_HABITACION and fondo >= LADO_MINIMO_HABITACION and self.al_dibujar_habitacion is not None:
				self.al_dibujar_habitacion(x, y, ancho, fondo)
		self.Refresh()

	def _al_pulsar_central(self, evento: wx.MouseEvent) -> None:
		punto = (evento.GetX(), evento.GetY())
		self._raton = punto
		self._gesto = {"tipo": "desplazar", "inicio": punto, "actual": punto, "id": "", "activo": True}
		self._capturar()

	def _al_soltar_central(self, _evento: wx.MouseEvent) -> None:
		if self._gesto is not None and self._gesto["tipo"] == "desplazar":
			self._gesto = None
			self._soltar()

	def _al_rueda(self, evento: wx.MouseEvent) -> None:
		factor = FACTOR_ZOOM if evento.GetWheelRotation() > 0 else 1 / FACTOR_ZOOM
		self.vista.zoom(factor, evento.GetX(), evento.GetY())
		self.Refresh()

	def _al_doble_clic(self, evento: wx.MouseEvent) -> None:
		self._cancelar_gesto()
		if self.herramienta != "seleccion" or self.contexto.entorno is None:
			return
		elegido = self.elemento_en_pixel(evento.GetX(), evento.GetY())
		if elegido:
			self.contexto.seleccionar(elegido)
			if self.al_editar is not None:
				self.al_editar(elegido)

	def _al_menu_contextual(self, evento: wx.ContextMenuEvent) -> None:
		"""Menú contextual con el ratón, la tecla Aplicaciones o Mayús+F10."""
		posicion = evento.GetPosition()
		if posicion == wx.DefaultPosition:
			# Desde el teclado: junto al elemento seleccionado, no donde esté el ratón.
			figura = mp.figura_de(self.figuras, self.contexto.seleccion)
			if figura is not None:
				px, py = self.vista.a_pantalla(*figura.centro())
				posicion = wx.Point(int(px), int(py))
			else:
				posicion = wx.Point(self.FromDIP(10), self.FromDIP(10))
		else:
			posicion = self.ScreenToClient(posicion)
			if self.contexto.entorno is not None:
				elegido = self.elemento_en_pixel(posicion.x, posicion.y)
				if elegido:
					self.contexto.seleccionar(elegido)
		menu = self.al_menu() if self.al_menu is not None else None
		if menu is None:
			return
		try:
			self.PopupMenu(menu, posicion)
		finally:
			menu.Destroy()

	# ── Mover ────────────────────────────────────────────────────────────────

	def mover_elemento(self, id_elemento: str, dx: float, dy: float) -> bool:
		"""Desplaza un elemento (dx al este, dy al norte) con ``edicion.mover`` y lo anuncia.

		Pasa por ``contexto.ejecutar``: entra en el historial y se puede
		deshacer. Devuelve False si no se movió (sin desplazamiento, elemento
		que ya no existe u operación que el dominio rechaza, que se anuncia).
		"""
		contexto = self.contexto
		if contexto.entorno is None or not id_elemento or (abs(dx) < 1e-9 and abs(dy) < 1e-9):
			return False
		encontrado = contexto.entorno.buscar(id_elemento)
		if encontrado is None:
			return False
		nombre = getattr(encontrado[1], "nombre", "") or id_elemento
		try:
			# El elemento se vuelve a resolver por su id dentro de la operación:
			# el entorno del contexto puede no ser ya el mismo objeto.
			contexto.ejecutar(_("mover {nombre}").format(nombre=nombre), lambda: edicion.mover(contexto.entorno, id_elemento, dx, dy))
		except ValueError as error:
			contexto.anunciar(str(error))
			return False
		contexto.anunciar(self.texto_posicion(id_elemento))
		return True

	def texto_posicion(self, id_elemento: str) -> str:
		"""«Mesa: 2,5 metros al este, 1 metro al norte»: dónde ha quedado el centro de un elemento."""
		entorno = self.contexto.entorno
		encontrado = entorno.buscar(id_elemento) if entorno is not None else None
		if encontrado is None:
			return ""
		elemento = encontrado[1]
		try:
			x, y = edicion.centro_de(elemento)
		except ValueError:
			return ""
		return _("{nombre}: {este}, {norte}").format(
			nombre=getattr(elemento, "nombre", "") or id_elemento,
			este=_metros_hacia(x, _("al este"), _("al oeste")),
			norte=_metros_hacia(y, _("al norte"), _("al sur")),
		)

	# ── Teclado ──────────────────────────────────────────────────────────────

	def _al_tecla(self, evento: wx.KeyEvent) -> None:
		"""Teclas del plano. Lo que no se atiende sigue su camino (Tab, F6, atajos de menú)."""
		if wx.Window.FindFocus() is not self and evento.GetEventObject() is not self:
			evento.Skip()
			return
		tecla = evento.GetKeyCode()
		modificadores = evento.GetModifiers()
		direcciones = {
			wx.WXK_UP: (0.0, 1.0),
			wx.WXK_DOWN: (0.0, -1.0),
			wx.WXK_LEFT: (-1.0, 0.0),
			wx.WXK_RIGHT: (1.0, 0.0),
			wx.WXK_NUMPAD_UP: (0.0, 1.0),
			wx.WXK_NUMPAD_DOWN: (0.0, -1.0),
			wx.WXK_NUMPAD_LEFT: (-1.0, 0.0),
			wx.WXK_NUMPAD_RIGHT: (1.0, 0.0),
		}
		if tecla in direcciones and modificadores in (wx.MOD_NONE, wx.MOD_SHIFT):
			# atajo: Arriba, Abajo, Izquierda, Derecha: mover el elemento seleccionado un paso de cuadrícula
			# atajo: Mayús+Arriba, Mayús+Abajo, Mayús+Izquierda, Mayús+Derecha: mover el elemento seleccionado un paso fino
			paso = self.paso_fino() if modificadores == wx.MOD_SHIFT else self.paso_cuadricula()
			if (
				not self.contexto.seleccion
				or self.contexto.entorno is None
				or self.contexto.entorno.buscar(self.contexto.seleccion) is None
			):
				self.contexto.anunciar(_("No hay ningún elemento seleccionado que mover."))
				return
			dx, dy = direcciones[tecla]
			self.mover_elemento(self.contexto.seleccion, dx * paso, dy * paso)
			return
		if tecla == wx.WXK_ESCAPE and modificadores == wx.MOD_NONE:
			# atajo: Escape: cancelar el arrastre o el dibujo en curso y volver a la herramienta de selección
			cancelado = self._cancelar_gesto()
			if self.herramienta != "seleccion":
				self.fijar_herramienta("seleccion")
				cancelado = True
			if cancelado:
				self.contexto.anunciar(_("Cancelado."))
				return
			evento.Skip()
			return
		if tecla == wx.WXK_SPACE and modificadores == wx.MOD_NONE:
			# atajo: Espacio: mientras está pulsado, arrastrar con el ratón desplaza el plano
			self._espacio_pulsado = True
			return
		evento.Skip()

	def _al_soltar_tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_SPACE:
			self._espacio_pulsado = False
		evento.Skip()

	# ── Pintado ──────────────────────────────────────────────────────────────

	def _al_pintar(self, _evento: wx.PaintEvent) -> None:
		dc = wx.AutoBufferedPaintDC(self)
		ancho, alto = self.GetClientSize()
		try:
			self.pintar(dc, ancho, alto)
		except Exception:  # noqa: BLE001 - un fallo al pintar no puede repetirse sin fin ni tirar la ventana
			log.exception("Error al pintar el plano gráfico")

	def _colores(self) -> dict[str, wx.Colour]:
		"""Paleta del plano: la propia o, en alto contraste, solo colores del sistema."""
		texto, fondo, seleccion = color_sistema("texto"), color_sistema("fondo"), color_sistema("seleccion")
		if self.alto_contraste():
			return {
				"fondo": fondo,
				"texto": texto,
				"linea": texto,
				"tenue": color_sistema("desactivado"),
				"seleccion": seleccion,
				"acento": texto,
			}
		return {
			"fondo": wx.Colour(255, 255, 255),
			"texto": wx.Colour(0, 0, 0),
			"linea": wx.Colour(20, 20, 20),
			"tenue": wx.Colour(190, 190, 190),
			"seleccion": wx.Colour(0, 90, 200),
			"acento": wx.Colour(170, 30, 30),
		}

	def pintar(self, dc: wx.DC, ancho: int, alto: int) -> None:
		"""Dibuja el plano entero en ``dc`` (la pantalla, o un mapa de bits en las pruebas)."""
		colores = self._colores()
		contraste = self.alto_contraste()
		dc.SetBackground(wx.Brush(colores["fondo"]))
		dc.Clear()
		fuente = self.GetFont()
		porcentaje = int(self._preferencia("general.tamano_texto", 100))
		if porcentaje != 100:
			fuente = fuente.Scaled(porcentaje / 100.0)
		dc.SetFont(fuente)
		dc.SetTextForeground(colores["texto"])
		if self.contexto.entorno is None or self.contexto.planta_actual() is None:
			dc.DrawText(_("No hay ningún entorno abierto."), self.FromDIP(12), self.FromDIP(12))
			self._pintar_foco(dc, ancho, alto, colores)
			return
		clave = (
			id(self.figuras),
			len(self.figuras),
			self.vista.escala,
			tuple(self.vista.a_pantalla(0.0, 0.0)),
			ancho,
			alto,
			contraste,
			self.cuadricula_visible,
			porcentaje,
			self.paso_cuadricula(),
			tuple(colores["fondo"]),
		)
		if self._base is None or self._clave_base != clave or self._base.GetSize() != wx.Size(ancho, alto):
			self._base = self._pintar_base(fuente, colores, contraste, ancho, alto)
			self._clave_base = clave
		if self._base is not None:
			dc.DrawBitmap(self._base, 0, 0)
		else:
			self._pintar_capa_fija(dc, colores, contraste, ancho, alto)
		self._pintar_seleccion(dc, colores)
		self._pintar_gesto(dc, colores)
		self._pintar_regla(dc, ancho, alto, colores)
		self._pintar_foco(dc, ancho, alto, colores)

	def _pintar_base(self, fuente: wx.Font, colores: dict[str, wx.Colour], contraste: bool, ancho: int, alto: int) -> wx.Bitmap | None:
		"""Pinta la parte fija del plano (fondo, cuadrícula y figuras) en un mapa de bits que se reutiliza.

		Por qué: al arrastrar un elemento, al mover el ratón con una pared a
		medias o al cambiar la selección, el plano se repinta muchas veces por
		segundo y lo único que cambia es lo que va encima. Con un barrio de
		miles de espacios repintarlo todo cada vez bloqueaba la ventana. El mapa
		se rehace solo si cambia el entorno, la vista, el tamaño o los colores.
		"""
		if ancho <= 0 or alto <= 0:
			return None
		mapa = wx.Bitmap(ancho, alto)
		memoria = wx.MemoryDC(mapa)
		try:
			memoria.SetBackground(wx.Brush(colores["fondo"]))
			memoria.Clear()
			memoria.SetFont(fuente)
			memoria.SetTextForeground(colores["texto"])
			self._pintar_capa_fija(memoria, colores, contraste, ancho, alto)
		finally:
			memoria.SelectObject(wx.NullBitmap)
		return mapa

	def _pintar_capa_fija(self, dc: wx.DC, colores: dict[str, wx.Colour], contraste: bool, ancho: int, alto: int) -> None:
		"""Fondo, cuadrícula y las figuras que se ven (las de fuera de la ventana no se dibujan)."""
		self._pintar_fondos(dc)
		if self.cuadricula_visible:
			self._pintar_cuadricula(dc, ancho, alto, colores)
		margen = self.FromDIP(40)
		x0, y1 = self.vista.a_mundo(-margen, -margen)
		x1, y0 = self.vista.a_mundo(ancho + margen, alto + margen)
		if self._cajas_figuras is None or len(self._cajas_figuras) != len(self.figuras):
			self._cajas_figuras = [figura.caja() for figura in self.figuras]
		visibles = [
			figura
			for figura, caja in zip(self.figuras, self._cajas_figuras, strict=True)
			if caja[0] <= x1 and caja[2] >= x0 and caja[1] <= y1 and caja[3] >= y0
		]
		# Con muchas figuras a la vista (un barrio entero encajado en la ventana) se dibuja sin letras
		# ni símbolos menudos: no se distinguirían y costaría segundos. Al acercarse, vuelve el detalle.
		self._simplificado = len(visibles) > LIMITE_DETALLE
		for figura in visibles:
			self._pintar_figura(dc, figura, colores, contraste)

	def _px(self, punto: tuple[float, float]) -> wx.Point:
		x, y = self.vista.a_pantalla(*punto)
		# Se acota: con mucho zoom una coordenada lejana desbordaría los enteros de GDI.
		return wx.Point(int(max(-30000, min(30000, x))), int(max(-30000, min(30000, y))))

	def _pintar_fondos(self, dc: wx.DC) -> None:
		"""Imagen de fondo calibrada (plano escaneado) debajo de todo. Si falta o falla, se sigue sin ella."""
		entorno = self.contexto.entorno
		if entorno is None or not isinstance(entorno.procedencia, dict) or not entorno.procedencia.get("fondos"):
			return
		from app.importar import imagen as fondo_imagen
		from app.importar.comun import ErrorImportacion

		for fondo in fondo_imagen.fondos_de(entorno, self._planta_vista):
			if fondo.get("visible") is False:
				continue
			mapa = self._mapa_de_fondo(str(fondo.get("imagen") or ""))
			if mapa is None:
				continue
			try:
				metros_por_pixel, giro, x0, y0 = fondo_imagen.transformacion(fondo)
			except ErrorImportacion:
				log.warning("El fondo de la planta %s no tiene una calibración válida.", self._planta_vista)
				continue
			contexto_grafico = wx.GraphicsContext.Create(dc) if isinstance(dc, (wx.MemoryDC, wx.WindowDC)) else None
			if contexto_grafico is None:
				continue
			px, py = self.vista.a_pantalla(x0, y0)
			factor = metros_por_pixel * self.vista.escala
			contexto_grafico.Translate(px, py)
			# El giro del fondo es antihorario en el plano; en pantalla la y va hacia abajo.
			contexto_grafico.Rotate(-math.radians(giro))
			contexto_grafico.Scale(factor, factor)
			contexto_grafico.DrawBitmap(mapa, 0, 0, mapa.GetWidth(), mapa.GetHeight())
			contexto_grafico.Flush()

	def _mapa_de_fondo(self, nombre: str) -> wx.Bitmap | None:
		"""Mapa de bits de un recurso de imagen del paquete, ya con su opacidad; None si no se puede leer."""
		if not nombre:
			return None
		if nombre in self._fondos:
			return self._fondos[nombre]
		mapa: wx.Bitmap | None = None
		datos = self.contexto.recursos.get(nombre) or self.contexto.recursos.get(nombre.rsplit("/", 1)[-1])
		if datos:
			registro_nulo = wx.LogNull()  # una imagen dañada no debe abrir un cuadro de error de wx
			try:
				imagen = wx.Image(io.BytesIO(datos))
				if imagen.IsOk():
					if not imagen.HasAlpha():
						imagen.InitAlpha()
					imagen = imagen.AdjustChannels(1.0, 1.0, 1.0, 0.5)
					mapa = wx.Bitmap(imagen)
			finally:
				del registro_nulo
		if mapa is None:
			log.warning("No se pudo cargar la imagen de fondo «%s».", nombre)
		self._fondos[nombre] = mapa
		return mapa

	def _pintar_cuadricula(self, dc: wx.DC, ancho: int, alto: int, colores: dict[str, wx.Colour]) -> None:
		paso = mp.paso_visible_de_cuadricula(self.paso_cuadricula(), self.vista.escala, self.FromDIP(8))
		if paso <= 0:
			return
		dc.SetPen(wx.Pen(colores["tenue"], 1, wx.PENSTYLE_DOT))
		x0, y1 = self.vista.a_mundo(0, 0)
		x1, y0 = self.vista.a_mundo(ancho, alto)
		x = math.floor(x0 / paso) * paso
		while x <= x1:
			px = int(self.vista.a_pantalla(x, 0)[0])
			dc.DrawLine(px, 0, px, alto)
			x += paso
		y = math.floor(y0 / paso) * paso
		while y <= y1:
			py = int(self.vista.a_pantalla(0, y)[1])
			dc.DrawLine(0, py, ancho, py)
			y += paso

	def _pintar_figura(self, dc: wx.DC, figura: mp.Figura, colores: dict[str, wx.Colour], contraste: bool) -> None:
		clase = figura.clase
		if clase == "espacio":
			self._pintar_espacio(dc, figura, colores, contraste)
		elif clase == "zona":
			dc.SetPen(wx.Pen(colores["linea"], 1, wx.PENSTYLE_SHORT_DASH))
			dc.SetBrush(wx.Brush(colores["linea"], wx.BRUSHSTYLE_CROSSDIAG_HATCH))
			dc.DrawPolygon([self._px(p) for p in figura.puntos])
		elif clase == "via":
			dc.SetPen(wx.Pen(colores["fondo"] if not contraste else colores["linea"], self.FromDIP(2), wx.PENSTYLE_LONG_DASH))
			dc.DrawLines([self._px(p) for p in figura.puntos])
			self._pintar_rotulo(dc, figura.rotulo, figura.centro(), colores, con_fondo=True)
		elif clase == "ruta":
			dc.SetPen(wx.Pen(colores["acento"], self.FromDIP(2), wx.PENSTYLE_DOT))
			dc.DrawLines([self._px(p) for p in figura.puntos])
		elif clase == "pared":
			grosor = max(self.FromDIP(3), int(float(figura.datos.get("grosor", 0.1)) * self.vista.escala))
			dc.SetPen(wx.Pen(colores["linea"], grosor))
			dc.DrawLine(self._px(figura.puntos[0]), self._px(figura.puntos[1]))
		elif clase == "abertura":
			self._pintar_abertura(dc, figura, colores)
		elif clase == "objeto":
			relleno = colores["fondo"] if contraste or not figura.color else wx.Colour(figura.color)
			if not relleno.IsOk():
				relleno = colores["fondo"]
			dc.SetPen(wx.Pen(colores["linea"], self.FromDIP(1)))
			dc.SetBrush(wx.Brush(relleno))
			dc.DrawPolygon([self._px(p) for p in figura.puntos])
			if not self._simplificado:
				self._pintar_letra(dc, figura.letra, figura.centro(), _texto_sobre(relleno))
		else:
			self._pintar_punto(dc, figura, colores)

	def _pintar_espacio(self, dc: wx.DC, figura: mp.Figura, colores: dict[str, wx.Colour], contraste: bool) -> None:
		puntos = [self._px(p) for p in figura.puntos]
		trama = _TRAMAS.get(figura.tipo)
		if self._simplificado:
			# Vista de conjunto: relleno y contorno de un solo trazo (las paredes gruesas no se distinguirían).
			dc.SetPen(wx.Pen(colores["linea"], 1))
			dc.SetBrush(wx.Brush(colores["fondo"] if contraste else wx.Colour(_COLORES_ESPACIO.get(figura.tipo, "#F4F4F4"))))
			dc.DrawPolygon(puntos)
			if trama is not None:
				dc.SetBrush(wx.Brush(colores["linea"] if contraste else wx.Colour(40, 40, 40), trama))
				dc.DrawPolygon(puntos)
			self._pintar_rotulo(
				dc, figura.rotulo, figura.centro(), colores, con_fondo=trama is not None or not contraste, caja=figura.caja()
			)
			return
		dc.SetPen(wx.TRANSPARENT_PEN)
		if contraste:
			dc.SetBrush(wx.Brush(colores["fondo"]))
			dc.DrawPolygon(puntos)
		else:
			dc.SetBrush(wx.Brush(wx.Colour(_COLORES_ESPACIO.get(figura.tipo, "#F4F4F4"))))
			dc.DrawPolygon(puntos)
		if trama is not None:
			dc.SetBrush(wx.Brush(colores["linea"] if contraste else wx.Colour(40, 40, 40), trama))
			dc.DrawPolygon(puntos)
		# Los lados: pared gruesa si el espacio es cerrado, trazo fino discontinuo si es solo una zona o el lado está abierto.
		abiertos = set(figura.datos.get("lados_abiertos") or [])
		cerrado = bool(figura.datos.get("cerrado"))
		for indice, punto in enumerate(puntos):
			siguiente = puntos[(indice + 1) % len(puntos)]
			if cerrado and indice not in abiertos:
				dc.SetPen(wx.Pen(colores["linea"], self.FromDIP(3)))
			else:
				dc.SetPen(wx.Pen(colores["linea"], 1, wx.PENSTYLE_SHORT_DASH))
			dc.DrawLine(punto, siguiente)
		self._pintar_rotulo(dc, figura.rotulo, figura.centro(), colores, con_fondo=trama is not None or not contraste, caja=figura.caja())

	def _pintar_abertura(self, dc: wx.DC, figura: mp.Figura, colores: dict[str, wx.Colour]) -> None:
		"""Cada tipo con su símbolo: puerta con arco, ventana con doble línea, hueco con topes, portal con trazo doble y grueso."""
		a, b = figura.puntos[0], figura.puntos[1]
		pa, pb = self._px(a), self._px(b)
		if self._simplificado:
			dc.SetPen(wx.Pen(colores["acento"], self.FromDIP(2)))
			dc.DrawLine(pa, pb)
			return
		# Primero se «abre» la pared: un trazo del color del fondo sobre el muro.
		dc.SetPen(wx.Pen(colores["fondo"], self.FromDIP(5)))
		dc.DrawLine(pa, pb)
		largo = geo.distancia(a, b) or 1.0
		normal = (-(b[1] - a[1]) / largo, (b[0] - a[0]) / largo)
		tope = 0.12

		def desplazado(punto: tuple[float, float], metros: float) -> wx.Point:
			return self._px((punto[0] + normal[0] * metros, punto[1] + normal[1] * metros))

		dc.SetPen(wx.Pen(colores["linea"], self.FromDIP(1)))
		for extremo in (a, b):
			dc.DrawLine(desplazado(extremo, -tope), desplazado(extremo, tope))
		if figura.tipo == "puerta":
			dc.SetPen(wx.Pen(colores["acento"], self.FromDIP(1)))
			arco = mp.arco_de_puerta(a, b)
			dc.DrawLines([self._px(p) for p in arco])
			dc.DrawLine(pa, self._px(arco[-1]))
			if figura.datos.get("estado") != "abierta":
				dc.SetPen(wx.Pen(colores["acento"], self.FromDIP(2)))
				dc.DrawLine(pa, pb)
		elif figura.tipo == "ventana":
			dc.SetPen(wx.Pen(colores["linea"], self.FromDIP(1)))
			dc.DrawLine(desplazado(a, 0.05), desplazado(b, 0.05))
			dc.DrawLine(desplazado(a, -0.05), desplazado(b, -0.05))
		elif figura.tipo == "portal":
			dc.SetPen(wx.Pen(colores["acento"], self.FromDIP(3), wx.PENSTYLE_SHORT_DASH))
			dc.DrawLine(pa, pb)
			self._pintar_letra(dc, "P", geo.punto_medio(a, b), colores["texto"], con_fondo=colores["fondo"])

	def _pintar_punto(self, dc: wx.DC, figura: mp.Figura, colores: dict[str, wx.Colour]) -> None:
		"""Fuentes, referencias, conectores, inicio y premios: cada clase con su forma y su letra."""
		radio = self.FromDIP(8)
		dc.SetPen(wx.Pen(colores["linea"], self.FromDIP(1)))
		dc.SetBrush(wx.Brush(colores["fondo"]))
		if self._simplificado and figura.clase not in ("inicio", "premio"):
			# Vista de conjunto: un punto pequeño por referencia o sonido, sin letra.
			dc.SetBrush(wx.Brush(colores["linea"]))
			for punto in figura.puntos:
				centro = self._px(punto)
				dc.DrawRectangle(centro.x - 1, centro.y - 1, 3, 3)
			return
		for punto in figura.puntos:
			centro = self._px(punto)
			x, y = centro.x, centro.y
			if figura.clase == "fuente":
				dc.DrawCircle(centro, radio)
				dc.SetBrush(wx.TRANSPARENT_BRUSH)
				dc.DrawCircle(centro, radio + self.FromDIP(4))
				dc.SetBrush(wx.Brush(colores["fondo"]))
			elif figura.clase == "referencia":
				dc.DrawPolygon([wx.Point(x, y - radio), wx.Point(x + radio, y), wx.Point(x, y + radio), wx.Point(x - radio, y)])
			elif figura.clase == "conector":
				dc.DrawRectangle(x - radio, y - radio, 2 * radio, 2 * radio)
			elif figura.clase == "inicio":
				rumbo = math.radians(float(figura.datos.get("rumbo", 0.0)))
				largo = radio * 1.6
				punta = wx.Point(int(x + largo * math.sin(rumbo)), int(y - largo * math.cos(rumbo)))
				izquierda = wx.Point(int(x + radio * math.sin(rumbo - 2.4)), int(y - radio * math.cos(rumbo - 2.4)))
				derecha = wx.Point(int(x + radio * math.sin(rumbo + 2.4)), int(y - radio * math.cos(rumbo + 2.4)))
				dc.SetPen(
					wx.Pen(colores["acento"], self.FromDIP(2), wx.PENSTYLE_SHORT_DASH if figura.tipo == "actividad" else wx.PENSTYLE_SOLID)
				)
				dc.DrawPolygon([punta, derecha, izquierda])
				dc.SetPen(wx.Pen(colores["linea"], self.FromDIP(1)))
			else:  # premio; escondido dentro de un objeto, con trazo discontinuo (no solo otro color)
				dc.SetPen(
					wx.Pen(colores["acento"], self.FromDIP(2), wx.PENSTYLE_SHORT_DASH if figura.tipo == "dentro" else wx.PENSTYLE_SOLID)
				)
				dc.DrawCircle(centro, radio)
				dc.DrawCircle(centro, radio // 2)
				dc.SetPen(wx.Pen(colores["linea"], self.FromDIP(1)))
			if figura.clase != "inicio":
				self._pintar_letra(dc, figura.letra, punto, colores["texto"])
			else:
				self._pintar_letra(
					dc, figura.letra, punto, colores["texto"], desplazamiento=(radio + self.FromDIP(6), 0), con_fondo=colores["fondo"]
				)

	def _pintar_letra(
		self,
		dc: wx.DC,
		letra: str,
		punto: tuple[float, float],
		color: wx.Colour,
		desplazamiento: tuple[int, int] = (0, 0),
		con_fondo: wx.Colour | None = None,
	) -> None:
		if not letra:
			return
		centro = self._px(punto)
		ancho, alto = dc.GetTextExtent(letra)
		x, y = centro.x - ancho // 2 + desplazamiento[0], centro.y - alto // 2 + desplazamiento[1]
		if con_fondo is not None:
			dc.SetPen(wx.TRANSPARENT_PEN)
			dc.SetBrush(wx.Brush(con_fondo))
			dc.DrawRectangle(x - 1, y, ancho + 2, alto)
		dc.SetTextForeground(color)
		dc.DrawText(letra, x, y)

	def _pintar_rotulo(
		self,
		dc: wx.DC,
		texto: str,
		punto: tuple[float, float],
		colores: dict[str, wx.Colour],
		con_fondo: bool = False,
		caja: tuple[float, float, float, float] | None = None,
	) -> None:
		"""Nombre de un espacio o de una calle, si cabe a este nivel de zoom (si no, estorbaría)."""
		if not texto:
			return
		ancho, alto = dc.GetTextExtent(texto)
		if caja is not None:
			ancho_caja = (caja[2] - caja[0]) * self.vista.escala
			alto_caja = (caja[3] - caja[1]) * self.vista.escala
			if ancho > ancho_caja * 1.1 or alto > alto_caja:
				return
		centro = self._px(punto)
		x, y = centro.x - ancho // 2, centro.y - alto // 2
		if con_fondo:
			dc.SetPen(wx.TRANSPARENT_PEN)
			dc.SetBrush(wx.Brush(colores["fondo"]))
			dc.DrawRectangle(x - 2, y, ancho + 4, alto)
		dc.SetTextForeground(colores["texto"])
		dc.DrawText(texto, x, y)

	def _puntos_de_seleccion(self, figura: mp.Figura, dx: float = 0.0, dy: float = 0.0) -> list[wx.Point]:
		return [self._px((x + dx, y + dy)) for x, y in figura.puntos]

	def _pintar_contorno(self, dc: wx.DC, figura: mp.Figura, dx: float = 0.0, dy: float = 0.0) -> None:
		puntos = self._puntos_de_seleccion(figura, dx, dy)
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		if figura.forma == mp.POLIGONO:
			dc.DrawPolygon(puntos)
		elif figura.forma == mp.LINEA:
			dc.DrawLines(puntos)
		else:
			radio = self.FromDIP(12)
			for punto in puntos:
				dc.DrawRectangle(punto.x - radio, punto.y - radio, 2 * radio, 2 * radio)

	def _pintar_seleccion(self, dc: wx.DC, colores: dict[str, wx.Colour]) -> None:
		"""Selección: trazo grueso Y asas cuadradas en los vértices (no solo un cambio de color)."""
		figura = mp.figura_de(self.figuras, self.contexto.seleccion)
		if figura is None:
			return
		dc.SetPen(wx.Pen(colores["seleccion"], self.FromDIP(3)))
		self._pintar_contorno(dc, figura)
		asa = self.FromDIP(4)
		dc.SetPen(wx.Pen(colores["fondo"], 1))
		dc.SetBrush(wx.Brush(colores["seleccion"]))
		puntos = self._puntos_de_seleccion(figura)
		if figura.forma == mp.PUNTO:
			radio = self.FromDIP(12)
			puntos = [wx.Point(p.x + sx * radio, p.y + sy * radio) for p in puntos for sx in (-1, 1) for sy in (-1, 1)]
		for punto in puntos:
			dc.DrawRectangle(punto.x - asa, punto.y - asa, 2 * asa, 2 * asa)

	def _pintar_gesto(self, dc: wx.DC, colores: dict[str, wx.Colour]) -> None:
		"""Lo que se está haciendo con el ratón: el fantasma del elemento arrastrado, el rectángulo o la pared a medias."""
		dc.SetPen(wx.Pen(colores["seleccion"], self.FromDIP(1), wx.PENSTYLE_SHORT_DASH))
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		gesto = self._gesto
		if gesto is not None and gesto["tipo"] == "mover" and gesto["activo"]:
			figura = mp.figura_de(self.figuras, gesto["id"])
			if figura is not None:
				dx, dy = mp.desplazamiento_de_arrastre(self.vista, gesto["inicio"], gesto["actual"], self._paso_de_ajuste())
				self._pintar_contorno(dc, figura, dx, dy)
		elif gesto is not None and gesto["tipo"] == "rectangulo":
			x, y, ancho, fondo = mp.rectangulo_de_arrastre(self.vista, gesto["inicio"], gesto["actual"], self._paso_de_ajuste())
			esquina, opuesta = self._px((x, y + fondo)), self._px((x + ancho, y))
			dc.DrawRectangle(esquina.x, esquina.y, opuesta.x - esquina.x, opuesta.y - esquina.y)
			dc.SetTextForeground(colores["texto"])
			dc.DrawText(
				_("{ancho} por {fondo} m").format(ancho=texto_numero(ancho), fondo=texto_numero(fondo)), esquina.x + 4, esquina.y + 4
			)
		if self._primer_punto_pared is not None:
			dc.DrawLine(self._px(self._primer_punto_pared), self._px(self._punto_ajustado(*self._raton)))

	def _pintar_regla(self, dc: wx.DC, ancho: int, alto: int, colores: dict[str, wx.Colour]) -> None:
		"""Regla de escala abajo a la izquierda y la marca del norte arriba a la derecha."""
		metros = mp.paso_de_regla(self.vista.escala, self.FromDIP(140))
		largo = int(metros * self.vista.escala)
		margen = self.FromDIP(12)
		x, y = margen, alto - margen
		texto = _("{n} m").format(n=texto_numero(metros))
		ancho_texto, alto_texto = dc.GetTextExtent(texto)
		dc.SetPen(wx.TRANSPARENT_PEN)
		dc.SetBrush(wx.Brush(colores["fondo"]))
		dc.DrawRectangle(x - 4, y - alto_texto - self.FromDIP(10), max(largo, ancho_texto) + 8, alto_texto + self.FromDIP(14))
		dc.SetPen(wx.Pen(colores["linea"], self.FromDIP(2)))
		dc.DrawLine(x, y, x + largo, y)
		dc.DrawLine(x, y - self.FromDIP(5), x, y)
		dc.DrawLine(x + largo, y - self.FromDIP(5), x + largo, y)
		dc.SetTextForeground(colores["texto"])
		dc.DrawText(texto, x, y - alto_texto - self.FromDIP(6))
		norte = _("N")
		ancho_norte, alto_norte = dc.GetTextExtent(norte)
		cx = ancho - margen - ancho_norte
		dc.DrawText(norte, cx, margen + self.FromDIP(14))
		dc.DrawLine(cx + ancho_norte // 2, margen + self.FromDIP(12), cx + ancho_norte // 2, margen)
		dc.DrawLine(cx + ancho_norte // 2, margen, cx + ancho_norte // 2 - self.FromDIP(4), margen + self.FromDIP(6))
		dc.DrawLine(cx + ancho_norte // 2, margen, cx + ancho_norte // 2 + self.FromDIP(4), margen + self.FromDIP(6))
		del alto_norte

	def _pintar_foco(self, dc: wx.DC, ancho: int, alto: int, colores: dict[str, wx.Colour]) -> None:
		"""Rectángulo de foco: un control dibujado a mano tiene que enseñar que tiene el foco."""
		if not self.HasFocus():
			return
		dc.SetPen(wx.Pen(colores["seleccion"], self.FromDIP(2), wx.PENSTYLE_DOT))
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.DrawRectangle(1, 1, max(1, ancho - 2), max(1, alto - 2))


def _metros_hacia(valor: float, positivo: str, negativo: str) -> str:
	"""«2,5 metros al este», «1 metro al sur»."""
	cantidad = abs(valor)
	unidad = _("metro") if abs(cantidad - 1.0) < 0.005 else _("metros")
	return f"{texto_numero(cantidad)} {unidad} {positivo if valor >= 0 else negativo}"


def _texto_sobre(fondo: wx.Colour) -> wx.Colour:
	"""Negro o blanco, lo que más contraste dé sobre un color de relleno."""
	luminancia = 0.299 * fondo.Red() + 0.587 * fondo.Green() + 0.114 * fondo.Blue()
	return wx.Colour(0, 0, 0) if luminancia > 140 else wx.Colour(255, 255, 255)
