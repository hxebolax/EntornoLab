# Formato de entornos (`.elab`)

Un entorno de EntornoLab se guarda en un único fichero con extensión `.elab`. Este documento describe ese fichero con el detalle suficiente para leerlo, escribirlo o generarlo desde otro programa.

El código que lo implementa está en `app/dominio/formato.py` (el paquete) y `app/dominio/modelo.py` (el contenido).

## Lo esencial

- Un `.elab` es un fichero ZIP normal. Se puede abrir con cualquier programa de compresión.
- Dentro solo hay datos: textos en JSON, sonidos e imágenes. Nunca hay código, y EntornoLab no ejecuta nada de lo que contiene.
- Todos los JSON van en UTF-8.
- Las medidas van en metros. El eje X apunta al este y el eje Y al norte. Los rumbos se dan en grados: 0 es el norte, 90 el este, y crecen en el sentido del reloj.
- La versión actual del formato es la 1.

## Contenido del ZIP

```
manifiesto.json          obligatorio
entorno.json             obligatorio
actividades/<id>.json    opcional, una por actividad
sonidos/<nombre>         opcional: .wav, .ogg o .flac
imagenes/<nombre>        opcional: .png, .jpg, .jpeg, .gif, .bmp o .webp
```

No se admite ningún otro fichero ni ninguna otra carpeta, ni subcarpetas dentro de las tres indicadas. Un paquete con algo más se rechaza al abrirlo.

### `manifiesto.json`

Ficha mínima para reconocer el paquete sin leer el entorno entero.

```json
{
	"formato": 1,
	"aplicacion": "EntornoLab",
	"version": "1.0.0",
	"id": "vivienda-de-ejemplo",
	"nombre": "Vivienda de ejemplo"
}
```

| Clave | Significado |
| --- | --- |
| `formato` | Versión del formato del paquete. Si es mayor que la que entiende el programa, el paquete no se abre y se pide actualizar. |
| `aplicacion` | Siempre `EntornoLab`. |
| `version` | Versión del programa que lo escribió. Es informativa. |
| `id` | Identificador del entorno. |
| `nombre` | Nombre visible del entorno. |

### `entorno.json`

El entorno completo. Se describe en el apartado «El entorno».

### `actividades/<id>.json`

Cada actividad, juego o examen es un JSON declarativo. Este formato no las interpreta: se guardan y se devuelven tal cual, y es el paquete `app/actividades` quien las entiende (su estructura está en `docs/arquitectura.md`). El nombre del fichero es el `id` de la actividad; si una actividad no trae `id`, al cargarla toma el nombre de su fichero.

### `sonidos/` e `imagenes/`

Recursos propios del entorno. Una fuente de sonido cuyo campo `sonido` valga `timbre.ogg` se busca primero en `sonidos/timbre.ogg` del paquete, después en los complementos y por último en los sonidos de serie.

## Reglas de seguridad al abrir un paquete

Un `.elab` puede venir de otra persona, así que antes de leer nada se revisan todas sus entradas. El paquete se rechaza, con un mensaje que explica el motivo, si:

- No es un ZIP, está dañado o está cifrado con contraseña.
- Le falta `manifiesto.json` o `entorno.json`.
- Algún nombre es una ruta absoluta, contiene `..`, una barra invertida, dos puntos, caracteres de control, un nombre reservado de Windows (`con`, `nul`, `com1`…), o acaba en punto o en espacio.
- Hay un fichero de un tipo no admitido o en una carpeta no admitida.
- Hay dos entradas con el mismo nombre (sin distinguir mayúsculas).
- Tiene más de 2000 entradas.
- Un JSON pasa de 20 MB, un recurso pasa de 50 MB o el contenido total pasa de 300 MB. El tamaño se comprueba también al leer, sin fiarse del que declara el ZIP.

## Guardado seguro

Al guardar, el paquete se escribe entero en un fichero temporal junto al definitivo (`nombre.elab.tmp`), se comprueba que es un ZIP legible y solo entonces sustituye al anterior. La versión anterior queda como `nombre.elab.bak`. Un corte de luz o un disco lleno a mitad de guardar dejan intacto el fichero que había.

## Versiones y conversión

`entorno.json` lleva su propio `formato`. Al abrir un entorno de un formato anterior se convierte en memoria al actual, paso a paso (0 → 1 → 2…); el fichero no se toca hasta que se guarda. Un entorno sin `formato` se trata como formato 0 (borradores anteriores a la primera versión, que llamaban `habitaciones` a los espacios y guardaban el inicio como lista).

Quien añada un formato nuevo debe subir `FORMATO_ACTUAL` en `modelo.py` y añadir una función a `MIGRACIONES` en `formato.py`.

## Lectura tolerante

Todos los elementos se leen igual:

- Una clave que falta toma su valor de serie.
- Una clave desconocida se ignora.
- Un valor del tipo equivocado se sustituye por el valor de serie y se anota en el registro.

Por eso en un entorno escrito a mano basta con poner lo que se aparta de lo normal.

## El entorno

```json
{
	"formato": 1,
	"id": "vivienda-de-ejemplo",
	"nombre": "Vivienda de ejemplo",
	"descripcion": "Un piso pequeño para aprender a moverse por una casa: seis estancias en una planta.",
	"autor": "EntornoLab",
	"procedencia": {
		"fuente": "Entorno ficticio de ejemplo",
		"fecha": "2026",
		"escala": "1:1",
		"licencia": "CC0",
		"notas": "No representa ningún lugar real. Puede copiarse y modificarse libremente."
	},
	"georef": null,
	"inicio": {"planta": "pla-1", "x": -1.0, "y": 4.6, "rumbo": 90.0},
	"plantas": [],
	"conectores": [],
	"complementos": [],
	"contador_ids": 23
}
```

| Clave | Tipo | Significado |
| --- | --- | --- |
| `formato` | entero | Versión del formato del entorno. |
| `id`, `nombre`, `descripcion`, `autor` | texto | Identificación del entorno. |
| `procedencia` | objeto | De dónde sale: `fuente`, `fecha`, `escala`, `licencia`, `notas`. Todas opcionales. |
| `georef` | objeto o `null` | `{"lat0": …, "lon0": …}` si viene de un mapa real: la latitud y longitud del punto (0, 0). |
| `inicio` | posición | Punto y rumbo donde empieza el alumno si la actividad no dice otra cosa. |
| `plantas` | lista | Las plantas, de abajo arriba. |
| `conectores` | lista | Escaleras, rampas y ascensores que unen plantas. |
| `complementos` | lista de textos | Identificadores de los complementos de objetos que usa. |
| `contador_ids` | entero | Último número usado al generar identificadores (ver «Identificadores»). |

Una **posición** es `{"planta": id, "x": metros, "y": metros, "rumbo": grados}`.

Un **punto** es una lista de dos números, `[x, y]`. Un **contorno** es una lista de puntos que forma un polígono cerrado; el último punto no repite el primero. El lado número `i` va del punto `i` al siguiente.

### Identificadores

Cada planta y cada elemento tiene un `id` de texto, único en todo el entorno. EntornoLab los genera con un prefijo y un número (`esp-12`, `abe-8`, `obj-40`) tomado de `contador_ids`, que solo crece: un identificador borrado no se vuelve a usar, para que una actividad que nombraba un elemento borrado no acabe apuntando a otro.

En un entorno escrito a mano vale cualquier texto siempre que no se repita. Los prefijos que usa el programa son `pla` (planta), `esp` (espacio), `par` (pared), `abe` (abertura), `obj` (objeto), `fue` (fuente de sonido), `zon` (zona de suelo), `ref` (referencia), `via` (vía) y `con` (conector).

### Planta

```json
{
	"id": "pla-1",
	"nombre": "Vivienda",
	"descripcion": "",
	"nivel": 0,
	"altura_m": 0.0,
	"exterior": false,
	"espacios": [],
	"paredes": [],
	"aberturas": [],
	"objetos": [],
	"fuentes": [],
	"zonas": [],
	"referencias": [],
	"vias": []
}
```

`nivel` es el número de planta (0 la baja, negativos los sótanos) y `altura_m` la cota de su suelo. `exterior` es `true` en las plantas de calle.

### Espacio

Zona transitable con nombre: una habitación, un pasillo, una acera, una calzada.

```json
{
	"id": "esp-2",
	"nombre": "Pasillo",
	"descripcion": "",
	"tipo": "pasillo",
	"contorno": [[0.0, 4.0], [8.0, 4.0], [8.0, 5.2], [0.0, 5.2]],
	"cerrado": true,
	"lados_abiertos": [],
	"suelo": "madera",
	"acustica": "pasillo",
	"pared_material": "ladrillo",
	"macizo": false,
	"datos": {}
}
```

| Clave | Significado |
| --- | --- |
| `tipo` | `habitacion`, `pasillo`, `vestibulo`, `escalera`, `cabina`, `exterior`, `acera`, `calzada`, `paso_peatones`, `plaza`, `parque`, `sendero` o `edificio`. |
| `contorno` | Polígono simple (no se corta a sí mismo), en sentido antihorario. |
| `cerrado` | `true`: sus lados son paredes (interiores). `false`: es solo una zona (exteriores). |
| `lados_abiertos` | Índices de los lados sin pared cuando `cerrado` es `true`. |
| `suelo` | `baldosa`, `madera`, `moqueta`, `alfombra`, `hormigon`, `asfalto`, `acera`, `adoquin`, `tierra`, `hierba`, `grava`, `metal`, `arena`, `agua`, `tactil_botones` o `tactil_rayas`. |
| `acustica` | Eco del lugar: `seca`, `habitacion`, `sala_grande`, `pasillo`, `bano`, `escalera`, `nave`, `exterior`, `calle` o `parque`. |
| `pared_material` | Material de sus paredes: `ladrillo`, `hormigon`, `yeso`, `madera`, `cristal`, `metal`, `piedra`, `valla`, `seto`. |
| `macizo` | `true`: no se puede entrar (un edificio visto desde la calle). Todo su contorno es sólido. |
| `datos` | Atributos propios del tipo. Ver más abajo. |

**Las paredes de una habitación no se guardan.** Se deducen de su contorno: cada lado de un espacio `cerrado` es una pared, salvo los `lados_abiertos` y salvo los tramos que ocupan sus aberturas. Dos habitaciones adosadas comparten el lado común, que cuenta como una sola pared. En un rectángulo creado por el programa los lados van en este orden: 0 sur, 1 este, 2 norte, 3 oeste.

Claves de `datos` que usa el programa:

| Clave | Dónde | Significado |
| --- | --- | --- |
| `uso` | Habitaciones | `dormitorio`, `salon`, `cocina`, `bano`, `aula` u `oficina`. Lo lee el amueblado asistido. |
| `via` | Calzadas, aceras y pasos | Identificador de la vía a la que pertenecen. |
| `lado`, `ancho`, `tramo` | Aceras | Lado de la vía (`izquierda` o `derecha` según el sentido del eje), anchura y, si un cruce la partió, a qué lado del cruce queda. |
| `cruce`, `vias`, `centro` | Cruces | Marca la calzada común de dos vías. |
| `semaforo`, `sonoro`, `pulsador`, `isleta` | Pasos de peatones | Verdadero o falso. |
| `ciclo` | Pasos con semáforo | Segundos de cada fase: `verde_peatones_s`, `intermitente_s`, `rojo_peatones_s`. |
| `longitud`, `ancho`, `rumbo_cruce`, `extremos` | Pasos de peatones | Metros de bordillo a bordillo, anchura del paso, rumbo en que se cruza y los dos puntos de bordillo. |
| `zonas`, `referencias` | Pasos de peatones | Identificadores del pavimento táctil y de los semáforos creados con el paso (se borran con él). |

Ejemplo real de un paso de peatones con semáforo sonoro:

```json
{
	"id": "esp-15",
	"nombre": "Paso con semáforo de Calle Mayor",
	"descripcion": "Cruza la Calle Mayor al oeste del cruce. El semáforo pita cuando está verde para los peatones.",
	"tipo": "paso_peatones",
	"contorno": [[-10.0, 3.5], [-10.0, -3.5], [-6.0, -3.5], [-6.0, 3.5]],
	"cerrado": false,
	"suelo": "asfalto",
	"acustica": "calle",
	"datos": {
		"via": "via-2",
		"semaforo": true,
		"sonoro": true,
		"pulsador": true,
		"isleta": false,
		"longitud": 7.0,
		"ancho": 4.0,
		"rumbo_cruce": 180.0,
		"extremos": [[-8.0, 3.5], [-8.0, -3.5]],
		"zonas": ["zon-16", "zon-18"],
		"referencias": ["ref-17", "ref-19"],
		"ciclo": {"verde_peatones_s": 25, "intermitente_s": 5, "rojo_peatones_s": 45}
	}
}
```

### Pared

Tabique, valla o muro suelto. Solo hace falta para lo que no es el contorno de una habitación.

```json
{
	"id": "par-30",
	"nombre": "Valla del patio",
	"descripcion": "",
	"a": [2.0, 5.0],
	"b": [6.0, 5.0],
	"grosor": 0.1,
	"material": "valla",
	"bloquea_paso": true,
	"bloquea_sonido": false,
	"altura": 1.2
}
```

`bloquea_sonido` es `false` en una valla o un cristal bajo: cortan el paso pero se oye a través.

### Abertura

Puerta, hueco sin puerta, ventana o portal. Ocupa un tramo recto, de `a` a `b`, que tiene que estar sobre el lado de un espacio con paredes o sobre una pared suelta (con un margen de 5 centímetros).

```json
{
	"id": "abe-8",
	"nombre": "Puerta de la calle",
	"descripcion": "Es la puerta de la casa; da al rellano.",
	"tipo": "puerta",
	"a": [-2.0, 4.15],
	"b": [-2.0, 5.05],
	"estado": "cerrada",
	"hoja": "batiente",
	"material": "madera",
	"es_salida": true
}
```

| Clave | Valores |
| --- | --- |
| `tipo` | `puerta`, `hueco`, `ventana`, `portal`. |
| `estado` | `abierta`, `cerrada`, `con_llave`. |
| `hoja` | `batiente`, `corredera`, `automatica`, `ninguna`. |
| `es_salida` | `true` si cuenta como salida del edificio en juegos y exámenes. |

Cómo afecta al paso y al sonido:

| Abertura | ¿Se puede pasar? | ¿Tapa el sonido? |
| --- | --- | --- |
| Hueco, o puerta o portal abiertos | Sí | No |
| Puerta o portal cerrados | No, hasta que el alumno la abre | En parte |
| Puerta o portal con llave | No | En parte |
| Ventana | No | En parte |

Un portal es una abertura que pertenece a la vez al edificio y a la calle: se cruza andando, sin cambio de pantalla. El portal de un edificio `macizo` es solo una referencia para orientarse; no abre hueco, porque dentro no hay nada.

### Objeto

Un objeto colocado, tomado de un complemento. Es una forma con medidas reales que el alumno se encuentra y tiene que esquivar.

```json
{
	"id": "obj-40",
	"nombre": "Cama",
	"descripcion": "Cama de matrimonio con cabecero.",
	"tipo": "hogar/cama",
	"x": 2.5,
	"y": 7.7,
	"rumbo": 180.0,
	"ancho": 1.5,
	"fondo": 2.0,
	"alto": 0.5,
	"variante": "matrimonio",
	"estado": "",
	"datos": {}
}
```

| Clave | Significado |
| --- | --- |
| `tipo` | `<complemento>/<objeto>`. Si el complemento no está instalado, el objeto se conserva como una caja con sus medidas. También vale `caja` para un obstáculo sin ficha. |
| `x`, `y` | Centro del objeto. |
| `rumbo` | Hacia dónde mira su frente. Con rumbo 0 el ancho va de oeste a este y el fondo de sur a norte. |
| `ancho`, `fondo`, `alto` | Medidas reales en metros. |
| `variante` | Variante elegida del catálogo, o vacío. |
| `estado` | Estado actual (`abierto`, `cerrado`, `encendido`…), de los que declare su ficha. |
| `datos` | Sobrescrituras de la ficha del catálogo para este objeto: `bloquea`, `material`, `altura_base`. |

### Fuente de sonido

```json
{
	"id": "fue-17",
	"nombre": "Frigorífico",
	"descripcion": "Zumba todo el rato en la esquina sureste de la cocina.",
	"x": 7.6,
	"y": 0.5,
	"sonido": "frigorifico",
	"volumen": 0.5,
	"radio": 6.0,
	"bucle": true,
	"intervalo": 0.0,
	"altura": 1.0
}
```

`sonido` es el nombre de un sonido (del paquete, de un complemento o de serie). `radio` es hasta dónde se oye, en metros. Con `bucle` en `false`, `intervalo` son los segundos entre repeticiones. `altura` es a cuántos metros del suelo suena.

### Zona de suelo

Trozo de suelo distinto del resto del espacio: una alfombra, una banda de pavimento táctil.

```json
{
	"id": "zon-23",
	"nombre": "Alfombra del salón",
	"descripcion": "",
	"contorno": [[1.2, 1.0], [3.4, 1.0], [3.4, 2.6], [1.2, 2.6]],
	"suelo": "alfombra"
}
```

### Referencia

Punto de interés o de orientación.

```json
{
	"id": "ref-20",
	"nombre": "Felpudo",
	"descripcion": "Se nota bajo los pies nada más entrar.",
	"x": -1.5,
	"y": 4.6,
	"tipo": "tactil",
	"permanente": true
}
```

`tipo`: `punto`, `sonora`, `tactil`, `olor`, `parada`, `semaforo`, `portal`, `comercio` o `mobiliario`. `permanente` distingue las referencias fijas de las pasajeras (un coche aparcado, unas obras).

### Vía

Eje de una calle, por el que circula el tráfico. Solo tiene sentido en plantas exteriores.

```json
{
	"id": "via-2",
	"nombre": "Calle Mayor",
	"descripcion": "Calle principal, con bastante tráfico en los dos sentidos.",
	"eje": [[-40.0, 0.0], [40.0, 0.0]],
	"ancho": 7.0,
	"carriles": 2,
	"sentido": "doble",
	"trafico": 2,
	"velocidad_kmh": 30.0
}
```

`ancho` es el de la calzada. `sentido`: `doble`, `ida` (del primer punto del eje al último) o `vuelta`. `trafico` va de 0 (ninguno) a 3 (intenso).

La calzada y las aceras son espacios aparte (tipos `calzada` y `acera`) con `datos.via` igual al identificador de la vía.

### Conector

Une plantas. Va en la lista `conectores` del entorno, no dentro de una planta.

Una escalera, una rampa o una escalera mecánica tienen `tramos`:

```json
{
	"id": "con-49",
	"nombre": "Escalera principal",
	"descripcion": "Dos tramos de nueve peldaños con un rellano en medio.",
	"tipo": "escalera",
	"tramos": [
		{
			"desde": {"planta": "pla-1", "x": 8.8, "y": 8.6, "rumbo": 0.0},
			"hasta": {"planta": "pla-2", "x": 10.2, "y": 8.6, "rumbo": 180.0},
			"longitud_m": 6.0,
			"peldanos": 18
		}
	],
	"paradas": [],
	"datos": {"pasamanos": "ambos", "anchura": 1.2}
}
```

`desde` es la boca de abajo y el rumbo en que se sube; `hasta`, la boca de arriba y el rumbo con que se sale. `peldanos` es 0 en una rampa. En `datos`: `pasamanos` (`izquierda`, `derecha`, `ambos`, `ninguno`), `anchura` y, en las rampas, `pendiente_pct`.

Un ascensor tiene `paradas`:

```json
{
	"id": "con-50",
	"nombre": "Ascensor",
	"descripcion": "Avisa de la planta con voz.",
	"tipo": "ascensor",
	"tramos": [],
	"paradas": [
		{"planta": "pla-1", "puerta": {"planta": "pla-1", "x": 12.0, "y": 7.4, "rumbo": 0.0}},
		{"planta": "pla-2", "puerta": {"planta": "pla-2", "x": 12.0, "y": 7.4, "rumbo": 0.0}}
	],
	"datos": {"aviso_hablado": true, "puerta": "automatica"}
}
```

`puerta` es el punto delante de la puerta del ascensor, con el rumbo mirando a la cabina.

## Un entorno mínimo escrito a mano

Una habitación de 4 por 3 metros con una puerta en la pared sur. Todo lo que no aparece toma su valor de serie.

`manifiesto.json`:

```json
{"formato": 1, "aplicacion": "EntornoLab", "id": "mi-cuarto", "nombre": "Mi cuarto"}
```

`entorno.json`:

```json
{
	"formato": 1,
	"id": "mi-cuarto",
	"nombre": "Mi cuarto",
	"inicio": {"planta": "baja", "x": 2.0, "y": 1.5, "rumbo": 0},
	"plantas": [
		{
			"id": "baja",
			"nombre": "Planta baja",
			"espacios": [
				{"id": "cuarto", "nombre": "Cuarto", "contorno": [[0, 0], [4, 0], [4, 3], [0, 3]]}
			],
			"aberturas": [
				{"id": "puerta", "nombre": "Puerta", "a": [1.5, 0], "b": [2.32, 0], "estado": "abierta"}
			]
		}
	]
}
```

Se comprimen los dos ficheros en un ZIP (sin carpeta que los envuelva) y se le pone la extensión `.elab`.

## Comprobar un entorno

`app.dominio.validacion.validar(entorno, catalogo)` devuelve la lista de problemas, cada uno con su gravedad (`error` o `aviso`), un código estable, el mensaje, el identificador del elemento y de la planta, y una sugerencia. Comprueba, entre otras cosas:

- Contornos válidos: al menos tres vértices, con superficie y sin cortarse.
- Espacios cerrados sin ninguna puerta ni hueco.
- Aberturas que no caen sobre ninguna pared.
- Conectores hacia plantas que no existen o con un extremo fuera de todo espacio.
- Objetos fuera de su espacio, solapados, que tapan una puerta o que dejan un paso más estrecho que el mínimo.
- Punto de inicio fuera de todo espacio, dentro de un muro o dentro de un objeto.
- Identificadores vacíos o repetidos.
- Fuentes de sonido sin nombre de sonido.
- Plantas sin espacios.

Los entornos de ejemplo de `data/ejemplos` se generan con `tools/generar_ejemplos.py` y sirven de muestra de todo lo anterior.
