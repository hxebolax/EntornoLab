# El Estudio: construcción de entornos

Este documento describe cómo está hecha la aplicación del profesional (wxPython) y cómo ampliarla. El contrato general entre módulos está en [arquitectura.md](arquitectura.md); el formato de los entornos, en [formato-de-entornos.md](formato-de-entornos.md).

El Estudio lo forman dos mitades que se escriben por separado:

- **Construcción de entornos** (`app/ui/`, salvo `app/ui/seguimiento/`): ventana principal, menús, árbol, lista, propiedades, plano gráfico, catálogo de objetos, complementos, importar, exportar, preferencias y modo recorrido.
- **Seguimiento** (`app/ui/seguimiento/`): alumnos, editor de actividades, supervisión en vivo, sesiones, informes y cuaderno de evaluación.

La ventana principal y la barra de menús son de la primera mitad. La segunda se engancha por un único punto, descrito en «Integración del seguimiento».

## Módulos

Sin wx (se prueban sin ventana):

| Módulo | Qué hace |
|---|---|
| `app/ui/contexto.py` | `ContextoEstudio`: el documento abierto y los servicios comunes |
| `app/ui/menus.py` | La tabla de menús y su formato |
| `app/ui/esquemas.py` | `Campo` y las utilidades de formulario: números con coma, letras de acceso, validación |
| `app/ui/esquemas_elementos.py` | El esquema de propiedades de cada clase de elemento y de cada diálogo de «Insertar» |
| `app/ui/operaciones.py` | Lo que hace cada orden sobre el entorno: árbol, filas de la lista, aplicar propiedades, plantillas, búsqueda |
| `app/ui/archivos.py` | Recientes, carpeta de entornos, autoguardado de recuperación |
| `app/ui/modelo_plano.py` | Geometría del plano gráfico: conversión de coordenadas, selección por punto, arrastre |
| `app/ui/recorrido.py` | Modo recorrido: la sala local, el reproductor hijo y la atención de las peticiones |
| `app/ui/complemento_propio.py` | Construcción, miniatura, guardado y empaquetado de un complemento propio |

Con wx:

| Módulo | Qué hace |
|---|---|
| `app/ui/ventana_principal.py` | Ventana, barra de menús, zona de trabajo, archivos, cierre |
| `app/ui/formulario.py` | `Formulario` y `DialogoFormulario`: formularios generados de un esquema |
| `app/ui/plano.py` | `PanelPlano`: el plano gráfico |
| `app/ui/dialogos_insertar.py` | Diálogos del menú Insertar y del menú Editar |
| `app/ui/dialogo_catalogo.py` | «Insertar objeto» del catálogo |
| `app/ui/dialogo_complementos.py` | Complementos instalados |
| `app/ui/asistente_complemento.py` | Asistente «Crear un complemento propio» |
| `app/ui/dialogos_herramientas.py` | Comprobar, medir, amueblar y buscar |
| `app/ui/recorrido_wx.py` | Temporizador y diálogos del modo recorrido |
| `app/ui/dialogo_progreso.py` | Progreso por hitos con cancelación |
| `app/ui/dialogos_importar.py`, `app/ui/dialogos_exportar.py` | Importar y exportar |
| `app/ui/preferencias.py` | Preferencias |
| `app/ui/accesibilidad/` | Controles y utilidades accesibles (lista con lectura por columnas, casillas, diálogos, ayuda de Control+H, revisión del teclado) |

## ContextoEstudio

`app.ui.contexto.ContextoEstudio` es el único objeto que comparten todas las partes. No importa wx.

Atributos:

| Atributo | Contenido |
|---|---|
| `ventana` | La ventana principal (`wx.Frame`), o `None` en pruebas sin interfaz. Úsela como padre de los diálogos |
| `entorno` | El `Entorno` abierto, o `None` |
| `ruta_paquete` | `Path` del `.elab` abierto, o `None` si aún no se ha guardado |
| `actividades` | Lista de diccionarios de actividad del paquete abierto. El panel de actividades la edita en el sitio |
| `recursos` | Recursos del paquete: nombre interno (`sonidos/x.ogg`, `imagenes/plano.png`) → bytes |
| `catalogo` | El `Catalogo` de complementos cargado |
| `configuracion` | La `Configuracion` |
| `tareas` | El `GestorTareas` del Estudio, para el trabajo en segundo plano |
| `historial` | El `Historial` de deshacer y rehacer del entorno |
| `modificado` | `True` si hay cambios sin guardar |
| `seleccion` | Id del elemento (o de la planta) elegido; cadena vacía si no hay |
| `planta_id` | Id de la planta que se está viendo |
| `actividad_actual` | Actividad elegida en el panel de actividades, o `None`. El plano dibuja sus premios y su inicio |

Métodos:

| Método | Qué hace |
|---|---|
| `ejecutar(nombre, operacion, anuncio=None)` | Hace un cambio en el ENTORNO que se puede deshacer. Guarda el estado, llama a `operacion()`, marca modificado, emite `entorno_cambiado` y anuncia. Si `operacion` lanza una excepción, el entorno queda como estaba y la excepción sigue |
| `deshacer()`, `rehacer()` | Devuelven el nombre de la operación, o `None` |
| `marcar_modificado(nombre_operacion="")` | Para cambios del paquete que NO son del entorno: las actividades. Marca modificado y emite `actividades_cambiadas` |
| `guardar(ruta=None) -> bool` | Guarda el paquete (entorno, actividades, recursos). Sin ruta conocida abre «Guardar como». Nunca lanza |
| `anunciar(texto, interrumpir=False)` | Frase breve por el lector de pantalla y en la barra de estado |
| `lanzar_reproductor(argumentos) -> Proceso` | Arranca el reproductor como proceso hijo (`app.core.procesos`) |
| `suscribir(evento, funcion) -> cancelar` | Se llama a `funcion()` cuando ocurre el evento. Devuelve la función para darse de baja |
| `emitir(evento)` | Avisa a los suscritos |
| `seleccionar(id)`, `elemento_seleccionado()` | Selección compartida por el árbol, la lista y el plano |
| `planta_actual()`, `ir_a_planta(id)` | Planta que se ve |
| `abrir_documento(entorno, ruta=None, actividades=None, recursos=None, modificado=False)` | Pone un entorno como documento abierto |
| `cerrar_documento()` | Deja el Estudio sin entorno |
| `paso_libre()` | Paso libre mínimo, en metros, de las preferencias |
| `letras_ocupadas()` | Letras de acceso de los menús de la barra y cifras 1 a 5 (Alt+1 a Alt+5 llevan a los paneles), que ningún control de la ventana principal puede repetir |
| `anadir_recurso(nombre, datos)` | Añade un recurso al paquete (un sonido grabado, una imagen) |
| `recargar_catalogo()` | Vuelve a leer los complementos y emite `catalogo_cambiado` |

Eventos: `entorno_abierto`, `entorno_cerrado`, `entorno_cambiado`, `actividades_cambiadas`, `seleccion_cambiada`, `planta_cambiada`, `documento_cambiado` y `catalogo_cambiado`. Las funciones suscritas se llaman sin argumentos, en el hilo de la interfaz; si declaran un parámetro obligatorio reciben el contexto.

Regla importante: el objeto `entorno` se **sustituye** por otro al deshacer, rehacer y abrir. No guarde referencias al entorno, a una planta ni a un elemento entre dos eventos: guarde el `id` y búsquelo de nuevo con `contexto.entorno.buscar(id)`.

## Formato de la tabla de menús

La barra se construye a partir de `MENUS`, en `app/ui/menus.py`. Es una lista de menús `(título, entradas)`. Cada entrada es:

- `None`: un separador.
- `(nombre, etiqueta, ayuda)`: una orden.
  - `nombre`: identificador de la orden. En los menús propios es el sufijo del método `VentanaPrincipal._al_<nombre>`. En `MENUS_SEGUIMIENTO` es el nombre de una función del módulo `app.ui.seguimiento.integracion`, que se llama con el `ContextoEstudio` como único argumento.
  - `etiqueta`: texto con `&` delante de su letra de acceso y, si tiene atajo, un tabulador y la combinación en inglés, que es como la entiende wx: `N_("&Guardar\tCtrl+S")`.
  - `ayuda`: frase que explica la orden.
- `(nombre, etiqueta, ayuda, tipo)`: lo mismo, con `tipo` igual a `"casilla"` u `"opcion"`.
- `(etiqueta, [entradas])`: un submenú.

Ejemplo:

```python
from app.core.i18n import N_

MENUS_SEGUIMIENTO = [
	(
		N_("A&lumnos"),
		[
			("mostrar_alumnos", N_("&Fichas de alumnos...\tCtrl+L"), N_("Abre las fichas de los alumnos.")),
			None,
			("mostrar_sesiones", N_("&Sesiones..."), N_("Lista las sesiones guardadas.")),
		],
	),
]
```

Reglas:

- Todos los textos van marcados con `N_` (se traducen al crear el menú).
- En cada menú y submenú, ninguna letra de acceso se repite.
- Los menús de la barra usan estas letras: A (Archivo), E (Editar), I (Insertar), V (Ver), H (Herramientas) y U (Ayuda). Los menús de seguimiento tienen que usar otras.
- Atajos ya usados por la ventana principal, que no se pueden repetir: Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+Mayús+S, Ctrl+Z, Ctrl+Y, F4, Ctrl+D, F2, Ctrl+M, Ctrl+G, Ctrl+R, Ctrl+F, Ctrl+Mayús+P, Ctrl+Mayús+H, Ctrl+Mayús+A, Ctrl+Mayús+U, Ctrl+Mayús+O, Ctrl+Mayús+F, Ctrl+Mayús+R, Alt+1 a Alt+5, F6, Mayús+F6, Alt+RePág, Alt+AvPág, Ctrl+más, Ctrl+menos, F8, Ctrl+Mayús+G, F5, Ctrl+Mayús+M, F9, Mayús+F9, Ctrl+coma, F1, Ctrl+F1 y Ctrl+H. Tampoco se usan las teclas reservadas: F10, Mayús+F10, Alt+F4, Ctrl+Tab, Ctrl+1 a Ctrl+0 ni nada con Insert.
- Los menús de seguimiento se insertan en la barra delante de «Herramientas».

## Integración del seguimiento

La ventana principal importa `app.ui.seguimiento.integracion` de forma tolerante: si el módulo no existe o falla al importarse, lo apunta en el registro y funciona sin esos menús. Del módulo usa, si están:

| Nombre | Uso |
|---|---|
| `MENUS_SEGUIMIENTO` | Menús que se añaden a la barra, con el formato de arriba |
| `crear_panel_actividades(padre, contexto) -> wx.Window` | Página «Actividades» del cuaderno de la zona de trabajo. `padre` es el `wx.Notebook` |
| `mostrar_alumnos(contexto)`, `mostrar_supervision(contexto)`, `mostrar_sesiones(contexto)`, `mostrar_informes(contexto)`, `mostrar_cuaderno(contexto)` | Funciones de las órdenes de menú |
| `al_cerrar(contexto)` | Se llama al cerrar la ventana principal, antes de destruirla, para cerrar la sala, parar tareas y guardar |

Lo que debe cumplir el panel de actividades:

- Sus etiquetas y botones llevan letra de acceso y no repiten las de los menús de la barra (`contexto.letras_ocupadas()` las da en el momento).
- Después de tocar `contexto.actividades` llama a `contexto.marcar_modificado("nombre de la operación")`.
- Si quiere que el plano dibuje los premios y el inicio de una actividad, la pone en `contexto.actividad_actual` y llama a `contexto.emitir("actividades_cambiadas")`.
- Se suscribe a `entorno_abierto` y `entorno_cerrado` para rellenarse y vaciarse.

Si el título de un menú de seguimiento repite la letra de otro menú de la barra, la ventana le busca una letra libre en vez de dejarlo inalcanzable, y entiende también las entradas escritas en otro orden razonable (`menus.normalizar_entrada`). Una orden de seguimiento que lanza una excepción se registra y se explica en un mensaje; la ventana sigue viva.

## La ventana principal

`VentanaPrincipal(configuracion, instancia=None, catalogo=None, tareas=None, lanzador=None)`. Los tres últimos argumentos son para las pruebas: un catálogo ya cargado, un gestor de tareas y un doble de la función que arranca el reproductor.

La zona de trabajo es un `wx.Notebook` con tres páginas:

- **Entorno**: a la izquierda el árbol (`wx.TreeCtrl`), la lista de elementos (`ListaAccesible`) y la frase que describe el elemento elegido; en el centro el plano gráfico (`PanelPlano`); a la derecha el formulario de propiedades (`Formulario`) con «Aplicar cambios» y «Descartar cambios».
- **Descripción**: el entorno entero en texto (`edicion.describir_entorno`), en un campo de solo lectura. Si hay una actividad elegida, al final van su inicio y dónde está cada premio (`modelo_plano.describir_actividad`), lo mismo que dibuja el plano. Se pone al día con `actividades_cambiadas`.
- **Actividades**: el panel de la otra mitad, si está.

Cómo se mantiene la sincronía. La selección vive en `contexto.seleccion`. Quien la cambia llama a `contexto.seleccionar(id)`, que emite `seleccion_cambiada`; la ventana mueve entonces los otros paneles con una guarda (`_sincronizando`) para que sus propios eventos no vuelvan a disparar el cambio.

- Árbol → lista, propiedades y plano: al moverse por el árbol, la lista se rellena con los elementos de ese nodo (`operaciones.elementos_de_nodo`).
- Lista → árbol, propiedades y plano: la lista no se vuelve a rellenar mientras la persona se mueve por ella.
- Plano → árbol, lista y propiedades.

El árbol lógico (`operaciones.arbol_de`) se calcula una vez por cambio del entorno y se guarda en `_arbol_logico`; la lista (`elementos_de_nodo(..., arbol)`) y las búsquedas lo reutilizan. Los nodos nativos del `wx.TreeCtrl` no se borran y se rehacen: se SINCRONIZAN con el árbol lógico (`_poner_nodo`, `_poner_hijos`), reutilizando por posición los que ya hay y sin tocar los subárboles que no han cambiado, conservando qué nodos estaban desplegados y cuál estaba elegido. Con más de `LIMITE_ARBOL_COMPLETO` nodos (1.500) los hijos de cada espacio y de cada grupo se crean al desplegarlo (`EVT_TREE_ITEM_EXPANDING`); `_asegurar_item(clave)` los crea cuando hay que llevar la selección a un nodo que aún no existe. El formulario de propiedades no se rehace mientras la persona está escribiendo en él; si el elemento nuevo tiene los mismos campos que el anterior se reutilizan los controles, y los formularios de los últimos dieciséis tipos de elemento se guardan ocultos (`Formulario.guardar_cuerpos`).

La lista de elementos es virtual (`ListaAccesible(virtual=True)` con `reemplazar_proveedor`): una planta de un barrio tiene miles de filas y solo se componen las que el control pide (`operaciones.FilasPerezosas`).

Las letras de acceso de la página «Entorno» se reparten al crearla (`esquemas.con_letra`), partiendo de las letras de los menús que haya en la barra en ese momento: así no chocan aunque el seguimiento añada menús. Si a una etiqueta no le queda ninguna letra libre recibe una cifra («Material (6)»).

### Archivos

- Título: `*Nombre - EntornoLab` cuando hay cambios sin guardar.
- `confirmar_descartar()` pregunta con los botones «Guardar», «No guardar» y «Cancelar» antes de cerrar, abrir, crear o adoptar otro entorno.
- `adoptar_borrador(entorno, nombre, recursos=None)` pone un entorno recién creado o importado como documento nuevo, sin ruta y modificado.
- Un ejemplo se abre como documento nuevo: guardar no escribe encima del fichero que viene con el programa.
- Recientes: `editor.recientes` en la configuración (`app/ui/archivos.py`).
- Copia de recuperación: cada `editor.autoguardado_min` minutos, si hay cambios, se escribe `data/temp/recuperacion/<id>.elab` sin tocar el documento. Se borra al guardar y al cerrar con normalidad. Al arrancar, `ofrecer_recuperacion()` pregunta «Recuperar», «Descartar la copia» o «Cancelar».
- Si un `.elab` está dañado y existe su `.bak`, se ofrece abrir la copia.
- Un `.elab` recibido por la línea de órdenes o de una segunda instancia se abre con `abrir_archivos`.
- Complementos que faltan: al abrir un paquete (o recuperar una copia), `avisar_complementos_que_faltan()` cuenta con `operaciones.complementos_que_faltan(entorno, catalogo)` los objetos cuyo `tipo` es de un complemento no instalado. Esos objetos se conservan y se dibujan como cajas con sus medidas. Se avisa UNA vez con un mensaje accesible (`elegir_opcion`, título «Complementos que faltan») que los nombra y pregunta «¿Buscar en el catálogo en línea?». Solo con «Buscar en el catálogo en línea» se abre `dialogo_complementos_en_linea.mostrar_complementos_en_linea(ventana, al_cambiar=contexto.recargar_catalogo, buscar=id)` (filtrado por el id si falta uno solo); abrirlo es la acción explícita que permite descargar el catálogo. Con «Cerrar» no se intenta ninguna conexión.
- Recursos: `contexto.recursos` (audios grabados de los premios, imágenes de fondo) viaja entero en cada guardado, también tras abrir, deshacer y volver a guardar.

## Rendimiento con entornos grandes

El caso de referencia es un barrio importado de OpenStreetMap: 3.000 espacios, 2.000 puertas, 2.600 referencias y más de 1.400 objetos. `tests/_entornos_grandes.py` los genera sin red a partir de la muestra real de `tests/datos` y `tests/test_rendimiento_estudio.py` (marcada `lento`) comprueba los presupuestos de tiempo.

- **Índice espacial por planta.** `Planta.espacios_en` y `espacio_en` usan `IndiceEspacios` (rejilla de cajas, `app/dominio/indice_espacial.py`), guardado en la planta y rehecho solo si cambia la lista de espacios (`ListaEspacios.version`) o se sustituye un contorno (`Espacio.__setattr__`, `invalidar_indices()`). Da exactamente lo mismo que `espacios_en_exhaustivo`. Regla: un contorno se SUSTITUYE (`espacio.contorno = [...]`); quien lo cambie en el sitio llama a `invalidar_indices()`.
- **Una pasada por planta.** `operaciones.contenido_de_planta` y `edicion.aberturas_por_espacio` sitúan cada elemento una vez (y recuerdan lo ya situado mientras los espacios no cambien), en lugar de preguntar por cada pareja espacio-elemento. `describir_entorno`, `vecinos` y la validación usan el índice.
- **Lotes de comprobación.** `colocacion.lote_de_comprobaciones()` calcula una vez por planta las paredes y las zonas de paso de las puertas para todos los objetos que se comprueban (validación y amueblado).
- **Historial.** Cada operación guarda el entorno de antes como diccionario (`a_dict`, optimizado); al deshacer y rehacer, el entorno que se deja se guarda tal cual, sin convertirlo.
- **Plano.** La parte fija se pinta en un mapa de bits que se reutiliza mientras no cambien el entorno ni la vista; la selección y los gestos van encima. Solo se dibujan las figuras que se ven y, con más de `LIMITE_DETALLE` (1.500) a la vista, sin letras ni símbolos menudos.
- **Segundo plano.** `app/ui/espera.py` decide: con un entorno de más de `UMBRAL_ELEMENTOS` (1.500) elementos, «Comprobar el entorno», las comprobaciones antes de exportar y las exportaciones van a un hilo con el diálogo de progreso; la página «Descripción» se compone en segundo plano sin diálogo y se descarta si el entorno cambió entretanto (`contexto.version`).

Tiempos medidos con 3.000 espacios (antes de estos cambios, con 350 espacios, elegir un nodo del árbol tardaba más de tres minutos con esta muestra y entre 10 y 12 s con la del usuario): elegir en el árbol o en la lista, de 3 a 80 ms (la primera vez que se ven las propiedades de un tipo de elemento, hasta 0,12 s, porque se crean sus controles); abrir, 0,5 s; mover o deshacer, de 0,1 a 0,26 s; comprobar el entorno, 1,8 s en segundo plano.

## Cómo añadir un tipo de elemento

1. Añada la clase al modelo (`app/dominio/modelo.py`) y sus funciones de edición (`app/dominio/edicion.py`), con sus pruebas.
2. En `app/ui/operaciones.py`: su nombre de tipo (`nombre_tipo`), sus textos de medidas y posición (`texto_medidas`, `texto_posicion`), sus valores (`valores_de`) y cómo se aplican (`aplicar_valores`, usando las funciones de edición cuando existan). Si no cuelga de un espacio, decida en `arbol_de` en qué grupo sale.
3. En `app/ui/esquemas_elementos.py`: su esquema de propiedades (una función `_esquema_…` y su línea en `esquema_de`) y una entrada en `ORDENES` para insertarlo: título, campos, valores de partida, nombre para el historial y la función que lo crea.
4. En `app/ui/menus.py`: la entrada del menú Insertar. Si su `nombre` es la clave de `ORDENES`, no hace falta escribir ningún manejador.
5. En `app/ui/modelo_plano.py`: su figura en `figuras_de_planta`, y en `app/ui/plano.py` cómo se pinta.
6. Documente el atajo, si lo tiene, en `data/docs/teclas.md` y pase `tools/comprobar_teclas.py`.

Las pruebas `test_cada_clase_de_elemento_tiene_esquema_y_valores` y `test_teclado_de_cada_dialogo_de_orden` fallan si falta algo de lo anterior.

## Cómo añadir un diálogo

- Si es un formulario, declare sus campos con `c(...)` (`app/ui/esquemas.py`) y ábralo con `pedir_formulario(padre, título, campos, valores, validar)`. `validar` recibe los valores ya convertidos; si lanza `ErrorCampo` el foco va a ese campo, y si lanza otro `ValueError` (un `ErrorEdicion`, por ejemplo) se enseña su mensaje y el diálogo sigue abierto. Para un cambio del entorno, haga dentro `contexto.ejecutar(nombre, operación)`.
- Tipos de campo: `texto`, `largo`, `metros`, `decimal`, `entero`, `si_no`, `opcion`, `casillas`, `deslizador`, `ruta_fichero`, `ruta_carpeta` y `solo_lectura`. `grupo` reparte los campos en pestañas, `si` los condiciona y `recarga` reconstruye el formulario al cambiar ese campo. Las etiquetas se escriben sin `&`: la letra se reparte sola.
- Si necesita una lista u otros controles, use `crear_campo` (etiqueta justo antes del control), `ListaAccesible`, `crear_botonera` y `preparar_dialogo` de `app/ui/accesibilidad`, y dele métodos con nombre (`fijar`, `aceptar`…) para manejarlo en las pruebas.
- Nunca `wx.SpinCtrlDouble`, `wx.SearchCtrl`, `wx.grid.Grid` ni `wx.lib.agw`. Los números van en `wx.TextCtrl` validados, con coma o punto decimal (`esquemas.leer_numero`).
- Añada una prueba con `afirmar_teclado_correcto(dialogo)`.

## Tres formas de colocar

- **Por medidas**: los formularios de Insertar piden metros («habitación de 4 por 3», «puerta a 1,20 de la esquina oeste»).
- **Por relación**: «Habitación adosada a otra» (lado y alineación), puerta «en la pared norte», objeto «contra una pared», «en una esquina» o «junto a otro elemento» (`app/ui/dialogo_catalogo.py`).
- **Recorriendo**: el modo recorrido, abajo.

Al colocar un objeto se ensaya antes sobre una copia del entorno. Si no cabe ni con la variante menor ni encogido dentro de su rango, se explica y no se coloca nada ni se apunta en el historial. Si cabe pero tapa una puerta o deja un paso estrecho (`editor.paso_libre_m`), se pregunta con «Dejarlo así» o «Quitarlo».

## Catálogo de objetos y complementos

«Insertar objeto» (`DialogoCatalogo`) está pensado para más de mil objetos: un `wx.TreeCtrl` de clasificación (Todos, Favoritos, Usados recientemente y complemento → categoría → subcategoría, con recuentos), búsqueda por texto ordenada por relevancia, filtros combinables (ámbito, lugar, estancia, función, tipo de obstáculo, «puede esconder un premio», «tiene sonido propio»), lista virtual, recuento escrito y anunciado una vez por filtrado, favoritos (Ctrl+D), objetos relacionados y miniatura solo de la fila enfocada. Usa `Catalogo.arbol()`, `facetas()` y `relacionados()` si existen y, si no, lo calcula con las fichas. Favoritos y recientes se guardan en `data/config/catalogo_uso.json`.

«Complementos instalados» filtra por nombre o categoría y activa o desactiva sin reiniciar (`complementos.desactivados`). Los complementos añadidos desde un `.elabc` o creados con el asistente se apuntan como «del usuario» en `data/config/complementos.json`, que es lo que permite quitarlos. El asistente «Crear un complemento propio» pide también la clasificación y deja la lógica sin wx en `app/ui/complemento_propio.py`.

## Modo recorrido

`Herramientas ▸ Recorrer el entorno` (F9) crea un `ControladorRecorrido` (`app/ui/recorrido_wx.py`) sobre una `SesionRecorrido` (`app/ui/recorrido.py`, sin wx):

1. Guarda el paquete. Si el entorno aún no tiene fichero, se recorre desde `data/temp/recorrido/<id>.elab`, sin darle ruta al documento.
2. Abre una `Sala` local (`red=False`, puerto libre, código generado).
3. Lanza el reproductor con `contexto.lanzar_reproductor(["--recorrido", paquete, "--sala", "127.0.0.1:<puerto>", "--codigo", código])` y, al recorrer desde un elemento, `"--inicio", "planta,x,y,rumbo"`.
4. Un `wx.Timer` (150 ms) atiende los sucesos de la sala. Cada `peticion` se resuelve y se contesta con `Sala.responder(alumno, id, aceptada, texto, **datos)`.

El protocolo solo tiene tres acciones de `peticion`; lo demás viaja en `datos` (ver «Modo recorrido» en [reproductor.md](reproductor.md)):

| Opción del menú de edición del reproductor (F4) | `accion` | `datos` | Qué hace el Estudio |
|---|---|---|---|
| Colocar un objeto aquí | `colocar_aqui` | `clase: "objeto"`, `objeto`, `nombre` | `colocacion.colocar_en_punto`; si no cabe, lo dice y no lo coloca. Sin `objeto`, abre el catálogo con la posición ya puesta |
| Poner un premio aquí | `colocar_aqui` | `clase: "premio"`, `nombre` | Añade el premio a la actividad elegida en la pestaña Actividades; si no hay ninguna, lo explica |
| Poner aquí el inicio | `colocar_aqui` | `clase: "inicio"` | `edicion.fijar_inicio` |
| Marcar este punto | `marcar_punto` | `nombre` | Crea una referencia |
| Medir desde aquí y hasta aquí | `medir_desde_aqui` | `fase: "desde"` o `"hasta"`, `distancia_m` | Fija el origen y, después, dice la distancia y hacia dónde queda |

Cada respuesta lleva un `texto` corto, que el reproductor dice, y tras un cambio aceptado `datos.recargar = true` y `datos.paquete`: el reproductor vuelve a leer el paquete del disco y sigue en el mismo punto. Cuando el cambio se hizo en la ventana del Estudio y no por una petición, el Estudio guarda y envía la orden `reiniciar`, que en el modo recorrido hace lo mismo.

Mientras hay recorrido, cada cambio hecho en el Estudio se guarda y se avisa (`ControladorRecorrido.al_cambiar_entorno`).

## Plano gráfico y equivalencias con el teclado

El plano (`app/ui/plano.py`) dibuja a escala la planta actual con doble búfer: espacios con su nombre y su trama, paredes, puertas con su arco, ventanas, objetos con su huella real, su letra y su color, fuentes, referencias, conectores, vías, pasos de peatones, premios e inicio de la actividad elegida, imagen de fondo, cuadrícula y regla. En alto contraste usa solo colores del sistema. Nada depende solo del color.

Los premios son los de `contexto.actividad_actual`: el plano se repinta con `actividades_cambiadas` (al elegir otra actividad o tocar sus premios). Un premio con `dentro_de` se dibuja en el centro de su objeto con trazo discontinuo (`Figura.tipo == "dentro"`). Lo que el plano dibuja de la actividad se lee también en texto: al final de la página «Descripción» y en la ayuda del plano (Control+H), con `PanelPlano.descripcion_actividad()`.

«Comprobar el entorno» (F5, `dialogos_herramientas.avisos_del_documento`) valida el entorno y cada actividad del paquete con `validar_actividad(..., recursos=contexto.recursos)`, que avisa del audio de un premio que no está en el paquete. Los avisos de una actividad llevan su nombre delante y, como un premio no es un elemento del plano, no ofrecen «Ir al elemento».

Un lienzo no es accesible para el lector de pantalla. Por eso todo lo que hace el plano se puede hacer sin él:

| En el plano, con el ratón | Sin el plano |
|---|---|
| Clic: seleccionar | Elegir en el árbol o en la lista; Editar ▸ Buscar elemento (Ctrl+F) |
| Arrastrar: mover | Editar ▸ Mover (Ctrl+M), o cambiar la posición en Propiedades |
| Flechas en el plano: mover un paso | Editar ▸ Mover (Ctrl+M) |
| Doble clic: propiedades | Intro en el árbol o en la lista; F4 |
| Botón derecho: menú contextual | Tecla Aplicaciones o Mayús+F10 en el árbol o en la lista |
| Dibujar una habitación arrastrando | Insertar ▸ Habitación por medidas (Ctrl+Mayús+H) |
| Dibujar una pared con dos clics | Insertar ▸ Pared suelta |
| Clic con la herramienta de objeto | Insertar ▸ Objeto del catálogo (Ctrl+Mayús+O) |
| Rueda: zoom | Ver ▸ Acercar y Alejar (Ctrl+más, Ctrl+menos) |
| Botón central o Espacio y arrastrar: desplazar | Ver ▸ Ver todo el plano (F8) |
| Ver dónde está cada cosa | Página «Descripción» (Alt+5), la frase del elemento elegido y Herramientas ▸ Medir |
| Ver los problemas | Herramientas ▸ Comprobar el entorno (F5) |

## Preferencias

`app/ui/preferencias.py` genera el diálogo de la tabla `app/ui/esquema_preferencias.py`: un `Campo` por clave de configuración, con `grupo` como pestaña. Para añadir una preferencia, añádala a `app/core/configuracion.py` (valor, regla y prueba) y a esa tabla; una prueba falla si una clave no interna se queda sin campo.

Paquete de sonido: Preferencias ▸ Sonido tiene la lista de paquetes (`app.audio.paquetes.listar()`), la descripción del elegido y «Escuchar una muestra del paquete». Al aceptar se guarda `sonido.paquete` en `config.json`, que comparten el Estudio y el reproductor. El cambio se aplica en caliente en el proceso que tiene un banco de sonidos enlazado (`paquetes.conectar`), es decir, en el reproductor: uno que esté en marcha lo recoge cuando relee la configuración (cuando el Estudio se lo ordena por la sala o al volver a su menú) y, en todo caso, lo usa el siguiente que se abra. El Estudio no envía hoy esa orden por su cuenta al cambiar la preferencia: la relectura es cosa del reproductor y de la supervisión.
