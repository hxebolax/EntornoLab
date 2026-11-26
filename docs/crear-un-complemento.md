# Crear un complemento propio

Guía paso a paso para hacer a mano un complemento de objetos de EntornoLab. No hace falta saber programar: un complemento es una carpeta con un fichero de texto que se escribe con el Bloc de notas.

La referencia completa de cada clave está en `docs/formato-de-complementos.md`. Aquí se cuenta el camino, con un ejemplo entero.

## Qué va a salir de aquí

Un complemento llamado «Mi centro» con seis objetos para la recepción de un centro de día:

- un mostrador en ele;
- un banco de espera, con tres tamaños;
- una mesa redonda;
- un cartel que cuelga del techo (un obstáculo que el bastón no detecta);
- una máquina de café que zumba;
- un felpudo, que no corta el paso pero se nota al pisarlo.

Al terminar, esos objetos aparecen en el catálogo del Estudio como `mi-centro/mostrador`, `mi-centro/banco_espera`, etc., y se pueden colocar en cualquier entorno.

## Antes de empezar: qué es un objeto

Un objeto no es un dibujo. Es una **forma con medidas reales**: su huella vista desde arriba, su altura, de qué está hecho y cómo se comporta. El alumno no lo ve: se lo encuentra, choca con él, lo rodea, lo oye.

Por eso lo que importa al definirlo es:

- **Cuánto mide de verdad**, en metros. Mida el mueble real con una cinta o busque sus medidas habituales.
- **Qué forma tiene su huella**: un rectángulo, un círculo, una ele o un polígono.
- **Si corta el paso** y **a qué altura está**. Un cartel colgado a la altura de la cabeza no lo encuentra el bastón.
- **Cómo suena** al golpearlo y si hace algún ruido él solo.
- **Qué se puede hacer con él**: abrirlo, sentarse, pulsar un botón.

## Paso 1. Crear la carpeta

1. Abra la carpeta de EntornoLab y, dentro, `data` y después `plugins`.
2. Cree una carpeta nueva. Su nombre es el **identificador** del complemento: solo minúsculas sin tildes ni eñes, cifras, guion y guion bajo. Para el ejemplo: `mi-centro`.

Dentro de esa carpeta solo puede haber:

```
mi-centro/
	complemento.json        obligatorio: la ficha
	sonidos/                opcional: ficheros .wav, .ogg o .flac
	imagenes/               opcional: .png, .jpg, .jpeg, .gif, .bmp o .webp
	locales/en.json         opcional: traducciones, una por idioma
	LEEME.md                opcional: explicación y licencia
```

Nada más: ni otras carpetas, ni subcarpetas, ni otros tipos de fichero.

## Paso 2. Escribir la ficha general

Dentro de `mi-centro`, cree un fichero de texto llamado `complemento.json` (compruebe que no se queda en `complemento.json.txt`). Guárdelo con codificación UTF-8, que es la que usa el Bloc de notas de Windows 11.

Empiece por esto:

```json
{
	"formato": 1,
	"id": "mi-centro",
	"nombre": "Mi centro",
	"version": "1.0.0",
	"autor": "Su nombre",
	"licencia": "CC BY 4.0",
	"descripcion": "Objetos de la recepción de mi centro de día.",
	"categorias": {"recepcion": "Recepción"},
	"estados": {"libre": "Libre", "ocupado": "Ocupado"},
	"objetos": []
}
```

- `id` tiene que ser igual que el nombre de la carpeta.
- `version`: súbala cada vez que comparta una versión nueva (`1.0.1`, `1.1.0`).
- `licencia`: con qué permiso lo comparte. `CC BY 4.0` deja usarlo y modificarlo citándole; `CC0` lo deja sin condiciones.
- `categorias`: los grupos en que se ordenan sus objetos en el catálogo, con su nombre visible.
- `estados`: el nombre visible de cada estado que usen los objetos (se explica en el paso 5).
- `objetos`: la lista de fichas, que ahora está vacía.

### Reglas de escritura de un JSON

Casi todos los fallos al escribir un complemento son de puntuación:

- Los textos van entre comillas dobles rectas (`"así"`), no curvas («así» ni “así”).
- Los números llevan **punto** decimal, no coma: `0.75`.
- Los elementos de una lista se separan con comas, y **después del último no va coma**.
- `true` y `false` se escriben en minúsculas y sin comillas.
- Cada `{` y cada `[` que se abre tiene que cerrarse.
- No se pueden poner comentarios dentro del fichero.

## Paso 3. El primer objeto: un banco

Entre los corchetes de `"objetos": []` va la ficha de cada objeto, entre llaves y separadas por comas. La de un banco de sala de espera:

```json
{
	"id": "banco_espera",
	"nombre": "Banco de espera",
	"categoria": "recepcion",
	"etiquetas": ["banco", "asiento", "sala de espera"],
	"descripcion": "Banco de tres plazas contra la pared, con asiento duro de plástico.",
	"ambito": ["interior"],
	"forma": {"tipo": "rectangulo"},
	"medidas": {
		"ancho": [1.1, 1.7, 2.3],
		"fondo": [0.55, 0.6, 0.7],
		"alto": [0.78, 0.8, 0.85]
	},
	"variantes": [
		{"id": "dos_plazas", "nombre": "De dos plazas", "ancho": 1.15, "fondo": 0.6, "alto": 0.8},
		{"id": "tres_plazas", "nombre": "De tres plazas", "ancho": 1.7, "fondo": 0.6, "alto": 0.8},
		{"id": "cuatro_plazas", "nombre": "De cuatro plazas", "ancho": 2.3, "fondo": 0.6, "alto": 0.8}
	],
	"colocacion": ["pared", "suelo"],
	"bloquea": true,
	"material": "plastico",
	"sonidos": {"golpe": "golpe/plastico"},
	"estados": ["libre", "ocupado"],
	"acciones": [
		{"id": "sentarse", "nombre": "Sentarse", "de": "libre", "a": "ocupado"},
		{"id": "levantarse", "nombre": "Levantarse", "de": "ocupado", "a": "libre"}
	],
	"contenedor": true,
	"simbolo": {"letra": "Ba", "color": "#2E6DA4"}
}
```

Qué dice cada línea:

| Clave | En el ejemplo | Para qué sirve |
| --- | --- | --- |
| `id` | `banco_espera` | Nombre interno, con las mismas reglas que el del complemento. No lo cambie después: los entornos que usen el objeto lo guardan. |
| `nombre` | Banco de espera | Lo que se lee y se oye en el catálogo. |
| `categoria` | `recepcion` | Una de las claves de `categorias`. |
| `etiquetas` | banco, asiento… | Palabras por las que se le puede buscar. Ponga los sinónimos. |
| `descripcion` | Banco de tres plazas… | Lo que oye el alumno. Breve; diga qué es y cómo se percibe con el tacto, el bastón o el oído. No dé un color como único dato. |
| `ambito` | interior | `interior`, `exterior` o los dos. |
| `forma` | rectángulo | La huella vista desde arriba. Ver el paso 4. |
| `medidas` | tres números por medida | **Mínimo, por defecto y máximo**, en metros. |
| `variantes` | dos, tres, cuatro plazas | Tamaños con nombre. Cada uno debe caer dentro del rango. |
| `colocacion` | pared, suelo | Dónde se puede poner: `suelo`, `pared`, `esquina`, `acera`, `calzada`. |
| `bloquea` | `true` | Corta el paso. |
| `material` | plástico | De qué está hecho. |
| `sonidos` | `golpe/plastico` | Qué suena al chocar con él. Ver el paso 6. |
| `estados` y `acciones` | libre, ocupado | Lo que se puede hacer con él. Ver el paso 5. |
| `contenedor` | `true` | En un juego se puede esconder un premio dentro o debajo. |
| `simbolo` | Ba, azul | Una o dos letras y un color `#RRGGBB` con que se dibuja su huella en el plano del profesional. |

### Las medidas, con cuidado

- El **ancho** va de lado a lado mirando el objeto de frente; el **fondo**, de delante a atrás; el **alto** es su altura.
- El número de en medio es el tamaño con que sale el objeto al colocarlo.
- El mínimo y el máximo son los tamaños más pequeño y más grande **que existen de verdad**. El programa los usa para que un objeto nunca quede más grande que la habitación: si no cabe con su tamaño por defecto, prueba la variante mayor que quepa; si no, lo encoge sin bajar del mínimo; y si ni así cabe, no lo coloca.
- Si pone un máximo exagerado «por si acaso», alguien acabará con una silla de tres metros.

Algunas medidas habituales para orientarse: una mesa mide de 72 a 76 cm de alto; una silla, 45 cm hasta el asiento y 90 con el respaldo; una encimera, 90 cm de alto y 60 de fondo; una puerta, de 72 a 92 cm de ancho; un mostrador de atención, 110 cm de alto; un bolardo, de 50 a 110 cm.

## Paso 4. Las formas

Hay cuatro tipos de forma.

| `tipo` | Huella |
| --- | --- |
| `rectangulo` | Un rectángulo de ancho por fondo. |
| `circulo` | Un círculo (o un óvalo, si el ancho y el fondo son distintos). |
| `ele` | Una L. |
| `poligono` | La figura que dibujen los puntos que se le den. |

Una mesa redonda:

```json
{
	"id": "mesa_redonda",
	"nombre": "Mesa redonda",
	"categoria": "recepcion",
	"etiquetas": ["mesa", "mesa circular"],
	"descripcion": "Mesa redonda de una sola pata central. Se rodea sin esquinas.",
	"forma": {"tipo": "circulo"},
	"medidas": {"ancho": [0.8, 1.1, 1.4], "fondo": [0.8, 1.1, 1.4], "alto": [0.72, 0.75, 0.78]},
	"material": "madera",
	"sonidos": {"golpe": "golpe/madera"},
	"simbolo": {"letra": "Mr", "color": "#8B5A2B"}
}
```

Un mostrador en ele, dibujado punto a punto:

```json
{
	"id": "mostrador",
	"nombre": "Mostrador en ele",
	"categoria": "recepcion",
	"etiquetas": ["mostrador", "recepción", "información"],
	"descripcion": "Mostrador alto que dobla en ángulo recto. Se sigue con la mano hasta la esquina.",
	"forma": {"tipo": "poligono", "puntos": [[0, 0], [1, 0], [1, 0.4], [0.3, 0.4], [0.3, 1], [0, 1]]},
	"medidas": {"ancho": [1.8, 2.4, 3.0], "fondo": [1.4, 1.8, 2.4], "alto": [1.05, 1.1, 1.15]},
	"colocacion": ["suelo", "esquina"],
	"material": "madera",
	"sonidos": {"golpe": "golpe/madera"},
	"contenedor": true,
	"simbolo": {"letra": "Mo", "color": "#8B5A2B"}
}
```

Cómo se dibuja un polígono:

- Imagine el objeto visto desde arriba, metido en un cuadrado. Cada punto son dos números entre 0 y 1.
- El primer número va de 0 (lado izquierdo) a 1 (lado derecho).
- El segundo va de 0 (la parte de **atrás**, la que se arrima a la pared) a 1 (el **frente**).
- Los puntos se dan en orden, recorriendo el borde. El último se une solo con el primero.
- El borde no puede cruzarse consigo mismo.
- Procure que la figura toque los cuatro lados del cuadrado: así el ancho y el fondo que declare serán los de verdad.

En el mostrador: se empieza atrás a la izquierda `[0, 0]`, se va atrás a la derecha `[1, 0]`, se avanza un poco `[1, 0.4]`, se vuelve hacia la izquierda `[0.3, 0.4]`, se avanza hasta el frente `[0.3, 1]` y se termina delante a la izquierda `[0, 1]`. Ese cuadrado se estira luego a los 2,40 por 1,80 metros del mostrador.

## Paso 5. Estados y acciones

Un objeto puede tener **estados** (cerrado, abierto) y **acciones** que lo llevan de uno a otro.

- `estados` es la lista de estados. El primero es el inicial.
- Cada acción tiene `id`, `nombre`, el estado `de` del que parte y el estado `a` al que llega. Puede llevar un `sonido`.
- Una acción sin `de` ni `a` es un gesto que no cambia nada: pulsar un botón, tocar una campana.
- El nombre visible de cada estado se pone en la tabla `estados` de la ficha general (paso 2).

Si además añade `"paso_libre": ["abierto"]`, el objeto corta el paso salvo cuando está abierto: sirve para un torno o para una puerta de cristal.

## Paso 6. Sonidos

```json
"sonidos": {
	"golpe": "golpe/metal",
	"uso": "sonidos/cafe.ogg",
	"propio": {"sonido": "fuente/maquina_expendedora", "volumen": 0.4, "radio": 6}
}
```

- `golpe`: lo que suena al chocar con el objeto.
- `uso`: lo que suena al usarlo.
- `propio`: un sonido que emite él solo todo el rato, con su `volumen` (de 0 a 1) y su `radio` en metros (hasta dónde se oye). Es lo que más ayuda al alumno a orientarse: un frigorífico, una fuente, una máquina. Si le añade `"estado": "encendido"`, solo suena en ese estado.

Hay dos maneras de nombrar un sonido:

- **Uno de los que trae el programa.** Se escribe su nombre sin extensión. Los golpes por material: `golpe/madera`, `golpe/metal`, `golpe/cristal`, `golpe/plastico`, `golpe/tela`, `golpe/piedra`, `golpe/ladrillo`. Las puertas: `puerta/abrir`, `puerta/cerrar`. Lo que suena solo: `fuente/frigorifico`, `fuente/grifo`, `fuente/reloj`, `fuente/television`, `fuente/ventilador`, `fuente/fuente_agua`, `fuente/maquina_expendedora`, `fuente/campanas`, `fuente/pajaros`. La lista entera está en `docs/sonido.md`.
- **Uno suyo.** Grábelo, guárdelo en la carpeta `sonidos` del complemento como `.ogg`, `.wav` o `.flac` y escriba `sonidos/` y el nombre del fichero con su extensión: `sonidos/cafe.ogg`.

Consejos para un sonido propio: corto (de uno a cuatro segundos), en mono, sin silencio al principio y no muy fuerte. Si es para `propio`, que se pueda repetir sin que se note el corte. Grabe usted mismo o use sonidos cuya licencia le permita compartirlos, y dígalo en el `LEEME.md`.

La máquina de café del ejemplo, que usa solo sonidos del programa:

```json
{
	"id": "maquina_cafe",
	"nombre": "Máquina de café",
	"categoria": "recepcion",
	"etiquetas": ["máquina de café", "cafetera", "vending"],
	"descripcion": "Máquina de café alta como un armario. Zumba todo el rato: se oye desde la puerta.",
	"medidas": {"ancho": [0.55, 0.6, 0.7], "fondo": [0.6, 0.7, 0.8], "alto": [1.7, 1.83, 1.85]},
	"colocacion": ["pared", "esquina"],
	"material": "metal",
	"sonidos": {
		"golpe": "golpe/metal",
		"propio": {"sonido": "fuente/maquina_expendedora", "volumen": 0.4, "radio": 6}
	},
	"acciones": [{"id": "pulsar", "nombre": "Pedir un café", "sonido": "interfaz/elegir"}],
	"simbolo": {"letra": "Mc", "color": "#B03A2E"}
}
```

## Paso 7. Obstáculos colgados y objetos que se pisan

**Un obstáculo colgado.** Si la parte más baja del objeto no llega al suelo, el bastón pasa por debajo y la persona se da con él en el pecho o en la cabeza. Son los obstáculos que más conviene ensayar. Se declaran con dos claves:

- `altura_base`: los metros que hay del suelo a su parte más baja.
- `detectable_baston`: `false`.

```json
{
	"id": "cartel_colgante",
	"nombre": "Cartel colgante",
	"categoria": "recepcion",
	"etiquetas": ["cartel", "rótulo", "obstáculo en altura"],
	"descripcion": "Cartel que cuelga del techo sobre el mostrador. Queda a la altura de la cabeza de alguien alto.",
	"medidas": {"ancho": [0.8, 1.2, 2.0], "fondo": [0.05, 0.1, 0.2], "alto": [0.3, 0.4, 0.6]},
	"altura_base": 1.8,
	"detectable_baston": false,
	"material": "plastico",
	"sonidos": {"golpe": "golpe/plastico"},
	"simbolo": {"letra": "Cc", "color": "#7D3C98"}
}
```

**Un objeto que se pisa.** Una alfombra, un felpudo o una franja de pavimento táctil no cortan el paso, pero se notan. Se declaran con `"bloquea": false` y, si cambian el suelo, con `suelo`. Con `aviso` se le dice una frase al alumno cuando lo pisa.

```json
{
	"id": "felpudo",
	"nombre": "Felpudo",
	"categoria": "recepcion",
	"etiquetas": ["felpudo", "alfombra de entrada"],
	"descripcion": "Felpudo ancho detrás de la puerta. Se nota bajo los pies: acabas de entrar.",
	"medidas": {"ancho": [1.0, 1.5, 2.5], "fondo": [0.6, 0.9, 1.5], "alto": [0.01, 0.02, 0.03]},
	"bloquea": false,
	"suelo": "moqueta",
	"aviso": "Estás en el felpudo de la entrada.",
	"material": "tela",
	"sonidos": {"golpe": "golpe/tela"},
	"simbolo": {"letra": "Fe", "color": "#566573"}
}
```

Los suelos que existen son: `baldosa`, `madera`, `moqueta`, `alfombra`, `hormigon`, `asfalto`, `acera`, `adoquin`, `tierra`, `hierba`, `grava`, `metal`, `arena`, `agua`, `tactil_botones` y `tactil_rayas`.

## El ejemplo completo

Este es el `complemento.json` entero, con los seis objetos ya clasificados (paso 8). Puede copiarlo tal cual en `data/plugins/mi-centro/complemento.json`.

<!-- ejemplo-completo -->
```json
{
	"formato": 1,
	"id": "mi-centro",
	"nombre": "Mi centro",
	"version": "1.0.0",
	"autor": "Su nombre",
	"licencia": "CC BY 4.0",
	"descripcion": "Objetos de la recepción de mi centro de día.",
	"categorias": {
		"recepcion": "Recepción"
	},
	"estados": {
		"libre": "Libre",
		"ocupado": "Ocupado"
	},
	"subcategorias": {
		"mostradores": "Mostradores",
		"asientos": "Asientos",
		"mesas": "Mesas",
		"senales": "Señales y carteles",
		"maquinas": "Máquinas",
		"suelo": "Lo que se pisa"
	},
	"objetos": [
		{
			"id": "mostrador",
			"nombre": "Mostrador en ele",
			"categoria": "recepcion",
			"subcategoria": "mostradores",
			"etiquetas": ["mostrador", "recepción", "información"],
			"descripcion": "Mostrador alto que dobla en ángulo recto. Se sigue con la mano hasta la esquina.",
			"ambito": ["interior"],
			"forma": {"tipo": "poligono", "puntos": [[0, 0], [1, 0], [1, 0.4], [0.3, 0.4], [0.3, 1], [0, 1]]},
			"medidas": {"ancho": [1.8, 2.4, 3.0], "fondo": [1.4, 1.8, 2.4], "alto": [1.05, 1.1, 1.15]},
			"colocacion": ["suelo", "esquina"],
			"material": "madera",
			"sonidos": {"golpe": "golpe/madera"},
			"contenedor": true,
			"simbolo": {"letra": "Mo", "color": "#8B5A2B"},
			"funcion": "mostrador",
			"lugares": ["centro_salud", "residencia"],
			"estancias": ["recepcion"],
			"frecuencia": "muy_comun"
		},
		{
			"id": "banco_espera",
			"nombre": "Banco de espera",
			"categoria": "recepcion",
			"subcategoria": "asientos",
			"etiquetas": ["banco", "asiento", "sala de espera"],
			"descripcion": "Banco de tres plazas contra la pared, con asiento duro de plástico.",
			"ambito": ["interior"],
			"forma": {"tipo": "rectangulo"},
			"medidas": {"ancho": [1.1, 1.7, 2.3], "fondo": [0.55, 0.6, 0.7], "alto": [0.78, 0.8, 0.85]},
			"variantes": [
				{"id": "dos_plazas", "nombre": "De dos plazas", "ancho": 1.15, "fondo": 0.6, "alto": 0.8},
				{"id": "tres_plazas", "nombre": "De tres plazas", "ancho": 1.7, "fondo": 0.6, "alto": 0.8},
				{"id": "cuatro_plazas", "nombre": "De cuatro plazas", "ancho": 2.3, "fondo": 0.6, "alto": 0.8}
			],
			"colocacion": ["pared", "suelo"],
			"bloquea": true,
			"material": "plastico",
			"sonidos": {"golpe": "golpe/plastico"},
			"estados": ["libre", "ocupado"],
			"acciones": [
				{"id": "sentarse", "nombre": "Sentarse", "de": "libre", "a": "ocupado"},
				{"id": "levantarse", "nombre": "Levantarse", "de": "ocupado", "a": "libre"}
			],
			"contenedor": true,
			"simbolo": {"letra": "Ba", "color": "#2E6DA4"},
			"funcion": "asiento",
			"lugares": ["centro_salud", "residencia"],
			"estancias": ["sala_espera", "recepcion"],
			"frecuencia": "muy_comun",
			"relacionados": ["mesa_redonda", "maquina_cafe"]
		},
		{
			"id": "mesa_redonda",
			"nombre": "Mesa redonda",
			"categoria": "recepcion",
			"subcategoria": "mesas",
			"etiquetas": ["mesa", "mesa circular"],
			"descripcion": "Mesa redonda de una sola pata central. Se rodea sin esquinas.",
			"ambito": ["interior"],
			"forma": {"tipo": "circulo"},
			"medidas": {"ancho": [0.8, 1.1, 1.4], "fondo": [0.8, 1.1, 1.4], "alto": [0.72, 0.75, 0.78]},
			"material": "madera",
			"sonidos": {"golpe": "golpe/madera"},
			"simbolo": {"letra": "Mr", "color": "#8B5A2B"},
			"funcion": "mesa",
			"lugares": ["centro_salud", "residencia"],
			"estancias": ["sala_espera"],
			"frecuencia": "comun"
		},
		{
			"id": "cartel_colgante",
			"nombre": "Cartel colgante",
			"categoria": "recepcion",
			"subcategoria": "senales",
			"etiquetas": ["cartel", "rótulo", "obstáculo en altura"],
			"descripcion": "Cartel que cuelga del techo sobre el mostrador. Queda a la altura de la cabeza de alguien alto.",
			"ambito": ["interior"],
			"medidas": {"ancho": [0.8, 1.2, 2.0], "fondo": [0.05, 0.1, 0.2], "alto": [0.3, 0.4, 0.6]},
			"altura_base": 1.8,
			"detectable_baston": false,
			"material": "plastico",
			"sonidos": {"golpe": "golpe/plastico"},
			"simbolo": {"letra": "Cc", "color": "#7D3C98"},
			"funcion": "senalizacion",
			"lugares": ["centro_salud", "residencia"],
			"estancias": ["recepcion"],
			"obstaculo": "cabeza",
			"frecuencia": "comun"
		},
		{
			"id": "maquina_cafe",
			"nombre": "Máquina de café",
			"categoria": "recepcion",
			"subcategoria": "maquinas",
			"etiquetas": ["máquina de café", "cafetera", "vending"],
			"descripcion": "Máquina de café alta como un armario. Zumba todo el rato: se oye desde la puerta.",
			"ambito": ["interior"],
			"medidas": {"ancho": [0.55, 0.6, 0.7], "fondo": [0.6, 0.7, 0.8], "alto": [1.7, 1.83, 1.85]},
			"colocacion": ["pared", "esquina"],
			"material": "metal",
			"sonidos": {
				"golpe": "golpe/metal",
				"propio": {"sonido": "fuente/maquina_expendedora", "volumen": 0.4, "radio": 6}
			},
			"acciones": [
				{"id": "pulsar", "nombre": "Pedir un café", "sonido": "interfaz/elegir"}
			],
			"simbolo": {"letra": "Mc", "color": "#B03A2E"},
			"funcion": "pago",
			"lugares": ["centro_salud", "residencia"],
			"estancias": ["sala_espera"],
			"frecuencia": "ocasional"
		},
		{
			"id": "felpudo",
			"nombre": "Felpudo",
			"categoria": "recepcion",
			"subcategoria": "suelo",
			"etiquetas": ["felpudo", "alfombra de entrada"],
			"descripcion": "Felpudo ancho detrás de la puerta. Se nota bajo los pies: acabas de entrar.",
			"ambito": ["interior", "exterior"],
			"medidas": {"ancho": [1.0, 1.5, 2.5], "fondo": [0.6, 0.9, 1.5], "alto": [0.01, 0.02, 0.03]},
			"bloquea": false,
			"suelo": "moqueta",
			"aviso": "Estás en el felpudo de la entrada.",
			"material": "tela",
			"sonidos": {"golpe": "golpe/tela"},
			"simbolo": {"letra": "Fe", "color": "#566573"},
			"funcion": "referencia",
			"lugares": ["centro_salud", "residencia"],
			"estancias": ["entrada", "recepcion"],
			"obstaculo": "ras_suelo",
			"frecuencia": "comun"
		}
	]
}
```

## Paso 8. Clasificar los objetos

El catálogo del Estudio tiene más de dos mil objetos. Para que el suyo se encuentre (en el árbol, con los filtros y en el amueblado asistido), clasifíquelo. Es opcional, pero vale la pena: son unas pocas líneas por objeto.

```json
{
	"id": "banco_espera",
	"subcategoria": "asientos",
	"funcion": "asiento",
	"lugares": ["centro_salud", "residencia"],
	"estancias": ["sala_espera", "recepcion"],
	"frecuencia": "muy_comun",
	"relacionados": ["mesa_redonda", "maquina_cafe"]
}
```

| Clave | Qué es |
| --- | --- |
| `subcategoria` | Un grupo dentro de su categoría. Su nombre visible va en la tabla `subcategorias` de la ficha general, como las categorías: `"subcategorias": {"asientos": "Asientos"}`. |
| `funcion` | Para qué sirve: `asiento`, `mesa`, `mostrador`, `almacenaje`, `electrodomestico`, `sanitario`, `senalizacion`, `barrera`, `vegetacion`, `vehiculo`, `juego`, `deporte`… |
| `lugares` | En qué tipos de lugar es habitual: `vivienda`, `colegio`, `hospital`, `centro_salud`, `residencia`, `calle`, `estacion`… |
| `estancias` | En qué estancia o zona suele estar: `dormitorio`, `cocina`, `aula`, `sala_espera`, `recepcion`, `anden`… |
| `obstaculo` | Solo si la que se deduce de sus medidas no vale: `ras_suelo`, `bajo`, `medio`, `alto`, `voladizo`, `cabeza` o `aereo`. |
| `riesgos` | Si además se mueve (`movil`), es temporal (`temporal`), es un desnivel (`desnivel`), quema (`caliente`), es transparente (`transparente`) o resbala (`resbaladizo`). |
| `frecuencia` | Lo habitual que es: `muy_comun`, `comun` u `ocasional`. Lo más común sale antes en el catálogo. |
| `relacionados` | Objetos que suelen ir con él: el catálogo los ofrece con «Objetos relacionados». |

Los valores de `funcion`, `lugares`, `estancias`, `obstaculo`, `riesgos` y `frecuencia` son cerrados: tienen que ser de las tablas de `docs/formato-de-complementos.md` («Clasificación»), donde están todos con su nombre visible. El comprobador avisa si alguno no existe. La ventaja de que sean cerrados es que se traducen solos y que los filtros del Estudio enseñan siempre las mismas opciones, venga el objeto de donde venga.

Con su banco clasificado así, al amueblar una habitación como sala de espera el programa ya lo tiene en cuenta: busca primero asientos clasificados en la estancia `sala_espera`.

## Paso 9. Imágenes (opcional)

Cada objeto puede llevar una imagen para el profesional: una foto del mueble real o un esquema.

1. Guarde la imagen en la carpeta `imagenes` del complemento, como `.png` o `.jpg`. No se admiten `.svg`.
2. Añada a la ficha del objeto:

```json
"imagen": {"fichero": "imagenes/mostrador.png", "descripcion": "Mostrador de madera clara en ele, con el lado largo de cara a la puerta."}
```

La `descripcion` en texto es obligatoria: es lo que lee quien no ve la imagen.

## Paso 10. Traducciones (opcional)

Para que el complemento se pueda usar en otro idioma, cree la carpeta `locales` y, dentro, un fichero por idioma con su código: `en.json` para el inglés, `ca.json` para el catalán.

```json
{
	"nombre": "My centre",
	"descripcion": "Objects from the reception of my day centre.",
	"categorias": {"recepcion": "Reception"},
	"estados": {"libre": "Free", "ocupado": "Occupied"},
	"objetos": {
		"banco_espera": {
			"nombre": "Waiting bench",
			"descripcion": "Three-seat bench against the wall, with a hard plastic seat.",
			"etiquetas": ["bench", "seat", "waiting room"],
			"variantes": {"dos_plazas": "Two seats", "tres_plazas": "Three seats", "cuatro_plazas": "Four seats"},
			"acciones": {"sentarse": "Sit down", "levantarse": "Stand up"}
		},
		"felpudo": {
			"nombre": "Doormat",
			"descripcion": "Wide mat just inside the door. You feel it underfoot: you have just come in.",
			"etiquetas": ["doormat", "entrance mat"],
			"aviso": "You are on the entrance mat."
		}
	}
}
```

Solo hay que poner lo que se traduce; lo demás se queda en español. Los identificadores no se tocan.

## Paso 11. Probarlo

1. Cierre el Estudio si estaba abierto y vuelva a abrirlo. Al arrancar lee todas las carpetas de `data/plugins`.
2. Abra el catálogo de objetos. Deben aparecer los seis, en la categoría «Recepción».
3. Si alguno no aparece, o no aparece ninguno, mire los avisos del catálogo: dicen qué objeto falla y por qué.
4. Cree un entorno de prueba con una habitación de 5 por 4 metros y coloque cada objeto:
   - contra una pared, en una esquina y en el centro;
   - en cada una de sus variantes;
   - y pruebe a ponerlo en una habitación pequeña, de 2 por 2 metros: tiene que encogerse hasta su mínimo o negarse a entrar, nunca quedar más grande que la habitación.
5. Recorra el entorno como lo haría el alumno, con auriculares:
   - ¿se oye el golpe al chocar con cada objeto y suena al material que es?
   - ¿se oye la máquina de café desde la puerta, y se sabe de dónde viene?
   - ¿se entiende la descripción hablada sin haber visto nunca el objeto?
   - ¿avisa el bastón sonoro de todo menos del cartel colgante?

### Si el complemento no carga

| Lo que pasa | Causa más probable |
| --- | --- |
| No aparece ningún objeto | El fichero no es un JSON correcto: falta o sobra una coma, una comilla o una llave. O se llama `complemento.json.txt`. |
| «El identificador no es válido» | Mayúsculas, tildes, eñes o espacios en un `id`. |
| Falta un objeto | Sus medidas no cumplen mínimo ≤ por defecto ≤ máximo, o el polígono se cruza o tiene puntos fuera de 0 a 1. |
| El objeto sale como una caja de un metro | No se han escrito sus `medidas`. |
| No suena | El nombre del sonido está mal escrito, o el fichero no está en la carpeta `sonidos`. |

## Paso 12. Validarlo

Antes de compartirlo, pásele el comprobador. Devuelve una lista de errores (hay que corregirlos) y de avisos (conviene revisarlos), cada uno con el objeto afectado y cómo arreglarlo. Una lista vacía significa que está listo.

- **Desde el Estudio**: Herramientas, «Complementos instalados»; elija el complemento en la lista y pulse el botón «Comprobar». Solo revisa complementos ya instalados (en `data\plugins`): si lo está escribiendo en otra carpeta, cópiela antes ahí o use la línea de órdenes.
- **Desde la línea de órdenes**, si trabaja con el código fuente. En la carpeta de EntornoLab:

```
.venv\Scripts\python.exe -c "from app.dominio.catalogo import validar_complemento; [print(a.gravedad, a.codigo, a.mensaje, a.sugerencia) for a in validar_complemento(r'data\plugins\mi-centro')] or print('Sin problemas.')"
```

La tabla con todos los códigos de error y de aviso está en `docs/formato-de-complementos.md`, apartado «Comprobar un complemento».

Lista de repaso antes de compartir:

- [ ] La carpeta se llama igual que el `id`.
- [ ] Tiene nombre, versión, autor y licencia.
- [ ] Cada objeto tiene categoría, etiquetas, descripción hablada y sus tres medidas.
- [ ] Las medidas son las de objetos reales, con mínimo y máximo sensatos.
- [ ] Lo que cuelga lleva `altura_base` y `"detectable_baston": false`.
- [ ] Todos los sonidos e imágenes propios están en sus carpetas y tiene permiso para compartirlos.
- [ ] Cada imagen tiene su descripción en texto.
- [ ] Ha probado cada objeto recorriendo un entorno.
- [ ] El comprobador no devuelve nada.

## Paso 13. Empaquetarlo como `.elabc`

Un complemento se comparte en un solo fichero con extensión `.elabc`. Es un ZIP corriente con los ficheros del complemento.

**Con la función del programa** (`empaquetar_complemento`), que mete solo los ficheros admitidos. En la carpeta de EntornoLab:

```
.venv\Scripts\python.exe -c "from app.dominio.catalogo import empaquetar_complemento; print(empaquetar_complemento(r'data\plugins\mi-centro', r'mi-centro-1.0.0.elabc'))"
```

El primer dato es la carpeta del complemento y el segundo, el fichero que se crea.

**A mano**, sin programa ninguno:

1. En el Explorador, pulse con el botón derecho (o con la tecla Aplicaciones) sobre la carpeta `mi-centro`.
2. Elija «Comprimir en», «Archivo ZIP» (en versiones anteriores de Windows: «Enviar a», «Carpeta comprimida»).
3. Cambie el nombre del fichero `mi-centro.zip` por `mi-centro-1.0.0.elabc`.

Las dos maneras valen: el ZIP puede llevar los ficheros sueltos o dentro de una única carpeta.

## Paso 14. Compartirlo e instalarlo

- **Enviarlo directamente.** Pase el fichero `.elabc` por correo, en un lápiz de memoria o en una carpeta compartida. Quien lo recibe lo instala desde el Estudio, en Herramientas, «Complementos instalados», con el botón «Añadir desde fichero» y eligiendo el fichero. No tiene que descomprimir nada.
- **Publicarlo en el catálogo en línea**, para que cualquiera lo instale y lo actualice desde la propia aplicación. Cómo se propone un complemento y cómo se revisa está en `docs/catalogo-de-complementos.md`.

Al instalar un `.elabc` el programa comprueba que no trae nada peligroso (solo datos: ni programas ni rutas fuera de su carpeta) y que la ficha se lee bien. Si algo falla no instala nada, y si había una versión anterior la deja como estaba.

Un entorno que use sus objetos se abre también en un equipo que no tenga el complemento: los objetos se ven como cajas con sus medidas y el programa avisa de qué complemento falta. Por eso conviene enviar el `.elabc` junto con el entorno.

### Publicar una versión nueva

1. Corrija o amplíe el complemento.
2. Suba `version` en `complemento.json`.
3. No cambie el `id` de los objetos que ya existían: los entornos que los usan los buscan por ese nombre. Tampoco estreche sus rangos de medidas por debajo de lo que ya se estuviera usando.
4. Valide, empaquete y comparta de nuevo. Al instalarlo sustituye a la versión anterior.

## Los complementos de serie como modelo

En `data/plugins` están los veinte complementos que trae el programa, con más de dos mil objetos: vivienda, colegio, oficina y comercio, calle, transporte, juego, sanidad, residencia y ayudas técnicas, hostelería, comunidad y edificio, vehículos y aparcamiento, cultura y ocio, deporte, parque y naturaleza, administración y servicios, tiendas, trabajo y taller, educación superior e infantil, obstáculos temporales y estaciones y aeropuerto. Abra el `complemento.json` de cualquiera para ver cómo están hechos un sofá en ele, un semáforo con sus fases, una marquesina en U, una cama de hospital o un cofre que se abre, y cómo está clasificado cada objeto. Se pueden copiar y adaptar (licencia CC BY 4.0, citando a su autor). `data/plugins/LEEME.md` los resume y `data/plugins/CATALOGO.md` es el índice de todos, por complemento, categoría y subcategoría.

Hay además un complemento sin objetos, `comun`: guarda los sonidos que comparten varios complementos (cada uno, una sola vez en el disco) y los nombres visibles de la clasificación en español y en inglés. Si su complemento quiere usar uno de esos sonidos sin copiarlo, cítelo como `comun:<fichero>` y ponga `"depende_de": ["comun"]` en la ficha general (ver `docs/formato-de-complementos.md`, «Sonidos de otro complemento»).

Los complementos de serie se escriben en Python, en `tools/complementos_serie/` (un módulo por complemento), y se generan con `tools/generar_complementos.py`, que escribe los JSON, las miniaturas, los sonidos, los `LEEME.md` y el `CATALOGO.md` y saca un informe de recuentos por complemento, categoría y función. No hace falta nada de eso para hacer el suyo: basta con el JSON.
