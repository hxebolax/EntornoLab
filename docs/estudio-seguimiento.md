# El Estudio: seguimiento

Documentación de desarrollo de `app/ui/seguimiento`: fichas de alumnos, editor de actividades, supervisión en vivo, sesiones, informes y cuaderno de evaluación real. La otra mitad del Estudio (ventana principal y construcción de entornos) está en [estudio.md](estudio.md); la lógica que hay debajo, en [seguimiento.md](seguimiento.md), [supervision.md](supervision.md) y `docs/actividades.md`.

Quien usa esta parte es un profesional de rehabilitación que puede ser ciego (lector de pantalla y teclado) o ver (ratón), y trata datos de salud, a menudo de menores. De ahí salen las dos reglas que mandan en todo el paquete:

- **Accesibilidad.** Controles nativos, etiqueta creada justo antes de cada control, letra de acceso en todo, textos largos en campos de solo lectura, nada que se actualice solo roba el foco, y todo lugar se dice en palabras (nunca solo en coordenadas o en un plano).
- **Privacidad.** El nombre real, las notas y las observaciones se guardan cifrados con la contraseña del profesional; la contraseña no se guarda; por la red solo viaja el alias; en los registros no se escribe ningún dato personal.

## Módulos

Sin wx (se prueban sin ventana):

| Módulo | Qué hace |
|---|---|
| `contexto.py` | `ContextoSeguimiento` (la forma del contexto que se necesita, como `Protocol`) y `ContextoDePrueba` |
| `textos.py` | Tablas de nombres (perfil, estilo, modo, ayudas...), formatos y `Letras`, que reparte las letras de acceso |
| `acceso.py` | `AccesoDatos`: contraseña, fichero de acceso, apertura de la base, incorporación de sesiones y caducidad |
| `sala.py` | `GestorSala`: la sala de supervisión única del Estudio y el reparto de sus sucesos |
| `servicio.py` | `ServicioSeguimiento`: lo que comparten las ventanas (acceso, sala, ventanas abiertas, reproductores lanzados) |
| `lugares.py` | Lugares en palabras: listas de plantas, espacios y objetos; punto «junto a», «en una esquina»; `describir_punto` |
| `actividades_api.py` | Puerta única a `app.actividades`, con reserva si falta alguna función |
| `reserva_actividades.py` | Esquema mínimo de reserva (cuatro tipos); es también el esquema de prueba del formulario |
| `sonidos.py` | Lista de sonidos elegibles y `Escucha`, tolerante a que no haya sonido |
| `presentador_alumnos.py` | Filas de la lista, ajustes de juego, cálculo del paso, lista de trabajo, resumen del borrado |
| `presentador_actividades.py` | Filas, copias, `condicion_cumplida`, premios, objetivos, ayudas, niveles, paquete para el alumno |
| `presentador_supervision.py` | Filas y textos de la sala y de los alumnos, frases de los sucesos, qué se anuncia |
| `presentador_registros.py` | Sesiones (filtros, narración del recorrido), informes (construir, guardar) y cuaderno |

Con wx:

| Módulo | Ventanas y diálogos |
|---|---|
| `comun.py` | `DialogoFormulario`, `DialogoLectura`, `VentanaSeguimiento`, `Reloj`, creadores de controles con su etiqueta |
| `dialogos_acceso.py` | `DialogoCrearContrasena`, `DialogoPedirContrasena`, `DialogoCambiarContrasena`; `asegurar_base` |
| `alumnos.py` | `VentanaAlumnos`, `DialogoAlumno`, `DialogoCalcularPaso`, `DialogoBorrarAlumno`, `DialogoRecompensas`, `DialogoListaTrabajo` |
| `panel_actividades.py` | `PanelActividades`, `DialogoTipoActividad`, `DialogoAsignar`, `DialogoExportarPaquete` |
| `formulario_actividad.py` | `DialogoActividad`: el formulario generado del esquema |
| `campos.py` | Un `EditorCampo` por tipo de campo y el registro `EDITORES` |
| `selector_lugar.py` | `PanelLugar`, `DialogoLugar`, `DialogoElemento` |
| `editor_premios.py` | `PanelPremios`, `DialogoPremio`, `DialogoRepartir`, `DialogoColocarRecorriendo` |
| `editor_objetivos.py` | `PanelObjetivos`, `DialogoObjetivo` |
| `editor_ayudas.py` | `PanelAyudas`, `DialogoAyudas`, `DialogoNiveles`, `DialogoNivel` |
| `supervision.py` | `VentanaSupervision`, `DialogoPista`, `DialogoAnuncios`, `DialogoSesionLocal` |
| `sesiones.py` | `VentanaSesiones`, `DialogoSesion`, `DialogoRecorrido` |
| `informes.py` | `VentanaInformes` |
| `cuaderno.py` | `VentanaCuaderno`, `DialogoEvaluacion`, `DialogoRuta` |
| `plano_simple.py` | `PlanoSimple`: dibujo pequeño y solo visual (no recibe el foco) |
| `integracion.py` | El punto de enganche con la ventana principal |

Regla del paquete: la lógica va en los módulos sin wx (presentadores) y las ventanas solo crean controles y llaman. Lo que una ventana enseña sale de una función de un presentador que se puede probar con diccionarios.

## Punto de integración

La ventana principal solo conoce `app.ui.seguimiento.integracion`:

```python
MENUS_SEGUIMIENTO: list                                  # menús «A&lumnos» y «&Supervisión»
crear_panel_actividades(padre, contexto) -> wx.Window    # pestaña «Actividades»
mostrar_alumnos(contexto)
mostrar_supervision(contexto)
mostrar_sesiones(contexto, alumno_id=None)
mostrar_informes(contexto, alumno_id=None, sesion_id=None)
mostrar_cuaderno(contexto, alumno_id=None)
cambiar_contrasena(contexto) -> bool
bloquear_datos(contexto)
empezar_sesion_local(contexto)
anuncios_supervision(contexto)
al_cerrar(contexto)                                      # ventanas, sala, reproductores y base
```

`MENUS_SEGUIMIENTO` usa el formato de `app/ui/menus.py`: cada menú es `(título, entradas)` y cada entrada es `(nombre_de_funcion, etiqueta, ayuda)` o `None` para un separador; la función es una de este módulo y recibe el contexto. Letras de menú: L (Alumnos) y S (Supervisión). Atajos: Control+L, Control+T, Control+I, Control+U y F7.

Las funciones `mostrar_*` devuelven la ventana (o `None` si se cancela la contraseña). Cada ventana se abre una sola vez: si ya existe se trae al frente.

Del contexto se usa, por su forma (`contexto.ContextoSeguimiento`, sin importar `app.ui.contexto`): `ventana`, `entorno`, `ruta_paquete`, `actividades`, `catalogo`, `configuracion`, `marcar_modificado`, `guardar`, `anunciar`, `lanzar_reproductor` y `suscribir`. Si existen, también `recursos` o `anadir_recurso` (el audio grabado de un premio), `modificado`, `actividad_actual` con `emitir` (para que el plano dibuje la actividad elegida) y `letras_ocupadas` (letras de los menús que el panel no puede repetir).

El panel de actividades edita `contexto.actividades` en el sitio y llama a `contexto.marcar_modificado(...)` tras cada cambio. No guarda referencias al entorno: lo lee del contexto en cada acción.

## Flujo de la contraseña

Todo está en `acceso.AccesoDatos` (sin wx) y `dialogos_acceso.asegurar_base` (los diálogos).

1. **Estados** (`AccesoDatos.estado()`): `sin_contrasena` (primera vez, con `privacidad.cifrar_fichas` activada), `bloqueada` (hay contraseña y no se ha escrito en esta sesión de trabajo), `abierta`, y `sin_cifrar` (preferencia apagada y sin contraseña creada: se abre sin preguntar).
2. **Crear.** `DialogoCrearContrasena` explica en un campo de solo lectura que la contraseña no se guarda y que, si se pierde, los campos cifrados no se pueden recuperar; pide la contraseña dos veces (mínimo 8 caracteres). `crear_contrasena` genera una sal, deriva la clave con `cifrado.derivar_clave` (scrypt), abre la base con `abrir_base(ruta, clave=..., cifrar=cifrado.cifrar, descifrar=cifrado.descifrar)` y guarda la sal y un comprobante (`cifrado.crear_comprobante`) en `data/config/seguimiento_acceso.json`. Si la base ya tenía datos sin cifrar, `BaseSeguimiento` los cifra al abrirla con clave. Si el fichero no se puede escribir, se deshace el cifrado: sin él no habría forma de comprobar la contraseña la próxima vez.
3. **Pedir.** `DialogoPedirContrasena` deriva la clave con la sal guardada y la compara con el comprobante (`cifrado.clave_correcta`) antes de tocar la base. Si no es la buena lo dice, vacía el campo y deja el foco en él.
4. **Una vez por sesión de trabajo.** La base abierta queda en el `ServicioSeguimiento`; `asegurar_base` la devuelve sin preguntar mientras siga abierta.
5. **Bloquear.** `bloquear_datos` cierra las ventanas que enseñan datos, cierra la base y suelta la clave. La supervisión no se cierra: por la sala solo viaja el alias.
6. **Cambiar.** `cambiar_contrasena` comprueba la actual, escribe el fichero nuevo como `.nuevo`, recifra con `BaseSeguimiento.cambiar_cifrador` (una transacción) y solo entonces sustituye el fichero. Si falla cualquier paso se conserva la contraseña anterior. Después deja una copia de seguridad nueva.
7. **Al abrir** se incorporan las sesiones de `data/sessions` (`incorporar_sesiones`, borrando el fichero, que va sin cifrar) y, si `privacidad.caducidad_dias` es mayor que cero, se borran las sesiones caducadas. Lo hecho se anuncia en una frase.

La derivación de la clave tarda décimas de segundo y se hace en el hilo de la interfaz con el cursor de espera: es una sola vez por sesión y no merece un diálogo de progreso.

Lo que la contraseña **no** protege: el alias, el resumen y el recorrido de las sesiones, el año de nacimiento y las rutas del cuaderno (ver «Privacidad» en [seguimiento.md](seguimiento.md)). La ficha lo dice junto a cada campo.

## Editor de actividades

`DialogoActividad` se genera de `campos_de(tipo)`:

- una pestaña por `grupo`, en el orden en que aparecen los grupos (título en `presentador_actividades.TITULOS_GRUPO`);
- un editor por campo, según su `tipo` (`campos.EDITORES`);
- la `ayuda` del campo queda como texto de ayuda de sus controles: Control+H la dice;
- un campo con `depende_de` se atenúa mientras su casilla esté apagada, y atenuado no se valida ni se guarda;
- las claves con punto (`mensajes.inicio`) se leen y escriben en diccionarios anidados;
- el modo (juego, práctica o examen) no viene en el esquema: se añade a la pestaña General, y queda fijo en los tipos de examen;
- las claves que el formulario no conoce se conservan tal cual.

Al aceptar: primero cada editor valida lo suyo (`ErrorCampo` lleva el control, y el diálogo cambia a su pestaña y le da el foco); después `validar_actividad`. Si hay errores se enseñan y se elige entre «Corregir» (foco en el campo que deduce `campo_de_aviso`, y en la fila del premio u objetivo que falla) y «Guardar de todos modos».

Las letras de acceso de un formulario generado no se pueden escribir a mano: las reparte `textos.Letras`, que da a cada etiqueta su primera letra libre, sin repetir las de los botones de fuera de las pestañas. `afirmar_teclado_correcto` lo comprueba en las pruebas con todos los tipos reales.

### Cómo añadir un editor de campo

Para un tipo de campo nuevo del esquema (por ejemplo `color`):

1. Escriba en `campos.py` una clase que herede de `EditorCampo`:

```python
class EditorColor(EditorCampo):
	"""Un color elegido de una lista corta."""

	def crear(self) -> None:
		self.anadir_etiqueta()                      # SIEMPRE justo antes del control al que nombra
		self.control = wx.Choice(self.padre, choices=[_("Rojo"), _("Verde")], name=self.nombre)
		self.anadir_control(self.control)           # lo añade al sizer y lo apunta como control principal

	def poner(self, valor: Any) -> None:
		self.control.SetSelection(1 if valor == "verde" else 0)

	def leer(self) -> str:                          # lanza ErrorCampo(mensaje, control) si no vale
		return ("rojo", "verde")[self.control.GetSelection()]
```

2. Apúntela: `EDITORES["color"] = EditorColor` (o `campos.registrar("color", EditorColor)`).
3. Añada el tipo a algún campo de `reserva_actividades.campos_de`: la prueba `test_todos_los_tipos_de_campo_tienen_editor_en_el_esquema_de_prueba` exige que el esquema de prueba use todos los editores, y `test_formulario_generado_del_esquema_de_prueba` lo abre y le pasa la revisión de teclado.

Reglas de un editor: controles nativos; la etiqueta con `self.etiqueta()` (que pone los dos puntos y la letra de acceso); todo control creado se añade a `self.ventanas` (lo hacen `anadir_etiqueta` y `anadir_control`) para que el formulario pueda atenuarlo; si el valor ocupa más de una clave, redefina `cargar` y `volcar` (como `EditorAyudas`, que además guarda `niveles`). Un tipo que no tenga editor se enseña con `EditorDesconocido`, de solo lectura, y su valor no se toca.

### Premios

`PanelPremios` es una lista de cinco columnas en la que el lugar se lee en palabras («Dormitorio, dentro de Armario»). Tres formas de colocar:

- **Elegir el lugar** (`DialogoPremio` con `PanelLugar`): planta, espacio y «dentro de un objeto» (solo los contenedores de ese espacio, según el catálogo), «junto a» un objeto, puerta o referencia, «en el centro», «en una esquina» o coordenadas. Un campo de solo lectura dice el lugar resultante.
- **Repartir automáticamente** (`DialogoRepartir`): cuántos, en qué plantas, visibilidad y si pueden ir dentro de objetos; «Generar la vista previa» llama a `repartir_premios` con otra semilla cada vez y enseña el resultado en una lista antes de aceptar.
- **Colocar recorriendo** (`DialogoColocarRecorriendo`): guarda el entorno, abre una sala local en un puerto libre, lanza `--recorrido <paquete> --sala 127.0.0.1:<puerto> --codigo <código>` y espera una `peticion` (`marcar_punto` o `colocar_aqui`) del reproductor. Toma su posición, le contesta para que oiga «Premio colocado aquí» y abre el diálogo del premio con ese lugar. Si no se puede (entorno sin guardar, sin reproductor) el botón lo explica al pulsarlo en vez de estar atenuado: un botón atenuado no recibe el foco y un lector no puede leer por qué no funciona. Esta sala es independiente de la del modo recorrido de la ventana principal (`app/ui/recorrido.py`).

El audio grabado de un premio se lee del fichero elegido y se añade al paquete con `contexto.anadir_recurso` o `contexto.recursos` como `sonidos/<nombre>`.

## Supervisión en vivo

Mismo patrón que el panel de servidor de JuegoGTA: la sala va en su hilo y la ventana solo lee y pide.

- `GestorSala` guarda la única `Sala` del Estudio. `sondear()` vacía `Sala.eventos_pendientes()` y entrega cada suceso a todos los que escuchan (`escuchar`), lo llame el temporizador que lo llame. Así la ventana de supervisión y «Colocar recorriendo» no se quitan sucesos.
- `VentanaSupervision.refrescar()` (cada 500 ms, con `comun.Reloj`) llama a `sondear()`, toma `foto()` y repinta. No espera a la red. Abrir la sala en red (que crea el certificado) va en un hilo (`comun.en_segundo_plano`).
- **Sin molestar.** La lista de alumnos no se reconstruye: se actualizan celdas (`ListaAccesible.actualizar_fila` no repinta lo que no cambia) y se añaden filas al final. Los campos de solo lectura solo se reescriben si el texto cambia y conservan el cursor (`poner_texto`, `anadir_linea`). Ninguna actualización llama a `SetFocus`.
- **Voz.** `presentador_supervision.frases_a_anunciar` filtra por los tipos elegidos (`supervision.eventos_anunciados`, con el interruptor general `supervision.anunciar_eventos`), da frases breves y resume si hay más de dos en un refresco. Se dicen con `contexto.anunciar`, sin interrumpir. Todo lo anunciado está también en la lista de sucesos.
- **Órdenes.** Cada botón tiene su atajo (tabla de `instalar_atajos`) y usa `Sala.pedir`, que vuelve al momento. El resultado se dice, porque el foco no se mueve. Recolocar y añadir un premio usan los selectores de lugar y necesitan tener abierto en el Estudio el entorno del alumno.
- **Marcas.** `GestorSala.marcar` envía la orden `marca`; el reproductor la pasa a su `Grabadora` y queda, cifrada, en la sesión al incorporarla.
- **Cortafuegos y segunda salida.** El estado de la sala en red incluye el aviso del cortafuegos. La casilla de la segunda salida solo guarda `supervision.segunda_salida` y lo explica; quien la aplica es el reproductor.
- **La ficha hacia el reproductor.** `ServicioSeguimiento` escucha la sala desde que se crea: con cada `conectado`/`reconectado` de un alias con ficha (y la base abierta) envía la orden `alumno` (`presentador_alumnos.datos_para_reproductor`: ajustes de juego, estilo, lista de trabajo y niveles; nunca nombre real ni notas). `enviar_ficha(alumno)` la reenvía cuando cambia: lo llaman la ventana de alumnos al guardar la ficha o la lista de trabajo, el panel de actividades al asignar, y `asegurar_base` al abrir los datos (con las sesiones recién incorporadas). Ver [supervision.md](supervision.md).
- **Preferencias hacia el reproductor.** `preferencias.mostrar_preferencias` pasa `al_aplicar` al diálogo; si lo guardado lo usa el reproductor, `avisar_reproductores` pide `releer_configuracion` a todos los conectados (`ServicioSeguimiento.releer_configuracion_en_reproductores`), solo si el servicio ya existe.
- **Reproductores que se cierran.** `ServicioSeguimiento.lanzar` pasa cada proceso a `GestorSala.vigilar(proceso, alias)`; el suceso `proceso_terminado` lo dicen la ventana de supervisión (y lo apunta en los sucesos del alumno) o, si está cerrada, el panel de actividades: «El reproductor de Luna se ha cerrado», y si fue inesperado, «… inesperadamente; puede volver a abrirlo» (este se dice siempre, aunque no se hayan elegido los anuncios de conexión).
- **Probar ahora con un alumno.** Con los datos de alumnos ya abiertos y alguna ficha, «Probar ahora» pregunta «Probar como» (`DialogoProbarComo`); con un alumno, abre una sala local si no la hay y lanza el reproductor con `--alumno`, que recibe su ficha al conectarse. Mientras quede un reproductor vivo, el panel sondea la sala (`Reloj` de 500 ms), aunque la ventana de supervisión esté cerrada. Sin los datos abiertos no se pregunta: probar no pide la contraseña.

`comun.Reloj` es un `wx.Timer` que no pertenece a la ventana: si la ventana se destruye con el temporizador en marcha, el siguiente tic lo nota y se para. Se evita así atender `EVT_WINDOW_DESTROY`, que con un temporizador propio de un diálogo provocó un fallo nativo en las pruebas.

## Sesiones, informes y cuaderno

- **Sesiones.** Filtros por alumno, entorno, actividad, modo y fechas (texto, como `2026-11-20` o `20/11/2026`). El detalle enseña el informe de sesión en un campo de solo lectura, las notas (cifradas) y las marcas. «Repetir el recorrido» pone `informes.describir_recorrido` en una lista de un paso por elemento, en metros o en pasos del alumno.
- **Informes.** Cinco tipos; vista previa en texto; guardar en TXT, HTML o CSV (`informes.guardar`) y abrir el HTML en el navegador. El fichero temporal que se abre en el navegador se borra en `al_cerrar`. Todos llevan el aviso `informes.AVISO`.
- **Cuaderno.** Una evaluación tiene fecha, lugar, entorno relacionado, rutas con resultado, nivel de ayuda, tipo de recorrido, ayudas de movilidad y observaciones (cifradas). Los días desde el último entrenamiento se calculan (`cuaderno.dias_desde_ultima_sesion`) y se enseñan en un campo de solo lectura. «Comparar con el simulador» enseña `informe_real_frente_virtual`.

## Pruebas

`tests/test_ui_seguimiento_acceso.py`, `_alumnos.py`, `_actividades.py`, `_supervision.py` y `_registros.py`; utilidades en `tests/_ui_seguimiento_util.py` (`equipo`: contexto de prueba con base, fichero de acceso y sala en la carpeta temporal; `casa()`: entorno con un armario contenedor; `responder_con`: rellena un diálogo y lo acepta; `revisar`: `afirmar_teclado_correcto`).

```
.venv\Scripts\python.exe -m pytest tests -q -k "ui_seguimiento"
.venv\Scripts\python.exe -m pytest tests -q -k "ui_seguimiento" -m interfaz
```

- Las ventanas se construyen sin mostrarse (`comun.mostrar_al_abrir = False`) y los diálogos modales se contestan con `dialogo_modal`.
- El cifrado es el de verdad (`app/core/cifrado.py`): las pruebas leen el fichero de la base y comprueban que el nombre real, las notas y las observaciones no están en claro.
- La supervisión se prueba con una `Sala` real y un `ClienteSupervision` real en `127.0.0.1`.
- El formulario se prueba con el esquema de reserva y, si `app.actividades` está, con todos sus tipos.
- Cada ventana y diálogo pasa `afirmar_teclado_correcto`.

No se ha podido verificar aquí: lo que dice un lector de pantalla real (NVDA, JAWS), la supervisión entre dos ordenadores, el cortafuegos de Windows y el reproductor real atendiendo las órdenes.
