# Formato de complementos de objetos

Los objetos con los que se amuebla un entorno (muebles, material de calle, elementos de transporte) no están dentro de EntornoLab: vienen en complementos. Este documento explica cómo se hace uno a mano, sin programar.

El código que lo implementa está en `app/dominio/catalogo.py`.

- Para hacer uno paso a paso, con un ejemplo completo: `docs/crear-un-complemento.md`.
- Los complementos que vienen de serie (`hogar`, `colegio`, `oficina_y_comercio`, `calle`, `transporte` y `juego`) están en `data/plugins` y sirven de modelo: `data/plugins/LEEME.md`.

## Lo esencial

- Un complemento es una carpeta con un fichero `complemento.json` y, si hacen falta, sonidos, imágenes y traducciones.
- Es solo datos. No lleva código y EntornoLab no ejecuta nada de él.
- Un objeto no es un dibujo: es una forma con medidas reales, su huella en planta y su altura, que el alumno se encuentra y tiene que esquivar. En el plano se dibuja esa huella con una letra y un color.
- Todas las medidas van en metros.

## Dónde va

Cada complemento ocupa una carpeta dentro de `data/plugins`, con el mismo nombre que su identificador:

```
data/plugins/hogar/
	complemento.json        obligatorio
	sonidos/                opcional: .wav, .ogg o .flac
	imagenes/               opcional: .png, .jpg, .jpeg, .gif, .bmp o .webp
	locales/<idioma>.json   opcional: traducciones
	LEEME.txt               opcional: cualquier .txt o .md en la raíz
```

No se admiten otros ficheros, otras carpetas ni subcarpetas.

## Instalar y compartir

Hay dos maneras de instalar un complemento:

1. Copiar su carpeta dentro de `data/plugins`.
2. Empaquetarlo en un ZIP con extensión `.elabc` e instalarlo desde el Estudio con Herramientas, «Complementos instalados», botón «Añadir desde fichero» (función `instalar_complemento`).

Un `.elabc` es un ZIP con los ficheros del complemento, sueltos o dentro de una única carpeta. `empaquetar_complemento(carpeta, destino)` lo crea a partir de la carpeta.

Al instalar un `.elabc` se aplican las mismas comprobaciones de seguridad que a un entorno: se rechazan las rutas absolutas, los `..`, las barras invertidas, los nombres reservados de Windows, los tipos de fichero no admitidos, los ficheros repetidos y los demasiado grandes (20 MB un JSON, 50 MB un recurso, 300 MB en total, 2000 entradas). El complemento se extrae a una carpeta provisional y solo sustituye al instalado cuando su ficha se ha leído bien y tiene al menos un objeto utilizable; si algo falla, no queda nada a medias y la versión anterior sigue en su sitio.

## `complemento.json`

```json
{
	"formato": 1,
	"id": "hogar",
	"nombre": "Hogar",
	"version": "1.0",
	"autor": "Nombre de quien lo hace",
	"licencia": "CC BY 4.0",
	"descripcion": "Muebles de salón, cocina, dormitorio y baño.",
	"categorias": {"dormitorio": "Dormitorio", "salon": "Salón"},
	"objetos": []
}
```

| Clave | Obligatoria | Significado |
| --- | --- | --- |
| `formato` | No | Versión del formato. Ahora es 1. Un complemento de un formato más nuevo no se carga. |
| `id` | Sí | Identificador: de 1 a 64 caracteres, solo minúsculas sin tilde, cifras, guion y guion bajo, empezando por letra o cifra. Debe coincidir con el nombre de la carpeta. |
| `nombre` | Recomendada | Nombre visible. |
| `version`, `autor`, `licencia` | Recomendadas | El comprobador avisa si faltan. |
| `descripcion` | No | Qué contiene. |
| `categorias` | No | Nombre visible de cada categoría que usen los objetos. |
| `estados` | No | Nombre visible de cada estado que usen los objetos: `{"abierto": "Abierto"}`. Si falta uno, se enseña la propia clave. |
| `subcategorias` | No | Nombre visible de cada subcategoría que usen los objetos: `{"asientos": "Asientos"}`. Ver «Clasificación». |
| `depende_de` | No | Complementos de los que toma sonidos: `["comun"]`. Ver «Sonidos de otro complemento». |
| `taxonomia` | No | Nombres visibles propios de los valores de la clasificación, por faceta: `{"funcion": {"asiento": "Asiento"}}`. Solo hace falta para traer la clasificación traducida a un idioma que el programa aún no tiene; lo usa el complemento `comun`. |
| `objetos` | Sí | Lista de fichas de objeto. |

## Ficha de un objeto

Ejemplo completo:

```json
{
	"id": "armario",
	"nombre": "Armario",
	"categoria": "dormitorio",
	"etiquetas": ["armario", "ropero", "guardarropa"],
	"descripcion": "Armario de dos puertas, alto hasta casi el techo.",
	"ambito": ["interior"],
	"forma": {"tipo": "rectangulo"},
	"medidas": {
		"ancho": [0.8, 1.2, 3.0],
		"fondo": [0.5, 0.6, 0.7],
		"alto": [1.8, 2.0, 2.4]
	},
	"variantes": [
		{"id": "dos_puertas", "nombre": "De dos puertas", "ancho": 1.0, "fondo": 0.6, "alto": 2.0},
		{"id": "tres_puertas", "nombre": "De tres puertas", "ancho": 1.5, "fondo": 0.6, "alto": 2.0}
	],
	"colocacion": ["suelo", "pared"],
	"bloquea": true,
	"altura_base": 0.0,
	"detectable_baston": true,
	"material": "madera",
	"sonidos": {
		"golpe": "golpe/madera",
		"uso": "sonidos/puerta_armario.ogg"
	},
	"estados": ["cerrado", "abierto"],
	"acciones": [
		{"id": "abrir", "nombre": "Abrir", "de": "cerrado", "a": "abierto", "sonido": "sonidos/puerta_armario.ogg"},
		{"id": "cerrar", "nombre": "Cerrar", "de": "abierto", "a": "cerrado", "sonido": "sonidos/puerta_armario.ogg"}
	],
	"contenedor": true,
	"simbolo": {"letra": "A", "color": "#8B5A2B"},
	"imagen": {"fichero": "imagenes/armario.png", "descripcion": "Armario de madera clara con dos puertas y tiradores metálicos."}
}
```

Solo `id` es obligatorio. Todo lo demás tiene un valor de serie, pero un objeto útil declara al menos nombre, categoría, descripción y medidas.

| Clave | Valor de serie | Significado |
| --- | --- | --- |
| `id` | — | Identificador del objeto dentro del complemento, con las mismas reglas que el del complemento. En un entorno el objeto se nombra `<complemento>/<objeto>`: `hogar/armario`. |
| `nombre` | El `id` | Nombre visible. |
| `categoria` | Vacía | Para filtrar el catálogo: `dormitorio`, `cocina`, `calle`… Texto libre. |
| `etiquetas` | Ninguna | Palabras para encontrarlo. El amueblado asistido busca por ellas. |
| `descripcion` | Vacía | Descripción hablada para el alumno. |
| `ambito` | `["interior"]` | `interior`, `exterior` o los dos. |
| `forma` | Rectángulo | Forma de su planta. Ver «Formas». |
| `medidas` | 1 m en cada una | Ancho, fondo y alto. Ver «Medidas y variantes». |
| `variantes` | Ninguna | Tamaños con nombre. |
| `colocacion` | `["suelo"]` | Dónde se puede poner: `suelo`, `pared`, `esquina`, `acera`, `calzada`. |
| `bloquea` | `true` | Si corta el paso. `false` en una alfombra o una marca en el suelo. |
| `altura_base` | 0 | Metros del suelo a su parte más baja. Mayor que 0 en un objeto colgado o en voladizo. |
| `detectable_baston` | `true` | `false` si queda a la altura de la cabeza y el bastón no lo encuentra. |
| `material` | `madera` | Material, para el sonido del golpe. |
| `sonidos` | Ninguno | Ver «Sonidos». |
| `estados` | Ninguno | Estados posibles. El primero es el inicial. |
| `acciones` | Ninguna | Lo que el alumno puede hacer con él. Ver «Estados y acciones». |
| `contenedor` | `false` | Si puede esconder un premio dentro o debajo. |
| `dinamica` | Ninguna | Comportamiento declarado que interpreta el motor (un semáforo: sus fases y tiempos). Ver «Dinámica». |
| `paso_libre` | Ninguno | Estados en los que el objeto deja pasar aunque `bloquea` sea `true`: `["abierto"]` en un torno o en una puerta de terraza. |
| `suelo` | Ninguno | Suelo que se pisa encima de un objeto que no corta el paso: `alfombra` en una alfombra, `metal` en una tapa de alcantarilla, `tactil_botones` en una franja de botones. Los valores son los suelos del programa (`baldosa`, `madera`, `moqueta`, `alfombra`, `hormigon`, `asfalto`, `acera`, `adoquin`, `tierra`, `hierba`, `grava`, `metal`, `arena`, `agua`, `tactil_botones`, `tactil_rayas`). |
| `aviso` | Ninguno | Frase que se le dice al alumno al pisarlo o al llegar a él: «Borde del andén: detente». |
| `simbolo` | Inicial del nombre, gris | Letra (una o dos) y color `#RRGGBB` con que se dibuja su huella en el plano. |
| `imagen` | Ninguna | Ilustración o foto opcional: `fichero` y `descripcion`. La descripción en texto es obligatoria si hay imagen. |
| `subcategoria` | Ninguna | Grupo dentro de su categoría («asientos» dentro de «salón»). Su nombre visible va en la tabla `subcategorias` del complemento. |
| `funcion` | Ninguna | Para qué sirve. Un valor de la tabla de funciones. |
| `lugares` | Ninguno | Tipos de lugar donde es habitual. Valores de la tabla de lugares. |
| `estancias` | Ninguna | Estancias o zonas donde suele estar. Valores de la tabla de estancias. |
| `obstaculo` | Se deduce | Clase de obstáculo: a qué altura queda y si el bastón lo encuentra. Si falta, se deduce de `bloquea`, `altura_base` y el alto. |
| `riesgos` | Ninguno | Riesgos añadidos: se mueve, es temporal, es un desnivel… |
| `frecuencia` | `comun` | Lo habitual que es: `muy_comun`, `comun` u `ocasional`. Ordena los resultados del catálogo. |
| `relacionados` | Ninguno | Objetos que suelen ir con él: ids del mismo complemento (`silla`) o tipos completos (`hogar/silla`). |

Las nueve últimas claves son la clasificación: se explican en «Clasificación».

### Medidas y variantes

Cada medida es una lista de tres números en metros: mínimo, por defecto y máximo.

```json
"medidas": {"ancho": [1.2, 1.6, 2.4], "fondo": [0.7, 0.9, 1.1], "alto": [0.72, 0.75, 0.78]}
```

Tienen que cumplir 0 < mínimo ≤ por defecto ≤ máximo. Un número suelto es una medida fija: `"ancho": 0.2` equivale a `[0.2, 0.2, 0.2]`.

- El **ancho** es la medida de lado a lado, mirando el objeto de frente.
- El **fondo** es la medida de delante a atrás.
- El **alto** es su altura.

Las variantes son tamaños con nombre, cada uno con su `ancho`, `fondo` y `alto`, que deben caer dentro del rango.

Estas medidas son las que hacen que un objeto nunca quede desproporcionado. Al colocarlo en un hueco, el programa hace esto por orden:

1. Si cabe con sus medidas por defecto, las usa.
2. Si no, elige la variante más grande que quepa.
3. Si no cabe ninguna, lo encoge hasta el hueco, sin bajar del mínimo.
4. Si ni al mínimo cabe, lo dice y no lo coloca.

Por eso conviene que el mínimo y el máximo sean los de objetos que existen de verdad.

### Formas

La forma es la huella del objeto vista desde arriba. Hay cuatro tipos:

| `tipo` | Huella |
| --- | --- |
| `rectangulo` | Un rectángulo de ancho por fondo. |
| `circulo` | Una elipse inscrita en ese rectángulo, aproximada por un polígono de 16 lados. Con ancho igual a fondo es un círculo. |
| `ele` | Una L. Sin `puntos`, el brazo largo ocupa todo el ancho por detrás y el corto sale hacia delante por la izquierda. |
| `poligono` | El polígono que den los `puntos`. |

Los `puntos` se dan en un cuadrado de 0 a 1, que luego se estira al ancho y al fondo del objeto:

- El primer número va de 0 (lado izquierdo) a 1 (lado derecho), mirando el objeto desde detrás.
- El segundo va de 0 (parte de atrás, la que se arrima a la pared) a 1 (frente).

```json
"forma": {"tipo": "poligono", "puntos": [[0, 0], [1, 0], [0, 1]]}
```

Ese ejemplo es un triángulo con el ángulo recto atrás a la izquierda. Los puntos deben formar un polígono simple (sin cruces) de al menos tres vértices, todos entre 0 y 1. `ele` admite también `puntos` propios para una L de otras proporciones.

El frente del objeto mira hacia su rumbo. Un mueble colocado contra una pared queda con la parte de atrás en la pared y el frente hacia la habitación.

### Sonidos

```json
"sonidos": {
	"golpe": "golpe/metal",
	"uso": "sonidos/puerta_nevera.ogg",
	"propio": {"sonido": "fuente/frigorifico", "volumen": 0.5, "radio": 6}
}
```

- `golpe`: suena al chocar con el objeto.
- `uso`: suena al usarlo.
- `propio`: sonido que emite él solo, con su `volumen` (0 a 1) y su `radio` en metros (un frigorífico que zumba, un semáforo que pita).

Hay dos clases de nombre:

- **Un fichero del complemento**: lleva extensión (`puerta_nevera.ogg`) o empieza por `sonidos/` (`sonidos/puerta_nevera.ogg`). Tiene que estar en la carpeta `sonidos` del complemento.
- **Un sonido de serie del programa**: cualquier otro nombre, sin extensión. Los de serie se llaman «familia/nombre» y están listados en `data/sounds/catalogo.json` y en `docs/sonido.md`: `golpe/madera`, `golpe/metal`, `golpe/cristal`, `golpe/plastico`, `golpe/tela`, `golpe/piedra`, `golpe/ladrillo`, `puerta/abrir`, `puerta/cerrar`, `fuente/frigorifico`, `fuente/grifo`, `fuente/reloj`, `fuente/television`, `fuente/ventilador`, `fuente/fuente_agua`, `fuente/maquina_expendedora`, `semaforo/verde`, `semaforo/rojo`…

El sonido `propio` puede llevar además `"estado"`: entonces solo suena mientras el objeto está en ese estado (una lavadora que zumba cuando está `funcionando`, un televisor `encendido`). Sin `estado`, suena siempre.

#### Sonidos de otro complemento

Un complemento puede usar un sonido de otro en lugar de llevar su propia copia: lo cita como `<complemento>:<fichero>` (`comun:sentarse.flac`) y declara ese complemento en `depende_de` de su ficha general. Así un sonido que usan veinte complementos ocupa una sola vez en el disco. El comprobador da error (`dependencia_no_declarada`) si se usa un sonido de un complemento que no está en `depende_de`, y (`sonido_ausente`) si ese complemento está instalado al lado y no tiene el fichero. Si el complemento del que se depende no está instalado, el catálogo lo avisa (`dependencia_ausente`) y el objeto funciona igual, sin ese sonido.

Los complementos de serie lo usan así: el complemento `comun` (sin objetos) guarda los sonidos que comparten varios, y los que los seis complementos originales ya llevaban dentro se quedan en su original (`hogar:sentarse.flac`), porque hay entornos que los piden por su nombre de siempre.

Para programadores: `clave_de_sonido(id_complemento, nombre)` da el nombre con el que el banco de sonidos (`app/audio/banco.py`) encuentra cada uno (`hogar/lavadora.flac` para `sonidos/lavadora.flac` del complemento `hogar`; el mismo nombre para uno de serie).

### Estados y acciones

```json
"estados": ["cerrado", "abierto"],
"acciones": [
	{"id": "abrir", "nombre": "Abrir", "de": "cerrado", "a": "abierto", "sonido": "sonidos/puerta_armario.ogg"}
]
```

Una acción lleva el objeto del estado `de` al estado `a`. Los dos tienen que estar en `estados`. Son declaraciones: el motor las aplica, el complemento no ejecuta nada.

- Una acción sin `de` ni `a` no cambia el estado: es un gesto suelto, como tocar un piano o pulsar el botón de un semáforo (`{"id": "pulsar", "nombre": "Pulsar el botón", "sonido": "semaforo/pulsador"}`).
- El primer estado de la lista es el inicial.
- `paso_libre` dice en qué estados el objeto deja pasar. Un torno con `"estados": ["cerrado", "abierto"]` y `"paso_libre": ["abierto"]` corta el paso hasta que se valida el billete.
- El nombre que se enseña y se dice de cada estado sale de la tabla `estados` de la ficha general del complemento.

### Dinámica

`dinamica` declara un comportamiento que cambia solo con el tiempo. El complemento solo lo describe; lo ejecuta el motor del juego. Hay dos tipos.

**Semáforo.** Recorre sus fases en orden y vuelve a empezar. Cada fase es un estado del objeto (tiene que estar en `estados`), dura unos segundos y puede tener un sonido que se repite mientras dura:

```json
"estados": ["rojo", "verde", "intermitente"],
"dinamica": {
	"tipo": "semaforo",
	"para": "peatones",
	"fases": [
		{"estado": "rojo", "segundos": 45, "sonido": "semaforo/rojo"},
		{"estado": "verde", "segundos": 25, "sonido": "semaforo/verde"},
		{"estado": "intermitente", "segundos": 5, "sonido": "semaforo/intermitente"}
	],
	"sonoro": true,
	"pulsador": true,
	"espera_tras_pulsar_s": 8,
	"radio": 14,
	"volumen": 0.6
}
```

| Clave | Significado |
| --- | --- |
| `para` | `peatones` o `vehiculos`. |
| `fases` | Lista de fases: `estado`, `segundos` y, si suena, `sonido`. |
| `sonoro` | `true` si avisa con sonido. Un semáforo sin sonido no pone `sonido` en sus fases. |
| `pulsador` | `true` si tiene botón de petición de paso (el objeto declara entonces la acción `pulsar`). |
| `espera_tras_pulsar_s` | Segundos que tarda en ponerse verde después de pulsar. |
| `radio`, `volumen` | Alcance en metros y volumen (0 a 1) del sonido de las fases. |

**Temporizador.** El objeto pasa solo de un estado a otro cuando lleva un tiempo en el primero: una lavadora que termina, un microondas que pita.

```json
"estados": ["apagado", "funcionando"],
"dinamica": {"tipo": "temporizador", "estado": "funcionando", "segundos": 90, "al_terminar": "apagado", "sonido_al_terminar": "sonidos/microondas_fin.flac"}
```

`sonido_al_terminar` es opcional.

## Clasificación

Con miles de objetos, encontrarlos depende de clasificarlos bien. Toda la clasificación es OPCIONAL (un complemento antiguo sin ella sigue valiendo), pero los complementos de serie la llevan completa en el cien por cien de sus objetos y conviene que los demás también.

```json
"categoria": "salon",
"subcategoria": "asientos",
"funcion": "asiento",
"lugares": ["vivienda", "residencia"],
"estancias": ["salon", "sala_comun"],
"obstaculo": "medio",
"riesgos": [],
"frecuencia": "muy_comun",
"relacionados": ["mesa_centro", "hogar/lampara_pie"]
```

- **Categoría y subcategoría** son propias de cada complemento: texto libre, con su nombre visible en las tablas `categorias` y `subcategorias` de la ficha general. Forman el árbol del catálogo: complemento → categoría → subcategoría.
- **Función, lugares, estancias, clase de obstáculo, riesgos y frecuencia** son valores CERRADOS, iguales para todos los complementos: así un filtro enseña siempre las mismas opciones. El comprobador avisa (`valor_desconocido`) de cualquier valor que no esté en estas tablas, y al cargar se ignora. Sus nombres visibles, en español y en inglés, los lleva el complemento `comun`; se traducen como cualquier texto del programa.
- Las claves solo se añaden, nunca se quitan ni se renombran: un complemento escrito hoy seguirá valiendo mañana.

### Funciones (`funcion`)

| Valor | Nombre visible |
| --- | --- |
| `asiento` | Asiento |
| `mesa` | Mesa o superficie de trabajo |
| `mostrador` | Mostrador o barra |
| `descanso` | Cama o descanso |
| `almacenaje` | Almacenaje |
| `expositor` | Expositor o vitrina |
| `electrodomestico` | Electrodoméstico |
| `maquina` | Máquina o aparato |
| `sanitario` | Sanitario o fontanería |
| `iluminacion` | Iluminación |
| `climatizacion` | Climatización |
| `senalizacion` | Señalización e información |
| `referencia` | Referencia en el suelo o táctil |
| `barrera` | Barrera o cierre |
| `control_acceso` | Control de acceso |
| `estructura` | Elemento del edificio o de la vía |
| `vegetacion` | Vegetación |
| `vehiculo` | Vehículo |
| `juego` | Juego o juguete |
| `deporte` | Deporte |
| `instrumento` | Instrumento musical |
| `ayuda_tecnica` | Ayuda técnica o apoyo |
| `equipo_medico` | Equipo sanitario |
| `residuos` | Residuos y limpieza |
| `decoracion` | Decoración |
| `comunicacion` | Comunicación |
| `pago` | Pago y venta automática |
| `seguridad` | Seguridad y emergencia |
| `herramienta` | Herramienta o equipo de trabajo |
| `carga` | Carga y mercancías |
| `agua` | Agua |
| `animal` | Animal o personaje |
| `trasto` | Trasto u obstáculo suelto |
| `fantasia` | Elemento fantástico |

### Lugares (`lugares`)

| Valor | Nombre visible |
| --- | --- |
| `vivienda` | Vivienda |
| `comunidad` | Edificio de viviendas |
| `colegio` | Colegio o instituto |
| `guarderia` | Guardería o escuela infantil |
| `universidad` | Universidad |
| `oficina` | Oficina |
| `tienda` | Tienda |
| `supermercado` | Supermercado |
| `centro_comercial` | Centro comercial |
| `bar` | Bar o cafetería |
| `restaurante` | Restaurante |
| `hotel` | Hotel |
| `hospital` | Hospital |
| `centro_salud` | Centro de salud o consulta |
| `farmacia` | Farmacia |
| `residencia` | Residencia |
| `administracion` | Administración pública |
| `banco` | Banco |
| `servicios` | Servicios (peluquería, lavandería, correos) |
| `culto` | Lugar de culto o tanatorio |
| `museo` | Museo o sala de exposiciones |
| `biblioteca` | Biblioteca |
| `cine_teatro` | Cine, teatro o auditorio |
| `ocio` | Ocio (bolera, recreativos, centro cívico) |
| `polideportivo` | Polideportivo |
| `gimnasio` | Gimnasio |
| `piscina` | Piscina |
| `parque` | Parque o jardín público |
| `parque_infantil` | Parque infantil |
| `playa` | Playa |
| `naturaleza` | Campo y naturaleza |
| `jardin` | Jardín o huerto |
| `calle` | Calle |
| `obra` | Obra |
| `aparcamiento` | Aparcamiento |
| `parada` | Parada de transporte |
| `estacion` | Estación de tren, metro o autobús |
| `aeropuerto` | Aeropuerto |
| `puerto` | Puerto |
| `taller` | Taller |
| `almacen` | Almacén |
| `fabrica` | Fábrica |
| `laboratorio` | Laboratorio |
| `fantasia` | Mundo de fantasía |
| `cualquiera` | Cualquier lugar |

### Estancias (`estancias`)

| Valor | Nombre visible |
| --- | --- |
| `salon` | Salón |
| `comedor` | Comedor |
| `cocina` | Cocina |
| `dormitorio` | Dormitorio |
| `habitacion_infantil` | Habitación infantil |
| `bano` | Baño o aseo |
| `aseo_adaptado` | Aseo adaptado |
| `entrada` | Entrada o recibidor |
| `pasillo` | Pasillo |
| `terraza` | Terraza o balcón |
| `lavadero` | Lavadero |
| `trastero` | Trastero |
| `garaje` | Garaje |
| `portal` | Portal |
| `rellano` | Escalera y rellano |
| `patio` | Patio |
| `azotea` | Azotea |
| `cuarto_instalaciones` | Cuarto de instalaciones o de basuras |
| `aula` | Aula |
| `aula_infantil` | Aula infantil o sala de cunas |
| `aula_grada` | Aula en grada |
| `laboratorio` | Laboratorio |
| `patio_recreo` | Patio de recreo |
| `comedor_colectivo` | Comedor colectivo |
| `sala_lectura` | Sala de lectura |
| `despacho` | Despacho |
| `zona_trabajo` | Zona de trabajo de oficina |
| `sala_reuniones` | Sala de reuniones |
| `recepcion` | Recepción |
| `sala_espera` | Sala de espera |
| `ventanilla` | Atención al público |
| `cajeros` | Zona de cajeros |
| `consulta` | Consulta médica |
| `habitacion_hospital` | Habitación de hospital |
| `urgencias` | Urgencias |
| `sala_rehabilitacion` | Sala de rehabilitación |
| `sala_comun` | Sala de estar común |
| `barra` | Barra de bar |
| `sala_restaurante` | Sala de restaurante o cafetería |
| `terraza_bar` | Terraza de bar |
| `cocina_profesional` | Cocina profesional |
| `habitacion_hotel` | Habitación de hotel |
| `vestibulo` | Vestíbulo |
| `sala_ventas` | Sala de ventas |
| `cajas` | Línea de cajas |
| `probador` | Probadores |
| `trastienda` | Trastienda |
| `galeria_comercial` | Galería de centro comercial |
| `sala_exposicion` | Sala de exposición |
| `sala_butacas` | Sala de butacas |
| `escenario` | Escenario |
| `taquilla` | Taquillas y venta de entradas |
| `salon_actos` | Salón de actos |
| `sala_juegos` | Sala de juegos |
| `pista` | Pista deportiva |
| `sala_musculacion` | Sala de musculación |
| `vestuario` | Vestuario |
| `grada` | Grada |
| `vaso_piscina` | Vaso y playa de piscina |
| `zona_juegos` | Zona de juegos infantiles |
| `zona_canina` | Zona canina |
| `merendero` | Merendero |
| `sendero` | Sendero o camino |
| `arena_playa` | Arena de playa |
| `jardin` | Jardín |
| `huerto` | Huerto |
| `acera` | Acera |
| `calzada` | Calzada |
| `cruce` | Cruce o paso de peatones |
| `plaza` | Plaza |
| `parada` | Parada |
| `anden` | Andén |
| `control_seguridad` | Control de seguridad |
| `facturacion` | Facturación |
| `puerta_embarque` | Puerta de embarque |
| `recogida_equipajes` | Recogida de equipajes |
| `plaza_aparcamiento` | Plazas de aparcamiento |
| `nave` | Nave de taller o fábrica |
| `almacen` | Almacén |
| `muelle_carga` | Muelle de carga |
| `zona_obra` | Zona de obras |
| `sala_culto` | Sala de culto |
| `velatorio` | Velatorio |
| `salon_servicio` | Local de servicios |
| `castillo` | Castillo |
| `cueva` | Cueva |
| `bosque` | Bosque |
| `nave_espacial` | Nave espacial |
| `isla` | Isla |
| `interior_vehiculo` | Dentro de un autobús, tranvía, metro o tren |
| `cualquiera` | Cualquier estancia |

### Clases de obstáculo (`obstaculo`)

Para orientación y movilidad es lo que más importa: qué encuentra el bastón y qué no.

| Valor | Nombre visible |
| --- | --- |
| `ras_suelo` | A ras de suelo: se pisa |
| `bajo` | Bajo: por debajo de la rodilla |
| `medio` | A media altura: de la rodilla al pecho |
| `alto` | Alto: de cuerpo entero |
| `voladizo` | En voladizo: el bastón pasa por debajo |
| `cabeza` | A la altura de la cabeza |
| `aereo` | Por encima de la cabeza |

Si el objeto no la declara, se deduce de sus medidas: lo que empieza a 2.20 m o más es `aereo`; a 1.40 m o más, `cabeza`; a 0.30 m o más, `voladizo`; lo que no corta el paso, `ras_suelo`; y lo apoyado en el suelo, `bajo` si no llega a 0.50 m, `medio` hasta 1.20 m y `alto` por encima. Se declara a mano cuando la deducción engaña: una mesa alta de bar con un solo pie (`voladizo`: el tablero sobresale por encima de donde barre el bastón) o una palmera en maceta cuyas hojas quedan a la altura de la cara (`cabeza`). Lo que cuelga a 0.30 m o más debe llevar además `"detectable_baston": false`.

### Riesgos (`riesgos`)

| Valor | Nombre visible |
| --- | --- |
| `movil` | Se mueve |
| `temporal` | Temporal: cambia de un día a otro |
| `desnivel` | Desnivel o hueco |
| `caliente` | Quema |
| `transparente` | Transparente o difícil de ver |
| `resbaladizo` | Resbala o moja |

Un desnivel (borde de andén, foso, zanja) conviene que lleve también su `aviso`.

### Frecuencias (`frecuencia`)

| Valor | Nombre visible |
| --- | --- |
| `muy_comun` | Muy común |
| `comun` | Común |
| `ocasional` | Ocasional |

### Buscar y filtrar (para programadores)

`Catalogo` (en `app/dominio/catalogo.py`) ofrece, además de `buscar(texto, categoria, ambito, colocacion)`, `categorias()` y `complementos()` de siempre:

- `buscar_avanzado(texto, *, complemento, categoria, subcategoria, funcion, lugar, estancia, obstaculo, riesgo, ambito, colocacion, frecuencia, contenedor, con_sonido, usable, orden="relevancia", limite=None)`: el texto se busca sin tildes ni mayúsculas en el nombre, las etiquetas (que hacen de sinónimos, en todos los idiomas cargados), el identificador, la clasificación y la descripción; con varias palabras tienen que estar todas. Cada filtro admite un valor o varios (basta con cumplir uno) y se combinan entre sí. `contenedor`, `con_sonido` y `usable` son de sí o no. Orden: `relevancia` (lo que mejor casa con el texto y, a igualdad, lo más común), `frecuencia` o `nombre`.
- `facetas(texto, **filtros)`: cada faceta (`complemento`, `categoria`, `subcategoria`, `funcion`, `lugar`, `estancia`, `obstaculo`, `riesgo`, `ambito`, `colocacion`, `frecuencia`, `contenedor`, `con_sonido`, `usable`) con sus valores y cuántos objetos hay en cada uno (`ValorFaceta(clave, nombre, total)`). El recuento de una faceta se hace sin su propio filtro, para poder cambiar de opción sin borrarlo antes.
- `arbol(texto, *, con_objetos=False, **filtros)`: la jerarquía complemento → categoría → subcategoría con recuentos (`NodoArbol(nivel, clave, nombre, total, hijos, tipos)`), para un control de árbol.
- `relacionados(tipo, limite=12)`: lo que suele ir con un objeto: primero lo que declara en `relacionados` y después lo de funciones afines que comparte estancia con él.
- `nombre_de(faceta, clave)`: el nombre visible de un valor, en el idioma cargado.

Todo se calcula sobre un índice en memoria que se rehace solo cuando cambia algo (se instala, activa o desactiva un complemento): con los más de dos mil objetos de serie, cargar lleva unas décimas de segundo y una búsqueda, unos pocos milisegundos.

## Traducciones

Los textos de `complemento.json` se escriben en español. Para traducirlos se añade un fichero por idioma en `locales/`, con el código del idioma como nombre: `locales/en.json`, `locales/ca.json`.

```json
{
	"nombre": "Home",
	"descripcion": "Living room, kitchen, bedroom and bathroom furniture.",
	"categorias": {"dormitorio": "Bedroom", "salon": "Living room"},
	"objetos": {
		"armario": {
			"nombre": "Wardrobe",
			"descripcion": "Two-door wardrobe, almost ceiling high.",
			"etiquetas": ["wardrobe", "closet"],
			"variantes": {"dos_puertas": "Two doors", "tres_puertas": "Three doors"},
			"acciones": {"abrir": "Open", "cerrar": "Close"},
			"aviso": "Texto del aviso, si el objeto tiene uno.",
			"imagen": "Light wooden wardrobe with two doors and metal handles."
		}
	},
	"estados": {"cerrado": "Closed", "abierto": "Open"}
}
```

- Solo hay que poner lo que se traduce. Lo que falte se queda en español.
- Las etiquetas traducidas se suman a las originales, de modo que el objeto se encuentra en los dos idiomas.
- Si no hay fichero para una variante regional (`en_GB`), se usa el del idioma base (`en`).
- Los identificadores no se traducen: son claves. Tampoco las claves de las categorías ni las de los estados; sí sus nombres visibles, en `categorias` y en `estados`.
- `imagen` es la descripción en texto de la imagen del objeto.

## Comprobar un complemento

Antes de compartir un complemento conviene pasarle el comprobador (`validar_complemento(carpeta)`, o, en el Estudio, Herramientas, «Complementos instalados», botón «Comprobar», que revisa los ya instalados). Devuelve una lista de avisos, cada uno con su gravedad, el objeto afectado y cómo arreglarlo. Una lista vacía significa que está listo.

Errores (hay que corregirlos):

| Código | Qué pasa |
| --- | --- |
| `complemento_no_valido` | Falta `complemento.json`, no es JSON, el identificador no vale o el formato es más nuevo. |
| `complemento_sin_objetos` | No hay lista `objetos`. |
| `objeto_no_valido` | Una ficha no se puede usar: identificador no válido, medidas que no cumplen mínimo ≤ por defecto ≤ máximo, forma desconocida, puntos fuera de 0 a 1. El objeto se salta; los demás se cargan. |
| `objeto_repetido` | Dos objetos con el mismo identificador. Se usa el primero. |
| `variante_fuera_de_rango` | Una variante mide menos del mínimo o más del máximo. |
| `estado_desconocido` | Una acción, una fase de la dinámica, `paso_libre` o el `estado` del sonido propio usan un estado que no está en `estados`. |
| `sonido_ausente` | Un sonido que dice ser un fichero del complemento (lleva extensión o empieza por `sonidos/`) no está. |
| `imagen_ausente` | La imagen declarada no está. |
| `imagen_sin_descripcion` | La imagen no tiene descripción en texto. |
| `traduccion_no_valida` | Un fichero de `locales` no es JSON. |
| `dependencia_no_declarada` | Un objeto usa un sonido de otro complemento (`comun:x.flac`) que no está en `depende_de`. |

Avisos (conviene revisarlos):

| Código | Qué pasa |
| --- | --- |
| `carpeta_distinta` | La carpeta no se llama como el identificador. |
| `ficha_incompleta` | Falta nombre, versión, autor o licencia. |
| `sin_categoria`, `sin_descripcion` | Al objeto le falta la categoría o la descripción hablada. |
| `medida_ausente` | No declara una medida y se usará un metro. |
| `valor_desconocido` | Un valor de `ambito`, `colocacion`, `suelo`, del `tipo` de la dinámica o de la clasificación (`funcion`, `lugares`, `estancias`, `obstaculo`, `riesgos`, `frecuencia`) que no existe. |
| `subcategoria_sin_nombre` | Un objeto usa una subcategoría que no está en la tabla `subcategorias`. |
| `relacionado_desconocido` | Un objeto dice ir con otro que no existe en el complemento. |
| `color_no_valido` | El color del símbolo no tiene la forma `#RRGGBB`. |
| `traduccion_sobrante` | Una traducción nombra un objeto que no existe. |

## Qué pasa si falta un complemento

Si un entorno usa un objeto de un complemento que no está instalado, el entorno se abre igual: el objeto se conserva como una caja rectangular con las medidas que tenía, corta el paso y el validador avisa con el código `tipo_no_instalado`. Al instalar el complemento, el objeto recupera su forma y su comportamiento.

Un complemento se puede desactivar sin desinstalarlo. Sus objetos dejan de salir en el catálogo, pero los ya colocados siguen funcionando.

## Amueblado asistido

«Amueblar esta habitación como dormitorio» busca en los complementos instalados los muebles típicos de cada uso. Para que encuentre los de un complemento, sus objetos deben estar marcados como de `interior` y llevar alguna de estas palabras como identificador, nombre o etiqueta (se comparan sin tildes ni mayúsculas):

| Uso | Palabras que busca |
| --- | --- |
| Dormitorio | cama; mesilla, mesita; armario, ropero; escritorio, mesa; silla |
| Salón | sofa; television, televisor, tele; mesa baja, mesa de centro, mesa; sillon, butaca; estanteria, libreria |
| Cocina | frigorifico, nevera; encimera; cocina, vitroceramica, fogones; fregadero; lavavajillas, lavadora; mesa; silla, taburete |
| Baño | inodoro, vater, retrete; lavabo; ducha, banera; bide |
| Aula | pizarra; mesa del profesor, escritorio; pupitre, mesa de alumno, mesa; armario, estanteria; papelera |
| Oficina | escritorio, mesa de oficina, mesa; silla de oficina, silla; archivador, cajonera; estanteria, armario; papelera |

Además hay usos que se apoyan en la clasificación: buscan cada mueble primero entre los objetos clasificados en sus estancias (y con la función que corresponde: un asiento, una mesa, un sanitario), el más relevante y común; y solo si ahí no hay ninguno, en todo el catálogo, pero exigiendo que el nombre o una etiqueta sea exactamente la palabra. Así una sala de espera recibe bancadas de espera y no bancos de calle.

| Uso | Estancias donde busca | Muebles que busca, por orden |
| --- | --- | --- |
| Sala de espera | `sala_espera` | bancada, sillas de espera; bancada, sillas de espera, banco; pantalla de turnos, pantalla; gestor de turnos, dispensador de turno, turnos; maquina expendedora, maquina de cafe; planta; papelera |
| Consulta médica | `consulta` | mesa de consulta, mesa; silla, sillas; camilla; lavamanos, lavabo; bascula, tallimetro; contenedor, papelera |
| Habitación de hospital | `habitacion_hospital` | cama; mesilla; sillon, butaca; armario; portasueros, pie de gotero; lavamanos, lavabo |
| Aseo adaptado | `aseo_adaptado` | inodoro, vater; lavabo; plato de ducha, ducha; barra, asidero; asiento de ducha, banqueta de ducha; espejo |
| Bar | `barra`, `sala_restaurante` | barra; taburete; mesa; silla; tragaperras, maquina; botellero; papelera, cubo |
| Restaurante | `sala_restaurante` | mesa de restaurante, mesa; silla de restaurante, silla; banco corrido, banco; mesa corrida, mesa; aparador, mueble de cubiertos; atril de reservas, atril; trona |
| Habitación de hotel | `habitacion_hotel` | cama; armario; escritorio, tocador; silla, butaca; minibar, nevera; portamaletas |
| Recepción | `recepcion`, `vestibulo` | mostrador de recepcion, mostrador; sofa; butaca, sillon; mesa de centro, mesa; planta; expositor de folletos, folletos; perchero |
| Biblioteca | `sala_lectura` | mostrador de prestamo, mostrador; estanteria; estanteria; mesa de lectura, mesa; silla; catalogo, puesto de consulta; papelera |
| Gimnasio | `sala_musculacion` | cinta de correr, cinta; bicicleta estatica, bicicleta; eliptica; mancuernero, mancuernas; banco plano, banco; espejo; fuente, dispensador de papel |
| Vestuario | `vestuario` | taquillas; banco; duchas, ducha; perchas, percha; secamanos, secador; bascula |
| Garaje | `garaje`, `plaza_aparcamiento` | coche, turismo; estanteria; columna; bicicletas, bicis; neumaticos; extintor |
| Portal | `portal` | buzones; banco; jardinera, planta; tablon, tablon de anuncios; espejo; boca de incendio, extintor |
| Andén | `anden` | banco; asiento abatible, asientos; panel, pantalla; maquina de billetes, maquina; columna; papelera; extintor |
| Parque infantil | `zona_juegos` | columpio; tobogan; balancin de muelle, balancin; arenero; banco; papelera |

`NOMBRES_USOS` (en `app/dominio/colocacion.py`) da el nombre visible de cada uso. En todos, igual que en los de siempre, cada objeto se ajusta al hueco con sus variantes y su rango, no se tapa ninguna puerta y se respeta el paso libre fijado: en una habitación de dos por dos se coloca lo que quepa y nada más grande que ella.

Cuando varios complementos tienen el mismo mueble (una silla, una papelera, un escritorio) se usa el primero por orden de nombre. Quien llama a `amueblar_espacio` puede pasar `preferidos=("colegio",)` para que, a igualdad, gane el de ese complemento; así amueblan los entornos de ejemplo las aulas con el complemento de colegio y los despachos con el de oficina.

Para que el amueblado elija bien, conviene que solo un objeto del complemento lleve cada palabra tal cual como identificador, nombre o etiqueta: la cama principal se etiqueta `cama` y la litera, `litera` y `cama litera`, pero no `cama` a secas.

## Un complemento mínimo

Carpeta `data/plugins/mis-objetos/` con un único fichero `complemento.json`:

```json
{
	"formato": 1,
	"id": "mis-objetos",
	"nombre": "Mis objetos",
	"version": "1.0",
	"autor": "Yo",
	"licencia": "CC0",
	"objetos": [
		{
			"id": "columna",
			"nombre": "Columna",
			"categoria": "estructura",
			"etiquetas": ["columna", "pilar"],
			"descripcion": "Columna redonda de hormigón.",
			"ambito": ["interior", "exterior"],
			"forma": {"tipo": "circulo"},
			"medidas": {"ancho": [0.3, 0.4, 0.8], "fondo": [0.3, 0.4, 0.8], "alto": [2.2, 2.5, 4.0]},
			"material": "hormigon",
			"sonidos": {"golpe": "golpe/piedra"},
			"simbolo": {"letra": "C", "color": "#707070"}
		}
	]
}
```

Al abrir el Estudio, la columna aparece en el catálogo como `mis-objetos/columna`.
