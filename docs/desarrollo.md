# Desarrollo de EntornoLab

Guía para quien programa, prueba, traduce y publica EntornoLab. El contrato entre módulos está en [arquitectura.md](arquitectura.md); las convenciones de código, en [CONTRIBUTING.md](../CONTRIBUTING.md). Este documento no viaja con la aplicación: la documentación de usuario está en `data/docs`.

## Requisitos

- Windows de 64 bits.
- Python 3.15 de 64 bits (con el lanzador `py`).
- Nada más: todas las dependencias se instalan en el entorno virtual del proyecto.

## Montar el entorno

1. Abra una consola en la carpeta del proyecto.
2. Ejecute `entorno.bat crear`. Crea `.venv` con Python 3.15 e instala `requirements.txt` y `requirements-dev.txt`.
3. Compruebe el resultado con `entorno.bat diagnostico`: muestra las versiones de Python, wxPython, pygame-ce, numpy, sounddevice, cryptography y cx_Freeze, y si están OpenAL Soft y el lector de pantalla.

`entorno.bat` sin argumentos abre un menú numerado. Con una orden, la ejecuta y devuelve un código de salida (0 es correcto), de modo que sirve en otros guiones.

Órdenes de `entorno.bat`:

- `crear`: crea o repara el entorno virtual e instala dependencias.
- `instalar`: instala las dependencias en el entorno existente.
- `actualizar`: sube las dependencias a la última versión permitida.
- `ejecutar`: abre el Estudio desde el código, sin consola.
- `depurar`: abre el Estudio con consola y registro en modo DEBUG.
- `jugar`: abre el reproductor desde el código. Admite argumentos: `entorno.bat jugar data\ejemplos\vivienda-de-ejemplo.elab --alumno ana`.
- `pruebas`: ejecuta las pruebas. Admite argumentos de pytest: `entorno.bat pruebas -m lento`.
  Las pruebas que miden tiempos de respuesta (marcador `rendimiento`) no entran en la batería normal, porque con el equipo ocupado por otras pruebas sus tiempos no significan nada. Se ejecutan solas y con el equipo libre: `entorno.bat pruebas -m rendimiento`.
- `comprobar`: pasa ruff, compara los atajos con la lista de teclas, comprueba las notas de la versión y el estado de los idiomas, y arranca el Estudio y el reproductor con `--comprobar-arranque`. Si existe una versión compilada, arranca también sus dos ejecutables.
- `sonidos`: genera el paquete de sonidos por defecto en `data\sounds\por_defecto` (y `data\sounds\catalogo.json`). El paquete «Natural» se genera aparte, con `tools\generar_paquete_sonidos.py` (ver `docs\sonido.md`).
- `ejemplos`: genera los entornos de ejemplo en `data\ejemplos`.
- `idiomas`: extrae las cadenas, actualiza los catálogos, los compila e informa de lo pendiente.
- `compilar`: compila con cx_Freeze, verifica, prueba el arranque y empaqueta en ZIP.
- `compilar-debug`: compila con consola, para ver errores de arranque.
- `empaquetar`: vuelve a crear el ZIP y `version.json` a partir de la compilación existente.
- `limpiar`: borra compilaciones y cachés. No toca `.venv` ni `data`.
- `datos`, `registros`: abren esas carpetas en el Explorador.
- `diagnostico`: describe el entorno.
- `congelar`: guarda las versiones exactas instaladas en `requirements-lock.txt`.

## Ejecutar

- Estudio: `entorno.bat ejecutar`, o `.venv\Scripts\python.exe main.py`.
- Reproductor: `entorno.bat jugar`, o `.venv\Scripts\python.exe jugar.py`. Es lo mismo que `main.py --jugar`.
- Comprobación sin ventanas: `main.py --comprobar-arranque` y `jugar.py --comprobar-arranque` arrancan, no muestran nada y salen con 0 si todo fue bien.

Argumentos del reproductor (con `jugar.py`, o con `main.py --jugar`):

- `[paquete] [--actividad id] [--alumno alias] [--sala equipo:puerto --codigo c] [--inicio planta,x,y,rumbo]`
- `--recorrido paquete --sala equipo:puerto --codigo c` para el modo recorrido.
- `--guion fichero.json [--informe informe.json] [paquete ...]`: sin ventana ni sonido, sigue los pasos del guion, sale con un código y deja un informe JSON (ver [reproductor.md](reproductor.md#sin-ventana-y-modo-guion)).

Variables de entorno útiles:

- `APP_DATA_DIR`: usa otra carpeta en lugar de `data`. Las pruebas la fijan siempre; sirve también para tener un perfil aparte.
- `APP_IDIOMA`: fuerza un idioma (`set APP_IDIOMA=en`) sin tocar la configuración.
- `APP_DEPURACION=1`: registro en DEBUG y copia de los mensajes en la consola. La pone `entorno.bat depurar`.
- `APP_SIN_SONIDO=1`: motor de sonido nulo (`app/audio/fabrica.py`). `APP_SIN_VOZ=1`: sin voz (`app/audio/voz.py`).
- `APP_SIN_VENTANA=1`: el reproductor arranca sin ventana ni sonido (controladores «dummy» de SDL, motor nulo, voz que solo apunta y sin mandos; es `Aplicacion(pruebas=True)`). Como los procesos hijos heredan el entorno, el Estudio lanza así reproductores reales en las pruebas.
- `APP_GUION` y `APP_GUION_INFORME`: equivalen a `--guion` y `--informe` del reproductor; `APP_GUION` implica `APP_SIN_VENTANA`. Sirven para dar un guion al reproductor que lanza el Estudio («Probar ahora», «Recorrer el entorno»...) sin cambiar sus argumentos.
- `APP_GUION_MOTOR`: motor de sonido del guion (`openal`, `bass`, `clasico`, `estereo` o `nulo`), abierto «en memoria», sin tarjeta; manda sobre la clave `motor` del guion.

### Orden de arranque

`main.py` y `jugar.py` comparten `app/core/arranque.py` y siguen el mismo orden:

1. `multiprocessing.freeze_support()`.
2. Registro, solo con la biblioteca estándar, antes de importar nada pesado.
3. Configuración e idioma.
4. La aplicación: el Estudio crea `wx.App`, fija el idioma de wx y comprueba la instancia única; el reproductor llama a `app.reproductor.arranque.ejecutar(argumentos)`.

El reproductor sale antes de la instancia única y nunca importa wx. Todo va dentro de una red de seguridad: si el arranque falla, se escribe `data\logs\arranque_fallido.log` y se muestra un cartel.

## Dónde mirar cuando algo falla

Todo está en `data\logs`:

- `incidencias.log`: avisos y errores del Estudio de todas las sesiones. Es el primer sitio donde mirar.
- `sesion_AAAAMMDD_HHMMSS.log`: todo lo de una sesión del Estudio. El `.jsonl` del mismo nombre contiene lo mismo, un JSON por línea.
- `jugar_AAAAMMDD_HHMMSS_pPID.log`: una sesión del reproductor. Cada reproductor abierto tiene el suyo; no escriben en `incidencias.log`.
- `no_controladas\`: una excepción no controlada por archivo, escrita al instante.
- `fallo_nativo.log` y `fallo_nativo_jugar.log`: volcado si el proceso muere por un fallo de una biblioteca nativa.
- `arranque_fallido.log`: fallos del propio arranque.

`app.core.diagnostico.generar_paquete()` crea en `data\diagnostico` un ZIP con los registros y los datos del sistema, sin configuración, fichas, sesiones ni entornos, y con el nombre de la cuenta de Windows borrado de las rutas.

## Infraestructura común (`app/core`)

Resumen de lo que ofrece cada módulo. Los detalles están en la docstring de cada uno.

### Rutas (`paths.py`)

Toda ruta de datos sale de aquí; nunca se escribe una ruta absoluta ni se usa `os.getcwd()`. Cada función devuelve la carpeta y la crea si falta.

- Se distribuyen: `ruta_binarios()` (`bin`), `ruta_sonidos()` (`sounds`), `ruta_traducciones()` (`locales`), `ruta_documentacion()` (`docs`), `ruta_iconos()` (`icons`), `ruta_complementos()` (`plugins`), `ruta_ejemplos()` (`ejemplos`).
- No se distribuyen: `ruta_configuracion()` (`config`), `ruta_registros()` (`logs`), `ruta_base_datos()` (`db`), `ruta_sesiones()` (`sessions`), `ruta_entornos()` (`entornos`), `ruta_cache()`, `ruta_temporales()`, `ruta_copias()`, `ruta_diagnostico()`.

### Configuración (`configuracion.py`)

```python
from app.core.configuracion import obtener_configuracion

config = obtener_configuracion()
motor = config.obtener("sonido.motor")
config.establecer("sonido.volumen_maestro", 0.8)          # valida, guarda y avisa
config.establecer_diferido("voz.velocidad", 60)            # agrupa el guardado (deslizadores)
config.establecer_varias({"juego.paso_m": 0.7, "juego.unidad": "pasos"})
cancelar = config.suscribir(self._al_cambiar, prefijo="sonido.")
```

- El archivo es `data\config\config.json`. Los valores por defecto están en `VALORES_POR_DEFECTO` y las reglas de tipo y rango en `REGLAS`.
- `establecer` lanza `ErrorValidacion` si el valor no es válido. `guardar()` devuelve `True` o `False` y nunca lanza.
- Un archivo dañado se aparta como `config.json.corrupto-FECHA` y se recupera `config.json.bak`.
- Al cerrar la aplicación se llama a `guardar_pendiente()`.
- Estudio y reproductor son dos procesos con el mismo archivo: quien necesite ver lo que guardó el otro llama a `cargar()`.
- `app.core.config` es el nombre antiguo y reexporta lo mismo.

Secciones: `general`, `ventana`, `registro`, `sonido`, `voz`, `juego`, `teclado`, `mando`, `editor`, `supervision`, `privacidad`, `accesibilidad`, `actualizaciones`, `complementos` e `importar`. Cada clave está comentada en `VALORES_POR_DEFECTO`.

Para añadir una preferencia:

1. Añada su valor por defecto en `VALORES_POR_DEFECTO` (su tipo es el tipo esperado).
2. Si tiene rango o lista cerrada, añada una `Regla` en `REGLAS`.
3. Léala con `obtener` donde se use y, si debe aplicarse sin reiniciar, suscríbase.
4. Si cambia el nombre de una clave que ya existe, suba `VERSION_ESQUEMA` y escriba la migración en `MIGRACIONES`.

### Secretos y cifrado (`secretos.py`, `cifrado.py`)

- `secretos.AlmacenSecretos`: secretos de este equipo, cifrados con DPAPI en `data\config\secretos.dat`. No viajan a otro ordenador.
- `cifrado`: datos personales de las fichas, cifrados con la contraseña del profesional para que viajen con la carpeta. `derivar_clave(contrasena, sal)` usa `hashlib.scrypt`; `cifrar(datos, clave)` y `descifrar(datos, clave)` usan AES-256-GCM del paquete `cryptography` y lanzan `ErrorCifrado`. `derivar_clave` es lenta a propósito: llámela desde una tarea de fondo.

### Registro (`registro.py`, `vigilante_ui.py`, `diagnostico.py`)

- En cada módulo: `log = logging.getLogger(__name__)` y mensajes con formato diferido (`log.info("Cargado %s", nombre)`).
- `configurar_registro()` solo se llama en el arranque del Estudio; `configurar_registro_auxiliar()`, en el del reproductor.
- `registro.operacion("importar")` marca y mide una operación; `registro.registrar_secreto(valor)` oculta un valor en todos los registros; `registro.vaciar()` espera a que lo registrado esté en disco.
- Las trazas guardan solo rutas relativas (`registro.acortar_rutas_de_traza`); lo que se envía sustituye las carpetas del equipo por marcadores (`registro.anonimizar_rutas`). Ver [Privacidad del entorno de desarrollo](#privacidad-del-entorno-de-desarrollo).
- `diagnostico.generar_paquete()` deja en `data\diagnostico` un ZIP con los últimos registros anonimizados y `sistema.txt`, sin configuración, fichas, sesiones ni entornos. Lo piden Ayuda, «Generar paquete de diagnóstico» del Estudio (en una tarea de fondo) y la última línea de la ayuda de Jugar.
- `vigilante_ui.iniciar()` detecta congelaciones del hilo de la interfaz y deja la pila culpable en el registro.
- `app/ui/dialogo_error.py` muestra un diálogo accesible ante una excepción no controlada.

### Tareas y procesos (`tareas.py`, `procesos.py`)

- `GestorTareas.enviar(funcion, ..., al_terminar=, al_fallar=, al_progresar=)` ejecuta trabajo en un hilo y entrega las respuestas en el hilo de la interfaz. La tarea llama a `tarea.comprobar()` entre pasos para poder cancelarse. `@en_interfaz` y `ejecutar_en_interfaz` llevan una llamada al hilo de la interfaz.
- `procesos.lanzar_reproductor(argumentos)` arranca el reproductor como proceso hijo del Estudio y devuelve un `Proceso` con `vivo()`, `terminar()` y `esperar()`. El hijo entra en un Job Object de Windows: si el Estudio muere, Windows lo cierra. `Proceso.terminado_por_el_estudio` dice si lo cerró el propio Estudio; `GestorSala.vigilar(proceso, alias)` (`app/ui/seguimiento/sala.py`) avisa con el suceso `proceso_terminado` cuando un reproductor termina, y de si fue inesperado.

### El hilo de la interfaz: qué puede ir en él

Mientras el hilo de la interfaz está ocupado, el lector de pantalla se queda mudo y Windows marca la ventana como «No responde». Reglas:

- **Ninguna acción puede tenerlo ocupado más de 100 ms** con un entorno de 3.000 espacios (la referencia: un barrio importado de OpenStreetMap). Lo vigilan `tests/test_rendimiento_estudio.py` y `tests/test_rendimiento_reproductor.py` (marcadas `lento`), y en uso real `vigilante_ui` anota en el registro cualquier bloqueo de más de 3 s con la pila culpable.
- **Primero, mejores algoritmos**: nada de recorrer todos los espacios por cada elemento (usar `Planta.espacios_en`, que tiene índice espacial, o `IndiceEspacios.en_caja`), nada de reconstruir lo que no ha cambiado, listas virtuales y textos que se componen al pedirlos.
- **Editar, deshacer y rehacer ponen al día solo lo afectado**: el historial guarda por diferencias y deshace en el sitio (`app/dominio/diferencias.py`); tras `entorno_cambiado`, `contexto.cambio` dice qué elementos cambiaron y quien enseña el entorno rehace solo eso (ver «Historial por diferencias» en [estudio.md](estudio.md#historial-por-diferencias)). Una operación nueva no declara lo que toca: basta con que pase por `contexto.ejecutar`. Tampoco se le pregunta al control nativo por cada uno de sus miles de nodos (cada llamada al `wx.TreeCtrl` cuesta unos 15 µs).
- **Lo que siga tardando de verdad va a un hilo** con `GestorTareas` y, si la persona tiene que esperar el resultado, con `app.ui.dialogo_progreso.ejecutar_tarea` (o `app.ui.espera.hacer`, que solo lo usa con entornos grandes). El trabajo NUNCA toca wx: los resultados llegan al hilo de la interfaz con `wx.CallAfter` (lo hace el gestor).
- **Cómo informar del progreso**: desde el hilo de trabajo, `dialogo_progreso.informar(tarea, fase, hecho, total)` en cada vuelta (también sirve para cancelar). La fase dice QUÉ se hace y las cifras cuánto («Comprobando los objetos de Calle: 300 de 1424.»). El diálogo escribe el estado y el tiempo transcurrido en un campo de solo lectura, anuncia por voz solo los cambios de fase (con 3 s mínimo entre avisos) y un recordatorio cada 15 s sin novedades, según `voz-y-braille.md` del agente de accesibilidad. Toda operación de más de medio segundo tiene que decir qué está haciendo y dejar cancelar.
- **El trabajo de fondo lee, no escribe**: mientras el diálogo de progreso es modal el entorno no se edita. Lo que se calcula sin diálogo (la página «Descripción») compara `contexto.version` al terminar y se descarta si el entorno cambió.

### Ayuda (`documentacion.py`, `app/ui/visor_ayuda.py`)

- F1 abre `data\docs\manual.md` y Control+F1 abre `data\docs\teclas.md` en un visor no modal con lista de secciones y búsqueda.
- Tras actualizar, se muestran una vez las novedades de `data\docs\novedades.md`. Cada versión se encabeza con `## Versión X.Y.Z - AAAA-MM-DD`.
- `tools\comprobar_teclas.py` compara los atajos del código con `teclas.md`. Las teclas atendidas a mano se marcan en el código con `# atajo: Ctrl+H`.

## Pruebas

- Todas: `entorno.bat pruebas`, o `.venv\Scripts\python.exe -m pytest -q`.
- Una parte: `.venv\Scripts\python.exe -m pytest tests\test_core_i18n.py -q`.
- Sin las lentas: `-m "not lento and not red and not interfaz"`.

Marcadores: `lento` (más de un segundo), `red` (necesita Internet) e `interfaz` (muestra ventanas o envía teclas reales). Por defecto no se ejecutan `red` ni `interfaz`.

Lo que garantiza `tests\conftest.py` sin que la prueba haga nada:

- Cada prueba tiene su propia carpeta `data` vacía. Nunca se toca la real.
- No hay red, salvo conexiones a `127.0.0.1`.
- No hay voz, ni ventanas, ni sonido: pygame usa los controladores «dummy» de SDL y el idioma es siempre el español.
- Un diálogo modal real hace fallar la prueba en vez de colgar la sesión.

Fixtures disponibles:

- `data_temporal` (y su nombre antiguo `datos_temporales`): la carpeta `data` de la prueba.
- `sin_red`: registro de los intentos de conexión bloqueados.
- `app_wx`: la única `wx.App` de la sesión. Ninguna prueba crea otra.
- `marco`, `panel`: un marco sin mostrar y un panel dentro; se destruyen solos.
- `marco_visible`: solo en pruebas marcadas `interfaz`.
- `voz_simulada`: guarda lo que se habría dicho (`textos`, `ultimo`, `contiene`).
- `dialogo_modal`: los diálogos modales devuelven la respuesta programada con `responder(...)`.
- `ayudas_wx`: el módulo `tests.ayudas_wx`, con `simular_tecla`, `esperar_hasta`, `procesar_eventos`, `enviar_orden` y `propiedades_msaa`.

Los paquetes `app/dominio`, `app/motor` y `app/actividades` se prueban sin wx, sin pygame y sin sonido.

Pruebas de proceso real (`tests\test_integracion_proceso_real.py`, marcadas `lento`): el Estudio lanza el reproductor DE VERDAD con `procesos.lanzar_reproductor`, con `APP_SIN_VENTANA=1` y un guion en `APP_GUION`; se conecta a una sala real en `127.0.0.1`, recibe órdenes, termina una actividad y su sesión se incorpora. La fixture `_sin_huerfanos` comprueba que no queda ningún proceso vivo.

En EVT_WINDOW_DESTROY de una ventana creada desde Python, evento.GetEventObject() no es self (wxPython 4.3): compare evento.GetId() con el id guardado. Un wx.Timer(dueño) que sigue en marcha tras destruir su dueño cierra el proceso (0xc0000374 o access violation) en el siguiente Dispatch.

## Traducción

El código se escribe en español. Cada idioma adicional es un catálogo gettext en `data\locales\<idioma>\LC_MESSAGES\entornolab.po`.

### En el código

- `from app.core.i18n import _, _n, N_`.
- Texto para el usuario: `_("&Guardar")`.
- Plurales: `_n("Se encontró {n} premio", "Se encontraron {n} premios", n).format(n=n)`.
- Constantes definidas al importar: se marcan con `N_("Puerta")` y se traducen al mostrarlas con `_(constante)`.
- Frases completas con marcadores con nombre y `.format()` fuera de `_()`. Nunca una f-string dentro de `_()`.
- Un comentario `# Traductores: ...` en la línea anterior llega a quien traduce.
- No se traducen identificadores, claves de configuración ni mensajes del registro.
- Recuentos con `frase_cuenta(n, "{n} calle", "{n} calles")` (`app/importar/comun.py`): el extractor la reconoce como `_n`.
- Un número decimal para mostrar o decir: `.replace(".", separador_decimal())` (`app.core.i18n`), coma en español y punto en inglés.
- Una palabra que en español sirve para dos cosas y en otro idioma no (la tecla «Inicio» y la hora de «Inicio»), con contexto: `pgettext("tecla", "Inicio")`.

### Añadir un idioma

1. `.venv\Scripts\python.exe tools\extraer_cadenas.py`: genera `data\locales\entornolab.pot` con todas las cadenas de `app`, `main.py` y `jugar.py`. Termina con error si alguna cadena no se puede traducir.
2. `.venv\Scripts\python.exe tools\actualizar_po.py --nuevo fr`: crea `data\locales\fr\LC_MESSAGES\entornolab.po` con su regla de plurales.
3. Traduzca el `.po` con Poedit o con un editor de texto: rellene cada `msgstr` sin tocar `msgid`, los marcadores `{nombre}` ni el atajo que sigue al tabulador.
4. `.venv\Scripts\python.exe tools\compilar_traducciones.py`: genera el `.mo`. Una traducción con marcadores distintos del original se omite y se informa como error.
5. `.venv\Scripts\python.exe tools\informe_traducciones.py --detalle`: enumera lo que queda sin traducir, con el archivo y la línea de cada cadena.
6. Pruebe con `set APP_IDIOMA=fr` y `entorno.bat ejecutar`.

`entorno.bat idiomas` hace los pasos 1, 4 y 5 y actualiza todos los catálogos existentes.

Cuando cambie el código: `entorno.bat idiomas`. Las traducciones existentes se conservan, lo nuevo entra vacío, lo que desaparece queda como obsoleto y lo muy parecido se propone como aproximado («fuzzy») para revisarlo.

La aplicación lee el `.mo`; si no existe o el `.po` es más reciente, lee el `.po` directamente con las mismas validaciones. Así quien traduce prueba su trabajo sin compilar. El idioma se elige por este orden: `APP_IDIOMA`, la preferencia `general.idioma`, el idioma de Windows y, si no hay catálogo, español.

### Inglés

El catálogo inglés está completo. Los términos fijos (O&M, nombres del producto, menús de la barra con sus letras de acceso) están en [glosario-traduccion.md](glosario-traduccion.md). `tests/test_traduccion_en.py` comprueba que sigue al 100 %, que conserva marcadores, letras y atajos, que la ventana principal y los diálogos principales no repiten letras de acceso en inglés, que el Estudio y Jugar arrancan en inglés y que F1 abre el manual inglés. Al añadir textos nuevos: `entorno.bat idiomas`, traducirlos en el `.po` y pasar esa prueba.

La documentación de usuario traducida está en `data\docs\<idioma>\` con los mismos nombres de fichero (`data\docs\en\manual.md`, `teclas.md`, `novedades.md`...). `documentacion.ruta_documento` y `dialogo_texto.buscar_documento` buscan primero la del idioma de la interfaz y, si falta, la española. Al cambiar un documento español, actualice también su versión inglesa. `README_en.md` es la traducción de `README.md`.

### Traducir complementos y entornos de ejemplo

Sus textos no están en el código, así que no llegan al catálogo. Cada complemento o ejemplo lleva sus traducciones en `locales\<idioma>.json`:

```json
{
	"textos": {"Mesa": "Table", "Silla": "Chair"},
	"rutas": {"objetos/mesa/descripcion": "A four-legged table."}
}
```

- `textos`: texto en español y su traducción. Solo se aplica a los campos de texto (`nombre`, `descripcion`, `mensajes`, `etiquetas`, `categoria`...).
- `rutas`: traducción de un valor concreto. La ruta une las claves con `/`; un elemento de una lista se nombra por su `id`. Tiene prioridad.

En el código: `i18n.traducir_datos(datos, traducciones)` devuelve una copia traducida; `i18n.traducir_datos_de_carpeta(carpeta, datos)` carga además el fichero del idioma activo.

## Compilar

1. `entorno.bat pruebas` y `entorno.bat comprobar` sin fallos.
2. `entorno.bat compilar`.

Qué hace `compilar`:

1. `tools\antes_de_compilar.py`: compila las traducciones, comprueba que la versión tiene notas en `data\docs\novedades.md` y que el repositorio no lleva rutas del equipo de desarrollo (`tools\comprobar_rutas.py`).
2. `setup_cx.py build`: borra `build\entornolab` y genera `EntornoLab.exe` (Estudio) y `EntornoLabJugar.exe` (reproductor), con los runtimes de Visual C++. Incluye todos los paquetes de `app` (los lee del disco: un paquete nuevo no hay que añadirlo a mano), `basskit` con `bass.dll`, `certifi` y `markdown`, y deja fuera `pygments` y los ejemplos y pruebas de pygame. Al terminar borra el `entornolab.egg-info` que deja setuptools en la raíz.
3. `tools\verificar_build.py`: comprueba los dos ejecutables, las DLL de Visual C++, el catálogo español de wx, las DLL de los lectores de pantalla, SDL2, PortAudio, libsndfile, `bass.dll` de basskit (y que no viaja el basskit completo), `cacert.pem` de certifi, markdown con sus extensiones, cada paquete de `app`, `data\bin\openal\soft_oal.dll` con `alsoft.ini` y los perfiles HRTF, `data\sounds\catalogo.json` y un `pack.json` por paquete de sonidos, al menos un complemento y un ejemplo, el `.mo` de cada `.po` del proyecto, cada licencia enlazada desde `data\docs\licencias\LEEME.md`, que `data` viaja limpia y que nada lleva rutas del equipo de desarrollo (ver [Privacidad del entorno de desarrollo](#privacidad-del-entorno-de-desarrollo)).
4. Arranque de los dos ejecutables con `--comprobar-arranque` y `APP_DATA_DIR=build\comprobacion_data`, una COPIA de la `data` compilada: prueba con los recursos de verdad sin ensuciar la distribución.
5. `tools\verificar_build.py --motores`: en un Python aislado que solo ve `build\entornolab\lib`, abre OpenAL con HRTF (el perfil integrado y uno de `data\bin\openal\hrtf`) y BASS en modo «en memoria». Carga las DLL y los `.pyc` que viajan, sin abrir la tarjeta de sonido ni sonar.
   Después, `tools\verificar_build.py --guion`: ejecuta `EntornoLabJugar.exe` de verdad en modo guion (sin ventana ni sonido), con una copia temporal de la `data` compilada; abre el entorno de ejemplo, empieza su primera actividad y comprueba con el informe que OpenAL (con HRTF) y BASS arrancan en memoria, que hay paquetes de sonidos y que no falta ningún complemento. Unos 8 s.
6. `tools\empaquetar.py`: crea `build\EntornoLab_v<versión>.zip` y `build\version.json` (aplicación, versión, canal, SHA-256, tamaño y fecha; firmado solo si este equipo tiene la clave). El manifiesto para publicar lo prepara `tools\publicar_version.py` (ver [actualizaciones.md](actualizaciones.md)).

Todo funciona sin interacción: `entorno.bat compilar` termina con código 0 o 1.

A `build\entornolab\data` solo viajan `bin`, `sounds`, `locales`, `docs`, `icons`, `plugins` y `ejemplos`. De `locales` solo los `.mo`: la versión compilada no lee los `.po` ni la plantilla `.pot`. Nunca `config`, `logs`, `db`, `sessions`, `entornos`, `cache`, `temp` ni `backups`, ni `__pycache__`. Si ejecuta la copia compilada para probarla, su `data` deja de estar limpia: vuelva a compilar antes de distribuir.

Referencias de la primera compilación real (26-11-2026, versión 0.1.0, Python 3.15 y cx_Freeze 8.7.4): `entorno.bat compilar` completo, unos 70 s (compilación 27-35 s, verificación 0,3 s, cada arranque comprobado 1-4 s, motores 1 s, ZIP 12 s). `build\entornolab` ocupa unos 223 MB en unos 2900 archivos; el ZIP, unos 111 MB; cada ejecutable, 1,4 MB. Lo que más pesa: `lib\wx` (58 MB), `data\sounds` (32 MB), `lib\pygame` (23 MB) y numpy (33 MB con sus DLL).

## Privacidad del entorno de desarrollo

Regla: **la aplicación nunca muestra ni guarda rutas ni datos del equipo donde se desarrolla o se compila**. Ni la carpeta de usuario de quien programa (ni nada bajo ella), ni la carpeta de sus proyectos, ni la de su Python o su entorno virtual, ni su nombre de usuario ni su correo. Vale para el repositorio, para la compilación y para lo que el programa escribe o enseña al ejecutarse. Las rutas del equipo donde se EJECUTA (la carpeta portable de quien usa el programa) sí pueden salir en su propio registro local: es lo que hace falta para ayudarle. Lo que está pensado para enviarse, el paquete de diagnóstico, las sustituye por marcadores.

Cómo se cumple:

- **Repositorio.** Ninguna ruta escrita en el código, las pruebas, la documentación ni los datos generados (`receta.json`, `medidas.json`, `CREDITOS.txt`, inventarios, `.pot`): rutas relativas o marcadores. Las herramientas que necesitan una carpeta del autor la piden con un argumento o una variable de entorno y paran con un mensaje claro si falta: `tools\generar_paquete_sonidos.py` (`--exe` o `GENERADOR_SONIDOS_EXE`), `tools\montar_paquete_grabado.py` (`--fuentes` o `ENTORNOLAB_FUENTES_SONIDO`; `--descargadas` o `ENTORNOLAB_FUENTES_DESCARGADAS`) y `tools\firmar_version.py` (`--clave` o `ENTORNOLAB_CLAVES`; por defecto `~\.entornolab\claves`, calculada, no escrita).
- **Compilación** (`setup_cx.py`):
  - `replace_paths` completo (`rutas_a_reemplazar`): «`*`» y, detrás, las carpetas `site-packages`, la biblioteca estándar, el Python base y el proyecto. «`*`» solo no cubre los paquetes sin `__init__.py` (`win32comext`), cuyos `.pyc` viajaban con la ruta completa del entorno virtual en `co_filename`.
  - `__LIBS__` relativa (`parchear_constantes_cx_freeze`): cx_Freeze guardaba en `BUILD_CONSTANTS` las carpetas de DLL de `sounddevice`, `soundfile` y pywin32 con la ruta absoluta del entorno virtual. Ahora van relativas a `lib`, que es donde están en la copia distribuida.
  - Metadatos sin rutas (`limpiar_metadatos`): se retiran `direct_url.json` (basskit decía desde qué carpeta del proyecto se instaló) y `RECORD` de cada `*.dist-info` de `library.zip`. Se conservan `METADATA` y `entry_points.txt`: `importlib.metadata`, el paquete de diagnóstico y markdown los leen.
  - `ENTORNOLAB_DESTINO_BUILD` compila en otra carpeta, para no pisar una compilación en uso.
- **Ejecución** (`app\core\registro.py`, `app\core\diagnostico.py`):
  - `registro.acortar_rutas_de_traza` deja en cada `File "..."` de una traza la ruta relativa (`app/ui/ventana.py`, `wx/core.py`). Se aplica a todas las trazas del registro, a `no_controladas\` y a `arranque_fallido.log`, además de la redacción de secretos.
  - `registro.anonimizar_rutas` sustituye la carpeta de datos por `<carpeta de datos>`, la del programa por `<carpeta del programa>`, la del usuario por `%USERPROFILE%` (y `%TEMP%`, `%APPDATA%`...), cualquier otra `C:\Users\<nombre>` por `C:\Users\<usuario>`, y el nombre de la cuenta y del equipo por `<usuario>` y `<equipo>`. Cada ruta se busca con `\`, con `/` y con `\\` (como queda dentro de un JSON).
  - `diagnostico.anonimizar` (redactar, acortar trazas y anonimizar rutas) se aplica a todo lo que entra en el paquete de diagnóstico.

  La técnica viene de Puerto Bravo (`juego/registro.py`, `limpiar`: rutas conocidas de la más larga a la más corta, en sus tres formas, y luego un patrón para cualquier carpeta de usuario; `herramientas/comprobar_limpio.py`: buscar la ruta del proyecto y la carpeta de usuario en los bytes de cada `.pyc` y `.zip`).
- **Comprobación.** `tools\comprobar_rutas.py` busca en el CONTENIDO de cada fichero (texto y binarios, y dentro de `.zip`, `.whl`, `.elab` y `library.zip`) las cadenas de ESTE equipo, calculadas al vuelo y nunca escritas en el código: `os.path.expanduser("~")`, el nombre de usuario y del equipo, la carpeta que contiene el proyecto (también en cualquier otra unidad), `sys.base_prefix`, `sys.prefix`, la carpeta temporal y el correo de `git config`. Las busca en UTF-8 y en UTF-16, y con `\`, `/` y `\\`. Añade patrones genéricos: cualquier `C:\Users\<nombre>` concreto, un Python en la raíz de una unidad y la carpeta temporal de los asistentes de programación. En los binarios nativos de terceros (`.dll`, `.pyd`, `.exe`) solo busca las cadenas de este equipo, porque suelen llevar la ruta de depuración de quien los compiló. Una línea de texto que necesite de verdad una de esas cadenas (un ejemplo ficticio en una prueba) se marca con `# comprobar_rutas: permitido`.

  ```
  .venv\Scripts\python.exe tools\comprobar_rutas.py                          repositorio (lo que subiría git)
  .venv\Scripts\python.exe tools\comprobar_rutas.py --build build\entornolab compilación
  .venv\Scripts\python.exe tools\comprobar_rutas.py --zip build\EntornoLab_v0.1.0.zip
  ```

  Devuelve 1 si encuentra algo. La usan `tools\antes_de_compilar.py` (repositorio), `tools\verificar_build.py` (compilación) y `tests\test_sin_rutas_locales.py`.

## Publicar una versión

1. Cambie `APP_VERSION` en `app\core\version.py` y `version` en `pyproject.toml` (una prueba comprueba que coinciden).
2. Añada la entrada `## Versión X.Y.Z - AAAA-MM-DD` en `data\docs\novedades.md`, en lenguaje de usuario.
3. Actualice el manual y la lista de teclas si cambió algo visible.
4. `entorno.bat idiomas` y revise el informe de traducciones.
5. `entorno.bat pruebas` y `entorno.bat comprobar`.
6. `entorno.bat compilar`.
7. Pruebe a mano la versión compilada con un lector de pantalla, en un Windows sin Python instalado si es posible: arranque, F1, una partida con auriculares y el cierre.
8. Publique `build\EntornoLab_v<versión>.zip` y `build\version.json`. Las notas de la versión están en `build\notas_version.md`.
