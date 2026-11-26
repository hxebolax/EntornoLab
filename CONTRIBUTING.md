# Cómo contribuir a EntornoLab

EntornoLab es una aplicación de Windows, portable y sin conexión, que usan personas ciegas y con baja visión y los profesionales que las acompañan. Cada cambio debe funcionar con lector de pantalla y con teclado: la accesibilidad es un requisito, no un añadido.

Antes de programar, lea [docs/arquitectura.md](docs/arquitectura.md) (el contrato entre módulos) y [docs/desarrollo.md](docs/desarrollo.md) (cómo montar el entorno, probar, traducir y compilar). El índice de toda la documentación técnica está en [docs/LEEME.md](docs/LEEME.md).

Al participar, acepta las normas de [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Formas de ayudar

No hace falta programar para ayudar:

- **Probar y avisar de fallos.** Use la plantilla «Informe de fallo» de las incidencias. Diga la versión, su lector de pantalla y qué hacía.
- **Probar con personas.** EntornoLab no se ha probado todavía con alumnos, a mano con cada lector de pantalla ni con mandos físicos. Cualquier experiencia con ellos es muy valiosa: cuéntela en una incidencia con la plantilla «Propuesta de mejora», sin datos personales.
- **Proponer mejoras**, con la plantilla «Propuesta de mejora».
- **Crear complementos de objetos.** Vea [docs/crear-un-complemento.md](docs/crear-un-complemento.md) y proponga el suyo con la plantilla «Complemento nuevo».
- **Crear paquetes de sonidos.** Vea [docs/sonido.md](docs/sonido.md).
- **Traducir.** Vea el apartado «Traducción» de [docs/desarrollo.md](docs/desarrollo.md).
- **Mejorar la documentación**: `data/docs` para usuarios y `docs` para quien programa.

Nunca publique datos de alumnos (nombres, notas, sesiones, informes) en una incidencia, una propuesta o un registro adjunto. Los problemas de seguridad o de privacidad se avisan en privado, como explica [SECURITY.md](SECURITY.md).

## Flujo de trabajo

1. Abra una incidencia antes de un cambio grande, para hablarlo.
2. Haga un fork y cree una rama con un nombre que diga el cambio, por ejemplo `corregir-lectura-lista-premios`.
3. Haga cambios pequeños y centrados en una sola cosa.
4. Escriba los mensajes de los commits en español, en presente y diciendo qué cambia para quien usa la aplicación cuando se vea o se oiga.
5. Abra la solicitud de cambios con la plantilla y complete su lista de comprobación.
6. Las pruebas automáticas se pueden lanzar en GitHub Actions; lo que no cubren se comprueba a mano y se dice en la solicitud.

## Antes de entregar un cambio

1. `entorno.bat pruebas`: todas las pruebas pasan.
2. `entorno.bat comprobar`: ruff sin avisos, atajos documentados, notas de la versión e idiomas sin errores, y arranque correcto del Estudio y del reproductor.
3. Si el cambio se ve o se oye: actualice `data\docs\manual.md`, `data\docs\teclas.md` y `data\docs\novedades.md` en el mismo cambio. Si cambian las cifras del proyecto, vuelva a escribirlas en el README con `tools\cifras_proyecto.py --escribir README.md`.
4. Si añadió textos: `entorno.bat idiomas`.
5. Diga qué ha comprobado de verdad y qué queda por comprobar a mano (lector de pantalla, versión compilada). No afirme «probado con NVDA» sin haberlo hecho.

## Convenciones de código

### Lenguaje y formato

- Python 3.15, Windows de 64 bits.
- Todo en español de España: identificadores, comentarios, docstrings, mensajes y registros. Solo quedan en inglés los nombres de API ajenas.
- Tabulaciones para sangrar. Con tabulaciones, cada nivel se oye como una sola tabulación en el lector de pantalla.
- Una instrucción por línea. Nada de `a = 1; b = 2` ni de `if x: return`.
- Líneas de 140 caracteres como máximo.
- `from __future__ import annotations` en cada módulo.
- Anotaciones de tipo en las firmas públicas.
- Docstring en cada módulo, clase y función pública. Explica el porqué: qué problema resuelve y qué decisión se tomó, no lo que ya dice el código.
- `ruff check` sin avisos. La configuración está en `pyproject.toml`.

### Textos para el usuario

- Siempre con `_()` de `app.core.i18n`; plurales con `_n()`; constantes de módulo con `N_()` y `_()` al mostrarlas.
- Frases completas con marcadores con nombre: `_("Hola, {nombre}").format(nombre=nombre)`. Nunca una f-string, `%` ni `.format()` dentro de `_()`, ni frases construidas concatenando trozos.
- Nunca se comparan textos traducidos. Para decidir se usan identificadores.
- No use `_` como nombre de variable (`for _ in ...`): rompe las llamadas a `_()` de esa función.
- Los mensajes del registro no se traducen.

### Registro y errores

- `log = logging.getLogger(__name__)` en cada módulo. Ninguna configuración del registro fuera del arranque.
- Formato diferido: `log.info("Cargados %d objetos de %s", n, nombre)`. Nunca f-strings en una llamada de registro.
- Dentro de un `except`, `log.exception(...)` para conservar la traza.
- Ningún `except` silencioso. Si de verdad no hay nada que hacer, al menos `log.debug("motivo", exc_info=True)` y un comentario que lo justifique.
- Se captura la excepción concreta. Un `except Exception` solo en los límites (un hilo, un suscriptor, el arranque) y con su motivo en un comentario.
- No se registran datos personales: ni nombres o alias de alumnos, ni contenido de fichas, ni contraseñas, ni códigos de emparejamiento. Como mucho, un identificador interno.

### Datos y rutas

- La aplicación es portable: todo lo que genera o necesita vive en `data\`, junto al programa. Nunca en `%APPDATA%`, `%TEMP%` ni en el registro de Windows.
- Toda ruta sale de `app.core.paths`. Nunca rutas absolutas ni `os.getcwd()`.
- **Nunca una ruta ni un dato de su equipo** en nada que se suba o se distribuya: ni su carpeta de usuario, ni la de sus proyectos, ni la de su Python o su entorno virtual, ni su nombre de usuario o su correo. Tampoco en pruebas, documentación, recetas o informes generados. Una herramienta que necesite una carpeta suya (las fuentes de sonido, el Generador de sonidos, la clave de firma) la lee de un argumento o de una variable de entorno y, si falta, lo dice; nunca de una ruta escrita en el código. Los datos generados guardan rutas relativas. Para un ejemplo, use un marcador (`%USERPROFILE%`, `<carpeta con los originales>`). `.venv\Scripts\python.exe tools\comprobar_rutas.py` lo comprueba en el repositorio (y `--build build\entornolab` en una compilación); lo vigilan `tests\test_sin_rutas_locales.py`, `tools\antes_de_compilar.py` y `tools\verificar_build.py`. Detalles en [docs/desarrollo.md](docs/desarrollo.md#privacidad-del-entorno-de-desarrollo).
- Los archivos que no se pueden perder se escriben de forma atómica: temporal en la misma carpeta, `fsync` y `os.replace`.
- Las preferencias van en `app.core.configuracion`, con su valor por defecto y su regla. Los secretos de este equipo, en `app.core.secretos`. Los datos personales de las fichas, cifrados con `app.core.cifrado`.
- No se ejecuta código procedente de entornos, actividades o complementos: son solo datos. Al cargarlos se validan nombres, tamaños y tipos.

### Capas

- `app/dominio`, `app/motor` y `app/actividades` no importan `wx`, `pygame` ni bibliotecas de sonido. Reciben datos y devuelven datos o eventos, y se prueban sin ventana ni altavoces.
- El motor no suena ni habla: devuelve eventos que la capa de sonido y de voz aplica.
- El reproductor (`app/reproductor`) no importa `wx`. El Estudio (`app/ui`) no importa `pygame`.
- `app/core` solo depende de la biblioteca estándar al importarse. `wx` se importa dentro de las funciones que lo necesitan.

### Hilos e interfaz

- El hilo de la interfaz solo atiende a la interfaz. Lo que tarde más de unas décimas va a `app.core.tareas.GestorTareas`. Si ese hilo se bloquea, el lector de pantalla se queda mudo.
- Los controles solo se tocan desde el hilo principal: `wx.CallAfter`, `ejecutar_en_interfaz` o `@en_interfaz`.
- Las tareas largas se pueden cancelar (`tarea.comprobar()` entre pasos) y anuncian su progreso por hitos, no en cada paso.
- Todo acceso a la red o a otro proceso lleva un tiempo de espera.
- Los procesos auxiliares se lanzan con `app.core.procesos`, nunca con `subprocess` directamente: así no quedan huérfanos.

### Accesibilidad en wxPython

- La etiqueta `wx.StaticText` se crea justo antes de su control y con el mismo padre: el lector la toma como nombre del control.
- Cada control tiene letra de acceso (`&`) y no se repite dentro de la misma ventana ni choca con los menús.
- Los botones llevan el texto en español con acelerador: `wx.Button(self, wx.ID_OK, _("&Aceptar"))`. Nunca `wx.MessageBox`: no deja cambiar sus botones.
- Cada control explica su función con `SetHelpText` (Control+H).
- Escape cancela, Intro acepta, el foco inicial va al primer control útil y, al cerrar un diálogo, vuelve a donde estaba.
- La información no depende solo del color, de la posición ni de un sonido.
- Cada atajo nuevo se añade a `data\docs\teclas.md`. Las teclas atendidas a mano se marcan con `# atajo: Ctrl+H` para que `tools\comprobar_teclas.py` las vea.

### Accesibilidad en el reproductor

- Todo lo que aparece en pantalla se dice por voz, y todo se puede hacer con el teclado o con el mando.
- La voz pasa por `app.audio.voz`, que usa el lector de pantalla activo o SAPI y envía el texto al braille.
- El volumen respeta la protección auditiva: ningún sonido nuevo se la salta.

## Pruebas

- Con pytest, en `tests\`. Nombre por el comportamiento: `test_cancelar_no_guarda_cambios`, no `test_dialogo_3`.
- Nunca sobre el `data\` real ni saliendo a Internet. `tests\conftest.py` lo garantiza; no lo desactive.
- Ninguna ventana visible ni diálogo modal real. Use `marco`, `dialogo_modal` y las teclas sintéticas de `tests.ayudas_wx`.
- Sin `time.sleep` para esperar a un hilo: `hilo.join()` o `esperar_hasta(condicion)`.
- Cada fallo corregido deja una prueba que lo reproduce.
- Cubra el caso normal, los límites (vacío, uno, muchos, Unicode) y las ramas de error (archivo dañado, permiso denegado).
- Una prueba de más de un segundo lleva `@pytest.mark.lento`.

## Archivos por lotes

Los `.bat` se guardan con finales de línea CRLF, en UTF-8 sin BOM y con `chcp 65001`. Con finales LF, `goto` y las etiquetas fallan de forma intermitente. Las rutas van entre comillas, se usa `"%PY%" -m pip` en vez de activar el entorno, cada subrutina devuelve un código de salida y no se usa `cls`.

## Qué no se versiona ni se distribuye

- No se versionan `.venv`, `build` ni los datos generados: `data\config`, `data\logs`, `data\db`, `data\sessions`, `data\entornos`, `data\cache`, `data\temp` y `data\backups`.
- Sí se versionan y se distribuyen `data\bin`, `data\sounds`, `data\locales`, `data\docs`, `data\icons`, `data\plugins` y `data\ejemplos`.
- Si añade una carpeta nueva a `data`, decida a cuál de los dos grupos pertenece y actualice `app\core\paths.py`, `setup_cx.py`, `tools\verificar_build.py` y `.gitignore`.
