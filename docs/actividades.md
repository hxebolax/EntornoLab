# Actividades, juegos y exámenes (`app/actividades`)

Documentación de desarrollo. Una actividad es **un JSON declarativo** que viaja dentro del paquete `.elab` (`actividades/<id>.json`). El paquete `app/actividades` lo valida, lo describe, lo convierte en un objeto que se cuelga de la `Sesion` del motor y lo puntúa. No tiene interfaz ni sonido: se prueba entero con un robot (`tests/test_actividades_*.py`).

**Nunca se ejecuta nada de lo que trae una actividad.** Un tipo desconocido se juega como exploración libre y la validación lo señala.

```python
from app.actividades import TIPOS, campos_de, nueva_actividad, validar_actividad, crear_actividad, describir_actividad

datos = nueva_actividad("busqueda", entorno, catalogo, cantidad=5)        # o paquete.actividad("id")
avisos = validar_actividad(datos, entorno, catalogo)                       # lista de Aviso; vacía = lista para jugar
actividad = crear_actividad(datos, entorno, catalogo, estilo=alumno.estilo, semilla=None, nivel=nivel_del_alumno)
sesion = Sesion(entorno, catalogo, actividad.ajustes(ajustes_del_alumno), actividad=actividad, semilla=semilla, inicio=actividad.inicio())

eventos = sesion.avanzar(dt)                 # la sesión llama a los ganchos de la actividad
actividad.estado()                           # objetivo, hechos, total, puntos, estrellas, tiempo_restante, nivel…
actividad.orden_profesional(sesion, "pista", {"baliza_s": 10})   # devuelve eventos que presentar
resultado = EvFin.resultado                  # al terminar: todo lo que el seguimiento espera
```

Una `Actividad` sirve para **una** sesión: para volver a jugar se crea otra.

## Módulos

| Módulo | Qué hace |
| --- | --- |
| `tipos.py` | `TIPOS`, `InfoTipo`, `Campo`, `campos_de`, `leer_campo`, `poner_campo`, niveles de serie |
| `formato.py` | `normalizar`: lectura tolerante del JSON y valores de serie |
| `fabrica.py` | `crear_actividad`, `nueva_actividad`, `describir_actividad`, `CLASES` |
| `validacion.py` | `validar_actividad` |
| `base.py` | `Actividad`: premios, ayudas, niveles, tropiezos, órdenes del profesional, resultado |
| `juegos.py` | búsqueda, pistas, sacar los tesoros, escondite, sigue al guía, explorador, cruce |
| `secuencia.py` | actividades de pasos: recadero, rutas, localizar, visita guiada |
| `practicas.py` | exploración libre, familiarización de sala, línea guía |
| `examenes.py` | los cinco exámenes |
| `lugares.py` | de un id o una posición a un lugar; pistas con relaciones espaciales; rutas comparables |
| `reparto.py` | `repartir_premios` |
| `puntuacion.py` | salida 3-2-1-0, error angular, cociente de camino, regla de parada, estrellas |
| `recompensas.py` | `calcular(resultado, estilo)` |
| `cuestionario.py` | preguntas finales de esfuerzo, confianza y disfrute |
| `textos.py` | frases en los tres estilos |
| `plantillas.py` | actividades de ejemplo de los tres entornos de ejemplo |

## API pública

```
TIPOS: dict[str, InfoTipo]            InfoTipo(id, nombre, descripcion, modo_por_defecto, grupo)   grupo: juego | practica | examen
                                      nombre y descripcion en español; nombre_visible y descripcion_visible, traducidos
campos_de(tipo) -> list[Campo]        Campo(clave, etiqueta, tipo, ayuda, opciones=None, defecto=None, minimo=None, maximo=None,
                                            grupo="general", depende_de=None)
leer_campo(datos, clave, defecto=None) · poner_campo(datos, clave, valor) · valores_por_defecto(tipo)
nueva_actividad(tipo, entorno, catalogo=None, **opciones) -> dict
validar_actividad(datos, entorno, catalogo=None, recursos=None) -> list[Aviso]
                                      recursos: nombres de los recursos del paquete (un dict o una lista); sin ellos no se comprueba el audio
crear_actividad(datos, entorno, catalogo=None, estilo=None, semilla=None, nivel=None) -> Actividad
describir_actividad(datos, entorno) -> str
repartir_premios(entorno, cantidad, catalogo=None, semilla=None, plantas=None, visibilidad="cerca", dentro_de_objetos=True) -> list[dict]
normalizar(datos) -> dict
plantillas_de(nombre_del_ejemplo, entorno, catalogo=None) -> list[dict]
recompensas.calcular(resultado, estilo) -> list[dict]      {"tipo": "estrella" | "medalla" | "objeto", "nombre": ..., "motivo": ...}
cuestionario.preguntas(estilo) -> list[dict] · cuestionario.presentacion(estilo) · cuestionario.normalizar_respuestas(respuestas)

class Actividad:
  id, nombre, tipo, modo, datos, estilo, semilla, nivel
  al_empezar(sesion) · tras_mover(sesion) · al_interactuar(sesion, elemento) · tic(sesion, dt) · al_pedir(sesion, accion) · al_registrar(sesion, registro) · resultado(sesion)
  ajustes(base: AjustesJuego) -> AjustesJuego       copia con las ayudas, los límites y el estilo de la actividad
  inicio() -> Posicion | None
  estado() -> dict
  orden_profesional(sesion, tipo, datos) -> list[Evento]      tipo: pista | premio | ayudas | mensaje
  confirmar(sesion) -> list[Evento]                 «ya he llegado», «es hacia ahí», «esta respuesta»
  responder(sesion, opcion: int) -> list[Evento]    elige una opción de la pregunta en curso (0 es la primera)
  pregunta() -> dict | None                         {"texto", "opciones", "elegida"}
  valorar(sesion, respuestas) -> dict               apunta el cuestionario final con un registro «valoracion»
  acompanante() -> str · modo_baliza() -> str · reglas_ayudas() -> dict · tiempo_restante() -> float | None
```

### Campos del formulario

`campos_de(tipo)` describe el formulario de un tipo, en el orden en que conviene mostrarlo. Tipos de campo: `texto`, `texto_largo`, `entero`, `decimal`, `si_no`, `opcion`, `posicion`, `elemento`, `lista_premios`, `lista_objetivos`, `ayudas` y `sonido`.

- En `opcion`, `opciones` es una lista de pares `(valor, etiqueta)`.
- En `elemento`, `opciones` es la lista de clases que valen: `espacio`, `abertura`, `objeto`, `referencia`, `salida`, `conector`. El valor es el id del elemento.
- Una clave con punto (`mensajes.inicio`, `travieso.activo`, `regla_parada.de`) nombra un valor dentro de un diccionario; se lee y se escribe con `leer_campo` y `poner_campo`.
- `depende_de` es la clave de un campo `si_no` que debe estar activado para que el campo tenga sentido.
- `grupo` agrupa los campos en el formulario: `general`, `premios`, `objetivos`, `puntuacion`, `examen`, `ayudas`, `mensajes`, `final`.

## Formato común

Lo que falta toma su valor de serie (`normalizar`); los ejemplos de este documento solo llevan lo que cambia.

| Clave | Serie | Qué es |
| --- | --- | --- |
| `formato` | 1 | Versión del formato |
| `id`, `nombre`, `descripcion` | | El `id` es el nombre del fichero dentro del paquete |
| `tipo` | | Uno de los de `TIPOS` |
| `modo` | el del tipo | `juego`, `practica` o `examen`. Un tipo de examen es siempre `examen` |
| `estilo` | `del_alumno` | `infantil`, `juvenil`, `adulto` o `del_alumno` (el de su ficha) |
| `inicio` | `null` | `{"planta", "x", "y", "rumbo"}`; `null` es el inicio del entorno |
| `premios` | `[]` | Ver «Premios» |
| `objetivos` | `[]` | Pasos, paradas, zonas o escondites, según el tipo |
| `orden_obligatorio` | `false` | Búsqueda y visita guiada: en el orden de la lista |
| `ayudas` | `{}` | ayuda → `{"permitida": bool, "limite": int o null}`; también vale `false` o un número. Lo que no se indica queda como en la ficha del alumno |
| `baliza` | `al_pedir` | `nunca`, `al_pedir` (suena unos segundos al pedir una pista) o `siempre`. Si hay niveles, mandan ellos |
| `usar_niveles`, `niveles`, `nivel` | `false`, `[]`, 0 | Retirada progresiva de ayudas |
| `tiempo_limite_s` | `null` | Contrarreloj, en segundos de juego. `null` o 0: sin límite |
| `fallos_para_ayuda` | 3 | Tropiezos seguidos tras los que se ofrece una pista. 0: nunca |
| `travieso` | inactivo | `{"activo", "cada_s", "veces"}` |
| `con_acompanante`, `acompanante` | `true`, `""` | Personaje acompañante del estilo infantil y su nombre |
| `mensajes` | vacíos | `{"inicio", "logro", "final"}`; vacío es el mensaje de serie del estilo |
| `recompensas` | | `{"desbloqueos": [{"estrellas": 5, "nombre": "la casa del árbol"}], "estrellas_previas": 0}` |
| `cuestionario` | `false` | Preguntas opcionales al terminar |
| `semilla` | `null` (1 en examen) | Fija lo que se genera al azar |
| `regla_parada` | examen: 3 de 5 | `{"de": 5, "minimo": 3}` o `null` |

### Lugares

Donde una actividad nombra un sitio (`destino`, `origen`, `recoger`, `entregar`, `espacio`…) vale:

- el **id de un elemento** del entorno: un espacio (se llega al entrar en él), un objeto (se llega al tenerlo a mano, sin pared por medio), una abertura, una referencia, una fuente de sonido o un conector;
- una **posición** `{"planta", "x", "y"}`, con `nombre` opcional (se llega a 1,2 m).

Para un objeto, el destino real es el punto libre desde el que se le puede usar (`lugares.punto_de_acceso`): su centro no se puede pisar y, si está pegado a un tabique, el sitio libre más cercano a su centro puede caer en la habitación de al lado. (La ruta del navegador hasta el centro de un mueble ya acaba por su lado de la pared; `punto_de_acceso` sigue haciendo falta porque la llegada por radio, la baliza y la validación necesitan un punto que se pueda pisar.)

### Premios

```
{"id", "nombre", "planta", "x", "y",
 "visibilidad": "lejos" | "cerca" | "oculto",
 "dentro_de": id de objeto | null,
 "sonido": "", "mensaje": "", "audio": "sonidos/…" | null, "vibrar": true, "pista": ""}
```

- **Son fuentes de sonido de la sesión** (`sesion.anadir_fuente`, id `premio:<id>`), con la oclusión real del motor. `lejos` se oye a 30 m (`premio/aparece` cada 2,5 s); `cerca`, a 5 m (`premio/cerca`, en bucle); `oculto` no suena ni vibra. `sonido` sustituye al de serie.
- `dentro_de`: el premio está en un objeto y hay que **usarlo** (la orden `interactuar`) para encontrarlo; pasar a su lado no basta, y a través de una pared tampoco. Vale cualquier objeto; la validación avisa si su ficha no dice `contenedor`.
- Un premio suelto se recoge al llegar a 90 cm, o con `interactuar` si queda a mano (1,6 m).
- `mensaje` se dice al recogerlo; `audio` es un recurso del paquete (grabado por el profesional o la familia) que suena después.
- `vibrar`: patrón `premio_cerca` cada 1,3 s a menos de 2,5 m.
- Al recogerlo: `premio/recogido` (o `premio/tesoro` si era el último), vibración `objetivo`, registro `premio` y entra en la colección.

### Ayudas, baliza y niveles

Nombres de las ayudas: los de `app.motor.percepcion.AYUDAS`. `Actividad.ajustes(base)` devuelve una copia de los ajustes del alumno con las reglas de la actividad; por si quien crea la sesión no pasa por ahí, `al_empezar` las vuelve a aplicar.

Los **niveles** retiran ayudas poco a poco. Los de serie (`usar_niveles: true`):

| Nivel | Baliza | Además |
| --- | --- | --- |
| 0 | `siempre`: suena sola, paso a paso por el camino | |
| 1 | `al_pedir`: 20 segundos al pedir una pista | |
| 2 | `nunca` | la baliza queda prohibida |
| 3 | `nunca` | sin «dónde estoy» ni descripción |

Se supera un nivel completando la actividad sin pedir pistas, sin que haya habido que ofrecer ayuda y sin pistas del profesional. El resultado lleva `nivel`, `nivel_superado` y `nivel_siguiente`; quien guarda el progreso del alumno pasa ese valor en `crear_actividad(..., nivel=…)` la próxima vez. La actividad no guarda nada entre sesiones.

En el reproductor lo hace la pantalla de juego: al crear la actividad pide el nivel con `app.nivel_actividad(entorno_id, actividad_id)` (si la aplicación lo tiene y devuelve un entero) y, al terminar, devuelve `resultado["nivel_siguiente"]` con `app.anotar_nivel(entorno_id, actividad_id, nivel)`. Además sortea una **semilla por partida** y la pasa a `crear_actividad(..., semilla=…)` y a la `Sesion`; un examen la ignora y usa la suya. `nivel`, `nivel_siguiente`, `semilla` y `semilla_actividad` quedan en el resultado que se graba y que se envía a la sala.

Reglas que valen para todos los juegos y prácticas:

- **Ganar nunca depende solo de seguir una baliza.** Con la baliza continua no se gana la estrella de pocas ayudas ni se llega al último nivel, y la baliza solo lleva hasta el sitio: un premio escondido sigue habiendo que encontrarlo usando el objeto que lo guarda.
- **Las pausas no penalizan.** Todos los tiempos son tiempo de juego (`sesion.t`).
- **Chocar informa pero no elimina.** Lo dice el motor; la actividad solo cuenta.
- **Tras varios tropiezos seguidos se ofrece ayuda en vez de insistir** (`fallos_para_ayuda`): un tropiezo es una salida peor que la óptima, una confirmación equivocada, alejarse del guía, separarse de la línea, un cruce en rojo o con incidente, o cuatro choques en veinte segundos. También se ofrece tras 150 segundos sin avanzar. La pista que se pide después dice más y enciende la baliza un rato aunque el nivel la haya retirado. Nunca en examen.
- **El contrarreloj es siempre opcional** y avisa cuando queda un minuto.

### Estilos

El contenido de aprendizaje es el mismo; cambia cómo se dice (`textos.py`).

| | Inicio de una búsqueda | Al encontrar | Al terminar |
| --- | --- | --- | --- |
| `infantil` | «Soy Tiko y voy contigo. ¡A buscar tesoros! Hay 5 premios escondidos.» | «¡Has encontrado la moneda de oro!» | «¡Lo has conseguido! ¡Bravo!» |
| `juvenil` | «Misión: encontrar los premios escondidos.» | «Conseguido: la moneda de oro.» | «Misión cumplida. … Tu marca: 3 minutos y 12 segundos.» |
| `adulto` | «Prepara la visita: hay cosas que encontrar.» | «Encontrado: las llaves.» | «Actividad completada.» |

El estilo adulto no usa exclamaciones ni personajes. Las frases de examen son las mismas en los tres estilos y no valoran.

## Juegos

### `busqueda`: búsqueda del tesoro

Encontrar todos los premios. Propio: `orden_obligatorio` (solo suena y se puede coger el que toca), `anunciar_premios` (decir cuántos y cuáles), `travieso`.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "busqueda-del-tesoro",
  "tipo": "busqueda",
  "nombre": "Búsqueda del tesoro en casa",
  "descripcion": "Cinco tesoros escondidos por toda la casa: hay que entrar en todas las habitaciones y abrir cosas.",
  "estilo": "infantil",
  "premios": [
    {
      "id": "moneda",
      "nombre": "la moneda de oro",
      "planta": "pla-1",
      "x": 2.25,
      "y": 7.75,
      "dentro_de": "obj-49",
      "mensaje": "Estaba debajo de la cama."
    },
    {
      "id": "dinosaurio",
      "nombre": "el dinosaurio",
      "planta": "pla-1",
      "x": 3.5,
      "y": 3.55,
      "dentro_de": "obj-26"
    },
    {
      "id": "galleta",
      "nombre": "la galleta gigante",
      "planta": "pla-1",
      "x": 7.7,
      "y": 3.67,
      "dentro_de": "obj-34",
      "mensaje": "¡Qué fresquita!"
    },
    {
      "id": "patito",
      "nombre": "el patito de goma",
      "planta": "pla-1",
      "x": 5.75,
      "y": 6.95
    },
    {
      "id": "estrella",
      "nombre": "la estrella brillante",
      "planta": "pla-1",
      "x": 6.75,
      "y": 4.75,
      "visibilidad": "lejos"
    }
  ],
  "mensajes": {
    "inicio": "¡Hola! Tiko ha escondido cinco tesoros por la casa. ¡Vamos a buscarlos!",
    "final": "¡Has encontrado todos los tesoros de la casa!"
  },
  "cuestionario": true,
  "recompensas": {
    "desbloqueos": [
      {
        "estrellas": 5,
        "nombre": "la casa del árbol"
      }
    ]
  }
}
```

La versión adulta, sobria: «Prepara la visita: encuentra las llaves, el abrigo y el paraguas».

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "prepara-la-visita",
  "tipo": "busqueda",
  "nombre": "Prepara la visita",
  "descripcion": "Antes de salir de casa: localizar las llaves, el abrigo y el paraguas. Sobrio y práctico, pensado para adultos.",
  "estilo": "adulto",
  "premios": [
    {
      "id": "llaves",
      "nombre": "las llaves",
      "planta": "pla-1",
      "x": 4.29,
      "y": 0.8,
      "visibilidad": "oculto",
      "dentro_de": "obj-28"
    },
    {
      "id": "abrigo",
      "nombre": "el abrigo",
      "planta": "pla-1",
      "x": 0.3,
      "y": 5.95,
      "visibilidad": "oculto",
      "dentro_de": "obj-57"
    },
    {
      "id": "paraguas",
      "nombre": "el paraguas",
      "planta": "pla-1",
      "x": 7.25,
      "y": 4.75,
      "mensaje": "Estaba secándose junto al radiador del pasillo."
    }
  ],
  "mensajes": {
    "inicio": "Prepara la visita: encuentra las llaves, el abrigo y el paraguas.",
    "final": "Ya lo tienes todo para salir."
  },
  "baliza": "nunca"
}
```

### `pistas`: pistas encadenadas

Como una búsqueda en orden, pero solo suena el premio que toca y al cogerlo se oye la pista del siguiente. La pista es la `pista` del premio o, si no tiene y `pistas_automaticas` es cierto, una redactada con relaciones reales del entorno: «Está en la habitación que queda al este de Salón». Se elige como referencia una habitación que toque a la del premio y que quede bien alineada con un punto cardinal, sin nombrar la del premio. Pedir pista repite la de la cadena; insistir dice la habitación y, a la tercera, en qué parte y dentro de qué objeto.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "pistas-por-la-casa",
  "tipo": "pistas",
  "nombre": "Pistas por la casa",
  "descripcion": "Cuatro sobres encadenados: cada uno dice dónde está el siguiente, con relaciones reales entre las habitaciones.",
  "estilo": "juvenil",
  "premios": [
    {
      "id": "sobre-1",
      "nombre": "el primer sobre",
      "planta": "pla-1",
      "x": 7.69,
      "y": 0.9,
      "dentro_de": "obj-36"
    },
    {
      "id": "sobre-2",
      "nombre": "el segundo sobre",
      "planta": "pla-1",
      "x": 5.75,
      "y": 6.95
    },
    {
      "id": "sobre-3",
      "nombre": "el tercer sobre",
      "planta": "pla-1",
      "x": 2.25,
      "y": 0.15,
      "dentro_de": "obj-33"
    },
    {
      "id": "sobre-4",
      "nombre": "el sobre final",
      "planta": "pla-1",
      "x": 2.25,
      "y": 6.6,
      "dentro_de": "obj-52"
    }
  ],
  "usar_niveles": true,
  "nivel": 1
}
```

### `sacar_tesoros`: sacar los tesoros

El juego de AbES. Se recoge un tesoro (mientras se lleva, los demás callan y no se pueden coger) y se saca por una abertura marcada `es_salida`. Al cruzarla el tesoro puntúa y el alumno vuelve a aparecer dentro, junto a esa puerta. Propio: `tolerancia_m`.

<!-- entorno: centro-de-dos-plantas -->
```json
{
  "id": "sacar-los-tesoros",
  "tipo": "sacar_tesoros",
  "nombre": "Sacar los tesoros del centro",
  "descripcion": "Cinco tesoros por las dos plantas. Se sacan de uno en uno por la salida más cercana: 3, 2, 1 o 0 puntos según la salida.",
  "estilo": "juvenil",
  "premios": [
    {
      "id": "premio-1",
      "nombre": "el trofeo",
      "planta": "pla-2",
      "x": 1.75,
      "y": 0.75
    },
    {
      "id": "premio-2",
      "nombre": "el mapa antiguo",
      "planta": "pla-1",
      "x": 17.25,
      "y": 10.75
    },
    {
      "id": "premio-3",
      "nombre": "la llave maestra",
      "planta": "pla-2",
      "x": 17.25,
      "y": 11.25
    },
    {
      "id": "premio-4",
      "nombre": "el globo terráqueo",
      "planta": "pla-1",
      "x": 2.25,
      "y": 10.25
    },
    {
      "id": "premio-5",
      "nombre": "el reloj de arena",
      "planta": "pla-1",
      "x": 9.25,
      "y": 2.75
    }
  ],
  "cuestionario": true,
  "baliza": "nunca"
}
```

### `recadero`: el recadero

Coger algo en un sitio y llevarlo a otro. Cada objetivo es un encargo `{"nombre", "recoger", "entregar"}`, o un paso suelto `{"tipo": "recoger" | "entregar" | "ir_a", "destino", "nombre"}`. Se encadenan en orden.

<!-- entorno: barrio-de-ejemplo -->
```json
{
  "id": "recado-a-la-parada",
  "tipo": "recadero",
  "nombre": "Un recado hasta la parada",
  "descripcion": "Recoger una carta junto al buzón de correos y llevarla a la parada de autobús, cruzando las dos calles.",
  "estilo": "adulto",
  "objetivos": [
    {
      "id": "carta",
      "nombre": "la carta",
      "recoger": "ref-37",
      "entregar": "ref-23"
    }
  ]
}
```

### `escondite`: el escondite

Un personaje escondido que se delata con un sonido cada `cada_s` segundos (fuente `escondite`, audible a 45 m). Al encontrarlo se esconde otra vez, lejos, hasta completar las `rondas`. Los `objetivos` son los escondites posibles; vacío, los elige el programa. Para un adulto el «personaje» de serie es un teléfono que suena.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "el-escondite",
  "tipo": "escondite",
  "nombre": "¿Dónde está Rita?",
  "descripcion": "Encontrar a un personaje escondido que hace ruido de vez en cuando.",
  "estilo": "infantil",
  "personaje": "la rana Rita"
}
```

### `sigue_guia`: sigue al guía

Un guía recorre el camino más corto hasta `destino` y suena con los pasos del suelo que pisa. Se para a esperar (y llama) si el alumno queda a más de `distancia_espera`; ante una escalera o un ascensor espera a que llegue, dice por dónde hay que seguir y aguarda en la otra planta. No hay baliza ni niveles: el guía es la ayuda.

<!-- entorno: centro-de-dos-plantas -->
```json
{
  "id": "sigue-al-guia",
  "tipo": "sigue_guia",
  "nombre": "Sigue al guía hasta la biblioteca",
  "descripcion": "Un guía lleva al alumno del vestíbulo a la biblioteca; se le sigue por el sonido de sus pasos.",
  "destino": "esp-14"
}
```

### `explorador`: el explorador

Descubrir todos los espacios a los que se puede llegar (o la `fraccion` indicada). Cada uno nuevo suena a hallazgo (`premio/aparece`).

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "explorador",
  "tipo": "explorador",
  "nombre": "Explora la casa",
  "descripcion": "Descubrir todos los espacios del entorno; cada uno nuevo suena a hallazgo.",
  "estilo": "juvenil",
  "tiempo_limite_s": 600.0
}
```

### `cruce`: cruza con el pitido

En exteriores. Hay que cruzar una calzada `cruces` veces y, si se indica `destino`, llegar después a ese lugar. Usa los registros `cruce_empieza`, `cruce_inseguro` y `cruce` del motor. `"trafico": false` apaga los vehículos (para practicar solo el semáforo).

<!-- entorno: barrio-de-ejemplo -->
```json
{
  "id": "practica-de-cruce",
  "tipo": "cruce",
  "nombre": "Práctica de cruce",
  "descripcion": "Cruzar dos veces: por el paso con semáforo sonoro y por el paso sin semáforo. Es un simulador: no dice si un cruce real es seguro.",
  "cruces": 2
}
```

## Prácticas

### `exploracion`: exploración libre

Sin objetivo y sin final: termina cuando el alumno quiere (o al acabar el tiempo, si lo hay) y siempre cuenta como terminada. Anota qué parte del entorno se ha recorrido.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "exploracion-libre",
  "tipo": "exploracion",
  "nombre": "Exploración libre de la casa",
  "descripcion": "Recorrer el entorno con libertad, sin objetivo ni puntuación."
}
```

### `visita_guiada`: visita guiada

Cada objetivo es una zona `{"destino", "texto"}`; al llegar se dice el nombre del lugar y el texto. Sin texto se lee la descripción del espacio; sin zonas, se visitan todos los espacios. Con `narrada_en_vivo` no se lee nada: narra el profesional con la orden `mensaje`.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "visita-con-textos",
  "tipo": "visita_guiada",
  "nombre": "Visita a la casa con explicaciones",
  "descripcion": "Recorrer el entorno oyendo textos preparados en cada zona, o la narración en vivo del profesional.",
  "objetivos": [
    {
      "id": "zona-salon",
      "destino": "esp-4",
      "texto": "El sofá queda a la derecha según entras y la ventana, al fondo.",
      "tipo": "ir_a"
    },
    {
      "id": "zona-cocina",
      "destino": "esp-5",
      "texto": "El frigorífico zumba en la esquina. La mesa está en el centro.",
      "tipo": "ir_a"
    }
  ],
  "orden_obligatorio": true
}
```

### `ruta`: ruta

Ir a `destino`, pasando antes por los `objetivos` (paradas) si los hay.

<!-- entorno: centro-de-dos-plantas -->
```json
{
  "id": "ruta-a-informatica",
  "tipo": "ruta",
  "nombre": "Del vestíbulo a la sala de informática",
  "descripcion": "Ruta con cambio de planta. Las ayudas se retiran por niveles: con baliza, baliza al pedirla, sin baliza y sin «dónde estoy».",
  "destino": "esp-40",
  "usar_niveles": true
}
```

### `ruta_inversa`: ruta inversa

Se va a `destino` (con baliza paso a paso si `ida_guiada`) y se vuelve por donde se vino hasta el punto de partida, sin baliza. Solo se mide la vuelta.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "ida-y-vuelta-a-la-cocina",
  "tipo": "ruta_inversa",
  "nombre": "Ida y vuelta a la cocina",
  "descripcion": "Ir a un lugar y volver por donde se vino.",
  "destino": "esp-5"
}
```

### `volver_origen`: volver al origen

Se pasa por los `objetivos` en orden y se regresa al punto de partida. La vuelta es lo que se mide: el camino más corto suele ser un atajo que no se ha andado a la ida.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "vuelta-a-la-entrada",
  "tipo": "volver_origen",
  "nombre": "Cocina, baño y vuelta a la entrada",
  "descripcion": "Pasar por varios lugares y regresar al punto de partida por el camino más corto.",
  "objetivos": [
    {
      "id": "parada-1",
      "destino": "esp-5",
      "tipo": "ir_a"
    },
    {
      "id": "parada-2",
      "destino": "esp-7",
      "tipo": "ir_a"
    }
  ]
}
```

### `ruta_alternativa`: ruta alternativa

Ir a `destino` con un paso cortado (`corte`, o varios en `cortes`). Una puerta o un hueco cortados quedan con llave durante la partida (el entorno no se toca); un conector cortado no se puede cerrar: se avisa y se anota en `paso_cortado_usado` si se usa. El camino óptimo se calcula con `evitar` del navegador.

<!-- entorno: centro-de-dos-plantas -->
```json
{
  "id": "ascensor-averiado",
  "tipo": "ruta_alternativa",
  "nombre": "Hoy no funciona el ascensor",
  "descripcion": "Llegar al destino con una puerta o una escalera cortadas: hay que encontrar otro camino.",
  "destino": "esp-36",
  "cortes": [
    "con-50"
  ]
}
```

### `localizar`: localizar un espacio

Encontrar un espacio sabiendo solo su nombre. Con `confirmar`, entrar no basta: hay que decir que se ha llegado; si se confirma en otro sitio se dice «Todavía no has llegado» (es una práctica) y cuenta como tropiezo.

<!-- entorno: barrio-de-ejemplo -->
```json
{
  "id": "encuentra-el-centro-civico",
  "tipo": "localizar",
  "nombre": "Encuentra el centro cívico",
  "descripcion": "Llegar al vestíbulo del centro cívico sabiendo solo su nombre.",
  "destino": "esp-30",
  "confirmar": true,
  "baliza": "nunca"
}
```

### `perimetro`: familiarización de sala

Primero el perímetro, después el interior. El contorno de la sala se trocea de metro en metro y un trozo queda recorrido al pasar a menos de `distancia_pared`; al llegar a `fraccion_perimetro` se pasa al interior, que se da por conocido al pisar la `fraccion_interior` de una rejilla de un metro alejada de las paredes. En una sala pequeña el alcance se reduce (al 30 % de su lado menor), o desde el centro se tocarían todas las paredes a la vez.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "conoce-el-salon",
  "tipo": "perimetro",
  "nombre": "Conoce el salón",
  "descripcion": "Familiarización de sala: primero el perímetro siguiendo la pared y después el interior.",
  "inicio": {
    "planta": "pla-1",
    "x": 1.95,
    "y": 3.3,
    "rumbo": 180.0
  },
  "espacio": "esp-4",
  "baliza": "nunca"
}
```

### `linea_guia`: seguir una línea guía

Seguir un lado de un espacio (una pared, o el borde de una acera) de un extremo a otro. Se completa al recorrer el 90 %. Más de dos segundos a más de `distancia_maxima` cuenta como una separación.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "pared-del-pasillo",
  "tipo": "linea_guia",
  "nombre": "Sigue la pared del pasillo",
  "descripcion": "Seguir una pared o un bordillo de un extremo a otro sin separarse.",
  "inicio": {
    "planta": "pla-1",
    "x": 0.5,
    "y": 4.8,
    "rumbo": 90.0
  },
  "espacio": "esp-2",
  "lado": "norte"
}
```

## Exámenes

En modo examen:

- **No hay pistas ni baliza**, lo diga quien lo diga, y quedan prohibidas de serie «dónde estoy», la descripción, la lista de cercanos y los lugares descubiertos (el profesional puede volver a permitir estas cuatro en `ayudas`). Percibir (bastón sonoro, mirar, eco, brújula) sigue disponible.
- **No hay celebraciones ni se dice si se acierta.** Tras cada prueba se oye «Anotado». Al terminar, «El examen ha terminado. Gracias.»; el total solo se dice con `decir_resultado`.
- No se ofrece ayuda por tropiezos, no hay travieso y no hay estrellas ni medallas.
- **El tiempo de cada prueba es tiempo de juego**: en pausa no corre (`tiempo_por_prueba_s`; 0 es sin límite).
- **Semilla**: las pruebas que genera el programa salen de la `semilla` de los datos del examen (1 si no se indica), no de la semilla de la sesión ni de la que se pase a `crear_actividad` (esa solo vale para las actividades que no traen la suya). Mismo entorno y misma semilla: mismo examen, en el mismo orden y con el mismo rumbo de partida. Para otro examen equivalente se cambia la semilla en los datos.
- **Regla de parada** `{"de": 5, "minimo": 3}`: hacen falta 3 aciertos en las 5 primeras pruebas; se para en cuanto ya no se puede llegar (al tercer fallo). El resultado lleva `parada: true` y el motivo `regla_parada`.
- Cada prueba deja un registro `examen` y el resultado las lleva todas en `examen["pruebas"]`.

Campos comunes: `numero_pruebas`, `pruebas` (definidas a mano; vacío es generarlas), `tiempo_por_prueba_s`, `semilla`, `regla_parada`, `decir_resultado`.

**Confirmar.** El alumno confirma con `interactuar` cuando lo que tiene delante no es una puerta ni un ascensor (esos hacen falta para moverse). El reproductor tiene además la acción `confirmar` (tecla M; gatillo izquierdo más Y o Triángulo en el mando), que llama a `actividad.confirmar(sesion)` y no depende de lo que haya al alcance. En los exámenes de preguntas, `objetivo` pasa a la opción siguiente y la dice, e `interactuar` confirma la elegida; `actividad.responder(sesion, n)` elige por número y `actividad.pregunta()` (también en `estado()["pregunta"]`) da el texto (la pregunta sola, sin «cambia de opción…») y las opciones para un menú.

**Menú de respuestas del reproductor.** Cuando `estado()["pregunta"]` trae una pregunta con opciones, el reproductor abre un menú hablado con ellas un fotograma después de que aparezca (así la instrucción de la prueba suena antes y el menú no la corta). Aceptar una opción es `responder` más `confirmar`. Ese menú **no pausa** la partida: el tiempo de la prueba sigue corriendo. Atrás vuelve al juego sin contestar y `confirmar` lo abre otra vez. Leer la pregunta así no gasta usos de la ayuda `objetivo` ni mueve la opción elegida. Si la prueba cambia (se acaba su tiempo), el menú se cierra y se abre el de la siguiente.

### `examen_rutas`: rutas

Se coloca al alumno en el origen, mirando a un rumbo sorteado, y se le dice a dónde ir. Confirma cuando cree haber llegado. Generadas: se calcula la ruta entre cada pareja de espacios (un punto por espacio, catorce como mucho), se ordenan por longitud y se sortean del tramo en el que la longitud y el número de giros varían menos. `entrenadas` (lista de parejas de ids) las excluye.

Variantes (`variante`): `normal`; `inversa` (se enseña la ida con baliza y se mide la vuelta); `atajo` (se enseñan dos tramos, A a B y B a C, y se mide ir de C a A). La fase de aprendizaje no puntúa y el reloj arranca cuando empieza lo que se mide.

<!-- entorno: centro-de-dos-plantas -->
```json
{
  "id": "examen-de-rutas",
  "tipo": "examen_rutas",
  "nombre": "Examen de rutas del centro",
  "descripcion": "Cinco rutas no entrenadas de longitud parecida, con seis minutos para cada una.",
  "semilla": 2026
}
```

Definidas por el profesional, en la variante inversa:

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "examen-de-rutas-de-casa",
  "tipo": "examen_rutas",
  "nombre": "Examen de rutas de la casa",
  "descripcion": "Serie de rutas no entrenadas de dificultad comparable, con límite de tiempo. Se registra el acierto y el tiempo.",
  "pruebas": [
    {
      "id": "ruta-1",
      "origen": "esp-4",
      "destino": "esp-7"
    },
    {
      "id": "ruta-2",
      "origen": "esp-6",
      "destino": "esp-5"
    }
  ],
  "tiempo_por_prueba_s": 240,
  "regla_parada": null,
  "variante": "inversa"
}
```

### `examen_salida`: salida más corta

Desde cada punto de partida hay que salir del edificio. No se confirma: salir es la respuesta. Generadas: se prefieren los puntos donde la mejor salida queda claramente más cerca que la segunda. Propio: `acierto_minimo` (puntos que cuentan como acierto para la regla de parada), `tolerancia_m`.

<!-- entorno: centro-de-dos-plantas -->
```json
{
  "id": "examen-de-salida",
  "tipo": "examen_salida",
  "nombre": "Examen de salida más corta",
  "descripcion": "Desde cinco puntos del centro, salir por la salida más cercana.",
  "semilla": 2026,
  "regla_parada": null
}
```

### `examen_senalar`: señalar

Girarse hacia un lugar de la misma planta que no se ve desde donde se está, y confirmar. Durante este examen cada pulsación gira `giro_grados` (15) para poder afinar. Propio: `tolerancia_grados` (error que cuenta como acierto).

<!-- entorno: centro-de-dos-plantas -->
```json
{
  "id": "examen-de-senalar",
  "tipo": "examen_senalar",
  "nombre": "Examen de señalar",
  "descripcion": "Girarse hacia cinco lugares del centro que no se perciben desde donde se está.",
  "semilla": 2026,
  "regla_parada": null
}
```

### `examen_distancias`: comparar distancias

«¿Qué queda más cerca, A o B?», por distancia de camino (`criterio: "camino"`) o en línea recta (`"recta"`). Generadas: se descartan las preguntas en las que las dos distancias difieren menos de un 20 %.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "examen-de-distancias",
  "tipo": "examen_distancias",
  "nombre": "¿Qué queda más cerca?",
  "descripcion": "Decidir cuál de dos lugares queda más cerca, andando o en línea recta.",
  "numero_pruebas": 6,
  "semilla": 11,
  "criterio": "recta"
}
```

### `examen_reconstruccion`: reconstrucción

«¿Qué hay al norte del salón?» Solo se pregunta por espacios que se tocan y están bien alineados con un punto cardinal (30 grados como mucho), y las opciones falsas son espacios que no están en esa dirección: cada pregunta tiene una única respuesta correcta.

<!-- entorno: vivienda-de-ejemplo -->
```json
{
  "id": "examen-de-reconstruccion",
  "tipo": "examen_reconstruccion",
  "nombre": "¿Dónde está cada habitación?",
  "descripcion": "Colocar las habitaciones en su posición relativa respondiendo a preguntas como «¿qué hay al norte del salón?».",
  "pruebas": [
    {
      "id": "p1",
      "referencia": "esp-4",
      "direccion": "este",
      "correcta": "esp-5",
      "opciones": [
        "esp-7",
        "esp-6"
      ]
    }
  ],
  "regla_parada": null
}
```

## Cómo se puntúa y en qué se basa

| Medida | Cómo se calcula | En qué se apoya |
| --- | --- | --- |
| **Salida más corta, 3-2-1-0** (`sacar_tesoros`, `examen_salida`) | Con el navegador se ordenan las salidas alcanzables por distancia de camino desde el punto de partida (en el juego, desde donde se cogió el tesoro). La salida elegida vale 3 si es la más cercana, 2 la segunda, 1 la tercera y 0 cualquier otra o el tiempo agotado. Dos salidas que difieren menos de `tolerancia_m` comparten puesto | Es la prueba de AbES. Connors y otros (2014), adultos ciegos en un edificio real de dos plantas y tres salidas: quienes aprendieron jugando obtuvieron 2,71 sobre 3 frente a 1,66 con instrucción dirigida. Con adolescentes (Connors y otros, 2014), la puntuación obtenida durante el juego predijo el rendimiento real (correlaciones de 0,79 y 0,85). Por eso el juego guarda la misma puntuación que el examen |
| **Rutas: acierto y tiempo** (`examen_rutas`) | Acierto si al confirmar se está en el destino (dentro del espacio, o a 1,2 m del punto). Tiempo de juego por ruta, con límite (6 minutos de serie). Además, camino andado entre camino más corto | Rutas de A a B no entrenadas con límite de tiempo, como en AbES. En ese estudio no hubo diferencia entre grupos en esta prueba (88 a 93 % de aciertos): mide conocer rutas, no conocer el lugar |
| **Ruta inversa y atajos** (variantes de `examen_rutas`, `ruta_inversa`, `volver_origen`) | Igual que una ruta, pero lo que se mide no se ha practicado en ese sentido o por ese camino | Distinguen conocer una ruta de conocer el sitio. Es una práctica habitual de la investigación en cognición espacial; no hay cifras propias de AbES para ellas |
| **Señalar: error angular** (`examen_senalar`) | Grados (0 a 180) entre el rumbo del alumno al confirmar y la dirección en línea recta al lugar. Se da la media y la mediana | Tareas de señalamiento hacia lugares no percibidos (Lahav y otros, 2015, BlindAid: 9 personas, sin estadística por el tamaño de la muestra). Exploratorio |
| **Comparar distancias** (`examen_distancias`) | Acierto si se elige el lugar más cercano según el criterio configurado | Estimación de distancias, tarea clásica de mapa cognitivo. Sin respaldo específico en los estudios revisados |
| **Reconstrucción** (`examen_reconstruccion`) | Acierto si se elige el espacio que está en la dirección preguntada | Equivale a reconstruir el plano con piezas. Sin respaldo específico en los estudios revisados |
| **Cruces, 3-2-1-0** (`cruce`) | 3 por el paso y sin incidentes; 2 sin incidentes fuera del paso; 1 con el semáforo en rojo; 0 si un vehículo tuvo que frenar o pasó al lado | Bowman y Liu (2017): el entrenamiento virtual de la decisión de cruzar igualó al real en 12 personas con baja visión severa. La escala de puntos es una convención de este programa |
| **Cociente camino real / óptimo** | Metros andados en cada tramo medido entre metros del camino más corto del navegador. 1 es el camino más corto | Medida descriptiva habitual. El informe de seguimiento la muestra sin interpretar |
| **Perímetro e interior recorridos** (`perimetro`) | Parte de los trozos de un metro del contorno junto a los que se ha pasado, y parte de la rejilla interior pisada | La familiarización de sala (perímetro y después interior) es técnica habitual de orientación y movilidad. Los umbrales son convenciones de este programa |
| **Estrellas** | Una por motivo: `completar`; `pocas_ayudas` (dos o menos pistas, balizas, «dónde estoy», cercanos o descubiertos, y sin baliza continua); `atajo` (cociente de 1,35 o menos); `salida_optima` (media de 2,5 o más); `sin_choques`; `exploracion` (todos los espacios alcanzables visitados); `seguridad` (todos los cruces con 3 puntos) | Convenciones de este programa, para que haya más de una manera de hacerlo bien. No miden competencia |

Qué estrellas puede dar cada tipo: `ESTRELLAS` de su clase. Los exámenes no dan ninguna.

## Recompensas y cuestionario

`recompensas.calcular(resultado, estilo)` devuelve, en este orden: una estrella por motivo ganado, las medallas (`pleno` por ganar todas las estrellas posibles, `salidas` por sacar todos los tesoros por la salida óptima, `explorador` por descubrirlo todo, `nivel` por superar un nivel), un objeto por cada premio encontrado (la colección) y lo que se desbloquea. Los nombres cambian con el estilo. En un examen la lista está vacía.

Los **desbloqueos** los define el profesional: `{"estrellas": 5, "nombre": "la casa del árbol"}` se gana cuando las estrellas de sesiones anteriores (`recompensas.estrellas_previas`, que pone quien lleva la cuenta) más las de esta sesión cruzan el umbral.

Cada recompensa sale además como registro `recompensa` (`tipo`, `nombre`, `motivo`), que es lo que lee `app.seguimiento`.

Con `cuestionario: true` el resultado lleva en `cuestionario` tres preguntas opcionales (`esfuerzo`, `confianza`, `disfrute`), cada una con su texto en el estilo del alumno y una escala de 1 a 5 con nombres. El reproductor las presenta y llama a `actividad.valorar(sesion, {"esfuerzo": 2, "confianza": 4, "disfrute": 5})`, que emite el registro `valoracion` (también después de terminada la sesión).

En la pantalla de fin, si el resultado trae preguntas, se abren solas después del resultado (sin cortarlo), una a una, con «Prefiero no contestar» en cada una y «Dejar las preguntas» para saltarse las que quedan. Una pregunta saltada se guarda como `null`. Las respuestas van al registro `valoracion` y a `resultado["valoracion"]` de la sesión grabada. Sin `cuestionario: true` no se pregunta nada.

La exploración libre (`exploracion`, y cualquier tipo desconocido, que se juega como ella) no tiene final propio: en la pausa del reproductor se ofrece «Terminar la exploración», que la cierra como terminada (`motivo: "terminada"`) y lleva a la pantalla de fin; no cuenta como abandonarla. El reproductor lo sabe por el atributo de clase `TERMINA_A_VOLUNTAD`.

## Órdenes del profesional

`actividad.orden_profesional(sesion, tipo, datos)` atiende las órdenes de la supervisión (mismos datos que el protocolo, ver [supervision.md](supervision.md)). **Devuelve los eventos que hay que presentar al alumno y no los emite en la sesión**: quien llama los presenta o se los pasa a `sesion.emitir`. Los cambios de estado sí quedan hechos. En el reproductor, `PantallaJuego.orden_profesor` (a la que llama el `Enlace` de la supervisión) se los pasa a `PantallaJuego.presentar_eventos`, que los emite en la sesión (llegan a la grabación, a la sala y al alumno en el mismo fotograma) o, si la sesión ya ha terminado, los entrega directamente. El reproductor le pasa `pista`, `ayudas` y `premio`; el `mensaje` lo dice él.

| Orden | Datos | Qué hace |
| --- | --- | --- |
| `mensaje` | `texto` | Voz por el canal `profesional` |
| `pista` | `texto`, `baliza_s`, `destino` | Dice el texto (o una pista redactada para el objetivo actual) y, con `baliza_s`, enciende la baliza ese tiempo aunque el nivel o el examen la tengan retirada. En un examen la prueba en curso queda marcada `con_ayuda_profesional` |
| `ayudas` | `ayudas` | Cambia permisos y límites en marcha |
| `premio` | `nombre`, `id`, `planta`, `x`, `y`, `sonido`, `mensaje`, `visibilidad` | Añade un premio. Sin posición, cae en un punto libre del espacio donde está el alumno. En una búsqueda se suma al total; en lo demás es un regalo |

Las intervenciones se cuentan en `resultado["intervenciones_profesional"]`.

## Resultado

`EvFin.resultado` lleva lo de la sesión (`tiempo_activo`, `tiempo_pausa`, `distancia_m`, `pasos`, `choques`, `ayudas`, `espacios_visitados`, `semilla`) y, de la actividad:

| Clave | Qué es |
| --- | --- |
| `actividad` | `{"id", "nombre", "tipo", "modo", "estilo"}` |
| `completada`, `motivo` | `completada`, `tiempo`, `abandonada`, `regla_parada`, `terminada` (exploración libre), `sin_premios`… |
| `objetivos_hechos`, `objetivos_total`, `objetivos` | Recuento y lista `{"id", "nombre", "t"}` |
| `puntos`, `puntos_maximos` | Marcador del tipo |
| `estrellas`, `estrellas_motivos`, `estrellas_posibles`, `estrellas_previas`, `desbloqueos` | |
| `recompensas`, `medallas`, `coleccion` | |
| `premios` | `{"id", "nombre", "recogido", "t", "extra"}` de cada uno |
| `camino_real_m`, `camino_optimo_m`, `cociente_camino`, `tramos` | Solo de los tramos medidos |
| `tiempo_juego_s`, `tiempo_limite_s`, `fuera_de_tiempo` | Sin pausas |
| `choques_actividad`, `ayudas_usadas`, `ayudas_contadas`, `ayudas_ofrecidas`, `fallos`, `travesuras` | |
| `intervenciones_profesional` | orden → veces |
| `nivel`, `nivel_nombre`, `nivel_superado`, `nivel_siguiente`, `baliza_continua` | |
| `examen` | Puntuaciones del examen (`null` si no es un examen): `medida`, `pruebas_hechas`, `pruebas_total`, `aciertos`, `porcentaje_aciertos`, tiempos, `puntos`, `puntos_maximos`, `parada`, `con_ayuda_profesional`, `semilla`, lo propio de cada examen y `pruebas` |
| `puntuaciones` | Lo mismo que `examen` en un examen; en `sacar_tesoros` y `cruce`, la puntuación del juego. Es lo que se pasa a `grabadora.puntuaciones` |
| `valoracion`, `cuestionario` | Respuestas (cuando las haya) y preguntas |
| `semilla_actividad` | La semilla con la que se generó lo aleatorio |
| `aviso` | Recordatorio de que la puntuación no equivale a competencia real |
| propias del tipo | `exploracion`, `salidas`, `rondas`, `cruces`, `pasos_actividad`, `confirmaciones_fallidas`, `mensajes_del_profesional`, `cortes`, `perimetro_recorrido`, `linea_recorrida`, `alejamientos`… |

Registros que emite la actividad (además de los del motor): `objetivo` (`id`, `nombre`), `premio` (`id`, `nombre`, `dentro_de`, `extra`), `recompensa`, `examen` (una prueba), `puntuacion` (totales), `valoracion`, `ayuda_ofrecida`, `travieso`, `salida_puntuada`, `cruce_puntuado`, `pista_profesional` y `premio_nuevo`.

`estado()` da `objetivo`, `hechos`, `total`, `puntos`, `puntos_maximos`, `estrellas`, `tiempo_restante`, `nivel`, `nivel_nombre`, `fase`, `premios_pendientes`, `pregunta`, `terminada` y `completada`.

## Lo que la actividad toma del motor

- Los ganchos de `docs/motor.md` y lo que ofrece la `Sesion`: `decir`, `sonar`, `vibrar`, `registrar`, `anadir_fuente` y `quitar_fuente`, `baliza`, `recolocar`, `permitir_ayuda`, `distancia_a`, `nav`, `mundo`, `movimiento`, `percepcion`, `dinamica`.
- **Registros del motor.** La sesión pasa cada `EvRegistro` que emite (un choque, una entrada en un espacio, un cruce de calzada, un cambio de planta…) al gancho `al_registrar`. `Actividad.al_registrar` solo apunta los de `REGISTROS_DEL_MOTOR` y la actividad los atiende en su `tic` del mismo fotograma (`_al_registro` de cada tipo), porque el motor puede registrar a mitad de un paso. `tests/test_actividades_motor.py` lo vigila.
- El guía de `sigue_guia` suena con `sesion.acustica.disparar`, que hace sonar una vez una fuente añadida, con su oclusión.
- Lo que devuelven `al_pedir` y `al_interactuar` son eventos ya hechos (voz pedida, un sonido de interfaz): así el motor sabe que la pulsación se ha atendido y no añade «No hay ningún objetivo» o «No hay nada que usar aquí». Todo lo demás se dice con `sesion.decir`, casi siempre con prioridad 3 (instrucciones y llegadas no esperan turno).

## Validación

`validar_actividad` devuelve `Aviso` (los de `app.dominio.modelo`), con los errores primero.

El cuarto parámetro, `recursos`, es opcional: los nombres de los recursos del paquete (`contexto.recursos` en el Estudio, `Paquete.recursos` al abrir un `.elab`; vale el diccionario o una lista de nombres). Si se pasa, se comprueba que el `audio` de cada premio está entre ellos, escrito con su carpeta (`sonidos/x.wav`) o sin ella, como lo busca `Paquete.recurso`. Si no se pasa, esa comprobación no se hace: quien valida sin el paquete delante no puede saberlo. «Comprobar el entorno» (F5) del Estudio valida así cada actividad del paquete abierto.

| Código | Gravedad | Cuándo |
| --- | --- | --- |
| `tipo_desconocido`, `formato`, `entorno_vacio` | error | |
| `inicio_no_valido`, `inicio_sin_planta`, `inicio_fuera` | error | El inicio no está en un espacio transitable |
| `planta_no_existe`, `fuera_de_espacio`, `dentro_de_macizo` | error | Un premio o un punto dentro de un muro, fuera del entorno o en un edificio macizo |
| `dentro_de_mueble` | aviso | Un premio suelto cae dentro de un mueble |
| `premio_sin_lugar`, `contenedor_no_existe`, `contenedor_sin_acceso` | error | |
| `no_es_contenedor`, `premio_en_el_inicio` | aviso | |
| `audio_no_existe` | aviso | Solo con `recursos`: el audio grabado de un premio no está en el paquete; al recogerlo no sonaría |
| `inalcanzable` | error | No se puede llegar andando desde el inicio, ni siquiera con llaves |
| `bloqueado` | aviso | Solo se llega por una puerta con llave: puede ser a propósito |
| `no_existe`, `sin_destino`, `objetivo_sin_destino`, `sin_objetivos`, `sin_premios`, `espacio_no_existe`, `objeto_sin_acceso` | error | Ids que ya no existen o datos que faltan |
| `sin_salidas` | error | Hace falta al menos una salida alcanzable |
| `una_sola_salida` | aviso | Elegir la más cercana no mide nada |
| `corte_no_existe`, `corte_sin_alternativa` | error | |
| `sin_corte`, `corte_fuera_del_camino`, `destino_no_es_espacio` | aviso | |
| `sin_calzada`, `guia_sin_camino` | error | |
| `examen_sin_pruebas`, `pruebas_no_validas`, `examen_no_generable` | error | El entorno no da para ninguna prueba, o las definidas apuntan a lugares que no existen |
| `pruebas_insuficientes`, `rutas_poco_comparables`, `regla_parada_larga` | aviso | |
| `ayuda_desconocida`, `estilo_desconocido`, `nivel_fuera_de_rango` | aviso | |

## Reparto asistido de premios

`repartir_premios(entorno, cantidad, catalogo, semilla, plantas, visibilidad, dentro_de_objetos)`: «reparte N premios de modo que haya que pasar por todos los espacios». Empieza por el espacio más lejano del inicio (por distancia de camino) y elige cada vez el más alejado de los ya elegidos; el espacio donde se empieza queda el último. Si el espacio tiene un objeto `contenedor` del catálogo, el premio va dentro; si no, en un punto libre a más de 1,6 m del inicio. Con más premios que espacios da otra vuelta. Misma semilla, mismo reparto. Los nombres («Premio 1»…) son provisionales.

## Ejemplos distribuidos

`tools/generar_ejemplos.py --amueblar` guarda en cada `.elab` de `data/ejemplos` las actividades de `plantillas.py`, tras validarlas:

- **Vivienda**: búsqueda del tesoro infantil, «Prepara la visita» adulta, pistas por la casa, familiarización del salón y visita guiada.
- **Centro de dos plantas**: sacar los tesoros, exámenes de rutas, de salida y de señalar, sigue al guía y una ruta por niveles.
- **Barrio**: un recado hasta la parada, práctica de cruce y localizar el centro cívico.

Los ejemplos JSON de este documento son los de esos paquetes (o válidos en ellos): una prueba (`tests/test_actividades_documentacion.py`) los lee de aquí y los valida.

## Qué NO afirma el programa

- **Una puntuación del juego o de un examen no equivale a competencia en el lugar real.** Describe lo ocurrido en el simulador; la comprobación en el lugar real la hace el profesional y la anota en el cuaderno de evaluación.
- **No hay diagnósticos ni recomendaciones.** Las estrellas, las medallas y los niveles son parte del juego, no una valoración del alumno.
- **No dice que un cruce real sea seguro.** La práctica de cruce usa tráfico simulado y sirve para ensayar la decisión.
- **No demuestra transferencia.** Los estudios en que se apoyan las medidas tienen entre 4 y 38 participantes y un solo edificio; lo aprendido es ese lugar, no una habilidad general, y no hay ensayos con mando de consola.
- Los umbrales que no vienen de un estudio (estrellas, perímetro, puntos de cruce, tolerancias) son **convenciones de este programa**, sin validar con alumnos.
- El resultado lleva este aviso en la clave `aviso` y los informes del seguimiento lo repiten.

## Pruebas

```
.venv\Scripts\python.exe -m pytest tests -q -k "actividades or motor"
```

`tests/test_actividades_comun.py` tiene el `Jugador` (el robot del motor jugando una actividad: `ir`, `usar` un objeto, `salir_por` una abertura, `confirmar`) y los entornos de ejemplo amueblados con el catálogo real de `data/plugins`.

`tests/test_reproductor_actividades_reales.py` juega los 22 tipos de principio a fin desde el reproductor real (`Aplicacion(pruebas=True)`), con la actividad de su ejemplo en este documento: el `JugadorReal` es ese mismo `Jugador`, pero cada orden es una acción inyectada en la aplicación (también `confirmar` y los menús de respuestas y del cuestionario). Cada prueba acaba en el `EvFin`, la pantalla de fin y la sesión grabada con `nivel` y `nivel_siguiente`.
