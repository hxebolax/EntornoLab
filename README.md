# EntornoLab

[Read in English](README_en.md)

**Aprender lugares antes de visitarlos.** EntornoLab es una aplicación de Windows, portable y sin conexión, para que personas ciegas o con baja visión conozcan un edificio o una calle antes de ir. El profesional construye el lugar en el **Estudio** y el alumno lo recorre en **Jugar**, un audiojuego en primera persona con sonido 3D, con teclado o mando.

- Versión: 0.1.0 (primera versión pública).
- Autor: Héctor J. Benítez Corredera.
- Licencia: GPL 3 o posterior, con un permiso adicional para la biblioteca BASS.
- Idiomas: español e inglés.

EntornoLab es una herramienta educativa y de entrenamiento. No es un producto sanitario, no diagnostica ni trata, y no sustituye al aprendizaje en el lugar real con un profesional.

## Contenido

- [Para usuarios](#para-usuarios)
  - [Qué es y para quién](#qué-es-y-para-quién)
  - [Qué va a encontrar](#qué-va-a-encontrar)
  - [Complementos y catálogo en línea](#complementos-y-catálogo-en-línea)
  - [Paquetes de sonidos](#paquetes-de-sonidos)
  - [Requisitos](#requisitos)
  - [Descarga e instalación](#descarga-e-instalación)
  - [Primeros pasos](#primeros-pasos)
  - [Actualizaciones](#actualizaciones)
  - [Privacidad](#privacidad)
  - [Accesibilidad](#accesibilidad)
  - [Base científica, con sus límites](#base-científica-con-sus-límites)
  - [Aviso importante](#aviso-importante)
  - [Estado del proyecto](#estado-del-proyecto)
  - [Ayuda y avisos de fallos](#ayuda-y-avisos-de-fallos)
  - [Invítame a un café](#invítame-a-un-café)
  - [Idiomas](#idiomas)
- [Para programadores](#para-programadores)
  - [El proyecto en cifras](#el-proyecto-en-cifras)
  - [Árbol del proyecto](#árbol-del-proyecto)
  - [Arquitectura en breve](#arquitectura-en-breve)
  - [Requisitos de desarrollo](#requisitos-de-desarrollo)
  - [Montar el entorno](#montar-el-entorno)
  - [Ejecutar desde el código](#ejecutar-desde-el-código)
  - [Pruebas y estilo](#pruebas-y-estilo)
  - [Compilar con cx_Freeze](#compilar-con-cx_freeze)
  - [Verificar y empaquetar](#verificar-y-empaquetar)
  - [Publicar una versión firmada y el catálogo](#publicar-una-versión-firmada-y-el-catálogo)
  - [Crear complementos y paquetes de sonidos](#crear-complementos-y-paquetes-de-sonidos)
  - [Traducir a otro idioma](#traducir-a-otro-idioma)
  - [Convenciones de código](#convenciones-de-código)
  - [Mapa de la documentación técnica](#mapa-de-la-documentación-técnica)
- [Licencia](#licencia)
- [Créditos y agradecimientos](#créditos-y-agradecimientos)
- [Cómo citar](#cómo-citar)

## Para usuarios

### Qué es y para quién

EntornoLab tiene dos programas que comparten el mismo motor:

- **El Estudio** (`EntornoLab.exe`), para el profesional. Se maneja entero con teclado y lector de pantalla, y tiene además un plano gráfico para quien trabaja con ratón.
- **Jugar** (`EntornoLabJugar.exe`), para el alumno. Todo se dice por voz y todo se hace con el teclado o con un mando de Xbox o de PlayStation.

Está pensado para:

- **profesionales de rehabilitación y de orientación y movilidad**, ciegos o videntes, que preparan el aprendizaje de un lugar concreto: una casa, un colegio, un centro de trabajo, una estación o el camino a una parada;
- **alumnos con ceguera o con baja visión de cualquier edad**, con mensajes en estilo infantil, juvenil o adulto;
- **familias**, que acompañan en casa el trabajo que prepara el profesional;
- **centros**, que pueden usar la misma carpeta en varios equipos y supervisar a varios alumnos por la red local.

### Qué va a encontrar

#### En el Estudio

- **Construir interiores**: plantas, habitaciones por medidas o adosadas a otra, espacios de cualquier forma, puertas, huecos, ventanas y portales, paredes sueltas, escaleras, rampas y ascensores, fuentes de sonido, referencias y zonas de suelo (alfombras, pavimento táctil).
- **Construir exteriores**: calles con calzada y aceras, cruces, pasos de peatones con o sin semáforo sonoro, pulsador e isleta, edificios, manzanas y paradas.
- **Tres formas de colocar**: con medidas, en relación con lo que ya hay (adosada, contra una pared, en una esquina, junto a otro elemento) o recorriendo el entorno con Jugar y colocando las cosas donde se está.
- **Objetos de complementos**, con búsqueda, clasificación, ajuste a escala automático, aviso de obstáculos colgantes y propuesta de mobiliario para amueblar un espacio.
- **Comprobar** el entorno, **medir** entre elementos, un **plano gráfico** con cuadrícula y la **descripción completa** del lugar en texto.
- **Importar** de OpenStreetMap (sin inventar nada de lo que el mapa no dice), de planos DXF y SVG, una imagen de fondo para calcar y rutas GPX.
- **Exportar** el paquete para el alumno, la descripción en texto, Markdown o HTML accesible, el plano visual, el **plano táctil con leyenda en braille**, GeoJSON y DXF.
- **Fichas de alumnos** protegidas con contraseña y cifradas, con cálculo del paso, lista de trabajo, recompensas, exportación y borrado completo.
- **Supervisión en vivo**, en el mismo equipo o en la red local, cifrada: posición, lo que oye el alumno, sucesos, mensajes, pistas, premios en directo, recolocar, pausar y marcar momentos.
- **Sesiones, informes y cuaderno**: repetición del recorrido paso a paso, informes de sesión, comparación, evolución, examen y evaluación real, y un cuaderno para anotar las pruebas en el lugar físico.

#### En Jugar

- Recorrido en primera persona con **sonido 3D**: pasos según el suelo, choques y roces según el material, eco de cada lugar, puertas, escaleras, ascensores, semáforos y coches.
- **Catorce ayudas** que el alumno puede pedir: dónde estoy, mirar en cuatro direcciones, alrededor, lista de lo cercano, lugares descubiertos, brújula, bastón sonoro, eco, objetivo y pista, entre otras.
- **Tutorial**, «Aprender los sonidos» y «Practicar los controles».
- Teclas y botones **reasignables**, varias formas de moverse, giro y paso ajustables, distancias en metros o en pasos.
- Para baja visión: plano de la planta, alto contraste, texto grande y pantalla en negro.

#### Actividades y exámenes

- **22 tipos de actividad**: juegos (búsqueda del tesoro, el recadero, sacar los tesoros, el escondite, sigue al guía, el explorador, pistas encadenadas, cruza con el pitido), prácticas (exploración libre, visita guiada, rutas, ruta inversa, volver al origen, ruta alternativa, localizar un espacio, familiarización de sala, seguir una línea guía) y exámenes (rutas, salida más corta, señalar, distancias y reconstrucción).
- **Premios escondidos** a mano, dentro de objetos, repartidos automáticamente o colocados recorriendo, con mensaje y audio grabado.
- Objetivos, ayudas permitidas con límite de usos, niveles de retirada de ayudas, estilos, contrarreloj y «el travieso», que cambia premios de sitio.
- Exámenes sin pistas, con regla de parada y semilla para repetirlos igual. Nunca se dice al alumno si acierta.

### Complementos y catálogo en línea

Los objetos (muebles, aparatos, mobiliario urbano, obstáculos) vienen en **complementos**. EntornoLab trae varios de serie (hogar, colegio, oficina y comercio, calle, transporte y juego) y el listado completo de sus objetos está en `data/plugins/CATALOGO.md` cuando la versión lo incluye. Desde el Estudio se pueden:

- activar, desactivar, añadir y quitar complementos;
- instalar y actualizar complementos del **catálogo en línea**, firmado y comprobado: solo se admiten datos, nunca programas;
- crear complementos propios con un asistente y compartirlos en un fichero `.elabc`.

### Paquetes de sonidos

Jugar trae tres paquetes de sonidos que se cambian al momento: **Sintético** (el de serie, limpio y muy distinguible), **Natural** (instrumentos acústicos y modelos físicos) y **Grabado** (grabaciones reales de dominio público, parcial). Se pueden crear paquetes propios copiando ficheros en una carpeta; el detalle está en el manual.

### Requisitos

- Windows 10 u 11 de 64 bits.
- Auriculares estéreo (con altavoces también funciona, con menos precisión).
- Lector de pantalla recomendado: NVDA, JAWS u otro compatible. Sin él, Jugar habla con la voz de Windows, salvo que se elija otra salida de voz o ninguna.
- Mando de Xbox o de PlayStation, opcional.
- No necesita Internet ni permisos de administrador.

### Descarga e instalación

1. Vaya a la [página de publicaciones](https://github.com/hxebolax/EntornoLab/releases) y descargue el ZIP de la última versión (`EntornoLab_v` seguido del número).
2. Descomprímalo en una carpeta con permiso de escritura, por ejemplo en Documentos o en una memoria USB. No lo ponga en «Archivos de programa».
3. Dentro están `EntornoLab.exe` (Estudio), `EntornoLabJugar.exe` (Jugar) y la carpeta `data`, donde se guarda todo.

Para desinstalarlo, borre la carpeta. Para hacer una copia de seguridad, cópiela entera.

### Primeros pasos

- **Profesional**: abra `EntornoLab.exe`, pulse F1 para el manual y siga la [guía rápida para el profesional](data/docs/guia-rapida-profesional.md): de cero a la primera sesión en diez pasos.
- **Alumno**: abra `EntornoLabJugar.exe`, elija su alias y empiece por el «Tutorial». Hay una [guía rápida para jugar](data/docs/guia-rapida-alumno.md), con versión para niños.
- Toda la documentación de usuario: [manual](data/docs/manual.md), [lista de teclas](data/docs/teclas.md), [preguntas frecuentes](data/docs/preguntas-frecuentes.md) y [novedades](data/docs/novedades.md).

### Actualizaciones

El Estudio puede buscar versiones nuevas en Ayuda, «Buscar actualizaciones». De serie no se conecta por su cuenta: la primera vez pregunta si puede comprobarlo al arrancar, una vez al día como mucho. Las versiones van firmadas y se comprueban antes de instalarse; si la nueva no arranca, se vuelve sola a la anterior. Nunca se tocan sus entornos, fichas, sesiones ni preferencias.

### Privacidad

- Sin cuentas, sin nube y sin telemetría. Todo se guarda en la carpeta `data` del programa.
- Los datos personales de las fichas (nombre real, notas y observaciones) se cifran con AES-256-GCM y una contraseña del profesional que no se guarda en ningún sitio.
- Solo hay conexiones a Internet si usted las pide: actualizaciones y complementos (GitHub) e importación de OpenStreetMap. La supervisión usa el propio equipo o la red local, cifrada.
- Los registros no guardan nombres, alias, notas ni textos de los alumnos.
- Cada alumno tiene «Exportar datos» y «Borrar por completo».

### Accesibilidad

- El Estudio usa controles estándar de Windows con etiquetas, letras de acceso, ayuda de cada control (Ctrl+H), lectura de listas por columnas y anuncio del avance de las tareas largas.
- Nada depende solo del color ni del ratón: el plano gráfico es un añadido.
- Jugar dice todo lo que muestra, se maneja entero con teclado o mando, envía los mensajes a la línea braille y tiene alto contraste, texto grande y pantalla en negro.
- El manual (F1) se navega por encabezados y la lista de teclas (Ctrl+F1) está ordenada por ventana.

### Base científica, con sus límites

EntornoLab se inspira en estudios sobre aprendizaje de lugares con entornos virtuales sonoros, sobre todo los del juego AbES (Connors, Chrastil, Sánchez y Merabet, 2014): adultos ciegos que entrenaron un edificio real con un videojuego de audio acertaron tanto como con instrucción dirigida en rutas de un punto a otro, y les fue claramente mejor al buscar la salida más corta. Otros trabajos apuntan en la misma dirección con adolescentes, niños, cruce de calles y planos con sonido.

Los límites, con la misma claridad: son estudios pequeños (de 4 a 17 participantes) y de un solo edificio; se aprende el lugar entrenado, no una habilidad general; no está demostrado que sirva para barrios enteros, que dure meses ni que el mando equivalga al teclado. EntornoLab recoge lo que esos estudios señalan como más útil, pero no promete resultados. El apartado «Base científica y sus límites» del [manual](data/docs/manual.md) lo resume con cifras.

### Aviso importante

- EntornoLab **no es un producto sanitario**. No diagnostica ni trata.
- **No sustituye** al aprendizaje en el lugar real con un profesional de orientación y movilidad.
- **No sirve para decidir si un cruce real es seguro.** En la calle mandan lo que se oye y el profesional.
- Las puntuaciones y los informes describen lo que ocurrió en el simulador, no la competencia en el lugar real.

### Estado del proyecto

Versión 0.1.0, la primera pública.

- **Comprobado automáticamente**: más de cien ficheros de pruebas cubren el modelo de entornos, el motor, las actividades, el seguimiento, la supervisión, la importación y la exportación, las actualizaciones, los complementos, la configuración, la documentación y partes de la interfaz. Hay comprobaciones de estilo, de atajos de teclado y de arranque de los dos programas.
- **Falta probar con personas**: no se ha probado todavía con alumnos ni en un programa de rehabilitación, ni a mano con cada lector de pantalla, ni con mandos físicos, ni el seguimiento de cabeza con un sensor real. Sus avisos son muy bienvenidos.

### Ayuda y avisos de fallos

- Manual completo en el Estudio con F1.
- [Preguntas frecuentes](data/docs/preguntas-frecuentes.md).
- Avisos de fallos y propuestas en las [incidencias del proyecto](https://github.com/hxebolax/EntornoLab/issues), también desde Ayuda, «Avisar de un fallo». Nunca publique datos de alumnos.
- Problemas de seguridad o privacidad: en privado, como explica [SECURITY.md](SECURITY.md).

### Invítame a un café

EntornoLab es gratuito. Si le resulta útil y quiere apoyar su desarrollo, puede [invitar a un café al autor](https://www.paypal.com/paypalme/hjbcdonaciones). También está en el Estudio, en Ayuda, «Invítame a un café si te gusta mi trabajo».

### Idiomas

La aplicación está escrita en español de España y traducida por completo al inglés (interfaz, manual, lista de teclas, novedades y guías rápidas en `data/docs/en`). El idioma se elige en las preferencias o con la variable `APP_IDIOMA`; por defecto, el de Windows. Las traducciones a otros idiomas son bienvenidas: vea «Traducir a otro idioma» y el [glosario de la traducción inglesa](docs/glosario-traduccion.md).

## Para programadores

### El proyecto en cifras

Estas cifras las calcula `tools/cifras_proyecto.py` a partir de los datos reales. Para actualizarlas: `.venv\Scripts\python.exe tools\cifras_proyecto.py --escribir README.md`.

<!-- cifras:inicio -->

| Qué | Cuántos |
|---|---|
| Complementos de objetos de serie | 21 |
| Objetos en esos complementos | 2.258 |
| Sonidos distintos del catálogo de sonidos | 198 |
| Paquetes de sonidos | 3 (grabado, natural, por_defecto) |
| Tipos de actividad | 22 |
| Entornos de ejemplo | 3 |
| Idiomas de la interfaz (con catálogo, aunque esté incompleto) | 2 |
| Ficheros de pruebas automáticas | 120 |
| Funciones de prueba (sin contar las parametrizadas) | 1.819 |

<!-- cifras:fin -->

### Árbol del proyecto

En la raíz:

- `main.py`: arranque del Estudio (y de Jugar con `--jugar`).
- `jugar.py`: arranque de Jugar.
- `entorno.bat`: administración del proyecto: entorno virtual, pruebas, idiomas y compilación.
- `setup_cx.py`: compilación con cx_Freeze de los dos ejecutables.
- `pyproject.toml`: metadatos y configuración de ruff y pytest.
- `requirements.txt` y `requirements-dev.txt`: dependencias de la aplicación y de desarrollo.
- `__pip__/`: ruedas propias que viajan con el código, como basskit con BASS.

En `app/`, el código de la aplicación:

- `core/`: rutas, configuración, registro, cifrado, red, tareas, procesos, idiomas y versión.
- `dominio/`: modelo de entornos, geometría, edición, catálogo de objetos y validación.
- `motor/`: mundo, movimiento, percepción, acústica, dinámica de la calle y sesión de juego.
- `actividades/`: tipos de actividad, juegos, prácticas, exámenes y puntuación.
- `audio/`: motores de sonido, voz, braille, vibración y paquetes de sonidos.
- `entrada/`: acciones con nombre, teclado y mando.
- `reproductor/`: Jugar, con pygame: pantallas, menús, plano y conexión con la sala.
- `ui/`: el Estudio, con wxPython: ventana principal, diálogos, plano y ventanas de seguimiento.
- `seguimiento/`: alumnos, sesiones, medidas, informes y cuaderno.
- `supervision/`: sala, cliente, protocolo y seguridad de la supervisión en vivo.
- `importar/` y `exportar/`: OpenStreetMap, DXF, SVG, imagen y GPX; texto, planos visual y táctil, braille, GeoJSON y DXF.
- `services/`: actualizador y catálogo en línea de complementos.

En `data/`, lo que viaja con la aplicación:

- `bin/openal/`: OpenAL Soft y los perfiles HRTF.
- `sounds/`: paquetes de sonidos y catálogo de sonidos.
- `plugins/`: complementos de objetos de serie.
- `ejemplos/`: entornos de ejemplo.
- `docs/`: documentación de usuario y licencias de terceros.
- `locales/`: traducciones.
- `icons/`: iconos.

Y además:

- `docs/`: documentación técnica, que no viaja con la aplicación.
- `tests/`: pruebas con pytest.
- `tools/`: herramientas para generar sonidos, ejemplos y complementos, traducir, compilar, empaquetar y publicar.

Al usarse, el programa crea además en `data` las carpetas `config`, `logs`, `db`, `sessions`, `entornos`, `cache`, `temp` y `backups`, que no se versionan ni se distribuyen.

### Arquitectura en breve

- Dos procesos con el mismo motor: el Estudio (wxPython) y Jugar (pygame-ce). El Estudio lanza Jugar como proceso hijo para probar, recorrer o supervisar, y se comunican por la sala de supervisión.
- `app/dominio`, `app/motor` y `app/actividades` no importan wx, pygame ni bibliotecas de sonido: reciben datos y devuelven datos o eventos, y se prueban sin ventana ni altavoces.
- El motor no suena ni habla: produce eventos que aplican la capa de sonido y la de voz.
- La entrada se traduce a acciones con nombre, de modo que teclas y botones se reasignan sin tocar el motor.
- Todo lo que el programa genera vive en `data`, junto al ejecutable: es portable.

El contrato entre módulos está en [docs/arquitectura.md](docs/arquitectura.md).

### Requisitos de desarrollo

- Windows de 64 bits.
- Python 3.15 de 64 bits, con el lanzador `py`.
- Git.

Todo lo demás se instala en el entorno virtual del proyecto.

### Montar el entorno

1. Clone el repositorio:

   ```
   git clone https://github.com/hxebolax/EntornoLab.git
   cd EntornoLab
   ```

2. Cree el entorno virtual e instale las dependencias:

   ```
   entorno.bat crear
   ```

   Crea `.venv` con Python 3.15 e instala `requirements.txt` y `requirements-dev.txt`. Las ruedas propias de la carpeta `__pip__`, como **basskit** con la biblioteca BASS, se instalan solas desde el propio repositorio: `requirements.txt` las nombra por su ruta. Al terminar, `entorno.bat` comprueba que basskit carga `bass.dll`.

3. Compruebe el resultado:

   ```
   entorno.bat diagnostico
   ```

   Muestra las versiones de Python, wxPython, pygame-ce, numpy, sounddevice, cryptography, basskit y cx_Freeze, y si están OpenAL Soft y el lector de pantalla.

**OpenAL Soft** no se instala con pip: su biblioteca `soft_oal.dll` y los perfiles HRTF van en `data/bin/openal`, dentro del repositorio. Sin ella, el motor binaural no está disponible y se usa el siguiente.

`entorno.bat` sin argumentos abre un menú numerado. Con una orden, la ejecuta y devuelve un código de salida: `crear`, `instalar`, `actualizar`, `ejecutar`, `depurar`, `jugar`, `pruebas`, `comprobar`, `sonidos`, `ejemplos`, `idiomas`, `compilar`, `compilar-debug`, `empaquetar`, `limpiar`, `datos`, `registros`, `diagnostico` y `congelar`.

### Ejecutar desde el código

- Estudio: `entorno.bat ejecutar`, o `.venv\Scripts\python.exe main.py`.
- Estudio con consola y registro detallado: `entorno.bat depurar`.
- Jugar: `entorno.bat jugar`, o `.venv\Scripts\python.exe jugar.py`. Admite argumentos, por ejemplo:

  ```
  entorno.bat jugar data\ejemplos\vivienda-de-ejemplo.elab --alumno ana
  ```

- Comprobación sin ventanas: `main.py --comprobar-arranque` y `jugar.py --comprobar-arranque` salen con 0 si todo va bien.

Variables de entorno útiles: `APP_DATA_DIR` (otra carpeta `data`), `APP_IDIOMA` (forzar un idioma) y `APP_DEPURACION=1` (registro en DEBUG). Más detalle en [docs/desarrollo.md](docs/desarrollo.md).

### Pruebas y estilo

```
entorno.bat pruebas
.venv\Scripts\python.exe -m pytest tests -q -m "not red and not interfaz and not lento"
.venv\Scripts\python.exe -m ruff check app main.py jugar.py tools setup_cx.py tests
entorno.bat comprobar
```

- Las marcas son `lento` (más de un segundo), `red` (necesita Internet) e `interfaz` (muestra ventanas o envía teclas reales). De serie no se ejecutan `red` ni `interfaz`.
- Las pruebas nunca tocan la carpeta `data` real ni salen a Internet: lo garantiza `tests/conftest.py`.
- `entorno.bat comprobar` pasa ruff, compara los atajos del código con la lista de teclas (`tools/comprobar_teclas.py`), comprueba las notas de la versión y los idiomas, y arranca el Estudio y Jugar.

### Compilar con cx_Freeze

1. Asegúrese de que pasan las pruebas y la comprobación: `entorno.bat pruebas` y `entorno.bat comprobar`.
2. Compile:

   ```
   entorno.bat compilar
   ```

Qué hace `compilar`, por orden:

1. `tools/antes_de_compilar.py`: compila las traducciones y comprueba que la versión tiene notas en `data/docs/novedades.md`.
2. `setup_cx.py build`: genera en `build/entornolab` los dos ejecutables, `EntornoLab.exe` (Estudio) y `EntornoLabJugar.exe` (Jugar), con los runtimes de Visual C++.
3. `tools/verificar_build.py`: comprueba los ejecutables, las DLL necesarias, OpenAL Soft, la documentación y las licencias, y que `data` viaja limpia.
4. Arranca los dos ejecutables con `--comprobar-arranque`, con una carpeta `data` aparte.
5. `tools/empaquetar.py`: crea `build/EntornoLab_v<versión>.zip` y `build/version.json`.

El resultado es la carpeta distribuible `build/entornolab`, con los dos ejecutables y la carpeta `data`, y su ZIP. A `data` solo viajan `bin`, `sounds`, `locales`, `docs`, `icons`, `plugins` y `ejemplos`. `entorno.bat compilar-debug` compila con consola, para ver errores de arranque; no la distribuya.

### Verificar y empaquetar

- `entorno.bat comprobar` arranca también la versión compilada si existe.
- `entorno.bat empaquetar` vuelve a crear el ZIP y `version.json` a partir de la compilación existente.
- Antes de publicar, pruebe a mano la versión compilada con un lector de pantalla, si es posible en un Windows sin Python: arranque, F1, una partida con auriculares y el cierre.

### Publicar una versión firmada y el catálogo

Resumen; el detalle está en [docs/actualizaciones.md](docs/actualizaciones.md) y [docs/catalogo-de-complementos.md](docs/catalogo-de-complementos.md).

1. Suba `APP_VERSION` en `app/core/version.py` y `version` en `pyproject.toml` (una prueba comprueba que coinciden).
2. Añada la entrada `## Versión X.Y.Z - AAAA-MM-DD` en `data/docs/novedades.md`, en lenguaje de usuario.
3. Pase `entorno.bat idiomas`, `entorno.bat pruebas`, `entorno.bat comprobar` y `entorno.bat compilar`.
4. Ensaye con `tools/publicar_version.py --simular` y prepare con `tools/publicar_version.py`: deja en `build/publicar` el ZIP, el `version.json` firmado con Ed25519 y las notas de la versión. Con `--subir` y GitHub CLI, los publica.
5. Los complementos del catálogo en línea se publican con `tools/publicar_complemento.py` en el repositorio del catálogo, también firmados.

**La clave privada de firma nunca va al repositorio.** Se genera una sola vez con `tools/generar_claves.py`, se guarda fuera del proyecto (en la carpeta de la variable `ENTORNOLAB_CLAVES` o en el perfil del usuario) y la herramienta se niega a escribirla dentro del proyecto. La clave pública va en `app/services/actualizador.py`.

### Crear complementos y paquetes de sonidos

- Complementos: [docs/crear-un-complemento.md](docs/crear-un-complemento.md) (paso a paso) y [docs/formato-de-complementos.md](docs/formato-de-complementos.md) (referencia). Los de serie se generan con `tools/generar_complementos.py`.
- Paquetes de sonidos: [docs/sonido.md](docs/sonido.md) y `data/sounds/LEEME.md`. El paquete de serie se genera con `entorno.bat sonidos` y el «Natural», con `tools/generar_paquete_sonidos.py`.
- Entornos de ejemplo: `entorno.bat ejemplos`. El formato de los entornos está en [docs/formato-de-entornos.md](docs/formato-de-entornos.md).

### Traducir a otro idioma

El código se escribe en español y cada idioma es un catálogo gettext en `data/locales/<idioma>/LC_MESSAGES/entornolab.po`.

1. `.venv\Scripts\python.exe tools\extraer_cadenas.py`: genera la plantilla `entornolab.pot`.
2. `.venv\Scripts\python.exe tools\actualizar_po.py --nuevo fr`: crea el catálogo del idioma.
3. Traduzca el `.po` con Poedit o con un editor de texto, sin tocar los marcadores `{nombre}` ni el atajo que sigue al tabulador.
4. `.venv\Scripts\python.exe tools\compilar_traducciones.py`: genera el `.mo`.
5. `.venv\Scripts\python.exe tools\informe_traducciones.py --detalle`: lo que queda pendiente.
6. Pruebe con `set APP_IDIOMA=fr` y `entorno.bat ejecutar`.

`entorno.bat idiomas` hace todo el ciclo. Los complementos y los ejemplos llevan sus traducciones en `locales/<idioma>.json`. La documentación de usuario traducida va en `data/docs/<idioma>/` con los mismos nombres de fichero; F1 abre la del idioma de la interfaz y, si falta, la española.

### Convenciones de código

Python 3.15, todo en español de España, tabulaciones, líneas de 140 caracteres, `ruff check` sin avisos, textos con `_()`, registro sin datos personales y accesibilidad como requisito. La guía completa está en [CONTRIBUTING.md](CONTRIBUTING.md) y las normas de convivencia, en [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

### Mapa de la documentación técnica

El índice, con una línea por documento, está en [docs/LEEME.md](docs/LEEME.md). Los principales:

- [docs/arquitectura.md](docs/arquitectura.md): el contrato entre módulos.
- [docs/desarrollo.md](docs/desarrollo.md): entorno, pruebas, traducción y compilación.
- [docs/estudio.md](docs/estudio.md) y [docs/reproductor.md](docs/reproductor.md): las dos aplicaciones.
- [docs/motor.md](docs/motor.md), [docs/sonido.md](docs/sonido.md), [docs/voz.md](docs/voz.md) y [docs/entrada.md](docs/entrada.md): motor, sonido, voz y entrada.
- [docs/actividades.md](docs/actividades.md), [docs/seguimiento.md](docs/seguimiento.md), [docs/estudio-seguimiento.md](docs/estudio-seguimiento.md) y [docs/supervision.md](docs/supervision.md).
- [docs/formato-de-entornos.md](docs/formato-de-entornos.md), [docs/formato-de-complementos.md](docs/formato-de-complementos.md) e [docs/importar-y-exportar.md](docs/importar-y-exportar.md).
- [docs/actualizaciones.md](docs/actualizaciones.md) y [docs/catalogo-de-complementos.md](docs/catalogo-de-complementos.md).

## Licencia

EntornoLab, Copyright 2026 Héctor J. Benítez Corredera, es software libre: puede redistribuirlo y modificarlo bajo los términos de la [Licencia Pública General de GNU](LICENSE), versión 3 o (a su elección) cualquier versión posterior. Se distribuye sin ninguna garantía.

- **Permiso adicional para BASS.** La licencia incluye un permiso adicional (sección 7 de la GPL) para combinar EntornoLab con la biblioteca BASS. **BASS no es software libre y es gratuita solo para uso no comercial.** Para un uso comercial hace falta comprar su licencia a Un4seen Developments, o elegir otro motor de sonido y borrar `bass.dll`: el resto del programa funciona igual.
- **OpenAL Soft**, el motor binaural de serie, tiene licencia GNU LGPL.
- **Sonidos**: los paquetes «Sintético» y «Natural» tienen la licencia de EntornoLab; las grabaciones del paquete «Grabado» son CC0, con sus créditos en `data/sounds/grabado/CREDITOS.txt`.
- **Complementos**: cada uno declara su licencia en su ficha; los de serie de esta versión usan CC BY 4.0.
- **Datos de OpenStreetMap**: © colaboradores de OpenStreetMap, con licencia ODbL.
- La lista completa de componentes de terceros y sus textos está en [data/docs/licencias](data/docs/licencias/LEEME.md).

## Créditos y agradecimientos

- Autor: Héctor J. Benítez Corredera.
- EntornoLab se apoya en proyectos libres: wxPython, pygame-ce, OpenAL Soft, NumPy, sounddevice, soundfile, accessible_output2, cryptography, Python-Markdown, pywin32 y cx_Freeze. Usa también la biblioteca BASS de Un4seen Developments, perfiles HRTF de MIT KEMAR y SADIE II, y los datos y servicios de OpenStreetMap.
- Se inspira en la investigación sobre aprendizaje de lugares con audiojuegos y entornos virtuales, en especial los trabajos de Jaime Sánchez, Lotfi Merabet, Erin Connors y colaboradores (AbES, AudioDoom, AudioChile), de Orly Lahav y colaboradores (BlindAid), de Bowman y Liu sobre cruce de calles y de Giudice y colaboradores sobre planos con sonido y vibración, y en proyectos como Soundscape y VisionPulse. Citarlos no significa que sus autores avalen EntornoLab.

## Cómo citar

Si usa EntornoLab en un trabajo o una publicación, puede citarlo así:

> Benítez Corredera, H. J. (2026). EntornoLab (versión 0.1.0) [Software]. https://github.com/hxebolax/EntornoLab
