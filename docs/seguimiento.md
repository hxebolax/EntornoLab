# Seguimiento: fichas, sesiones, medidas e informes

Documentación técnica del paquete `app/seguimiento`. El contrato general está en `docs/arquitectura.md`; aquí está el detalle.

El paquete no importa `wx` ni `pygame`. Lo usan el reproductor (para grabar) y el Estudio (para todo lo demás).

## Módulos

| Módulo | Qué hace |
| --- | --- |
| `base.py` | Base SQLite, migraciones, copias y cifrado de campos |
| `alumnos.py` | Fichas: alta, edición, archivado, búsqueda, exportar, borrar, caducar |
| `sesiones.py` | Sesiones guardadas, notas y marcas del profesional |
| `cuaderno.py` | Cuaderno de evaluación en el lugar real |
| `recompensas.py` | Estrellas, medallas y colección |
| `grabadora.py` | Grabación de la sesión en el reproductor e incorporación a la base |
| `medidas.py` | Cálculo del resumen a partir de la traza |
| `informes.py` | Informes en texto, HTML y CSV; narración del recorrido |

## Privacidad: qué se guarda y cómo

- El alumno se identifica por un **alias** obligatorio y único. El alias no se cifra: es el identificador.
- **Se cifran**: nombre real y notas de la ficha, notas del profesional sobre una sesión, texto de las marcas y observaciones de la evaluación real (lista `CAMPOS_CIFRADOS` de `base.py`).
- **No se cifran**: el resumen y la traza de las sesiones, el lugar y las rutas de la evaluación real, las recompensas. Solo contienen el alias. Si se quiere cifrar todo el fichero hay que hacerlo por fuera (disco cifrado); este paquete cifra por campos.
- El fichero de sesión que escribe el reproductor (`data/sessions/<id>.json.gz`) va **sin cifrar** y solo lleva el alias. El texto de las marcas del profesional sí viaja en ese fichero; al incorporarlo se pasa cifrado a la base y conviene borrar el fichero (`borrar_incorporadas=True`).
- Los registros (`logging`) no contienen alias, nombres, notas ni textos: solo recuentos y nombres de fichero de sesión (que son identificadores aleatorios).
- La exportación de un alumno es un ZIP **sin cifrar**, pensado para entregarlo; el `LEEME.txt` lo avisa.

### Cifrado inyectable

`base.py` no conoce ningún algoritmo. Recibe un `Cifrador`:

```python
Cifrador.sin_cifrar()                                  # pruebas, o sin contraseña todavía
Cifrador(cifrar, descifrar)                            # funciones f(bytes) -> bytes
Cifrador.con_clave(clave, cifrar, descifrar)           # funciones f(datos, clave) -> bytes
abrir_base(ruta, clave=..., cifrar=..., descifrar=...) # atajo
```

Cada valor sensible se guarda como BLOB con un octeto delante: `0x00` texto en claro (UTF-8), `0x01` cifrado. Consecuencias:

- Una base creada sin cifrar se cifra sola la primera vez que se abre con clave.
- En la tabla `meta` hay un texto conocido cifrado (`prueba_cifrado`). Al abrir se descifra: si la clave no es la de la base se lanza `ErrorClave` antes de leer o escribir nada. Abrir sin clave una base cifrada también lanza `ErrorClave`.
- `BaseSeguimiento.cambiar_cifrador(nuevo)` recifra todos los campos en una transacción (cambio de contraseña).

Las funciones de cifrado deben lanzar una excepción si la clave es incorrecta (cifrado autenticado). Si devolvieran basura sin error, la comprobación de `prueba_cifrado` seguiría detectándolo, porque el texto no coincidiría.

## Base de datos

Fichero `data/db/entornolab.db` (`base.ruta_por_defecto()`, que usa `paths.ruta_base_datos()`); las pruebas pasan una ruta de `tmp_path`. Copias en `data/backups/` (`paths.ruta_copias()`) con el nombre `entornolab-<fecha>-<motivo>.db`; si la base se abre con otra ruta, en una carpeta `copias` junto a ella.

Conexión: una sola, con candado reentrante; `journal_mode=WAL`, `foreign_keys=ON`, `secure_delete=ON`, `synchronous=NORMAL`, transacciones explícitas (`BEGIN IMMEDIATE`, anidadas con `SAVEPOINT`). Al abrir se pasa `quick_check`.

Migraciones: lista `MIGRACIONES`; la posición es el número de versión (`PRAGMA user_version`). Cada una va en su transacción; antes de migrar una base con datos se hace una copia; una base de versión futura se rechaza (`ErrorVersionFutura`). Nunca se modifica una migración publicada: se añade otra.

### Esquema (versión 1)

```
meta(clave TEXT PK, valor BLOB)

alumnos(
  id INTEGER PK,
  alias TEXT NOT NULL UNIQUE COLLATE NOCASE,   -- no vacío
  alias_busqueda TEXT NOT NULL,                -- minúsculas y sin acentos
  nombre_real BLOB,                            -- cifrado, opcional
  notas BLOB,                                  -- cifrado, opcional
  ano_nacimiento INTEGER,
  perfil TEXT    baston | perro_guia | baja_vision | otro
  estilo TEXT    infantil | juvenil | adulto
  ajustes TEXT   JSON con los ajustes de juego
  alta TEXT      ISO 8601 en UTC
  archivado INTEGER 0/1
)

sesiones(
  id TEXT PK,                                  -- 32 hexadecimales, el del fichero
  alumno_id -> alumnos ON DELETE CASCADE,
  entorno_id, entorno_nombre,
  actividad_id, actividad_nombre, actividad_tipo,
  modo TEXT      juego | practica | examen
  inicio, fin TEXT ISO 8601 en UTC
  tiempo_activo, tiempo_pausa REAL             -- segundos
  completada INTEGER 0/1
  parcial INTEGER 0/1                          -- guardado automático de una sesión sin terminar
  resumen TEXT   JSON con todas las medidas
  traza BLOB     JSON comprimido con zlib
  notas BLOB     cifrado
)

evaluaciones_reales(
  id INTEGER PK,
  alumno_id -> alumnos ON DELETE CASCADE,
  entorno_id, entorno_nombre,
  fecha TEXT     AAAA-MM-DD
  lugar TEXT
  rutas TEXT     JSON [{"nombre", "resultado", "notas"}]
  nivel_ayuda TEXT, tipo_recorrido TEXT
  ayudas_movilidad TEXT  JSON, lista de textos
  observaciones BLOB     cifrado
  dias_desde_entrenamiento INTEGER
)

recompensas(
  id INTEGER PK,
  alumno_id -> alumnos ON DELETE CASCADE,
  tipo TEXT      estrella | medalla | objeto
  nombre TEXT, fecha TEXT,
  sesion_id -> sesiones ON DELETE SET NULL
)

marcas(
  id INTEGER PK,
  sesion_id -> sesiones ON DELETE CASCADE,
  t REAL         segundo de tiempo activo
  planta TEXT, x REAL, y REAL,
  texto BLOB     cifrado
)
```

Valores cerrados del cuaderno (`cuaderno.py`): resultado de ruta `conseguida | con_ayuda | no_conseguida | no_intentada`; nivel de ayuda `independiente | supervision | indicacion_verbal | ayuda_fisica` (o vacío); tipo de recorrido `entrenado | no_entrenado | inverso | alternativo | otro` (o vacío).

## Fichas (`alumnos.Fichas`)

```python
fichas = Fichas(base)
fichas.alta(alias, *, nombre_real="", notas="", ano_nacimiento=None, perfil="otro", estilo="adulto", ajustes=None) -> Alumno
fichas.editar(alumno_id, **cambios) -> Alumno
fichas.archivar(alumno_id, si=True) -> bool
fichas.obtener(alumno_id) -> Alumno | None
fichas.por_alias(alias) -> Alumno | None
fichas.buscar(texto="", *, incluir_archivados=False) -> list[Alumno]
fichas.exportar(alumno_id, destino) -> Path
fichas.borrar(alumno_id, *, carpeta_sesiones=None, purgar_copias=True) -> dict[str, int]
fichas.caducar_sesiones(dias, *, ahora=None, alumno_id=None) -> int
```

- La búsqueda solo mira el alias. El nombre real no se indexa a propósito: un índice en claro anularía el cifrado.
- **Exportar** escribe un ZIP con `LEEME.txt`, `alumno.json`, `sesiones.csv`, `sesiones/<id>.json` (resumen, traza, notas, marcas), `evaluaciones_reales.json`, `evaluaciones_reales.csv` y `recompensas.csv`. CSV con punto y coma, UTF-8 con BOM, y las celdas que empiezan por `=`, `+`, `-` o `@` llevan un apóstrofo delante para que la hoja de cálculo no las ejecute como fórmulas.
- **Borrar** es completo e irreversible: borra la ficha (las claves foráneas se llevan sesiones, marcas, evaluaciones y recompensas), borra los ficheros de sesión sin incorporar de ese alias, **elimina las copias de seguridad anteriores** (seguirían conteniéndolo), compacta la base (`VACUUM` con `secure_delete`) y deja una copia nueva. Quien llama debe haber pedido confirmación.
- **Caducar** borra las sesiones terminadas hace más de N días (con sus marcas). Fichas, evaluaciones y recompensas se conservan. Los ficheros sin incorporar se caducan con `grabadora.caducar_ficheros`.

## Grabación de una sesión

```python
grabadora = Grabadora(alias, entorno_id, entorno_nombre, actividad_id, actividad_nombre, actividad_tipo, modo,
                      espacios=[...], camino_optimo_m=None, carpeta=None)
grabadora.muestra(t, planta, x, y, rumbo)   # en cada fotograma; se guardan 4 por segundo
grabadora.evento(tipo, datos)               # o grabadora.registrar(ev_registro)
grabadora.pausar(True / False)
grabadora.marca(texto)                      # marca del profesional
grabadora.intervencion(tipo, datos)         # pausa, recolocar, mensaje... (sin el texto)
grabadora.puntuaciones({...})               # examen, tal como las da el motor
ruta = grabadora.terminar(completada, resultado)
```

- `t` es el **tiempo activo** de la sesión (el de `Sesion.estado()["tiempo_activo"]`): en pausa no corre. El tiempo en pausa lo mide la grabadora con un reloj monótono.
- Cada 60 segundos de juego se deja un **guardado parcial** en el mismo fichero (`"parcial": true`), en un hilo aparte, para no perder la sesión si el programa se cierra mal. `terminar` lo sustituye por el definitivo.
- Ninguna llamada bloquea el bucle del juego salvo `terminar`, que escribe el fichero.

### Formato de `data/sessions/<id>.json.gz`

JSON en UTF-8 comprimido con gzip:

```json
{
  "manifiesto": {
    "formato": 1, "aplicacion": "EntornoLab", "version": "1.0.0",
    "id": "0f3c…(32 hexadecimales)", "alias": "Luna",
    "entorno": {"id": "casa", "nombre": "Casa de ejemplo"},
    "actividad": {"id": "buscar", "nombre": "Buscar la llave", "tipo": "busqueda"},
    "modo": "practica",
    "inicio": "2026-11-20T10:00:00+00:00", "fin": "2026-11-20T10:05:12+00:00",
    "completada": true, "parcial": false, "frecuencia_hz": 4
  },
  "resumen": { "...": "ver «Medidas del resumen»" },
  "traza": {
    "muestras": [[0.0, "p0", 1.0, 1.0, 90.0], [0.25, "p0", 1.2, 1.0, 90.0]],
    "eventos": [{"t": 2.0, "tipo": "choque", "datos": {"con": "mesa"}, "pos": ["p0", 2.6, 1.0]}],
    "pausas": [[5.0, 30.0]],
    "marcas": [{"t": 5.0, "planta": "p0", "x": 5.0, "y": 1.0, "texto": "Duda en la puerta"}]
  }
}
```

- Muestra: `[t, planta, x, y, rumbo]`. Pausa: `[t en que empezó, duración]`.
- `pos` es la última posición conocida al ocurrir el evento; la añade la grabadora.

### Incorporar a la base

```python
resultado = incorporar_sesiones(carpeta, base, crear_alumnos=True, borrar_incorporadas=False)
# ResultadoIncorporacion(nuevas, actualizadas, repetidas, sin_alumno, alumnos_creados, erroneas)
```

Es **idempotente**: la sesión que ya está se salta (`repetida`) sin tocar las notas del profesional; una parcial se sustituye por la definitiva (`actualizada`). Un fichero dañado o con formato desconocido se apunta en `erroneas` y se sigue con los demás. El documento se valida (identificador, alias, modo, tipos, tamaño máximo descomprimido de 64 MB) porque llega de otro proceso. Al guardar, el texto de las marcas sale de la traza y va cifrado a la tabla `marcas`. Las recompensas del resumen (los eventos `recompensa` que registra la actividad) se apuntan una sola vez por sesión en la tabla `recompensas` del alumno.

**Nivel de ayudas en la ficha.** De cada sesión definitiva (no parcial) cuyo `resumen.resultado` traiga `nivel_siguiente`, `anotar_nivel_de_sesion` lo lleva a los ajustes de la ficha: `ajustes["niveles"]["<entorno_id>/<actividad_id>"] = nivel` y, en `ajustes["niveles_fin"]`, la hora de fin de la sesión que lo dio. Una sesión más antigua que la ya anotada no hace retroceder el nivel. Desde la ficha, el nivel vuelve al reproductor por la sala (orden `alumno`, ver [supervision.md](supervision.md)).

**Ajustes de juego de la ficha.** `Alumno.ajustes` guarda, además de `lista_trabajo`, `niveles` y `niveles_fin`, los ajustes de juego (`modo_movimiento`, `paso_m`, `giro_grados`, `velocidad_ms`, `formato_direccion`, `unidad`, `detalle`). Sus valores de serie son los de `VALORES_POR_DEFECTO` de `app/core/configuracion.py`, igual que los de `AjustesJuego`.

### Eventos que se entienden

La grabadora guarda cualquier `EvRegistro`. Las medidas usan estos tipos; en los datos se aceptan varios nombres de campo para no depender de una única forma:

| Tipo | Campos que se leen |
| --- | --- |
| `choque` | `con` / `objeto` / `nombre` / `material`; lugar |
| `ayuda` | `ayuda` / `tipo` / `nombre` |
| `objetivo` | `id` / `objetivo`; `nombre` / `texto` |
| `premio` | `id` / `premio`; `nombre` |
| `entrada_espacio` | `espacio` / `espacio_id` / `id`; `nombre` |
| `recompensa` | `tipo` (estrella, medalla, objeto); `nombre` |
| `intervencion` | `tipo` (la escribe `Grabadora.intervencion`) |
| `examen`, `puntuacion` | todos los datos, sin interpretar |
| `valoracion` | todos los datos (preguntas de esfuerzo, confianza, disfrute) |
| `contacto`, `interaccion`, `objeto` | solo el lugar, para la estrategia «de objeto en objeto» |

Lugar de un evento: `datos["x"]`, `datos["y"]`, `datos["planta"]` si vienen; si no, `pos`.

## Medidas del resumen (`medidas.calcular_resumen`)

```python
calcular_resumen(muestras, eventos, *, espacios=(), camino_optimo_m=None, pausas=(),
                 tiempo_activo_s=None, tiempo_pausa_s=None, puntuaciones=None, resultado=None) -> dict
```

Funciones puras. Lo que hace falta del entorno llega como dato: `espacios` es una lista de `{"id", "nombre", "planta", "contorno": [[x, y], …], "macizo": bool}` (el contorno es opcional) y `camino_optimo_m` lo calcula el motor (`navegacion`).

| Clave | Cómo se calcula |
| --- | --- |
| `distancia_m` | Suma de los tramos entre muestras consecutivas de la misma planta. Un tramo de más de 3 m, o de más de 6 m/s, es una recolocación: no suma y se cuenta en `saltos` |
| `tiempo_activo_s` | El que da el motor; si no, el instante de la última muestra o evento |
| `tiempo_pausa_s`, `pausas` | Suma y lista de `[t, duración]` |
| `tiempo_en_movimiento_s`, `tiempo_parado_s` | Tiempo de los tramos a 0,05 m/s o más, y el resto |
| `velocidad_media_ms` | Distancia entre tiempo activo |
| `velocidad_en_movimiento_ms` | Distancia entre tiempo en movimiento |
| `choques` | `total`, `lugares` (instante, planta, x, y, espacio, con qué) y `por_espacio` |
| `ayudas` | `total`, `por_tipo` y `lista` con instante y lugar |
| `objetivos`, `premios` | Listas con `t`, `id` y `nombre` |
| `recompensas` | Lista con `tipo`, `nombre` y `t` |
| `espacios` | `visitados` (id, nombre, primera entrada, número de entradas, tiempo dentro), `no_visitados`, `total`, `proporcion_visitada` y `fuente` |
| `camino_optimo_m`, `cociente_camino` | Distancia real entre camino óptimo; `null` si no hay óptimo |
| `giros` | `numero`, `izquierda`, `derecha`, `medias_vueltas`, `grados_totales` |
| `estrategia` | `tipo`, `confianza`, `indicadores`, `aproximada` |
| `intervenciones` | `total` y `por_tipo` |
| `examen` | Las puntuaciones recibidas del motor, o los eventos `examen` / `puntuacion` en `pruebas` |
| `valoracion` | Datos del último evento `valoracion` |
| `eventos_por_tipo`, `muestras`, `resultado`, `formato` | Recuentos, el diccionario de `EvFin` y la versión del resumen |

**Espacios visitados.** Si los espacios traen contorno se calcula con la traza (punto en polígono), lo que da además el tiempo en cada uno (`fuente: "traza"`). Si no, se usan los eventos `entrada_espacio` (`fuente: "eventos"`). Los espacios `macizo` no cuentan como «sin visitar».

**Giros.** Un giro es una rotación seguida en el mismo sentido que suma 30 grados o más; termina al cambiar de sentido o tras un segundo sin rotar. Media vuelta: 150 grados o más. Así un giro de 90 grados en seis pulsaciones cuenta como uno.

### Estrategia de exploración (`medidas.clasificar_estrategia`)

Heurística geométrica; gana la primera regla que se cumple:

1. **`perimetro`**: en el espacio donde hay más muestras, el 60 % o más de la distancia se hizo a un metro o menos de sus paredes **y** se recorrió la mitad o más del perímetro (dividido en trozos de un metro).
2. **`cuadricula`**: el recorrido se trocea en tramos rectos de 1,5 m o más (misma dirección ±20°); el 60 % o más de su longitud sigue un mismo eje **y** hay cuatro o más pasadas en sentidos alternos, cada una desplazada 0,5 m o más de la anterior.
3. **`objeto_a_objeto`**: hay tres o más tramos entre contactos distintos (choques, objetos usados, premios; separados más de un metro) casi rectos (distancia directa / distancia andada ≥ 0,7) **y** suman la mitad o más de la distancia.
4. **`sin_patron`** en otro caso; **`insuficiente`** si se anduvo menos de 8 m o hay menos de 40 muestras (10 segundos).

`confianza`: `alta` si los indicadores superan los umbrales con un 25 % de margen, `media` si los superan por menos, `baja` para «sin patrón», «insuficiente» y cuando se usó una aproximación.

**Límites** (el informe los repite):

- Es una descripción del recorrido, no una valoración: no dice si la estrategia era adecuada ni si se eligió a propósito.
- En espacios de menos de 3 m de ancho no se valora el perímetro (en un pasillo todo está junto a la pared).
- Sin contornos se usa la caja que encierra la traza (`aproximada: true`), y la confianza es baja.
- Solo se analiza el espacio principal. Una sesión que mezcla estrategias, o una actividad de ruta, sale «sin patrón».
- En el movimiento por pasos los tramos son rectos por construcción, lo que favorece «cuadrícula» y «objeto a objeto».
- Los umbrales son convenciones de este programa (constantes al principio de `medidas.py`); no están validados con alumnos.

## Informes (`informes.py`)

```python
informe_sesion(sesion, *, alias="", espacios=(), marcas=None) -> Informe
comparar_sesiones(lista, *, alias="") -> Informe
evolucion(lista, *, alias="") -> Informe
informe_examen(sesion, *, alias="") -> Informe
informe_real_frente_virtual(evaluaciones, lista, *, alias="") -> Informe
a_texto(informe) -> str    a_html(informe) -> str    a_csv(informe) -> str
generar(informe, formato) -> str             # "texto" | "html" | "csv"
guardar(informe, ruta, formato=None) -> Path
describir_recorrido(traza, *, espacios=(), unidad="metros", paso_m=0.7, con_tiempos=False) -> list[str]
```

Las sesiones se pasan como los diccionarios de `sesiones.obtener` / `sesiones.listar`; las evaluaciones, como `cuaderno.EvaluacionReal`.

Cada función construye un `Informe` neutro (título, secciones, tablas) y los tres formatos lo convierten, de modo que dicen lo mismo:

- **Texto**: sin dibujos de tabla; cada fila es «cabecera: valor; cabecera: valor».
- **HTML**: autónomo, sin scripts ni recursos externos; idioma declarado; un solo `h1`; cada sección con su `h2`; tablas con `caption` y `th` con `scope`; aviso en un `footer`; colores del sistema (nada depende del color). El texto del profesional se escapa.
- **CSV**: punto y coma; cada tabla con una fila de título y otra de cabeceras; los párrafos, como filas «sección; texto»; `guardar` añade BOM.

**Regla de redacción.** Los informes son descriptivos: se escribe «Tiempo activo: de 5 min a 3 min», nunca «ha mejorado». No hay diagnósticos ni recomendaciones, y todos terminan con el aviso (`informes.AVISO`) de que el rendimiento en el simulador no equivale a competencia en el lugar real. La comparación entre lo real y lo virtual solo coloca los datos juntos: no calcula correlaciones.

**`describir_recorrido`** narra un recorrido para repetirlo de oído: «Empieza en Sala de estar, mirando al este.», «Avanza 4,0 metros.», «Gira a la izquierda, unos 90 grados.», «Choca con la mesa.», «Entra en Cocina.», «Pausa de 1 min 15 s.», «Termina en Cocina.». Junta los movimientos seguidos del mismo tipo; omite giros de menos de 15 grados y desplazamientos de menos de 30 cm; los giros suaves hechos andando se cuentan como curva («Mientras tanto, va girando hacia la derecha…»).

## Pruebas

`tests/test_seguimiento_base.py`, `_alumnos.py`, `_grabadora.py`, `_medidas.py` y `_informes.py`, con la base en `tmp_path`. `tests/_seguimiento_util.py` tiene un cifrado de juguete (detecta la clave equivocada), trazas sintéticas y documentos de sesión de ejemplo.
