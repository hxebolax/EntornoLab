"""Ventana principal del Estudio: menús, zona de trabajo accesible y archivos.

Qué resuelve (y por qué):

- Barra de menús construida de la tabla ``app/ui/menus.py``: cada orden con su
  letra de acceso, su atajo y su texto de ayuda. Los menús de la otra mitad
  del Estudio (``app/ui/seguimiento``) se añaden con el mismo formato.
- Zona de trabajo con cuatro paneles que se recorren con F6: el ÁRBOL del
  entorno (``wx.TreeCtrl`` nativo), la LISTA de elementos del nodo elegido
  (``ListaAccesible``, que lee las columnas una a una), las PROPIEDADES del
  elemento elegido (formulario generado de su esquema) y el PLANO gráfico.
  Los cuatro comparten la selección a través del ``ContextoEstudio``.
- Todo lo que se puede hacer en el plano con el ratón se puede hacer desde
  el árbol, la lista y los menús: el plano complementa, no sustituye.
- Cada elemento elegido se describe en una frase, en un campo de solo
  lectura que se puede repasar (y que no se locuta sola: el lector ya
  anuncia el elemento al moverse por el árbol o la lista).
- Documento: asterisco en el título si hay cambios, pregunta al cerrar con
  botones que dicen la acción, recientes, copia de recuperación periódica y
  apertura de un ``.elab`` recibido por la línea de órdenes o de otra instancia.
- Lo del esqueleto que ya funcionaba: geometría guardada, cierre ordenado,
  F1 y Control+F1, bandeja opcional y Escape que NO cierra la ventana.
"""

from __future__ import annotations

import logging
import operator
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import wx

from app.core import paths, voz
from app.core.configuracion import Configuracion, ErrorConfiguracion
from app.core.i18n import _
from app.core.instancia_unica import ORDEN_ABRIR, ORDEN_MOSTRAR, InstanciaUnica, traer_al_frente
from app.core.tareas import GestorTareas, TareaCancelada
from app.core.version import NOMBRE_APLICACION
from app.dominio.catalogo import Catalogo
from app.dominio.diferencias import Afectados
from app.dominio.formato import ErrorFormato, cargar_paquete, recuperar_copia
from app.dominio.modelo import Entorno
from app.ui import archivos, dialogos_herramientas, dialogos_insertar, espera, menus, operaciones
from app.ui.accesibilidad.dialogos import elegir_opcion
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.accesibilidad.teclado import vincular_menu_contextual
from app.ui.bandeja import IconoBandeja
from app.ui.contexto import ContextoEstudio
from app.ui.dialogo_texto import mostrar_error, mostrar_mensaje
from app.ui.esquemas import ErrorCampo, con_letra, letra_de, letras_de
from app.ui.esquemas_elementos import ORDENES, esquema_de
from app.ui.formulario import Formulario
from app.ui.plano import PanelPlano

log = logging.getLogger(__name__)

# Cada cuánto mira la ventana si una segunda instancia le ha dejado órdenes.
INTERVALO_BUZON_MS = 500
# Tamaño mínimo aceptable al restaurar (evita ventanas de 0x0 por datos raros).
TAMANO_MINIMO = (400, 300)
# Tamaño de serie: caben el árbol, el plano y las propiedades.
TAMANO_DE_SERIE = (1100, 700)
# Hasta este número de nodos el árbol se crea entero y desplegado (como siempre). Por encima (un barrio
# importado), los hijos de cada espacio y de cada grupo se crean al desplegarlo: crear y borrar miles
# de nodos nativos de golpe dejaba la ventana sin responder.
LIMITE_ARBOL_COMPLETO = 1500
# Un paquete de más de esto (bytes) se lee en segundo plano con el diálogo de progreso.
TAMANO_PAQUETE_EN_SEGUNDO_PLANO = 4 * 1024 * 1024


def _cuenta_hasta(arbol: operaciones.Nodo, tope: int) -> int:
	"""Nodos del árbol, contando como mucho hasta ``tope`` (para saber si es pequeño sin recorrer un barrio entero)."""
	cuenta = 0
	for _nodo in arbol.recorrer():
		cuenta += 1
		if cuenta >= tope:
			break
	return cuenta


# Órdenes del menú contextual del árbol, la lista y el plano: (nombre de la orden, etiqueta).
MENU_CONTEXTUAL: list[tuple[str, str] | None] = [
	("editar", "&Propiedades..."),
	("renombrar", "Re&nombrar..."),
	("duplicar", "D&uplicar"),
	("mover", "&Mover..."),
	("girar", "&Girar..."),
	("medidas", "Cambiar m&edidas..."),
	("borrar", "&Borrar"),
	None,
	("insertar_objeto", "Insertar un &objeto del catálogo..."),
	("fijar_inicio", "Poner aquí el &inicio"),
	("recorrer_desde", "&Recorrer desde aquí"),
]


def _traducir_contextual() -> list[tuple[str, str] | None]:
	"""Las etiquetas del menú contextual, traducidas (aquí se marcan para el extractor)."""
	textos = {
		"editar": _("&Propiedades..."),
		"renombrar": _("Re&nombrar..."),
		"duplicar": _("D&uplicar"),
		"mover": _("&Mover..."),
		"girar": _("&Girar..."),
		"medidas": _("Cambiar m&edidas..."),
		"borrar": _("&Borrar"),
		"insertar_objeto": _("Insertar un &objeto del catálogo..."),
		"fijar_inicio": _("Poner aquí el &inicio"),
		"recorrer_desde": _("&Recorrer desde aquí"),
	}
	return [None if entrada is None else (entrada[0], textos[entrada[0]]) for entrada in MENU_CONTEXTUAL]


class VentanaPrincipal(wx.Frame):
	"""Ventana principal del Estudio."""

	def __init__(
		self,
		configuracion: Configuracion,
		instancia: InstanciaUnica | None = None,
		catalogo: Catalogo | None = None,
		tareas: GestorTareas | None = None,
		lanzador: Callable[[list[str]], Any] | None = None,
	) -> None:
		"""Crea la ventana sin mostrarla.

		:param catalogo: catálogo de complementos ya cargado; por defecto se
			leen los de ``data/plugins`` menos los desactivados en las preferencias.
		:param tareas: gestor de tareas en segundo plano; por defecto uno propio.
		:param lanzador: función que arranca el reproductor (las pruebas pasan un doble).
		"""
		super().__init__(None, title=NOMBRE_APLICACION)
		self._config = configuracion
		self._instancia = instancia
		self._bandeja: IconoBandeja | None = None
		self._saliendo = False
		self._forzar_salida = False
		self._rect_normal: wx.Rect | None = None
		self._tareas_propias = tareas is None
		self.tareas = tareas or GestorTareas(nombre="estudio")
		if catalogo is None:
			catalogo = self._cargar_catalogo()
		self.contexto = ContextoEstudio(self, configuracion, catalogo, self.tareas, lanzador)
		# Elementos de menú por nombre (para activarlos, marcarlos o probarlos).
		self.elementos_menu: dict[str, wx.MenuItem] = {}
		self._submenus_dinamicos: dict[str, wx.Menu] = {}
		self._funciones_dinamicas: dict[int, Callable[[], None]] = {}
		#: Último paquete de diagnóstico generado desde Ayuda (para las pruebas y por si se pide otra vez).
		self.ultimo_paquete_diagnostico: Path | None = None
		# Sincronía entre el árbol, la lista y el plano.
		self._sincronizando = False
		self._origen_seleccion = ""
		self._clave_nodo = operaciones.CLAVE_ENTORNO
		self._nodos: dict[str, wx.TreeItemId] = {}
		self._filas: operaciones.FilasPerezosas = operaciones.FilasPerezosas([], None)
		self._ids: list[str] = []
		# Árbol lógico vigente (se calcula una vez por cambio del entorno) y estado de los nodos nativos.
		self._arbol_logico: operaciones.Nodo | None = None
		# ``contexto.version`` que enseñan el árbol y la lista: si es la anterior, basta el parche para ponerse al día.
		self._version_arbol = -1
		self._arbol_completo = True
		self._materializados: set[str] = set()
		self._abiertos: set[str] = set()
		# Versión del entorno cuya descripción enseña (o está componiendo) la página «Descripción».
		self._version_descripcion = -1
		self._clave_propiedades = ""
		self._recorrido: Any = None
		self._integracion = self._cargar_seguimiento()

		self._crear_menus()
		self.CreateStatusBar()
		self._crear_zona_de_trabajo()
		self.SetStatusText(_("Listo"))
		self._aplicar_barra_estado(bool(self._config.obtener("ventana.barra_estado", True)))
		self._aplicar_icono()
		self._restaurar_geometria()

		self.Bind(wx.EVT_CLOSE, self._al_cerrar)
		self.Bind(wx.EVT_ICONIZE, self._al_minimizar)
		self.Bind(wx.EVT_SIZE, self._al_cambiar_geometria)
		self.Bind(wx.EVT_MOVE, self._al_cambiar_geometria)
		self.Bind(wx.EVT_MENU_OPEN, self._al_abrir_menu)

		self._temporizador_buzon = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self._al_revisar_buzon, self._temporizador_buzon)
		if self._instancia is not None:
			self._temporizador_buzon.Start(INTERVALO_BUZON_MS)
		self._temporizador_autoguardado = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self._al_autoguardar, self._temporizador_autoguardado)
		self._programar_autoguardado()

		for evento, funcion in (
			("entorno_abierto", self._al_abrir_entorno),
			("entorno_cerrado", self._al_abrir_entorno),
			("entorno_cambiado", self._al_cambiar_entorno),
			("seleccion_cambiada", self._al_cambiar_seleccion),
			("planta_cambiada", self._al_cambiar_planta),
			("documento_cambiado", self._actualizar_titulo_y_menus),
			("catalogo_cambiado", self._al_cambiar_catalogo),
			("actividades_cambiadas", self._actualizar_descripcion_si_vivo),
		):
			self.contexto.suscribir(evento, funcion)
		self._cancelar_config = self._config.suscribir(self._al_cambiar_preferencia, prefijo="editor.")
		self._al_abrir_entorno()

	# ── Servicios ────────────────────────────────────────────────────────────

	def _cargar_catalogo(self) -> Catalogo | None:
		"""Lee los complementos instalados; si falla, el Estudio arranca sin catálogo y lo dice el registro."""
		try:
			return Catalogo.cargar(desactivados=self._config.obtener("complementos.desactivados", []) or [])
		except Exception:  # noqa: BLE001 - un complemento roto no debe impedir abrir el Estudio
			log.exception("No se pudo cargar el catálogo de complementos")
			return None

	def _cargar_seguimiento(self) -> Any:
		"""Importa la otra mitad del Estudio de forma tolerante: si no está o falla, se trabaja sin ella."""
		try:
			from app.ui.seguimiento import integracion
		except ImportError:
			log.info(
				"El módulo app.ui.seguimiento.integracion no está disponible: el Estudio abre sin los menús de seguimiento.", exc_info=True
			)
			return None
		except Exception:  # noqa: BLE001 - un fallo de la otra mitad no debe impedir construir entornos
			log.exception("Falló la importación de app.ui.seguimiento.integracion; el Estudio abre sin los menús de seguimiento")
			return None
		return integracion

	def letras_de_menus(self) -> set[str]:
		"""Letras de acceso de los menús de la barra: ningún control de la ventana puede repetirlas."""
		barra = self.GetMenuBar()
		if barra is None:
			return set()
		# Las cifras 1 a 5 también están ocupadas: Alt+1 a Alt+5 llevan a los paneles (menú Ver).
		return letras_de(barra.GetMenuLabel(indice) for indice in range(barra.GetMenuCount())) | set("12345")

	# ── Menús ────────────────────────────────────────────────────────────────

	def _crear_menus(self) -> None:
		"""Crea la barra de menús a partir de ``menus.MENUS`` y de los menús de seguimiento."""
		barra = wx.MenuBar()
		tabla = list(menus.MENUS)
		ajenos = self._menus_de_seguimiento()
		if ajenos:
			posicion = next((i for i, (titulo, _entradas) in enumerate(tabla) if titulo == menus.MENU_ANTES_DE), len(tabla))
			tabla[posicion:posicion] = ajenos
		ocupadas: set[str] = set()
		for titulo, entradas in tabla:
			propio = (titulo, entradas) in menus.MENUS
			texto = _(titulo)
			if letra_de(texto) in ocupadas or not letra_de(texto):
				# Un menú ajeno que repite la letra de otro: se le busca una libre en vez de dejarlo inalcanzable.
				texto = con_letra(texto.replace("&", ""), ocupadas)
			ocupadas.add(letra_de(texto))
			barra.Append(self._crear_menu(entradas, propio), texto)
		self.SetMenuBar(barra)

	def _menus_de_seguimiento(self) -> list[menus.Menu]:
		"""Los menús que aporta ``app.ui.seguimiento.integracion``, si está y están bien formados."""
		if self._integracion is None:
			return []
		aportados = getattr(self._integracion, "MENUS_SEGUIMIENTO", None) or []
		validos: list[menus.Menu] = []
		for menu in aportados:
			if isinstance(menu, (tuple, list)) and len(menu) == 2 and isinstance(menu[0], str) and isinstance(menu[1], list):
				validos.append((menu[0], menu[1]))
			else:
				log.error("Menú de seguimiento mal formado (se ignora): %r", menu)
		return validos

	def _crear_menu(self, entradas: list[Any], propio: bool) -> wx.Menu:
		menu = wx.Menu()
		for entrada in entradas:
			if entrada is None:
				menu.AppendSeparator()
				continue
			if menus.es_submenu(entrada):
				etiqueta, contenido = entrada
				if isinstance(contenido, str):
					submenu = wx.Menu()
					self._submenus_dinamicos[contenido] = submenu
				else:
					submenu = self._crear_menu(contenido, propio)
				menu.AppendSubMenu(submenu, _(etiqueta))
				continue
			normal = menus.normalizar_entrada(entrada)
			if normal is None:
				log.error("Entrada de menú mal formada (se ignora): %r", entrada)
				continue
			nombre, etiqueta, ayuda, tipo = normal
			clase = {menus.CASILLA: wx.ITEM_CHECK, menus.OPCION: wx.ITEM_RADIO}.get(tipo, wx.ITEM_NORMAL)
			item = menu.Append(wx.ID_ANY, _(etiqueta).format(nombre=NOMBRE_APLICACION), _(ayuda) if ayuda else "", clase)
			self.Bind(wx.EVT_MENU, self._manejador(nombre, propio), item)
			self.elementos_menu[nombre] = item
		return menu

	def _manejador(self, nombre: str, propio: bool) -> Callable[[wx.CommandEvent], None]:
		"""La función que atiende una orden de menú.

		Propia: el método ``_al_<nombre>`` o, si no existe, la orden con
		formulario de ``ORDENES``. Ajena: la función ``<nombre>`` del módulo de
		integración, que recibe el contexto.
		"""
		if propio:
			metodo = getattr(self, f"_al_{nombre}", None)
			if metodo is not None:
				return metodo
			if nombre in ORDENES:
				return lambda _evento, n=nombre: self.orden(n)
			raise AttributeError(f"La orden de menú «{nombre}» no tiene manejador")
		return lambda _evento, n=nombre: self._orden_de_seguimiento(n)

	def _orden_de_seguimiento(self, nombre: str) -> None:
		"""Llama a una función de la otra mitad del Estudio sin dejar que un fallo suyo tire la ventana."""
		funcion = getattr(self._integracion, nombre, None)
		if not callable(funcion):
			log.error("La orden de seguimiento «%s» no existe en el módulo de integración", nombre)
			mostrar_error(self, _("Esta orden todavía no está disponible."), NOMBRE_APLICACION)
			return
		try:
			funcion(self.contexto)
		except Exception:  # noqa: BLE001 - se registra y se explica; la ventana sigue viva
			log.exception("Falló la orden de seguimiento «%s»", nombre)
			mostrar_error(self, _("No se pudo completar la orden. Los detalles están en la carpeta de registros."), NOMBRE_APLICACION)

	def orden(self, nombre: str, iniciales: dict[str, Any] | None = None) -> str | None:
		"""Hace una orden con formulario (``ORDENES``) y devuelve el id del elemento creado o cambiado."""
		return dialogos_insertar.ejecutar_orden(self.contexto, nombre, iniciales)

	def _al_abrir_menu(self, evento: wx.MenuEvent) -> None:
		"""Antes de enseñar un menú se ponen al día sus partes que dependen del estado."""
		evento.Skip()
		self._rellenar_dinamicos()
		self._actualizar_marcas()

	def _rellenar_dinamicos(self) -> None:
		"""Rellena «Recientes», «Abrir ejemplo» e «Ir a planta» con lo que haya ahora."""
		recientes = [
			(self._etiqueta_numerada(i, ruta.stem), str(ruta), lambda r=ruta: self._abrir_con_pregunta(r))
			for i, ruta in enumerate(archivos.recientes(self._config))
		]
		self._rellenar_submenu("recientes", recientes, _("(&No hay entornos recientes)"))
		ejemplos = [
			(self._etiqueta_numerada(i, nombre), str(ruta), lambda r=ruta: self._abrir_con_pregunta(r, como_ejemplo=True))
			for i, (ruta, nombre) in enumerate(archivos.ejemplos())
		]
		self._rellenar_submenu("ejemplos", ejemplos, _("(&No hay ejemplos instalados)"))
		plantas = []
		if self.contexto.entorno is not None:
			ordenadas = sorted(self.contexto.entorno.plantas, key=lambda p: p.nivel)
			plantas = [
				(
					self._etiqueta_numerada(i, operaciones.nombre_de(planta)),
					_("Enseña esta planta."),
					lambda p=planta.id: self._ir_a_planta(p),
				)
				for i, planta in enumerate(ordenadas)
			]
		self._rellenar_submenu("plantas", plantas, _("(&No hay plantas)"))

	@staticmethod
	def _etiqueta_numerada(indice: int, texto: str) -> str:
		"""«&1 Casa de Ana»: el número hace de letra de acceso y nunca se repite (hasta nueve)."""
		limpio = texto.replace("&", "&&")
		return f"&{indice + 1} {limpio}" if indice < 9 else limpio

	def _rellenar_submenu(self, clave: str, entradas: list[tuple[str, str, Callable[[], None]]], vacio: str) -> None:
		submenu = self._submenus_dinamicos.get(clave)
		if submenu is None:
			return
		for item in list(submenu.GetMenuItems()):
			self._funciones_dinamicas.pop(item.GetId(), None)
			submenu.Delete(item)
		if not entradas:
			submenu.Append(wx.ID_ANY, vacio).Enable(False)
			return
		for etiqueta, ayuda, funcion in entradas:
			item = submenu.Append(wx.ID_ANY, etiqueta, ayuda)
			self._funciones_dinamicas[item.GetId()] = funcion
			self.Bind(wx.EVT_MENU, self._al_elegir_dinamico, item)

	def _al_elegir_dinamico(self, evento: wx.CommandEvent) -> None:
		funcion = self._funciones_dinamicas.get(evento.GetId())
		if funcion is not None:
			funcion()

	def _actualizar_marcas(self) -> None:
		"""Pone al día las casillas y opciones de los menús."""
		marcas = {
			"cuadricula": self.plano.cuadricula_visible,
			"ajustar_cuadricula": self.plano.ajuste,
			"mostrar_plano": self.plano.IsShown(),
			"barra_estado": self.GetStatusBar().IsShown(),
			f"herramienta_{self.plano.herramienta}": True,
		}
		for nombre, valor in marcas.items():
			item = self.elementos_menu.get(nombre)
			if item is not None and item.IsCheckable():
				item.Check(bool(valor))

	def _actualizar_titulo_y_menus(self) -> None:
		"""Título con asterisco si hay cambios, y «Deshacer» y «Rehacer» con el nombre de la operación."""
		if not self or self._saliendo:
			return
		contexto = self.contexto
		if contexto.entorno is None:
			self.SetTitle(NOMBRE_APLICACION)
		else:
			marca = "*" if contexto.modificado else ""
			self.SetTitle(f"{marca}{contexto.nombre_documento()} - {NOMBRE_APLICACION}")
		historial = contexto.historial
		for nombre, texto, atajo, activo in (
			("deshacer", historial.texto_deshacer(), "Ctrl+Z", historial.puede_deshacer),
			("rehacer", historial.texto_rehacer(), "Ctrl+Y", historial.puede_rehacer),
		):
			item = self.elementos_menu[nombre]
			# La letra de acceso se conserva (D y R): el texto que sigue es el nombre de la operación.
			item.SetItemLabel(f"&{texto.replace('&', '&&')}\t{atajo}")
			item.Enable(bool(activo))

	# ── Zona de trabajo ──────────────────────────────────────────────────────

	def _etiqueta(self, texto: str, usadas: set[str]) -> str:
		"""Etiqueta con su letra de acceso preferida si está libre; si no, con otra libre."""
		preferida = letra_de(texto)
		if preferida and preferida not in usadas:
			usadas.add(preferida)
			return texto
		return con_letra(texto.replace("&", ""), usadas)

	def _crear_zona_de_trabajo(self) -> None:
		"""Cuaderno con la página «Entorno» (árbol, lista, plano y propiedades), «Descripción» y «Actividades».

		Cada ``StaticText`` se crea JUSTO ANTES de su control y con el mismo
		padre: de ahí toma el lector el nombre del árbol, de la lista y de los
		campos. El orden de creación es también el orden del tabulador.
		"""
		self.panel = wx.Panel(self)
		self.cuaderno = wx.Notebook(self.panel)
		pagina = wx.Panel(self.cuaderno, name=_("Entorno"))
		self.pagina_entorno = pagina
		usadas = self.letras_de_menus()

		etiqueta_arbol = wx.StaticText(pagina, label=self._etiqueta(_("Á&rbol del entorno:"), usadas))
		self.arbol = wx.TreeCtrl(
			pagina, style=wx.TR_DEFAULT_STYLE | wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_SINGLE, name=_("Árbol del entorno")
		)
		self.arbol.SetHelpText(
			_(
				"Árbol del entorno: plantas, espacios y lo que hay en cada uno. Las flechas lo recorren; Intro abre las propiedades; "
				"Suprimir borra; la tecla Aplicaciones abre el menú contextual; F6 pasa a la lista."
			)
		)
		etiqueta_lista = wx.StaticText(pagina, label=self._etiqueta(_("&Lista de elementos:"), usadas))
		self.lista = ListaAccesible(
			pagina,
			_("Lista de elementos"),
			[
				(_("Nombre"), self.FromDIP(150)),
				(_("Tipo"), self.FromDIP(110)),
				(_("Medidas"), self.FromDIP(120)),
				(_("Posición"), self.FromDIP(110)),
			],
			# Virtual: una planta de un barrio importado tiene miles de elementos y solo se componen las filas que se ven.
			virtual=True,
		)
		self.lista.SetHelpText(
			_(
				"Elementos del nodo elegido en el árbol. Arriba y abajo cambian de elemento; izquierda y derecha leen el tipo, las medidas y la posición; "
				"Intro abre las propiedades; Suprimir borra."
			)
		)
		etiqueta_frase = wx.StaticText(pagina, label=self._etiqueta(_("Elemento ele&gido:"), usadas))
		self.frase = wx.TextCtrl(
			pagina, style=wx.TE_READONLY | wx.TE_MULTILINE, size=self.FromDIP(wx.Size(-1, 64)), name=_("Elemento elegido")
		)
		self.frase.SetHelpText(_("Una frase que describe el elemento elegido: qué es, cuánto mide y dónde está."))

		self.plano = PanelPlano(pagina, self.contexto)
		self.plano.al_editar = lambda id_elemento: dialogos_insertar.editar_propiedades(self.contexto, id_elemento)
		self.plano.al_menu = self._crear_menu_contextual
		self.plano.al_dibujar_habitacion = self._al_dibujar_habitacion
		self.plano.al_dibujar_pared = self._al_dibujar_pared
		self.plano.al_colocar_objeto = self._al_colocar_objeto_en_plano

		self._texto_aplicar = self._etiqueta(_("Aplicar &cambios"), usadas)
		self._texto_descartar = self._etiqueta(_("Descartar ca&mbios"), usadas)
		self.titulo_propiedades = wx.StaticText(pagina, label=_("Propiedades"))
		self.propiedades = Formulario(pagina, letras_usadas=usadas, nombre=_("Propiedades"))
		# Recorrer el árbol pasa de un tipo de elemento a otro: se guardan los formularios de los últimos
		# dieciséis tipos (los tipos de espacio de un barrio, puertas, objetos, referencias…) para no crear una docena de controles nativos en cada flecha (más de 100 ms cada vez).
		self.propiedades.guardar_cuerpos = 16
		self.boton_aplicar = wx.Button(pagina, label=self._texto_aplicar)
		self.boton_aplicar.SetHelpText(_("Aplica al elemento los cambios escritos en el formulario de propiedades. Se pueden deshacer."))
		self.boton_descartar = wx.Button(pagina, label=self._texto_descartar)
		self.boton_descartar.SetHelpText(_("Vuelve a poner en el formulario los valores que tiene el elemento."))

		izquierda = wx.BoxSizer(wx.VERTICAL)
		izquierda.Add(etiqueta_arbol, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
		izquierda.Add(self.arbol, 3, wx.EXPAND | wx.ALL, 6)
		izquierda.Add(etiqueta_lista, 0, wx.LEFT | wx.RIGHT, 6)
		izquierda.Add(self.lista, 2, wx.EXPAND | wx.ALL, 6)
		izquierda.Add(etiqueta_frase, 0, wx.LEFT | wx.RIGHT, 6)
		izquierda.Add(self.frase, 0, wx.EXPAND | wx.ALL, 6)
		derecha = wx.BoxSizer(wx.VERTICAL)
		derecha.Add(self.titulo_propiedades, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
		derecha.Add(self.propiedades, 1, wx.EXPAND | wx.ALL, 6)
		botones = wx.BoxSizer(wx.HORIZONTAL)
		botones.Add(self.boton_aplicar, 0, wx.ALL, 6)
		botones.Add(self.boton_descartar, 0, wx.ALL, 6)
		derecha.Add(botones, 0)
		self._sizer_entorno = wx.BoxSizer(wx.HORIZONTAL)
		self._sizer_entorno.Add(izquierda, 3, wx.EXPAND)
		self._sizer_entorno.Add(self.plano, 4, wx.EXPAND | wx.TOP | wx.BOTTOM, 6)
		self._sizer_entorno.Add(derecha, 3, wx.EXPAND)
		pagina.SetSizer(self._sizer_entorno)
		self.cuaderno.AddPage(pagina, _("Entorno"))

		pagina_texto = wx.Panel(self.cuaderno, name=_("Descripción"))
		etiqueta_texto = wx.StaticText(pagina_texto, label=self._etiqueta(_("&Descripción del entorno:"), self.letras_de_menus()))
		# TE_RICH2 permite textos de más de 64 KB en Windows y lo leen bien NVDA y JAWS.
		self.texto_descripcion = wx.TextCtrl(
			pagina_texto, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_RICH2, name=_("Descripción del entorno")
		)
		self.texto_descripcion.SetHelpText(
			_("El entorno entero descrito en texto, una frase por línea. Es lo mismo que enseña el plano gráfico.")
		)
		sizer_texto = wx.BoxSizer(wx.VERTICAL)
		sizer_texto.Add(etiqueta_texto, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
		sizer_texto.Add(self.texto_descripcion, 1, wx.EXPAND | wx.ALL, 6)
		pagina_texto.SetSizer(sizer_texto)
		self.cuaderno.AddPage(pagina_texto, _("Descripción"))
		self.panel_actividades = self._crear_panel_actividades()
		if self.panel_actividades is not None:
			self.cuaderno.AddPage(self.panel_actividades, _("Actividades"))

		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(self.cuaderno, 1, wx.EXPAND)
		self.panel.SetSizer(sizer)

		self.arbol.Bind(wx.EVT_TREE_SEL_CHANGED, self._al_elegir_en_arbol)
		self.arbol.Bind(wx.EVT_TREE_ITEM_EXPANDING, self._al_desplegar)
		self.arbol.Bind(wx.EVT_TREE_ITEM_COLLAPSED, self._al_plegar)
		self.arbol.Bind(wx.EVT_TREE_ITEM_ACTIVATED, lambda _evento: self._al_editar(None))
		self.arbol.Bind(wx.EVT_KEY_DOWN, self._al_tecla_de_panel)
		self.lista.Bind(wx.EVT_LIST_ITEM_FOCUSED, self._al_elegir_en_lista)
		self.lista.Bind(wx.EVT_LIST_ITEM_SELECTED, self._al_elegir_en_lista)
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self._al_editar(None))
		self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla_de_panel)
		vincular_menu_contextual(self.arbol, self._crear_menu_contextual)
		vincular_menu_contextual(self.lista, self._crear_menu_contextual)
		self.boton_aplicar.Bind(wx.EVT_BUTTON, lambda _evento: self.aplicar_propiedades())
		self.boton_descartar.Bind(wx.EVT_BUTTON, lambda _evento: self._mostrar_propiedades(forzar=True))
		self.cuaderno.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._al_cambiar_de_pagina)
		self.plano.Show(bool(self._config.obtener("editor.plano_visible", True)))

	def _crear_panel_actividades(self) -> wx.Window | None:
		"""La página «Actividades», que escribe la otra mitad del Estudio. None si no está o falla."""
		crear = getattr(self._integracion, "crear_panel_actividades", None)
		if not callable(crear):
			return None
		try:
			panel = crear(self.cuaderno, self.contexto)
		except Exception:  # noqa: BLE001 - sin panel de actividades se sigue pudiendo construir entornos
			log.exception("No se pudo crear el panel de actividades")
			return None
		return panel if isinstance(panel, wx.Window) else None

	def _aplicar_icono(self) -> None:
		"""Usa ``data/icons/app.ico`` si existe (barra de tareas y Alt+Tab)."""
		ruta = paths.ruta_iconos() / "app.ico"
		if ruta.is_file():
			icono = wx.Icon(str(ruta), wx.BITMAP_TYPE_ICO)
			if icono.IsOk():
				self.SetIcon(icono)

	# ── Árbol, lista y propiedades ───────────────────────────────────────────

	def _al_abrir_entorno(self) -> None:
		"""Hay otro documento (o ninguno): todo se rellena de nuevo."""
		if not self or self._saliendo:
			return
		self._clave_nodo = operaciones.CLAVE_ENTORNO
		self._clave_propiedades = ""
		self._reconstruir_arbol(expandir_todo=True)
		self._rellenar_lista()
		self._mostrar_propiedades(forzar=True)
		self._actualizar_descripcion()
		self._actualizar_titulo_y_menus()

	def _al_cambiar_entorno(self) -> None:
		"""El entorno ha cambiado: se pone al día lo que se ve conservando dónde está la persona.

		Si el árbol y la lista enseñaban el estado de justo antes, el parche
		del historial (``contexto.cambio``) dice qué elementos han cambiado y
		solo se tocan sus nodos y sus filas; si no (otro documento, un cambio
		que no se vio), se rehace todo.
		"""
		if not self or self._saliendo:
			return
		cambio = self.contexto.cambio
		afectados = cambio.afectados() if cambio is not None and self._version_arbol == self.contexto.version - 1 else None
		self._reconstruir_arbol(afectados=afectados)
		self._rellenar_lista(afectados=afectados)
		self._mostrar_propiedades()
		self._actualizar_descripcion()
		if self._recorrido is not None and self._recorrido.activo:
			self._recorrido.al_cambiar_entorno()

	def _al_cambiar_catalogo(self) -> None:
		"""Hay otros complementos: los nombres de los objetos pueden ser otros, así que se rehace todo."""
		if not self or self._saliendo:
			return
		self._reconstruir_arbol()
		self._rellenar_lista()
		self._mostrar_propiedades()
		self._actualizar_descripcion()

	def _al_cambiar_planta(self) -> None:
		planta = self.contexto.planta_actual()
		if planta is not None and not self._sincronizando:
			self.SetStatusText(_("Planta: {nombre}").format(nombre=operaciones.nombre_de(planta)))

	def _reconstruir_arbol(self, expandir_todo: bool = False, afectados: Afectados | None = None) -> None:
		"""Pone el árbol al día con el entorno conservando qué estaba desplegado y qué estaba elegido.

		Con ``afectados`` (lo que cambió desde el árbol que se enseña) el árbol
		lógico nuevo comparte con el anterior los nodos de lo que no ha
		cambiado, y la sincronización salta esos nodos por identidad: solo se
		reescriben los nodos nativos de los elementos afectados.

		Por qué no se borra y se rehace: con un barrio importado de miles de
		espacios, crear los nodos nativos cuesta unos 30 µs cada uno y borrarlos
		unos 60 µs, y antes se hacía en cada cambio. Ahora:

		- el árbol lógico (``operaciones.arbol_de``) se calcula UNA vez por
		  cambio del entorno y se guarda; la lista y las búsquedas lo reutilizan;
		- los nodos nativos se SINCRONIZAN con él: un nodo cuyo subárbol no ha
		  cambiado no se toca, uno que cambió se reescribe en el sitio y solo se
		  crean o borran los que sobran o faltan;
		- en un entorno grande los hijos de un espacio o de un grupo no se
		  crean hasta que se despliega (``_al_desplegar``): la planta enseña sus
		  espacios y cada espacio dice que tiene contenido.
		"""
		anterior = self._arbol_logico
		parcial = afectados is not None and anterior is not None and not expandir_todo
		if parcial:
			# Lo desplegado ya está al día (``_al_desplegar`` y ``_al_plegar``): preguntarlo a cada uno de los
			# miles de nodos nativos (unos 15 µs cada pregunta) era la cuarta parte de lo que tardaba editar.
			abiertos = set(self._abiertos)
		else:
			abiertos = {clave for clave, item in self._nodos.items() if item.IsOk() and self.arbol.IsExpanded(item)}
		self._sincronizando = True
		# Congelar y descongelar repinta el árbol entero (decenas de milisegundos con miles de nodos):
		# solo compensa al crearlo de cero; al sincronizar cambian pocos nodos.
		congelar = anterior is None or expandir_todo
		if congelar:
			self.arbol.Freeze()
		try:
			entorno = self.contexto.entorno
			if entorno is None:
				self.arbol.DeleteAllItems()
				self._nodos = {}
				self._materializados = set()
				self._arbol_logico = None
				self._version_arbol = self.contexto.version
				raiz = self.arbol.AddRoot(_("No hay ningún entorno abierto"))
				self.arbol.SetItemData(raiz, "")
				self.arbol.SelectItem(raiz)
				return
			arbol = operaciones.arbol_de(
				entorno, self.contexto.catalogo, anterior=anterior if parcial else None, afectados=afectados if parcial else None
			)
			self._arbol_logico = arbol
			self._version_arbol = self.contexto.version
			self._arbol_completo = _cuenta_hasta(arbol, LIMITE_ARBOL_COMPLETO + 1) <= LIMITE_ARBOL_COMPLETO
			if expandir_todo:
				# Al abrir: siempre se ven las plantas y, si el árbol es pequeño, también lo de cada espacio.
				abiertos = {nodo.clave for nodo in arbol.recorrer() if "/" not in nodo.clave and (self._arbol_completo or nodo is arbol)}
				abiertos.update(hijo.clave for hijo in arbol.hijos)
			abiertos.add(operaciones.CLAVE_ENTORNO)
			self._abiertos = abiertos
			# Otro documento: los nodos nativos se reutilizan, pero sin dar por buenos los del anterior.
			comparar = None if expandir_todo else anterior
			if expandir_todo:
				self._materializados = set()
			raiz = self.arbol.GetRootItem()
			if not raiz.IsOk() or anterior is None:
				self.arbol.DeleteAllItems()
				self._nodos = {}
				self._materializados = set()
				raiz = self.arbol.AddRoot(arbol.texto)
				anterior = None
			self._poner_nodo(raiz, arbol, comparar if anterior is not None else None)
			destino = self._nodos.get(self._clave_nodo)
			if destino is None and self.contexto.seleccion:
				nodo = arbol.buscar_id(self.contexto.seleccion)
				destino = self._asegurar_item(nodo.clave) if nodo is not None else None
			if destino is None:
				destino = self._nodos[operaciones.CLAVE_ENTORNO]
			self._clave_nodo = str(self.arbol.GetItemData(destino) or operaciones.CLAVE_ENTORNO)
			if self.arbol.GetSelection() != destino:
				self.arbol.SelectItem(destino)
			self.arbol.EnsureVisible(destino)
		finally:
			if congelar:
				self.arbol.Thaw()
			self._sincronizando = False

	def _debe_materializar(self, nodo: operaciones.Nodo) -> bool:
		"""True si los hijos de ``nodo`` deben existir ya como nodos nativos (si no, se crean al desplegarlo)."""
		if not nodo.hijos:
			return False
		return self._arbol_completo or nodo.clave in self._abiertos or nodo.clave in self._materializados

	def _poner_nodo(self, item: wx.TreeItemId, nodo: operaciones.Nodo, anterior: operaciones.Nodo | None) -> None:
		"""Deja el nodo nativo ``item`` como dice el nodo lógico ``nodo`` (``anterior``: el que enseñaba antes, o None si no se sabe)."""
		arbol = self.arbol
		if anterior is not None and anterior == nodo and self._nodos.get(nodo.clave) == item:
			# Nada ha cambiado en este subárbol: ni se toca (es lo que hace barato editar un barrio).
			if self._debe_materializar(nodo) and nodo.clave not in self._materializados:
				self._poner_hijos(item, nodo, None)
			return
		if anterior is not None and anterior.clave != nodo.clave:
			anterior = None
		if anterior is None:
			# El nodo nativo enseñaba otra cosa: se olvida lo que apuntaba a él y a sus hijos antes de reutilizarlo.
			self._olvidar_item(item)
		if arbol.GetItemText(item) != nodo.texto:
			arbol.SetItemText(item, nodo.texto)
		if arbol.GetItemData(item) != nodo.clave:
			arbol.SetItemData(item, nodo.clave)
		self._nodos[nodo.clave] = item
		if self._debe_materializar(nodo):
			self._poner_hijos(item, nodo, anterior if nodo.clave in self._materializados else None)
		else:
			if arbol.GetChildrenCount(item, False):
				hijo, galleta = arbol.GetFirstChild(item)
				while hijo.IsOk():
					self._olvidar_item(hijo)
					hijo, galleta = arbol.GetNextChild(item, galleta)
				arbol.DeleteChildren(item)
			self._materializados.discard(nodo.clave)
			arbol.SetItemHasChildren(item, bool(nodo.hijos))
		abierto = arbol.IsExpanded(item)
		if abierto and anterior is not None and nodo.hijos:
			# El mismo nodo, desplegado (por la persona o al hacer visible un hijo): sigue desplegado.
			self._abiertos.add(nodo.clave)
		if nodo.hijos and nodo.clave in self._abiertos and not abierto:
			arbol.Expand(item)
		elif abierto and nodo.clave not in self._abiertos:
			arbol.Collapse(item)

	def _poner_hijos(self, item: wx.TreeItemId, nodo: operaciones.Nodo, anterior: operaciones.Nodo | None) -> None:
		"""Sincroniza los hijos nativos de ``item`` con los de ``nodo``, reutilizando por posición los que ya hay.

		Si solo se han quitado o añadido hijos (borrar un espacio, deshacer su
		borrado), se borran o insertan esos nodos nativos en su sitio: por
		posición se reescribirían todos los que van detrás, que en un barrio
		son miles.
		"""
		arbol = self.arbol
		previos = anterior.hijos if anterior is not None else []
		existentes = self._hijos_apuntados(item, nodo, previos)
		apuntados = existentes is not None
		if existentes is None:
			existentes = []
			hijo_item, galleta = arbol.GetFirstChild(item)
			while hijo_item.IsOk():
				existentes.append(hijo_item)
				hijo_item, galleta = arbol.GetNextChild(item, galleta)
		if len(existentes) != len(previos):
			# Lo que hay en pantalla no corresponde a ``anterior`` (no estaba creado): se reescribe todo.
			previos = []
		elif len(previos) != len(nodo.hijos) and self._insertar_y_quitar(item, nodo, previos, existentes):
			self._materializados.add(nodo.clave)
			return
		for posicion, hijo in enumerate(nodo.hijos):
			previo = previos[posicion] if posicion < len(previos) else None
			if posicion < len(existentes):
				if apuntados and previo is hijo and not (self._debe_materializar(hijo) and hijo.clave not in self._materializados):
					# El mismo nodo lógico (compartido con el árbol anterior) en su mismo nodo nativo: nada que hacer.
					continue
				self._poner_nodo(existentes[posicion], hijo, previo)
			else:
				self._poner_nuevo(arbol.AppendItem(item, hijo.texto), hijo)
		for posicion in range(len(nodo.hijos), len(existentes)):
			self._olvidar_item(existentes[posicion])
			arbol.Delete(existentes[posicion])
		self._materializados.add(nodo.clave)

	def _hijos_apuntados(self, item: wx.TreeItemId, nodo: operaciones.Nodo, previos: list[operaciones.Nodo]) -> list[wx.TreeItemId] | None:
		"""Los nodos nativos de los hijos ``previos`` sacados de ``_nodos``, sin recorrerlos en el control; None si no se puede.

		Recorrer los hijos nativos de una planta con miles de espacios son miles
		de llamadas al control (unos 15 µs cada una; contarlos con
		``GetChildrenCount`` también los recorre). Si los hijos estaban creados
		(el nodo está materializado), cada uno está apuntado con su clave; basta
		comprobar que el primero y el último son los del control.
		"""
		if not previos or nodo.clave not in self._materializados:
			return None
		apuntados = [self._nodos.get(previo.clave) for previo in previos]
		if any(apuntado is None for apuntado in apuntados):
			return None
		primero, _galleta = self.arbol.GetFirstChild(item)
		if not primero.IsOk() or primero != apuntados[0] or self.arbol.GetLastChild(item) != apuntados[-1]:
			return None
		return apuntados  # type: ignore[return-value]

	def _insertar_y_quitar(
		self, item: wx.TreeItemId, nodo: operaciones.Nodo, previos: list[operaciones.Nodo], existentes: list[wx.TreeItemId]
	) -> bool:
		"""Pone al día los hijos de ``item`` borrando e insertando solo los que sobran o faltan. False si no se puede así.

		Se puede cuando los hijos que siguen están en el mismo orden (lo normal:
		el historial y la edición conservan el orden de las listas).
		"""
		nuevas = {hijo.clave for hijo in nodo.hijos}
		viejas = {previo.clave: posicion for posicion, previo in enumerate(previos)}
		ultimo = -1
		for hijo in nodo.hijos:
			posicion = viejas.get(hijo.clave)
			if posicion is None:
				continue
			if posicion < ultimo:
				return False
			ultimo = posicion
		arbol = self.arbol
		quedan: list[tuple[operaciones.Nodo, wx.TreeItemId]] = []
		for previo, existente in zip(previos, existentes, strict=True):
			if previo.clave in nuevas:
				quedan.append((previo, existente))
			else:
				self._olvidar_item(existente)
				arbol.Delete(existente)
		siguiente = 0
		for posicion, hijo in enumerate(nodo.hijos):
			if siguiente < len(quedan) and quedan[siguiente][0].clave == hijo.clave:
				previo, existente = quedan[siguiente]
				siguiente += 1
				self._poner_nodo(existente, hijo, previo)
			else:
				self._poner_nuevo(arbol.InsertItem(item, posicion, hijo.texto), hijo)
		return True

	def _poner_nuevo(self, item: wx.TreeItemId, nodo: operaciones.Nodo) -> None:
		"""Rellena un nodo nativo recién creado: no hay nada que leer ni que olvidar de él.

		Cada llamada nativa al árbol cuesta decenas de microsegundos (más con un
		lector de pantalla abierto, que escucha cada cambio): con miles de
		espacios, ahorrarse las lecturas de ``_poner_nodo`` se nota al abrir.
		"""
		arbol = self.arbol
		arbol.SetItemData(item, nodo.clave)
		self._nodos[nodo.clave] = item
		if not nodo.hijos:
			return
		if self._debe_materializar(nodo):
			for hijo in nodo.hijos:
				self._poner_nuevo(arbol.AppendItem(item, hijo.texto), hijo)
			self._materializados.add(nodo.clave)
		else:
			arbol.SetItemHasChildren(item, True)
		if nodo.clave in self._abiertos:
			arbol.Expand(item)

	def _olvidar_item(self, item: wx.TreeItemId) -> None:
		"""Quita de ``_nodos`` las claves que apuntan a ``item`` o a sus descendientes nativos (antes de reutilizarlo o borrarlo)."""
		clave = self.arbol.GetItemData(item)
		if isinstance(clave, str) and self._nodos.get(clave) == item:
			del self._nodos[clave]
			self._materializados.discard(clave)
		hijo, galleta = self.arbol.GetFirstChild(item)
		while hijo.IsOk():
			self._olvidar_item(hijo)
			hijo, galleta = self.arbol.GetNextChild(item, galleta)

	def _asegurar_item(self, clave: str) -> wx.TreeItemId | None:
		"""El nodo nativo de ``clave``, creando antes los hijos de sus antepasados si aún no existían."""
		item = self._nodos.get(clave)
		if item is not None or self._arbol_logico is None:
			return item
		camino: list[operaciones.Nodo] = []
		padre = self._arbol_logico.padre_de(clave)
		while padre is not None:
			camino.append(padre)
			padre = self._arbol_logico.padre_de(padre.clave)
		for antepasado in reversed(camino):
			item_padre = self._nodos.get(antepasado.clave)
			if item_padre is None:
				return None
			if antepasado.clave not in self._materializados:
				self._poner_hijos(item_padre, antepasado, None)
		return self._nodos.get(clave)

	def _al_desplegar(self, evento: wx.TreeEvent) -> None:
		"""Al desplegar un espacio o un grupo de un entorno grande se crean en ese momento sus hijos."""
		evento.Skip()
		if self._saliendo or not self.arbol:
			return
		item = evento.GetItem()
		if not item.IsOk() or self._arbol_logico is None:
			return
		clave = self.arbol.GetItemData(item)
		if not isinstance(clave, str):
			return
		self._abiertos.add(clave)
		if clave in self._materializados:
			return
		nodo = self._arbol_logico.buscar(clave)
		if nodo is None or not nodo.hijos:
			return
		previo = self._sincronizando
		self._sincronizando = True
		self.arbol.Freeze()
		try:
			self._poner_hijos(item, nodo, None)
		finally:
			self.arbol.Thaw()
			self._sincronizando = previo

	def _al_plegar(self, evento: wx.TreeEvent) -> None:
		"""Recuerda que la persona ha plegado el nodo (sus hijos nativos se conservan: volver a abrirlo es inmediato)."""
		evento.Skip()
		if self._saliendo or not self.arbol:
			return
		item = evento.GetItem()
		clave = self.arbol.GetItemData(item) if item.IsOk() else None
		if isinstance(clave, str):
			self._abiertos.discard(clave)

	def _id_de_clave(self, clave: str) -> str:
		"""Id del elemento de un nodo del árbol («» en los grupos y en el entorno)."""
		if not clave or clave.startswith("@") and "/" not in clave:
			return ""
		return clave.rsplit("/", 1)[-1]

	def _al_elegir_en_arbol(self, evento: wx.TreeEvent) -> None:
		evento.Skip()
		# Al cerrar, el árbol emite estos avisos mientras se destruye: no hay nada que mostrar.
		if self._saliendo or not self.arbol or self._sincronizando or self.contexto.entorno is None:
			return
		item = evento.GetItem()
		if not item.IsOk():
			return
		self._clave_nodo = str(self.arbol.GetItemData(item) or operaciones.CLAVE_ENTORNO)
		self._rellenar_lista()
		self._origen_seleccion = "arbol"
		id_elemento = self._id_de_clave(self._clave_nodo)
		if id_elemento == self.contexto.seleccion:
			# Otro nodo del mismo elemento (una puerta sale bajo sus dos espacios) o un grupo: no hay evento, se refresca aquí.
			self._origen_seleccion = ""
			self._mostrar_propiedades()
		else:
			self.contexto.seleccionar(id_elemento)

	def _rellenar_lista(self, afectados: Afectados | None = None) -> None:
		"""Pone en la lista los elementos del nodo elegido en el árbol, sin mover a la persona de fila si sigue existiendo.

		Con ``afectados``, si la lista sigue teniendo los mismos elementos en el
		mismo orden, solo se recomponen las filas de los que han cambiado (la
		de una planta de un barrio tiene miles).
		"""
		entorno = self.contexto.entorno
		anterior = self._ids[self.lista.fila_actual()] if 0 <= self.lista.fila_actual() < len(self._ids) else ""
		elementos = operaciones.elementos_de_nodo(entorno, self._clave_nodo, self._arbol_logico) if entorno is not None else []
		previos = self._filas.elementos
		if afectados is not None and len(elementos) == len(previos) and all(map(operator.is_, elementos, previos, strict=True)):
			cambiados = afectados.ids()
			previo = self._sincronizando
			self._sincronizando = True
			try:
				for fila, id_elemento in enumerate(self._ids):
					if id_elemento in cambiados:
						self._ids[fila] = elementos[fila].id
						self._filas.olvidar(fila)
						self.lista.actualizar_fila(fila, self._filas[fila].celdas())
			finally:
				self._sincronizando = previo
			return
		# Las filas se componen cuando la lista las pide (solo las visibles): una planta de un barrio tiene miles.
		self._filas = operaciones.FilasPerezosas(elementos, self.contexto.catalogo)
		self._ids = [elemento.id for elemento in elementos]
		previo = self._sincronizando
		self._sincronizando = True
		try:
			filas = self._filas
			self.lista.reemplazar_proveedor(len(filas), lambda indice: filas[indice].celdas())
			ids = self._ids
			destino = self.contexto.seleccion if self.contexto.seleccion in ids else anterior
			if destino in ids:
				self.lista.enfocar_fila(ids.index(destino), anunciar=False)
			elif ids:
				self.lista.enfocar_fila(0, anunciar=False)
		finally:
			self._sincronizando = previo

	def _al_elegir_en_lista(self, evento: wx.ListEvent) -> None:
		evento.Skip()
		if self._saliendo or not self.lista or self._sincronizando:
			return
		fila = evento.GetIndex()
		if not 0 <= fila < len(self._ids) or self._ids[fila] == self.contexto.seleccion:
			return
		self._origen_seleccion = "lista"
		self.contexto.seleccionar(self._ids[fila])

	def _al_cambiar_seleccion(self) -> None:
		"""La selección ha cambiado en algún panel: los demás la siguen."""
		if not self or self._saliendo:
			return
		origen, self._origen_seleccion = self._origen_seleccion, ""
		seleccion = self.contexto.seleccion
		previo = self._sincronizando
		self._sincronizando = True
		try:
			if origen != "arbol" and seleccion and self._id_de_clave(self._clave_nodo) != seleccion:
				nodo = self._arbol_logico.buscar_id(seleccion) if self._arbol_logico is not None else None
				item = self._asegurar_item(nodo.clave) if nodo is not None else None
				if nodo is not None and item is not None:
					self.arbol.SelectItem(item)
					self.arbol.EnsureVisible(item)
					if origen != "lista":
						self._clave_nodo = nodo.clave
			if origen != "lista":
				if origen != "arbol":
					self._rellenar_lista()
				ids = self._ids
				if seleccion in ids:
					self.lista.enfocar_fila(ids.index(seleccion), anunciar=False)
		finally:
			self._sincronizando = previo
		self._mostrar_propiedades()

	def clave_elegida(self) -> str:
		"""Clave de lo que enseñan las propiedades: el id elegido o, si no hay, el entorno."""
		return self.contexto.seleccion or operaciones.CLAVE_ENTORNO

	def _mostrar_propiedades(self, forzar: bool = False) -> None:
		"""Carga en el formulario las propiedades del elemento elegido y pone su frase descriptiva."""
		entorno = self.contexto.entorno
		if entorno is None:
			self._clave_propiedades = ""
			self.propiedades.cargar([], {})
			self.frase.ChangeValue(_("No hay ningún entorno abierto. Cree uno con Archivo, Nuevo entorno, o abra uno con Archivo, Abrir."))
			self.titulo_propiedades.SetLabel(_("Propiedades"))
			self.boton_aplicar.Enable(False)
			self.boton_descartar.Enable(False)
			return
		clave = self.clave_elegida()
		try:
			_planta, elemento = operaciones.resolver(entorno, clave)
		except ValueError:
			clave, elemento = operaciones.CLAVE_ENTORNO, entorno
		self.frase.ChangeValue(dialogos_insertar.describir(self.contexto, elemento))
		foco = wx.Window.FindFocus()
		escribiendo = foco is not None and self.propiedades.IsDescendant(foco)
		if clave == self._clave_propiedades and escribiendo and not forzar:
			# La persona está escribiendo en este mismo formulario: no se le rehace debajo de las manos.
			return
		self._clave_propiedades = clave
		campos = esquema_de(elemento, entorno, self.contexto.catalogo)
		self.propiedades.cargar(campos, operaciones.valores_de(entorno, elemento, self.contexto.catalogo))
		self.titulo_propiedades.SetLabel(_("Propiedades de {nombre}").format(nombre=operaciones.nombre_de(elemento)))
		self.boton_aplicar.Enable(bool(campos))
		self.boton_descartar.Enable(bool(campos))
		self.pagina_entorno.Layout()

	def aplicar_propiedades(self) -> bool:
		"""Aplica al elemento lo escrito en el formulario de propiedades. False si algo no vale (foco en el campo)."""
		if self.contexto.entorno is None or not self._clave_propiedades:
			return False
		try:
			valores = self.propiedades.leer()
		except ErrorCampo as error:
			mostrar_error(self, error.mensaje, _("Revise las propiedades"))
			self.propiedades.enfocar(error.clave)
			return False
		clave = self._clave_propiedades
		try:
			cambiadas = dialogos_insertar.aplicar_propiedades(self.contexto, clave, valores)
		except ValueError as error:
			mostrar_error(self, str(error), _("No se puede hacer"))
			return False
		if not cambiadas:
			self.contexto.anunciar(_("Sin cambios."))
			return True
		self._mostrar_propiedades(forzar=True)
		self.contexto.anunciar(self.frase.GetValue())
		return True

	def _actualizar_descripcion(self) -> None:
		"""Pone al día la página «Descripción» (solo si se está viendo: componerla lleva su tiempo en entornos grandes)."""
		if self.cuaderno.GetSelection() != 1:
			return
		entorno = self.contexto.entorno
		if entorno is None:
			self._version_descripcion = -1
			self.texto_descripcion.ChangeValue(_("No hay ningún entorno abierto."))
			return
		from app.dominio import edicion

		version = self.contexto.version
		if espera.es_grande(entorno):
			# Con un barrio importado, describirlo todo tarda casi un segundo: se compone en segundo
			# plano y la página sigue respondiendo (y dice qué está haciendo) mientras tanto.
			if version == self._version_descripcion:
				return
			self._version_descripcion = version
			self.texto_descripcion.ChangeValue(
				_("Componiendo la descripción del entorno ({n} elementos)…").format(n=espera.tamano(entorno))
			)
			catalogo = self.contexto.catalogo
			self.tareas.enviar(
				lambda _tarea: edicion.describir_entorno(entorno, catalogo),
				al_terminar=lambda texto, v=version: self._descripcion_lista(texto, v),
				al_fallar=lambda error, v=version: self._descripcion_fallida(error, v),
				clave_unica=f"descripcion:{id(self)}:{version}",
				nombre="describir el entorno",
			)
			return
		try:
			texto = edicion.describir_entorno(entorno, self.contexto.catalogo)
		except Exception:  # noqa: BLE001 - un entorno a medias no debe dejar la página en blanco sin explicación
			log.exception("No se pudo describir el entorno")
			texto = _("No se pudo componer la descripción. Los detalles están en la carpeta de registros.")
		self._version_descripcion = version
		self._poner_descripcion(texto)

	def _poner_descripcion(self, texto: str) -> None:
		"""Escribe la descripción en su página, con lo que el plano dibuja de la actividad elegida al final."""
		# Los premios y el inicio de la actividad elegida, que el plano dibuja, también aquí en texto.
		actividad = self.plano.descripcion_actividad()
		if actividad:
			texto = f"{texto}\n\n{actividad}"
		self.texto_descripcion.ChangeValue(texto)
		self.texto_descripcion.SetInsertionPoint(0)

	def _descripcion_lista(self, texto: str, version: int) -> None:
		"""La descripción compuesta en segundo plano: se enseña si sigue siendo la del entorno actual."""
		if not self or self._saliendo:
			return
		if version != self.contexto.version:
			# El entorno cambió mientras se describía: se compone otra vez la buena.
			self._version_descripcion = -1
			self._actualizar_descripcion()
			return
		self._poner_descripcion(texto)
		if self.cuaderno.GetSelection() == 1:
			lineas = texto.count("\n") + 1
			self.contexto.anunciar(_("Descripción lista: {n} líneas.").format(n=lineas))

	def _descripcion_fallida(self, error: BaseException, version: int) -> None:
		if not self or self._saliendo:
			return
		self._version_descripcion = -1
		if version != self.contexto.version:
			# Probablemente se editó a la vez: se vuelve a intentar con el entorno de ahora.
			log.debug("La descripción en segundo plano falló con un entorno que ya cambió: %s", error)
			self._actualizar_descripcion()
			return
		log.error("No se pudo describir el entorno", exc_info=error)
		self.texto_descripcion.ChangeValue(_("No se pudo componer la descripción. Los detalles están en la carpeta de registros."))

	def _al_cambiar_de_pagina(self, evento: wx.BookCtrlEvent) -> None:
		evento.Skip()
		wx.CallAfter(self._actualizar_descripcion_si_vivo)

	def _actualizar_descripcion_si_vivo(self) -> None:
		if self and not self._saliendo:
			self._actualizar_descripcion()

	def _al_tecla_de_panel(self, evento: wx.KeyEvent) -> None:
		"""Suprimir en el árbol o en la lista borra el elemento elegido (con confirmación).

		Se atiende aquí y NO como atajo del menú: un atajo de menú le robaría
		la tecla a todos los campos de texto de la ventana.
		"""
		# atajo: Supr
		if evento.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not evento.HasAnyModifiers():
			self._al_borrar(None)
			return
		evento.Skip()

	def _crear_menu_contextual(self) -> wx.Menu | None:
		"""Menú contextual del elemento elegido (árbol, lista y plano comparten el mismo)."""
		if self.contexto.entorno is None:
			return None
		menu = wx.Menu()
		for entrada in _traducir_contextual():
			if entrada is None:
				menu.AppendSeparator()
				continue
			nombre, etiqueta = entrada
			item = menu.Append(wx.ID_ANY, etiqueta)
			menu.Bind(wx.EVT_MENU, self._manejador(nombre, True), item)
		return menu

	# ── Plano ────────────────────────────────────────────────────────────────

	def _al_dibujar_habitacion(self, x: float, y: float, ancho: float, fondo: float) -> None:
		"""Rectángulo arrastrado en el plano: se abre «Habitación por medidas» con esas medidas ya puestas."""
		self.orden(
			"insertar_habitacion",
			{"planta": self.contexto.planta_id, "x": round(x, 2), "y": round(y, 2), "ancho": round(ancho, 2), "fondo": round(fondo, 2)},
		)

	def _al_dibujar_pared(self, a: tuple[float, float], b: tuple[float, float]) -> None:
		"""Dos clics en el plano: se abre «Pared suelta» con los dos extremos ya puestos."""
		self.orden(
			"insertar_pared",
			{"planta": self.contexto.planta_id, "ax": round(a[0], 2), "ay": round(a[1], 2), "bx": round(b[0], 2), "by": round(b[1], 2)},
		)

	def _al_colocar_objeto_en_plano(self, x: float, y: float) -> None:
		from app.ui.dialogo_catalogo import insertar_objeto

		insertar_objeto(self.contexto, self.contexto.planta_id, None, (x, y), 0.0)

	# ── Mostrar, ocultar, bandeja ────────────────────────────────────────────

	def mostrar(self) -> None:
		"""Muestra la ventana con el foco en el árbol (la llama ``main.py``)."""
		self.Show()
		self.Raise()
		wx.CallAfter(self._enfocar_inicial)

	def _enfocar_inicial(self) -> None:
		"""Foco en el árbol, que siempre tiene un nodo elegido: así el lector anuncia algo útil al abrir."""
		if not self:
			return
		self.cuaderno.SetSelection(0)
		self.arbol.SetFocus()

	def despues_de_arrancar(self) -> None:
		"""Lo que se hace una vez, con la ventana ya visible: actualizaciones y oferta de recuperación."""
		if not self or self._saliendo:
			return
		try:
			from app.ui import dialogo_actualizacion

			dialogo_actualizacion.al_arrancar(self, al_haber_permiso=self._mirar_catalogo_en_linea)
		except Exception:  # noqa: BLE001 - un fallo al mirar actualizaciones no debe impedir trabajar
			log.exception("Falló la comprobación de actualizaciones del arranque")
		self.ofrecer_recuperacion()

	def _mirar_catalogo_en_linea(self) -> None:
		"""Con el mismo permiso que las actualizaciones, mira si hay complementos nuevos (en segundo plano)."""
		if not self._config.obtener("complementos.comprobar_actualizaciones", True):
			return
		try:
			from app.ui import dialogo_complementos_en_linea

			dialogo_complementos_en_linea.buscar_actualizaciones_en_segundo_plano(self)
		except Exception:  # noqa: BLE001 - es una comodidad: si falla se anota y ya
			log.exception("No se pudo mirar el catálogo en línea de complementos")

	def ocultar_en_bandeja(self) -> bool:
		"""Oculta la ventana dejando un icono en la bandeja. ``False`` si no hay bandeja.

		Si no se pudo poner el icono, NO se oculta: el usuario perdería el
		acceso a la ventana.
		"""
		if self._bandeja is None:
			self._bandeja = IconoBandeja(NOMBRE_APLICACION, self.restaurar, self.salir)
		if not self._bandeja.mostrar():
			log.warning("No se pudo poner el icono en la bandeja; la ventana no se oculta.")
			self._quitar_bandeja()
			return False
		self.Hide()
		voz.hablar(_("{nombre} sigue en la bandeja del sistema.").format(nombre=NOMBRE_APLICACION))
		return True

	def _quitar_bandeja(self) -> None:
		if self._bandeja is not None:
			self._bandeja.quitar()
			self._bandeja = None

	def restaurar(self) -> None:
		"""Muestra la ventana desde la bandeja, minimizada o detrás de otras.

		Si hay un diálogo modal abierto, el foco va a él: la ventana principal
		está desactivada detrás.
		"""
		if not self:
			return
		self.Show()
		if self.IsIconized():
			self.Iconize(False)
		self.Raise()
		# El icono se destruye después: quizá estamos dentro de su propio evento.
		wx.CallAfter(self._quitar_bandeja)
		dialogo = next(
			(v for v in wx.GetTopLevelWindows() if isinstance(v, wx.Dialog) and v.IsShown() and v.IsEnabled()),
			None,
		)
		if dialogo is not None:
			dialogo.Raise()
			dialogo.SetFocus()
		elif wx.Window.FindFocus() is None:
			wx.CallAfter(self._enfocar_inicial)
		if not traer_al_frente(self.GetHandle()):
			# Windows no dejó ponerla delante: al menos parpadea en la barra de tareas.
			self.RequestUserAttention()

	def salir(self) -> None:
		"""Sale de verdad, aunque esté activado «cerrar a la bandeja»."""
		self._forzar_salida = True
		self.Close()

	# ── Geometría ────────────────────────────────────────────────────────────

	def _restaurar_geometria(self) -> None:
		"""Aplica el tamaño y la posición guardados si siguen siendo visibles."""
		ancho = int(self._config.obtener("ventana.ancho", 800))
		alto = int(self._config.obtener("ventana.alto", 600))
		sin_guardar = int(self._config.obtener("ventana.x", -1)) < 0 and (ancho, alto) == (800, 600)
		if ancho < TAMANO_MINIMO[0] or alto < TAMANO_MINIMO[1] or sin_guardar:
			# Primera vez (o datos raros): un tamaño en el que caben el árbol, el plano y las propiedades.
			ancho, alto = self.FromDIP(wx.Size(*TAMANO_DE_SERIE))
			pantalla = (
				wx.Display(max(0, wx.Display.GetFromWindow(self))).GetClientArea() if wx.Display.GetCount() else wx.Rect(0, 0, ancho, alto)
			)
			ancho, alto = min(ancho, pantalla.width), min(alto, pantalla.height)
		self.SetSize(wx.Size(ancho, alto))
		x = int(self._config.obtener("ventana.x", -1))
		y = int(self._config.obtener("ventana.y", -1))
		# Se comprueba un punto de la barra de título: si ese monitor ya no
		# existe, la ventana se centraría en una pantalla que nadie ve.
		if x >= -50 and y >= -50 and wx.Display.GetFromPoint(wx.Point(x + 60, y + 15)) != wx.NOT_FOUND:
			self.SetPosition(wx.Point(x, y))
		else:
			self.Centre()
		if self._config.obtener("ventana.maximizada", False):
			self.Maximize(True)

	def _al_cambiar_geometria(self, evento: wx.Event) -> None:
		"""Recuerda el rectángulo «normal» (ni maximizada ni minimizada)."""
		if self.IsShown() and not self.IsMaximized() and not self.IsIconized():
			self._rect_normal = self.GetRect()
		evento.Skip()

	def _guardar_geometria(self) -> None:
		"""Anota posición y tamaño en la configuración (la escribe ``_al_cerrar``).

		Un solo ``establecer_varias`` sin guardar: cinco ``establecer`` seguidos
		escribirían el archivo cinco veces. El tamaño se acota a los límites
		que valida la configuración: una ventana minimizada o nunca mostrada
		puede dar un rectángulo diminuto.
		"""
		rect = self._rect_normal or self.GetRect()
		cambios = {
			"ventana.x": int(rect.x),
			"ventana.y": int(rect.y),
			"ventana.ancho": max(200, min(20000, int(rect.width))),
			"ventana.alto": max(150, min(20000, int(rect.height))),
			"ventana.maximizada": bool(self.IsMaximized()),
		}
		try:
			self._config.establecer_varias(cambios, guardar=False)
		except ErrorConfiguracion:
			log.exception("No se pudo anotar la geometría de la ventana")

	# ── Cierre ───────────────────────────────────────────────────────────────

	def _al_minimizar(self, evento: wx.IconizeEvent) -> None:
		if evento.IsIconized() and self._config.obtener("general.minimizar_a_bandeja", False):
			wx.CallAfter(self.ocultar_en_bandeja)
		evento.Skip()

	def _al_cerrar(self, evento: wx.CloseEvent) -> None:
		"""Cierre ordenado: bandeja si procede; si no, preguntar por los cambios, detener, guardar y destruir."""
		if (
			not self._forzar_salida
			and evento.CanVeto()
			and self._config.obtener("general.cerrar_a_bandeja", False)
			and self.ocultar_en_bandeja()
		):
			evento.Veto()
			return
		if evento.CanVeto() and not self.confirmar_descartar():
			# La persona canceló: sigue trabajando.
			self._forzar_salida = False
			evento.Veto()
			return
		self._saliendo = True
		self._temporizador_buzon.Stop()
		self._temporizador_autoguardado.Stop()
		if self._recorrido is not None:
			try:
				self._recorrido.detener()
			except Exception:  # noqa: BLE001 - el cierre sigue aunque el reproductor no responda
				log.exception("No se pudo detener el recorrido al cerrar")
		al_cerrar = getattr(self._integracion, "al_cerrar", None)
		if callable(al_cerrar):
			try:
				al_cerrar(self.contexto)
			except Exception:  # noqa: BLE001 - el cierre sigue aunque falle la otra mitad
				log.exception("Falló el cierre de la parte de seguimiento")
		if self.contexto.entorno is not None:
			# Se cierra a sabiendas (guardando o descartando): la copia de recuperación ya no hace falta.
			archivos.borrar_recuperacion(self.contexto.entorno.id)
		if self._tareas_propias:
			self.tareas.apagar(espera=3.0)
		self._cancelar_config()
		self._guardar_geometria()
		self._config.guardar_pendiente()
		self._config.guardar()
		self._quitar_bandeja()
		self._desconectar_paneles()
		log.info("Ventana principal cerrada.")
		self.Destroy()

	def _desconectar_paneles(self) -> None:
		"""Deja el árbol y la lista sin manejadores antes de destruir la ventana.

		Al destruirse, Windows borra los nodos del árbol uno a uno y, por cada
		uno, envía «selección cambiada». Si el manejador sigue conectado, intenta
		leer un árbol que wx ya ha destruido («wrapped C/C++ object of type
		TreeCtrl has been deleted») y el cierre acaba en una cascada de errores.
		"""
		for control, eventos in (
			(self.arbol, (wx.EVT_TREE_SEL_CHANGED, wx.EVT_TREE_ITEM_EXPANDING, wx.EVT_TREE_ITEM_COLLAPSED, wx.EVT_TREE_ITEM_ACTIVATED)),
			(self.lista, (wx.EVT_LIST_ITEM_FOCUSED, wx.EVT_LIST_ITEM_SELECTED, wx.EVT_LIST_ITEM_ACTIVATED)),
		):
			if not control:
				continue
			for evento in eventos:
				control.Unbind(evento)

	# ── Segunda instancia ────────────────────────────────────────────────────

	def _al_revisar_buzon(self, _evento: wx.TimerEvent | None) -> None:
		"""Atiende las órdenes de una segunda instancia (mostrar, abrir archivos)."""
		try:
			ordenes = self._instancia.recoger_ordenes() if self._instancia else []
			for orden in ordenes:
				if orden.orden in (ORDEN_MOSTRAR, ORDEN_ABRIR):
					self.restaurar()
				if orden.orden == ORDEN_ABRIR:
					self.abrir_archivos([Path(a) for a in orden.argumentos])
		except Exception:  # noqa: BLE001 - el temporizador late toda la sesión; no debe romperla
			log.exception("Error al atender las órdenes de otra instancia")

	# ── Archivos ─────────────────────────────────────────────────────────────

	def abrir_archivos(self, rutas: list[Path], interactivo: bool = True) -> bool:
		"""Abre el primer ``.elab`` de la lista (línea de órdenes o segunda instancia). True si se abrió.

		``interactivo=False``: sin ningún diálogo (``--comprobar-arranque``).
		"""
		for ruta in rutas:
			if ruta.suffix.lower() == archivos.EXTENSION:
				if not interactivo:
					return self.abrir_paquete(ruta, interactivo=False)
				return self._abrir_con_pregunta(ruta)
		if rutas:
			log.warning("Ninguno de los archivos recibidos es un entorno .elab: %s", rutas)
		return False

	def confirmar_descartar(self) -> bool:
		"""Si hay cambios sin guardar, pregunta qué hacer. True si se puede seguir (guardado o descartado)."""
		contexto = self.contexto
		if contexto.entorno is None or not contexto.modificado:
			return True
		pregunta = _("«{nombre}» tiene cambios sin guardar. ¿Qué quiere hacer?").format(nombre=contexto.nombre_documento())
		elegida = elegir_opcion(self, pregunta, _("Cambios sin guardar"), [_("&Guardar"), _("&No guardar"), _("&Cancelar")])
		if elegida == 0:
			return self.guardar()
		return elegida == 1

	def _abrir_con_pregunta(self, ruta: Path, como_ejemplo: bool = False) -> bool:
		"""Abre un paquete preguntando antes por los cambios sin guardar del que haya abierto."""
		if not self.confirmar_descartar():
			return False
		return self.abrir_paquete(ruta, como_ejemplo)

	def _leer_paquete(self, ruta: Path) -> Any:
		"""Lee un ``.elab``; si es grande, en segundo plano con el diálogo de progreso (la ventana sigue respondiendo).

		Un paquete de un barrio importado ocupa algo más de medio mega y se lee en
		menos de una décima; uno con muchos recursos (audios, planos escaneados)
		puede tardar segundos en descomprimirse. Lanza lo mismo que ``cargar_paquete``.
		"""
		try:
			tamano = ruta.stat().st_size
		except OSError:
			tamano = 0
		if tamano < TAMANO_PAQUETE_EN_SEGUNDO_PLANO or self.tareas is None:
			return cargar_paquete(ruta)
		from app.ui import dialogo_progreso

		megas = tamano / (1024 * 1024)
		return dialogo_progreso.ejecutar_tarea(
			self,
			_("Abrir"),
			lambda _tarea: cargar_paquete(ruta),
			self.tareas,
			self._config,
			_("Abriendo {nombre} ({megas:.1f} MB)").format(nombre=ruta.name, megas=megas),
		)

	def abrir_paquete(self, ruta: str | Path, como_ejemplo: bool = False, interactivo: bool = True) -> bool:
		"""Abre un ``.elab``. Un ejemplo se abre como documento nuevo, para no escribir encima del que viene con el programa.

		Con ``interactivo=False`` (la comprobación automática del arranque) no
		se abre ningún diálogo: no habría nadie que lo cerrara y el proceso se
		quedaría esperando para siempre. El error se registra y se devuelve False.
		"""
		ruta = Path(ruta)
		try:
			paquete = self._leer_paquete(ruta) if interactivo else cargar_paquete(ruta)
		except TareaCancelada:
			self.contexto.anunciar(_("Apertura cancelada."))
			return False
		except ErrorFormato as error:
			if not interactivo:
				log.error("No se pudo abrir %s: %s", ruta, error)
				return False
			copia = ruta.with_name(ruta.name + ".bak")
			if not copia.is_file():
				mostrar_error(self, str(error), _("Abrir"))
				return False
			pregunta = _("{error}\n\nHay una copia de seguridad de la última vez que se guardó bien. ¿Quiere abrirla?").format(error=error)
			if elegir_opcion(self, pregunta, _("Abrir"), [_("&Abrir la copia de seguridad"), _("&Cancelar")]) != 0:
				return False
			try:
				paquete = recuperar_copia(ruta)
			except ErrorFormato as error_copia:
				mostrar_error(self, str(error_copia), _("Abrir"))
				return False
		except OSError as error:
			log.exception("No se pudo leer %s", ruta)
			if interactivo:
				mostrar_error(self, _("No se pudo leer el fichero: {error}").format(error=error), _("Abrir"))
			return False
		if self.contexto.entorno is not None:
			archivos.borrar_recuperacion(self.contexto.entorno.id)
		self.contexto.abrir_documento(paquete.entorno, None if como_ejemplo else ruta, paquete.actividades, paquete.recursos)
		if not como_ejemplo and interactivo:
			archivos.anotar_reciente(self._config, ruta)
		self._anunciar_abierto()
		if interactivo:
			self.avisar_complementos_que_faltan()
		return True

	def avisar_complementos_que_faltan(self) -> bool:
		"""Si el entorno abierto usa complementos que no están instalados, lo dice UNA vez y ofrece buscarlos.

		Los objetos de esos complementos no se pierden: se conservan con sus
		medidas y se dibujan como cajas. El aviso es un mensaje accesible con
		botones que dicen la acción. El Estudio NO se conecta por su cuenta:
		solo si la persona elige «Buscar en el catálogo en línea» se abre el
		catálogo, y abrirlo es la acción explícita que le da permiso para
		descargar la lista (como el menú Herramientas). True si se abrió.
		"""
		faltan = operaciones.complementos_que_faltan(self.contexto.entorno, self.contexto.catalogo)
		if not faltan:
			return False
		log.warning("El entorno abierto usa complementos que no están instalados: %s", ", ".join(faltan))
		elegida = elegir_opcion(
			self,
			operaciones.texto_complementos_que_faltan(faltan),
			_("Complementos que faltan"),
			[_("&Buscar en el catálogo en línea"), _("&Cerrar")],
		)
		if elegida != 0:
			return False
		from app.ui import dialogo_complementos_en_linea

		# Con uno solo, el catálogo se abre ya filtrado por su identificador.
		buscar = next(iter(faltan)) if len(faltan) == 1 else ""
		dialogo_complementos_en_linea.mostrar_complementos_en_linea(self, al_cambiar=self.contexto.recargar_catalogo, buscar=buscar)
		return True

	def _anunciar_abierto(self) -> None:
		entorno = self.contexto.entorno
		if entorno is None:
			return
		espacios = sum(len(planta.espacios) for planta in entorno.plantas)
		self.contexto.anunciar(
			_("Abierto {nombre}: {plantas} plantas y {espacios} espacios.").format(
				nombre=self.contexto.nombre_documento(), plantas=len(entorno.plantas), espacios=espacios
			)
		)

	def adoptar_borrador(self, entorno: Entorno, nombre: str = "", recursos: dict[str, bytes] | None = None) -> bool:
		"""Pone un entorno recién creado o importado como documento nuevo, sin ruta y pendiente de guardar.

		Pregunta antes por los cambios sin guardar del documento abierto;
		devuelve False si la persona cancela.
		"""
		if not self.confirmar_descartar():
			return False
		if nombre and not entorno.nombre:
			entorno.nombre = nombre
		if self.contexto.entorno is not None:
			archivos.borrar_recuperacion(self.contexto.entorno.id)
		self.contexto.abrir_documento(entorno, None, [], recursos, modificado=True)
		self._anunciar_abierto()
		return True

	def guardar(self) -> bool:
		"""Guarda el documento; si aún no tiene fichero, pregunta dónde. True si quedó guardado."""
		contexto = self.contexto
		if contexto.entorno is None:
			return False
		if contexto.ruta_paquete is None:
			return self.guardar_como()
		return self._guardar_en(contexto.ruta_paquete)

	def guardar_como(self) -> bool:
		"""Pregunta dónde guardar (por defecto, en la carpeta de entornos) y guarda."""
		contexto = self.contexto
		if contexto.entorno is None:
			return False
		actual = contexto.ruta_paquete
		carpeta = str(actual.parent) if actual is not None else str(archivos.carpeta_entornos(self._config))
		nombre = actual.name if actual is not None else archivos.nombre_de_fichero(contexto.nombre_documento())
		with wx.FileDialog(
			self, _("Guardar el entorno"), carpeta, nombre, wildcard=_(archivos.COMODIN), style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
		) as dialogo:
			if dialogo.ShowModal() != wx.ID_OK:
				return False
			ruta = archivos.con_extension(dialogo.GetPath())
		return self._guardar_en(ruta)

	def _guardar_en(self, ruta: Path) -> bool:
		contexto = self.contexto
		if not contexto.guardar(ruta):
			mostrar_error(
				self,
				_("No se pudo guardar en {ruta}. Compruebe que la carpeta existe y que tiene permiso para escribir en ella.").format(
					ruta=ruta
				),
				_("Guardar"),
			)
			return False
		archivos.borrar_recuperacion(contexto.entorno.id)
		archivos.anotar_reciente(self._config, ruta)
		contexto.anunciar(_("Guardado {nombre}.").format(nombre=ruta.name))
		return True

	def _programar_autoguardado(self) -> None:
		"""Arranca o para el temporizador de la copia de recuperación según las preferencias."""
		minutos = int(self._config.obtener("editor.autoguardado_min", 5))
		self._temporizador_autoguardado.Stop()
		if minutos > 0:
			self._temporizador_autoguardado.Start(minutos * 60 * 1000)

	def _al_autoguardar(self, _evento: wx.TimerEvent | None) -> None:
		"""Escribe la copia de recuperación si hay cambios. En silencio: no interrumpe ni mueve el foco."""
		if not self._saliendo:
			archivos.guardar_recuperacion(self.contexto)

	def ofrecer_recuperacion(self) -> bool:
		"""Si quedó una copia de una sesión que no se cerró bien, ofrece recuperarla. True si se recuperó."""
		if self.contexto.entorno is not None:
			return False
		for copia in archivos.recuperaciones():
			fecha = time.strftime("%d/%m/%Y %H:%M", time.localtime(copia.fecha))
			pregunta = _(
				"La última vez el programa se cerró sin guardar los cambios de «{nombre}». Hay una copia de recuperación del {fecha}. ¿Qué quiere hacer con ella?"
			).format(nombre=copia.nombre, fecha=fecha)
			elegida = elegir_opcion(self, pregunta, _("Recuperar el trabajo"), [_("&Recuperar"), _("&Descartar la copia"), _("&Cancelar")])
			if elegida == 1:
				archivos.descartar_recuperacion(copia)
				continue
			if elegida != 0:
				return False
			try:
				paquete = cargar_paquete(copia.ruta)
			except (ErrorFormato, OSError) as error:
				mostrar_error(self, _("La copia de recuperación no se puede leer: {error}").format(error=error), _("Recuperar el trabajo"))
				continue
			self.contexto.abrir_documento(paquete.entorno, copia.ruta_original, paquete.actividades, paquete.recursos, modificado=True)
			self.contexto.anunciar(_("Recuperado {nombre}. Guárdelo para conservarlo.").format(nombre=copia.nombre))
			self.avisar_complementos_que_faltan()
			return True
		return False

	def _al_cambiar_preferencia(self, *_argumentos: Any) -> None:
		"""Una preferencia del editor ha cambiado: se aplica sin reiniciar."""
		if not self or self._saliendo:
			return
		self._programar_autoguardado()
		self.plano.refrescar()

	# ── Menú Archivo ─────────────────────────────────────────────────────────

	def _al_nuevo(self, _evento: wx.CommandEvent | None) -> None:
		if not self.confirmar_descartar():
			return
		entorno = dialogos_insertar.nuevo_entorno(self.contexto)
		if entorno is None:
			return
		if self.contexto.entorno is not None:
			archivos.borrar_recuperacion(self.contexto.entorno.id)
		self.contexto.abrir_documento(entorno, None, [], None, modificado=True)
		self._anunciar_abierto()
		self._enfocar_inicial()

	def _al_abrir(self, _evento: wx.CommandEvent | None) -> None:
		if not self.confirmar_descartar():
			return
		with wx.FileDialog(
			self,
			_("Abrir un entorno"),
			str(archivos.carpeta_entornos(self._config)),
			wildcard=_(archivos.COMODIN),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		) as dialogo:
			if dialogo.ShowModal() != wx.ID_OK:
				return
			ruta = Path(dialogo.GetPath())
		if self.abrir_paquete(ruta):
			self._enfocar_inicial()

	def _al_guardar(self, _evento: wx.CommandEvent | None) -> None:
		if not self._hay_entorno():
			return
		self.guardar()

	def _al_guardar_como(self, _evento: wx.CommandEvent | None) -> None:
		if not self._hay_entorno():
			return
		self.guardar_como()

	def _hay_entorno(self) -> bool:
		"""True si hay entorno abierto; si no, lo explica (mejor que una orden que no hace nada y calla)."""
		if self.contexto.entorno is not None:
			return True
		mostrar_mensaje(
			self, _("No hay ningún entorno abierto. Cree uno con Archivo, Nuevo entorno, o abra uno con Archivo, Abrir."), NOMBRE_APLICACION
		)
		return False

	def _importar(self, funcion: str, *argumentos: Any) -> None:
		from app.ui import dialogos_importar

		getattr(dialogos_importar, funcion)(self.contexto, *argumentos)

	def _al_importar_osm(self, _evento: wx.CommandEvent | None) -> None:
		self._importar("importar_osm")

	def _al_importar_dxf(self, _evento: wx.CommandEvent | None) -> None:
		self._importar("importar_plano", "dxf")

	def _al_importar_svg(self, _evento: wx.CommandEvent | None) -> None:
		self._importar("importar_plano", "svg")

	def _al_importar_imagen(self, _evento: wx.CommandEvent | None) -> None:
		if self._hay_entorno():
			self._importar("importar_imagen_fondo")

	def _al_importar_gpx(self, _evento: wx.CommandEvent | None) -> None:
		if self._hay_entorno():
			self._importar("importar_gpx")

	def _exportar(self, formato: str) -> None:
		if not self._hay_entorno():
			return
		from app.ui import dialogos_exportar

		dialogos_exportar.exportar(self.contexto, formato)

	def _al_exportar_paquete(self, _evento: wx.CommandEvent | None) -> None:
		self._exportar("paquete")

	def _al_exportar_texto(self, _evento: wx.CommandEvent | None) -> None:
		self._exportar("texto")

	def _al_exportar_svg(self, _evento: wx.CommandEvent | None) -> None:
		self._exportar("svg")

	def _al_exportar_tactil(self, _evento: wx.CommandEvent | None) -> None:
		self._exportar("tactil")

	def _al_exportar_geojson(self, _evento: wx.CommandEvent | None) -> None:
		self._exportar("geojson")

	def _al_exportar_dxf(self, _evento: wx.CommandEvent | None) -> None:
		self._exportar("dxf")

	def _al_propiedades_entorno(self, _evento: wx.CommandEvent | None) -> None:
		if self._hay_entorno():
			dialogos_insertar.editar_propiedades(self.contexto, operaciones.CLAVE_ENTORNO)

	def _al_salir(self, _evento: wx.CommandEvent | None) -> None:
		self.salir()

	# ── Menú Editar ──────────────────────────────────────────────────────────

	def _campo_enfocado(self) -> wx.TextCtrl | None:
		"""El campo de texto editable que tiene el foco, si lo hay.

		Control+Z y Control+Y son atajos de menú y se adelantan a los campos de
		texto: cuando el foco está en uno, la orden se le pasa a él.
		"""
		foco = wx.Window.FindFocus()
		return foco if isinstance(foco, wx.TextCtrl) and foco.IsEditable() else None

	def _al_deshacer(self, _evento: wx.CommandEvent | None) -> None:
		campo = self._campo_enfocado()
		if campo is not None and campo.CanUndo():
			campo.Undo()
			return
		nombre = self.contexto.deshacer()
		self.contexto.anunciar(_("Deshecho: {operacion}.").format(operacion=nombre) if nombre else _("No hay nada que deshacer."))

	def _al_rehacer(self, _evento: wx.CommandEvent | None) -> None:
		campo = self._campo_enfocado()
		if campo is not None and campo.CanRedo():
			campo.Redo()
			return
		nombre = self.contexto.rehacer()
		self.contexto.anunciar(_("Rehecho: {operacion}.").format(operacion=nombre) if nombre else _("No hay nada que rehacer."))

	def _al_editar(self, _evento: wx.CommandEvent | None) -> None:
		if self._hay_entorno():
			dialogos_insertar.editar_propiedades(self.contexto, self.clave_elegida())

	def _al_duplicar(self, _evento: wx.CommandEvent | None) -> None:
		dialogos_insertar.duplicar(self.contexto)

	def _al_renombrar(self, _evento: wx.CommandEvent | None) -> None:
		dialogos_insertar.renombrar(self.contexto)

	def _al_borrar(self, _evento: wx.CommandEvent | None) -> None:
		dialogos_insertar.borrar(self.contexto)

	def _al_buscar(self, _evento: wx.CommandEvent | None) -> None:
		if dialogos_herramientas.buscar_elemento(self.contexto):
			self.contexto.anunciar(self.frase.GetValue())

	def _al_fijar_inicio(self, _evento: wx.CommandEvent | None) -> None:
		dialogos_insertar.fijar_inicio(self.contexto)

	# ── Menú Insertar ────────────────────────────────────────────────────────

	def _al_insertar_objeto(self, _evento: wx.CommandEvent | None) -> None:
		if not self._hay_entorno():
			return
		from app.ui.dialogo_catalogo import insertar_objeto
		from app.ui.esquemas_elementos import _espacio_actual

		id_planta, id_espacio = _espacio_actual(self.contexto)
		insertar_objeto(self.contexto, id_planta or None, id_espacio or None)

	# ── Menú Ver ─────────────────────────────────────────────────────────────

	def paneles(self) -> list[wx.Window]:
		"""Los paneles de la zona de trabajo, en el orden de F6: árbol, lista, propiedades y plano."""
		lista: list[wx.Window] = [self.arbol, self.lista]
		primero = self.propiedades.primer_control()
		if primero is not None:
			lista.append(primero)
		if self.plano.IsShown():
			lista.append(self.plano)
		return lista

	def _panel_actual(self) -> int:
		"""Índice del panel que tiene el foco (-1 si el foco está en otra parte)."""
		foco = wx.Window.FindFocus()
		if foco is None:
			return -1
		for indice, panel in enumerate(self.paneles()):
			contenedor = self.propiedades if panel not in (self.arbol, self.lista, self.plano) else panel
			if foco is contenedor or contenedor.IsDescendant(foco):
				return indice
		return -1

	def _ir_a_panel(self, panel: wx.Window) -> None:
		self.cuaderno.SetSelection(0)
		panel.SetFocus()

	def _mover_panel(self, paso: int) -> None:
		lista = self.paneles()
		actual = self._panel_actual()
		self._ir_a_panel(lista[(actual + paso) % len(lista)] if actual >= 0 else lista[0])

	def _al_panel_siguiente(self, _evento: wx.CommandEvent | None) -> None:
		self._mover_panel(1)

	def _al_panel_anterior(self, _evento: wx.CommandEvent | None) -> None:
		self._mover_panel(-1)

	def _al_ver_arbol(self, _evento: wx.CommandEvent | None) -> None:
		self._ir_a_panel(self.arbol)

	def _al_ver_lista(self, _evento: wx.CommandEvent | None) -> None:
		self._ir_a_panel(self.lista)

	def _al_ver_propiedades(self, _evento: wx.CommandEvent | None) -> None:
		primero = self.propiedades.primer_control()
		if primero is None:
			self.contexto.anunciar(_("No hay propiedades que enseñar."))
			return
		self._ir_a_panel(primero)

	def _al_ver_plano(self, _evento: wx.CommandEvent | None) -> None:
		if not self.plano.IsShown():
			self._mostrar_plano(True)
		self._ir_a_panel(self.plano)

	def _al_ver_descripcion(self, _evento: wx.CommandEvent | None) -> None:
		self.cuaderno.SetSelection(1)
		self._actualizar_descripcion()
		self.texto_descripcion.SetFocus()
		self.texto_descripcion.SetInsertionPoint(0)

	def _ir_a_planta(self, id_planta: str) -> None:
		self.contexto.ir_a_planta(id_planta)
		planta = self.contexto.planta_actual()
		if planta is not None:
			self.contexto.anunciar(_("Planta: {nombre}").format(nombre=operaciones.nombre_de(planta)))

	def _planta_vecina(self, paso: int) -> None:
		entorno = self.contexto.entorno
		actual = self.contexto.planta_actual()
		if entorno is None or actual is None:
			self.contexto.anunciar(_("No hay plantas."))
			return
		ordenadas = sorted(entorno.plantas, key=lambda p: p.nivel)
		indice = ordenadas.index(actual) + paso
		if not 0 <= indice < len(ordenadas):
			self.contexto.anunciar(_("No hay más plantas hacia arriba.") if paso > 0 else _("No hay más plantas hacia abajo."))
			return
		self._ir_a_planta(ordenadas[indice].id)

	def _al_planta_arriba(self, _evento: wx.CommandEvent | None) -> None:
		self._planta_vecina(1)

	def _al_planta_abajo(self, _evento: wx.CommandEvent | None) -> None:
		self._planta_vecina(-1)

	def _al_acercar(self, _evento: wx.CommandEvent | None) -> None:
		self.plano.acercar()

	def _al_alejar(self, _evento: wx.CommandEvent | None) -> None:
		self.plano.alejar()

	def _al_encajar(self, _evento: wx.CommandEvent | None) -> None:
		self.plano.encajar()

	def _fijar_herramienta(self, nombre: str, anuncio: str) -> None:
		self.plano.fijar_herramienta(nombre)
		self.contexto.anunciar(anuncio)

	def _al_herramienta_seleccion(self, _evento: wx.CommandEvent | None) -> None:
		self._fijar_herramienta("seleccion", _("Herramienta del plano: seleccionar y mover."))

	def _al_herramienta_habitacion(self, _evento: wx.CommandEvent | None) -> None:
		self._fijar_herramienta("habitacion", _("Herramienta del plano: dibujar una habitación arrastrando un rectángulo."))

	def _al_herramienta_pared(self, _evento: wx.CommandEvent | None) -> None:
		self._fijar_herramienta("pared", _("Herramienta del plano: dibujar una pared con dos clics."))

	def _al_herramienta_objeto(self, _evento: wx.CommandEvent | None) -> None:
		self._fijar_herramienta("objeto", _("Herramienta del plano: un clic coloca un objeto del catálogo."))

	def _al_cuadricula(self, evento: wx.CommandEvent) -> None:
		self.plano.fijar_cuadricula(evento.IsChecked())

	def _al_ajustar_cuadricula(self, evento: wx.CommandEvent) -> None:
		self.plano.fijar_ajuste(evento.IsChecked())
		self._config.establecer("editor.cuadricula", bool(evento.IsChecked()))

	def _mostrar_plano(self, visible: bool) -> None:
		"""Muestra u oculta el plano. Si tenía el foco, se lleva antes al árbol: el foco no puede quedar en algo oculto."""
		if not visible and self.plano.HasFocus():
			self.arbol.SetFocus()
		self.plano.Show(visible)
		self.pagina_entorno.Layout()
		self._config.establecer("editor.plano_visible", bool(visible))

	def _al_mostrar_plano(self, evento: wx.CommandEvent) -> None:
		self._mostrar_plano(evento.IsChecked())

	def _al_barra_estado(self, evento: wx.CommandEvent) -> None:
		visible = evento.IsChecked()
		self._aplicar_barra_estado(visible)
		self._config.establecer("ventana.barra_estado", visible)

	def _aplicar_barra_estado(self, visible: bool) -> None:
		self.GetStatusBar().Show(visible)
		self.elementos_menu["barra_estado"].Check(visible)
		self.SendSizeEvent()

	# ── Menú Herramientas ────────────────────────────────────────────────────

	def _al_comprobar(self, _evento: wx.CommandEvent | None) -> None:
		if dialogos_herramientas.comprobar_entorno(self.contexto):
			self._ir_a_panel(self.arbol)

	def _al_medir(self, _evento: wx.CommandEvent | None) -> None:
		dialogos_herramientas.medir(self.contexto)

	def _al_amueblar(self, _evento: wx.CommandEvent | None) -> None:
		dialogos_herramientas.amueblar(self.contexto)

	def _controlador_recorrido(self) -> Any:
		if self._recorrido is None:
			from app.ui.recorrido_wx import ControladorRecorrido

			self._recorrido = ControladorRecorrido(self.contexto)
		return self._recorrido

	def recorrer(self, desde_seleccion: bool = False) -> bool:
		"""Abre el reproductor en modo recorrido. True si arrancó."""
		if not self._hay_entorno():
			return False
		controlador = self._controlador_recorrido()
		if controlador.activo:
			self.contexto.anunciar(_("El recorrido ya está en marcha. Deténgalo con Herramientas, Detener el recorrido."))
			return False
		inicio = None
		if desde_seleccion:
			inicio = operaciones.posicion_junto_a(self.contexto.entorno, self.contexto.seleccion) if self.contexto.seleccion else None
			if inicio is None:
				mostrar_mensaje(self, _("Seleccione antes el espacio o el elemento junto al que quiere empezar."), _("Recorrer"))
				return False
		if not controlador.iniciar(inicio):
			return False
		self.contexto.anunciar(_("Recorrido en marcha. Lo que pida desde el reproductor se hará aquí."))
		return True

	def _al_recorrer(self, _evento: wx.CommandEvent | None) -> None:
		self.recorrer()

	def _al_recorrer_desde(self, _evento: wx.CommandEvent | None) -> None:
		self.recorrer(desde_seleccion=True)

	def _al_detener_recorrido(self, _evento: wx.CommandEvent | None) -> None:
		if self._recorrido is None or not self._recorrido.activo:
			self.contexto.anunciar(_("No hay ningún recorrido en marcha."))
			return
		self._recorrido.detener()

	def _al_complementos(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.dialogo_complementos import mostrar_complementos

		mostrar_complementos(self.contexto)

	def _al_complementos_en_linea(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.dialogo_complementos_en_linea import mostrar_complementos_en_linea

		mostrar_complementos_en_linea(self, al_cambiar=self.contexto.recargar_catalogo)

	def _al_crear_complemento(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.asistente_complemento import mostrar_asistente_complemento

		mostrar_asistente_complemento(self.contexto)

	def _abrir_carpeta(self, carpeta: Path) -> None:
		if hasattr(os, "startfile"):
			try:
				os.startfile(carpeta)  # noqa: S606 - carpeta propia de la aplicación
			except OSError:
				log.exception("No se pudo abrir la carpeta %s", carpeta)

	def _al_carpeta_datos(self, _evento: wx.CommandEvent | None) -> None:
		self._abrir_carpeta(paths.ruta_datos())

	def _al_carpeta_registros(self, _evento: wx.CommandEvent | None) -> None:
		self._abrir_carpeta(paths.ruta_registros())

	def _al_preferencias(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.preferencias import mostrar_preferencias

		if mostrar_preferencias(self.contexto):
			self._programar_autoguardado()
			self.plano.refrescar()

	# ── Menú Ayuda ───────────────────────────────────────────────────────────

	def _al_manual(self, _evento: wx.CommandEvent | None) -> None:
		"""F1: el manual en el visor accesible (no modal; se puede seguir trabajando)."""
		from app.ui import visor_ayuda

		visor_ayuda.abrir_manual(self)

	def _al_teclas(self, _evento: wx.CommandEvent | None) -> None:
		"""Ctrl+F1: la lista de teclas en el visor accesible."""
		from app.ui import visor_ayuda

		visor_ayuda.abrir_teclas(self)

	def _al_novedades(self, _evento: wx.CommandEvent | None) -> None:
		"""Novedades de todas las versiones (al actualizar se enseñan solas una vez)."""
		from app.ui import visor_ayuda

		visor_ayuda.abrir_novedades(self)

	def _al_ayuda_contextual(self, _evento: wx.CommandEvent | None) -> None:
		"""Ctrl+H: la ayuda (``SetHelpText``) del control enfocado, en un mensaje que se puede repasar.

		Requiere ``wx.HelpProvider.Set(wx.SimpleHelpProvider())`` al arrancar;
		sin proveedor, ``SetHelpText`` no guarda nada.
		"""
		foco = wx.Window.FindFocus()
		texto = foco.GetHelpText() if foco else ""
		if not texto:
			texto = _("No hay ayuda para este control. Pulse F1 para abrir el manual.")
		mostrar_mensaje(self, texto, _("Ayuda"))

	def _al_actualizaciones(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.dialogo_actualizacion import mostrar_dialogo_actualizacion

		mostrar_dialogo_actualizacion(self)

	def _al_pagina_proyecto(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui import acerca_de

		self._tras_abrir_enlace(acerca_de.abrir_pagina_del_proyecto())

	def _al_avisar_fallo(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui import acerca_de

		self._tras_abrir_enlace(acerca_de.avisar_de_un_fallo())

	def _al_paquete_diagnostico(self, _evento: wx.CommandEvent | None) -> None:
		"""Genera el ZIP de diagnóstico en un hilo de trabajo: leer y comprimir los registros puede tardar unos segundos."""
		from app.core import diagnostico
		from app.core.version import APP_VERSION

		tarea = self.tareas.enviar(
			lambda _tarea: diagnostico.generar_paquete(NOMBRE_APLICACION, APP_VERSION),
			al_terminar=self._al_diagnostico_listo,
			al_fallar=self._al_diagnostico_fallido,
			clave_unica="diagnostico",
			nombre="paquete de diagnóstico",
		)
		if tarea is not None:
			self.contexto.anunciar(_("Generando el paquete de diagnóstico..."))

	def _al_diagnostico_listo(self, ruta: Path) -> None:
		"""Dice dónde ha quedado el paquete y ofrece abrir su carpeta."""
		if not self:
			return
		self.ultimo_paquete_diagnostico = ruta
		mensaje = _(
			"Se ha creado el paquete de diagnóstico «{nombre}» en la carpeta {carpeta}.\n\n"
			"Lleva los registros y los datos del sistema, sin configuración, fichas, sesiones ni entornos. "
			"Adjúntelo al avisar de un fallo."
		).format(nombre=ruta.name, carpeta=ruta.parent)
		eleccion = elegir_opcion(self, mensaje, _("Paquete de diagnóstico"), [_("&Abrir la carpeta"), _("&Cerrar")])
		if eleccion == 0:
			self._abrir_carpeta(ruta.parent)

	def _al_diagnostico_fallido(self, error: BaseException) -> None:
		if not self:
			return
		log.error("No se pudo generar el paquete de diagnóstico", exc_info=error)
		mostrar_error(self, _("No se pudo generar el paquete de diagnóstico: {error}").format(error=error), _("Paquete de diagnóstico"))

	def _al_cafe(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui import acerca_de

		self._tras_abrir_enlace(acerca_de.invitar_a_un_cafe())

	def _tras_abrir_enlace(self, abierto: bool) -> None:
		self.contexto.anunciar(_("Se ha abierto la página en el navegador.") if abierto else _("No se pudo abrir el navegador."))

	def _al_acerca_de(self, _evento: wx.CommandEvent | None) -> None:
		from app.ui.acerca_de import mostrar_acerca_de

		mostrar_acerca_de(self)
