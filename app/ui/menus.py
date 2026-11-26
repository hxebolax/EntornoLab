"""Tabla de menús del Estudio, sin wx.

La barra de menús se construye a partir de datos y no a mano, por tres
razones: se ve de un vistazo que cada orden tiene letra de acceso, atajo y
texto de ayuda; ``tools/comprobar_teclas.py`` encuentra los atajos; y la otra
mitad del Estudio (``app/ui/seguimiento``) añade sus menús con el mismo
formato sin tocar la ventana principal.

FORMATO. ``MENUS`` es una lista de menús ``(título, entradas)``. Cada entrada es:

- ``None``: un separador.
- ``(nombre, etiqueta, ayuda)``: una orden.
  - ``nombre``: identificador de la orden. En los menús propios es el sufijo
    del método ``VentanaPrincipal._al_<nombre>``; en ``MENUS_SEGUIMIENTO`` es
    el nombre de una función de ``app.ui.seguimiento.integracion`` que se
    llama con el ``ContextoEstudio``.
  - ``etiqueta``: texto con ``&`` delante de su letra de acceso y, si tiene
    atajo, un tabulador y la combinación EN INGLÉS, que es como la entiende
    wx (``Ctrl``, ``Shift``, ``Alt``): ``N_("&Guardar\\tCtrl+S")``.
  - ``ayuda``: frase que explica la orden (barra de estado).
- ``(nombre, etiqueta, ayuda, tipo)``: lo mismo con ``tipo`` ``"casilla"``
  (se marca y se desmarca) o ``"opcion"`` (una de varias seguidas).
- ``(etiqueta, [entradas…])``: un submenú con sus propias entradas.
- ``(etiqueta, "clave")``: un submenú que la ventana rellena sola
  (``"recientes"``, ``"ejemplos"``, ``"plantas"``).

Todos los textos van marcados con ``N_`` (se traducen al crear el menú) para
que el extractor de cadenas los vea. En cada menú ninguna letra de acceso se
repite, y ningún atajo se repite en toda la ventana.
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import N_

NORMAL = "normal"
CASILLA = "casilla"
OPCION = "opcion"

Entrada = Any
Menu = tuple[str, list[Entrada]]

MENUS: list[Menu] = [
	(
		N_("&Archivo"),
		[
			("nuevo", N_("&Nuevo entorno...\tCtrl+N"), N_("Crea un entorno con el asistente: en blanco o a partir de una plantilla.")),
			("abrir", N_("&Abrir...\tCtrl+O"), N_("Abre un entorno guardado (un fichero .elab).")),
			(N_("Abrir e&jemplo"), "ejemplos"),
			(N_("&Recientes"), "recientes"),
			None,
			("guardar", N_("&Guardar\tCtrl+S"), N_("Guarda el entorno abierto.")),
			("guardar_como", N_("Guardar &como...\tCtrl+Shift+S"), N_("Guarda el entorno con otro nombre o en otra carpeta.")),
			None,
			(
				N_("&Importar"),
				[
					("importar_osm", N_("&OpenStreetMap..."), N_("Crea un borrador de exterior con las calles de un lugar real.")),
					("importar_dxf", N_("Plano &DXF..."), N_("Convierte un plano de CAD en una planta, eligiendo capas y escala.")),
					("importar_svg", N_("Plano &SVG..."), N_("Convierte un dibujo vectorial en una planta, indicando su escala.")),
					(
						"importar_imagen",
						N_("&Imagen de fondo..."),
						N_("Pone un plano escaneado debajo del plano gráfico, con dos puntos de calibración."),
					),
					("importar_gpx", N_("Ruta &GPX..."), N_("Coloca una ruta o unos puntos grabados sobre un exterior georreferenciado.")),
				],
			),
			(
				N_("&Exportar"),
				[
					(
						"exportar_paquete",
						N_("&Paquete para el alumno..."),
						N_("Comprueba el entorno y guarda una copia lista para el alumno, con sus actividades."),
					),
					(
						"exportar_texto",
						N_("&Descripción en texto..."),
						N_("Guarda la descripción completa del entorno en texto, Markdown o HTML."),
					),
					(
						"exportar_svg",
						N_("Plano SVG &visual..."),
						N_("Guarda el plano de cada planta, a escala, para ver o imprimir en tinta."),
					),
					(
						"exportar_tactil",
						N_("Plano &táctil..."),
						N_("Guarda el plano de cada planta para lámina en relieve, con su leyenda en braille."),
					),
					("exportar_geojson", N_("&GeoJSON..."), N_("Guarda el entorno en GeoJSON para otros programas de mapas.")),
					("exportar_dxf", N_("D&XF..."), N_("Guarda el plano de cada planta en DXF para programas de CAD.")),
				],
			),
			None,
			("propiedades_entorno", N_("&Propiedades del entorno..."), N_("Nombre, descripción, autor y procedencia del entorno.")),
			None,
			("salir", N_("&Salir"), N_("Cierra la aplicación aunque esté activada la opción de cerrar a la bandeja.")),
		],
	),
	(
		N_("&Editar"),
		[
			("deshacer", N_("&Deshacer\tCtrl+Z"), N_("Deshace la última operación.")),
			("rehacer", N_("&Rehacer\tCtrl+Y"), N_("Vuelve a hacer la última operación deshecha.")),
			None,
			("editar", N_("&Propiedades del elemento...\tF4"), N_("Abre el formulario del elemento seleccionado (también con Intro).")),
			("duplicar", N_("D&uplicar\tCtrl+D"), N_("Crea una copia del elemento seleccionado, medio metro al este.")),
			("renombrar", N_("Re&nombrar...\tF2"), N_("Cambia el nombre del elemento seleccionado.")),
			("mover", N_("&Mover...\tCtrl+M"), N_("Desplaza el elemento seleccionado unos metros, o lo lleva a un punto.")),
			("girar", N_("&Girar...\tCtrl+G"), N_("Gira el elemento seleccionado los grados que se indiquen.")),
			("medidas", N_("Cambiar m&edidas...\tCtrl+R"), N_("Cambia el ancho, el fondo y el alto del elemento seleccionado.")),
			("borrar", N_("&Borrar"), N_("Borra el elemento seleccionado y lo que depende de él (también con Suprimir).")),
			None,
			("buscar", N_("Bu&scar elemento...\tCtrl+F"), N_("Busca un elemento por su nombre y lo selecciona.")),
			("fijar_inicio", N_("Poner aquí el &inicio"), N_("Pone el punto de inicio del recorrido en el elemento seleccionado.")),
		],
	),
	(
		N_("&Insertar"),
		[
			("insertar_planta", N_("&Planta...\tCtrl+Shift+P"), N_("Añade una planta de edificio o un plano de calle.")),
			(
				"insertar_habitacion",
				N_("&Habitación por medidas...\tCtrl+Shift+H"),
				N_("Crea una habitación rectangular diciendo sus medidas."),
			),
			(
				"insertar_adosada",
				N_("Habitación &adosada a otra...\tCtrl+Shift+A"),
				N_("Crea una habitación pegada a otra, compartiendo pared."),
			),
			("insertar_poligonal", N_("&Espacio poligonal..."), N_("Crea un espacio de cualquier forma escribiendo sus esquinas.")),
			None,
			(
				"insertar_abertura",
				N_("Puerta, hueco, &ventana o portal...\tCtrl+Shift+U"),
				N_("Abre una puerta, un hueco, una ventana o un portal en una pared."),
			),
			("insertar_pared", N_("Pared &suelta..."), N_("Añade un tabique, una valla o un muro entre dos puntos.")),
			None,
			("insertar_escalera", N_("Esca&lera..."), N_("Une dos plantas con una escalera.")),
			("insertar_rampa", N_("&Rampa..."), N_("Une dos plantas con una rampa.")),
			("insertar_ascensor", N_("Asce&nsor..."), N_("Une varias plantas con un ascensor.")),
			None,
			(
				"insertar_objeto",
				N_("&Objeto del catálogo...\tCtrl+Shift+O"),
				N_("Busca un objeto en los complementos y lo coloca a escala."),
			),
			("insertar_fuente", N_("&Fuente de sonido...\tCtrl+Shift+F"), N_("Añade un sonido fijo que sirve de referencia.")),
			("insertar_referencia", N_("Referenc&ia...\tCtrl+Shift+R"), N_("Añade un punto de interés o de referencia.")),
			("insertar_zona", N_("&Zona de suelo..."), N_("Añade un trozo de suelo distinto: una alfombra, pavimento táctil.")),
			None,
			(
				N_("E&xteriores"),
				[
					("insertar_calle", N_("&Calle con aceras..."), N_("Crea una calle con su calzada y sus dos aceras.")),
					("insertar_cruce", N_("C&ruce..."), N_("Resuelve el cruce de dos calles que ya existen.")),
					("insertar_paso", N_("&Paso de peatones..."), N_("Añade un paso de peatones a una calle, con o sin semáforo.")),
					("insertar_edificio", N_("&Edificio con portal..."), N_("Añade un edificio macizo con su portal en una fachada.")),
					("insertar_manzana", N_("&Manzana..."), N_("Añade una manzana maciza de cualquier forma.")),
					("insertar_parada", N_("Para&da..."), N_("Marca una parada de autobús, tranvía o taxi.")),
				],
			),
		],
	),
	(
		N_("&Ver"),
		[
			("ver_arbol", N_("Á&rbol del entorno\tAlt+1"), N_("Lleva el foco al árbol del entorno.")),
			("ver_lista", N_("&Lista de elementos\tAlt+2"), N_("Lleva el foco a la lista de elementos.")),
			("ver_propiedades", N_("&Propiedades\tAlt+3"), N_("Lleva el foco al formulario de propiedades del elemento.")),
			("ver_plano", N_("Plano &gráfico\tAlt+4"), N_("Lleva el foco al plano gráfico.")),
			("ver_descripcion", N_("&Descripción del entorno\tAlt+5"), N_("Enseña el entorno entero descrito en texto.")),
			("panel_siguiente", N_("Panel &siguiente\tF6"), N_("Pasa al panel siguiente de la zona de trabajo.")),
			("panel_anterior", N_("Panel a&nterior\tShift+F6"), N_("Pasa al panel anterior de la zona de trabajo.")),
			None,
			(N_("&Ir a planta"), "plantas"),
			("planta_arriba", N_("Planta de &arriba\tAlt+PgUp"), N_("Enseña la planta que está encima de la actual.")),
			("planta_abajo", N_("Planta de a&bajo\tAlt+PgDn"), N_("Enseña la planta que está debajo de la actual.")),
			None,
			("acercar", N_("A&cercar el plano\tCtrl++"), N_("Amplía el plano gráfico.")),
			("alejar", N_("Ale&jar el plano\tCtrl+-"), N_("Reduce el plano gráfico.")),
			("encajar", N_("&Ver todo el plano\tF8"), N_("Ajusta el plano gráfico para que quepa la planta entera.")),
			(
				N_("&Herramienta del plano"),
				[
					("herramienta_seleccion", N_("&Seleccionar y mover"), N_("El clic selecciona y el arrastre mueve."), OPCION),
					(
						"herramienta_habitacion",
						N_("Dibujar una &habitación"),
						N_("Arrastrando un rectángulo se crea una habitación."),
						OPCION,
					),
					("herramienta_pared", N_("Dibujar una &pared"), N_("Con dos clics se crea una pared suelta."), OPCION),
					(
						"herramienta_objeto",
						N_("Colocar un &objeto del catálogo"),
						N_("Un clic abre el catálogo y coloca el objeto elegido en ese punto."),
						OPCION,
					),
				],
			),
			None,
			("cuadricula", N_("C&uadrícula\tCtrl+Shift+G"), N_("Muestra u oculta la cuadrícula del plano."), CASILLA),
			(
				"ajustar_cuadricula",
				N_("Ajus&tar a la cuadrícula"),
				N_("Al dibujar y mover, las posiciones se redondean al paso de la cuadrícula."),
				CASILLA,
			),
			("mostrar_plano", N_("&Mostrar el plano gráfico"), N_("Muestra u oculta el plano gráfico en la zona de trabajo."), CASILLA),
			("barra_estado", N_("Barra de &estado"), N_("Muestra u oculta la barra de estado."), CASILLA),
		],
	),
	(
		N_("&Herramientas"),
		[
			(
				"comprobar",
				N_("&Comprobar el entorno\tF5"),
				N_("Revisa el entorno y enseña los problemas, con dónde están y cómo arreglarlos."),
			),
			(
				"medir",
				N_("&Medir entre dos elementos...\tCtrl+Shift+M"),
				N_("Dice la distancia, el rumbo y el hueco libre entre dos elementos."),
			),
			(
				"amueblar",
				N_("&Amueblar el espacio..."),
				N_("Propone el mobiliario de un espacio según su uso, para revisarlo y aceptarlo."),
			),
			None,
			("recorrer", N_("&Recorrer el entorno\tF9"), N_("Abre el reproductor para recorrer el entorno y colocar cosas andando.")),
			(
				"recorrer_desde",
				N_("Recorrer &desde el elemento seleccionado\tShift+F9"),
				N_("Recorre el entorno empezando junto al elemento seleccionado."),
			),
			("detener_recorrido", N_("De&tener el recorrido"), N_("Cierra el reproductor del modo recorrido.")),
			None,
			(
				"complementos",
				N_("Complementos &instalados..."),
				N_("Lista los complementos de objetos; permite activarlos, desactivarlos, añadirlos y quitarlos."),
			),
			(
				"complementos_en_linea",
				N_("Catálogo en &línea de complementos..."),
				N_("Busca complementos nuevos o actualizados en Internet."),
			),
			("crear_complemento", N_("Crear un complemento &propio..."), N_("Asistente para definir objetos propios y compartirlos.")),
			None,
			("carpeta_datos", N_("Abrir la carpeta de dat&os"), N_("Abre en el Explorador la carpeta data de la aplicación.")),
			("carpeta_registros", N_("Abrir la carpeta de re&gistros"), N_("Abre en el Explorador la carpeta de registros.")),
			None,
			("preferencias", N_("Pre&ferencias...\tCtrl+,"), N_("Abre las preferencias de la aplicación.")),
		],
	),
	(
		N_("Ay&uda"),
		[
			("manual", N_("&Manual de usuario\tF1"), N_("Abre el manual de usuario.")),
			("teclas", N_("&Lista de teclas\tCtrl+F1"), N_("Muestra todos los atajos de teclado.")),
			("novedades", N_("&Novedades de la versión"), N_("Muestra los cambios de cada versión.")),
			("ayuda_contextual", N_("Ayuda del control &enfocado\tCtrl+H"), N_("Explica para qué sirve el control que tiene el foco.")),
			None,
			("actualizaciones", N_("Buscar act&ualizaciones..."), N_("Comprueba si hay una versión nueva de la aplicación.")),
			("pagina_proyecto", N_("&Página del proyecto"), N_("Abre la página del proyecto en el navegador.")),
			("avisar_fallo", N_("Avisar de un &fallo"), N_("Abre en el navegador la página para avisar de un fallo.")),
			(
				"paquete_diagnostico",
				N_("Generar paquete de &diagnóstico..."),
				N_("Reúne los registros y los datos del sistema, sin datos personales, en un ZIP para enviarlo al avisar de un fallo."),
			),
			("cafe", N_("&Invítame a un café si te gusta mi trabajo"), N_("Abre en el navegador la página de donaciones del autor.")),
			None,
			("acerca_de", N_("&Acerca de {nombre}..."), N_("Muestra la versión y los datos técnicos de la aplicación.")),
		],
	),
]

#: Menú de la barra delante del cual se insertan los menús de ``MENUS_SEGUIMIENTO``.
MENU_ANTES_DE = N_("&Herramientas")


def es_submenu(entrada: Entrada) -> bool:
	"""True si la entrada es ``(etiqueta, [entradas])`` o ``(etiqueta, "clave")``."""
	return isinstance(entrada, tuple) and len(entrada) == 2


def normalizar_entrada(entrada: Entrada) -> tuple[str, str, str, str] | None:
	"""Devuelve ``(nombre, etiqueta, ayuda, tipo)`` de una orden, tolerando variantes razonables.

	Admite la forma canónica, un diccionario con esas claves y la forma
	``(etiqueta, atajo, ayuda, nombre)`` (el atajo aparte y el nombre al
	final), para que un menú escrito por otra mano no se quede sin enseñar por
	un detalle de orden. Devuelve ``None`` si no hay forma de entenderla.
	"""
	if isinstance(entrada, dict):
		nombre = str(entrada.get("nombre") or entrada.get("funcion") or "")
		etiqueta = str(entrada.get("etiqueta") or "")
		atajo = str(entrada.get("atajo") or "")
		if atajo and "\t" not in etiqueta:
			etiqueta = f"{etiqueta}\t{atajo}"
		return (nombre, etiqueta, str(entrada.get("ayuda") or ""), str(entrada.get("tipo") or NORMAL)) if nombre and etiqueta else None
	if not isinstance(entrada, (tuple, list)) or len(entrada) < 3:
		return None
	partes = [("" if parte is None else parte) for parte in entrada]
	if not all(isinstance(parte, str) for parte in partes[:4]):
		return None
	if "&" in partes[0] and len(partes) >= 4 and partes[3].isidentifier():
		# (etiqueta, atajo, ayuda, nombre)
		etiqueta = partes[0] if not partes[1] or "\t" in partes[0] else f"{partes[0]}\t{partes[1]}"
		return partes[3], etiqueta, partes[2], NORMAL
	tipo = partes[3] if len(partes) >= 4 and partes[3] in (NORMAL, CASILLA, OPCION) else NORMAL
	return partes[0], partes[1], partes[2], tipo


def ordenes(menus: list[Menu]) -> list[tuple[str, str, str, str]]:
	"""Todas las órdenes de unos menús, también las de los submenús, ya normalizadas."""
	encontradas: list[tuple[str, str, str, str]] = []

	def recorrer(entradas: list[Entrada]) -> None:
		for entrada in entradas:
			if entrada is None:
				continue
			if es_submenu(entrada):
				if isinstance(entrada[1], list):
					recorrer(entrada[1])
				continue
			normal = normalizar_entrada(entrada)
			if normal is not None:
				encontradas.append(normal)

	for _titulo, entradas in menus:
		recorrer(entradas)
	return encontradas
