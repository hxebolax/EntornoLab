# Reproductor (`app/reproductor`)

Documentación de desarrollo de la aplicación pygame-ce con la que juega el alumno, y del modo recorrido del profesional. El contrato general está en [arquitectura.md](arquitectura.md); el motor, en [motor.md](motor.md); el sonido y la voz, en [sonido.md](sonido.md) y [voz.md](voz.md); teclado y mando, en [entrada.md](entrada.md); la grabación de sesiones, en [seguimiento.md](seguimiento.md); y la sala, en [supervision.md](supervision.md).

El reproductor no tiene reglas de juego: une lo que ya existe. No importa `wx` y no abre la base de datos del profesional.

## Arrancar

```
jugar.py [paquete] [--actividad id] [--alumno alias] [--sala equipo:puerto --codigo c] [--inicio planta,x,y,rumbo]
jugar.py --recorrido paquete --sala equipo:puerto --codigo c
jugar.py --comprobar-arranque
jugar.py --guion fichero.json [--informe informe.json] [paquete ...]
```

`main.py --jugar …` es lo mismo. `app/reproductor/arranque.py` analiza los argumentos (`analizar_argumentos` → `OpcionesReproductor`) y `ejecutar(argumentos)` crea la `Aplicacion` y corre su bucle.

| Argumento | Efecto |
|---|---|
| sin argumentos | Menú principal. Si no hay alias conocido, pregunta quién juega. |
| `paquete` | Abre ese entorno y enseña sus actividades (y la exploración libre). |
| `--actividad id` | Empieza esa actividad directamente. Si no existe, lo dice y enseña la lista. |
| `--alumno alias` | Juega con ese alias (nunca un nombre real). No se escribe en el registro. |
| `--sala equipo:puerto --codigo c` | Se conecta a la sala del Estudio. El código tampoco va al registro. |
| `--inicio planta,x,y,rumbo` | Punto de inicio para el entorno pasado por argumento (manda sobre el de la actividad). |
| `--recorrido` | Modo recorrido del profesional; exige paquete, sala y código. |
| `--comprobar-arranque` | Ventana oculta, sin voz ni sonido; da cinco fotogramas y sale. |
| `--guion fichero.json` | Sin ventana ni sonido, sigue los pasos del guion y sale (ver abajo). |
| `--informe informe.json` | Con un guion, dónde dejar el informe. |

Códigos de salida: 0 correcto, 2 argumentos (o guion) no válidos y, solo con `--comprobar-arranque` o un guion, 3 si el entorno pedido no se puede abrir; 4 si falla una comprobación o una espera del guion. En el uso normal un entorno dañado no es un error de arranque: se dice en voz alta y se queda en el menú principal.

## Sin ventana y modo guion

`app/reproductor/guion.py`. Sirve para probar el reproductor real lanzado por el Estudio como proceso hijo y para diagnosticar una instalación (también la compilada, con `EntornoLabJugar.exe`).

- **Sin ventana ni sonido**: `APP_SIN_VENTANA=1` (o un guion) pone los controladores «dummy» de SDL antes de importar pygame y crea `Aplicacion(pruebas=True)`: motor de sonido nulo, `VozFalsa` (no habla: apunta lo que se habría dicho) y sin mandos. El hijo hereda el entorno, así que basta con ponerla antes de que el Estudio lance el reproductor con sus argumentos de siempre.
- **Guion**: `--guion fichero.json` o `APP_GUION`; el informe, `--informe` o `APP_GUION_INFORME`. El guion lleva cada fotograma con el reloj real (la red y los temporizadores avanzan como en el uso normal), da los pasos y, al terminar, cierra la aplicación con orden (la sesión queda grabada) y escribe el informe.
- **Motor de sonido**: la clave `motor` del guion o `APP_GUION_MOTOR` (`openal`, `bass`, `clasico`, `estereo` o `nulo`) cambia el motor nulo por ese, abierto «en memoria»: no abre la tarjeta ni suena. Con OpenAL el informe dice si el HRTF quedó activo y con qué perfil. No toca la configuración.

```json
{
  "motor": "openal",
  "plazo": 30,
  "pasos": [
    {"hasta": "conectado", "plazo": 60},
    {"tecla": "F4"},
    {"elegir": "Colocar un objeto aquí"},
    {"elegir": "Buscar por nombre"},
    {"escribir": "paraguero", "intro": true},
    {"elegir": "Paragüero,"},
    {"hasta": "dicho", "texto": "colocado"},
    {"comprobar": "hrtf"},
    {"salir": true}
  ]
}
```

| Paso | Qué hace |
|---|---|
| `{"accion": "avanzar"}` | Pulsa y suelta una acción (`app/entrada/acciones.py`). |
| `{"tecla": "F4", "mod": ["ctrl"], "texto": "a"}` | Una tecla por el camino real (pantalla, mapa de teclado y acciones). El nombre es el de pygame sin `K_`. |
| `{"escribir": "mesa", "intro": true}` | Letras en una entrada de texto y, si se pide, Intro. |
| `{"elegir": "Colocar"}` | Va a la opción del menú de arriba que empieza así y la acepta. |
| `{"fotogramas": 10}`, `{"segundos": 0.5}` | Deja pasar tiempo. Junto a `accion`, `tecla`, `escribir` o `elegir`, `fotogramas` es cuántos se dejan pasar después. |
| `{"hasta": condición, "plazo": s}` | Espera a que se cumpla; si vence el plazo (el del paso, el del guion o 30 s), falla. |
| `{"comprobar": condición, "no": true}` | Comprueba ya (negada con `no`). |
| `{"salir": true}`, `{"nota": "…"}` | Cierra el reproductor; una nota no hace nada. |

Condiciones: `conectado`, `desconectado`, `partida`, `sin_partida`, `fin` (la última partida ha terminado), `completada`, `pausada`, `dicho` (con `texto`, sin distinguir mayúsculas), `pantalla` (con `texto`: parte del título de la pantalla de arriba o su clase), `posicion` (`x`, `y`, `planta` y `tolerancia`), `salida`, `motor` (`nombre`), `hrtf`, `sin_fallos` y `sin_complementos_que_faltan`. Por defecto el guion se para en el primer fallo (`"seguir_tras_fallo": true` lo evita); con `"al_terminar": "seguir"` el bucle sigue tras el último paso hasta que el reproductor salga.

El informe (JSON) trae `correcto`, `codigo`, `fallos`, cada paso con su resultado y duración, `dicho` (texto y canal de todo lo dicho), `estado_final` (pantallas, alias, conexión y la última partida: entorno, actividad, terminada, completada, posición y resultado), `sonido` (`motor.estado()`: motor, pedido, `memoria`, `hrtf_activo`, `perfil_hrtf`, versión…), `motores_disponibles`, `paquetes_sonido`, `complementos` (instalados, objetos y los que faltan para el entorno) y `sesiones` (los ficheros de `data/sessions`).

## Módulos

| Módulo | Qué hace |
|---|---|
| `arranque.py` | Argumentos y punto de entrada. |
| `guion.py` | Sin ventana ni sonido y modo guion: pasos, condiciones, motor en memoria e informe. |
| `aplicacion.py` | `Aplicacion`: ventana, bucle a 60 fotogramas, pila de pantallas, servicios (voz, motor de sonido, entrada, vibración, presentador), opciones en caliente, dibujo y cierre. |
| `menus.py` | `Pantalla` (base), `Opcion`, `Menu`, `Mensaje`, `EntradaTexto` (con rueda de letras para el mando), `Espera` y `confirmar`. |
| `ajustes.py` | Traduce la configuración compartida a los diccionarios que piden el sonido, la voz, el mando y la sesión. |
| `alumno.py` | `Perfil`: alias, preferencias de juego, premios, última actividad y tutorial hecho, en `data/config/alumnos/<alias>.json`. |
| `entornos.py` | Dónde están los `.elab`, abrirlos con errores que se pueden decir (`ErrorEntorno`), catálogo de complementos y los que faltan. |
| `puente_actividades.py` | Lo único que el reproductor sabe de `app.actividades`: crear, describir, estado, recompensas y cuestionario; tolera que el paquete falte. |
| `textos.py` | Frases según el estilo (infantil, juvenil, adulto). |
| `plano.py` | Plano cenital de la planta para baja visión y acompañantes. |
| `supervision.py` | `Enlace`: la parte de la supervisión que corre en el bucle (órdenes, avisos, voz, huella). |
| `pantallas/principal.py` | Menú principal, «¿Quién juega?», «Mis premios» y «Acerca de». |
| `pantallas/elegir.py` | Elegir entorno, elegir actividad y «Continuar». |
| `pantallas/juego.py` | `PantallaJuego`: la partida, la pausa y las órdenes del profesor. |
| `pantallas/fin.py` | Fin de actividad: resultado, celebración, premios y cuestionario. |
| `pantallas/tutorial.py` | Entorno y actividad del tutorial, hechos por código. |
| `pantallas/aprender.py` | «Aprender los sonidos» y «Practicar los controles». |
| `pantallas/opciones.py` | Todas las opciones, la captura de teclas y la reasignación de botones. |
| `pantallas/ayuda.py` | Lista de teclas y botones del contexto, generada de `app/entrada`. |
| `pantallas/conexion.py` | «Conectar con mi profesor». |
| `pantallas/recorrido.py` | Menú de edición y salto a un lugar del modo recorrido. |

## El fotograma

`Aplicacion.paso(dt, eventos)` hace siempre, en este orden:

1. **Entrada.** Cada evento de pygame se ofrece crudo a la pantalla de arriba (`Pantalla.tecla`); si no lo consume, `Entrada.traducir(evento, contexto)` lo convierte en acciones. `Entrada.actualizar` añade las que salen de las palancas, y `Entrada.avisos()` las frases de mando conectado o desconectado.
2. **Acciones.** Cada acción va a `Pantalla.accion`; si la pantalla no la quiere, la aplicación atiende las comunes: repetir, historial, callar y ayuda.
3. **Supervisión.** `Enlace.atender` reparte avisos de conexión y órdenes del profesor.
4. **Partida.** Si hay partida, `PantallaJuego.fotograma(dt, activa)`: ejes → `Sesion.analogico`, `Sesion.avanzar(dt)`, registros a la `Grabadora` y a la sala, muestra de la traza y estado para el profesor. Los eventos se dejan con `Aplicacion.entregar`.
5. **Pantalla de arriba.** `Pantalla.actualizar(dt)`.
6. **Presentación.** `Presentador.aplicar(eventos, sesion, dt)`, **siempre**: también en los menús (con la lista vacía) y aunque un paso anterior haya fallado. Es quien llama a `tic` del motor de sonido, y la protección auditiva calla la salida si deja de recibirlo.

`dt` se recorta a 0,1 s. Un fallo en los pasos 1 a 5 se registra con su traza, se dice una vez («Ha habido un problema, pero puedes seguir») y el bucle continúa; con cinco fallos seguidos se cierra la partida y se vuelve al menú principal. El reproductor nunca se cierra por un fallo de un fotograma.

El fin de la sesión (`EvFin`) se atiende un fotograma después de ocurrir, para que lo último de la partida ya se haya dicho cuando hable la pantalla de resultado.

## Pila de pantallas

`Aplicacion.pila` es una lista; la última es la que recibe la entrada (`Aplicacion.cima`). El menú principal está siempre en la base. `abrir(pantalla)` la pone arriba y llama a su `al_entrar`; `cerrar(pantalla)` la quita, vuelve a llamar al `al_entrar` de la que queda arriba y después al `al_salir` de la que sale (así lo que diga su respuesta se oye lo último).

La partida (`Aplicacion.partida`) es una pantalla más de la pila, pero sigue viva debajo de sus menús: se pausa sola mientras tenga algo encima y sigue atendiendo al profesor.

### Pantallas

| Pantalla | Cómo se llega | Qué hace |
|---|---|---|
| Menú principal | arranque | Continuar, Elegir entorno, Mis premios, Aprender los sonidos, Practicar los controles, Tutorial, Opciones, Conectar con mi profesor, Cambiar de jugador, Ayuda, Acerca de, Salir. |
| ¿Quién juega? | arranque sin alias, «Cambiar de jugador» | Alias de este equipo, alias nuevo (texto) o invitado. |
| Elegir entorno | menú principal | Paquetes de `data/entornos`, de la carpeta de entornos del Estudio y de `data/ejemplos`; la ayuda de cada uno dice su descripción. |
| Actividades del entorno | elegir un entorno, o `paquete` por argumento | Actividades (descritas con `describir_actividad`) y exploración libre. |
| Juego | elegir actividad, Continuar, Tutorial, `--actividad`, `--recorrido` | Ver «La partida». |
| Pausa | acción `pausa`, perder el foco | Continuar, recordar el objetivo, repetir las instrucciones, opciones rápidas, volver al inicio, ayuda y abandonar. En el recorrido, además: edición, saltar y modo fantasma. |
| Fin de actividad | `EvFin` de una actividad no abandonada | Resultado hablado, estrellas, medallas y premios; cuestionario opcional; repetir, elegir otra o volver. |
| Mis premios | menú principal | Totales y, uno a uno, lo ganado y dónde. |
| Aprender los sonidos | menú principal | Grupos y sonidos de `catalogo_sonidos()`; aceptar suena, la ayuda explica. |
| Practicar los controles | menú principal | Dice qué hace cada tecla o botón sin ejecutarlo; se sale con la pausa dos veces. |
| Opciones | menú principal, pausa | Sonido, Voz y braille, Movimiento, Mando, Teclado, Estilo e idioma, Pantalla. |
| Captura de tecla | Opciones, Teclado | «Pulsa la tecla que quieres usar» (`CapturaTecla` de `app/entrada`). |
| Ayuda | acción `ayuda`, menú principal, pausa | Una línea por acción con su tecla o su botón. |
| Acerca de | menú principal | Versión, autor, licencia, enlaces, la invitación al café, OpenAL Soft y BASS. |
| Conectar con mi profesor | menú principal | Buscar salas, escribir la dirección o este mismo ordenador; después, el código. |
| Menú de edición, Saltar a un lugar | modo recorrido (F4, F8, panel táctil, pausa) | Peticiones al Estudio y saltos. |

### Añadir una pantalla

1. Si es una lista de opciones, no hace falta una clase: una función `abrir_algo(app)` que construya un `Menu(app, titulo, opciones)` y llame a `app.abrir(menu)`. `opciones` puede ser una lista o una función que la devuelva (se vuelve a pedir cada vez que el menú vuelve a quedar arriba, así los textos con valores están siempre al día).
2. Cada `Opcion(texto, accion=…, ajuste=…, ayuda=…)`: `accion` al aceptar; `ajuste(delta)` con izquierda y derecha (si devuelve `True`, el menú no repite el valor: ya ha hablado ella); `ayuda` con F1 o el botón de ayuda. Toda opción debe tener ayuda.
3. Si no es un menú, herede de `Pantalla` y redefina lo que necesite: `contexto` (`menu` o `juego`: con qué mapa se traducen teclas y botones), `al_entrar` (decir dónde se está), `accion`, `tecla` (solo para lo que no es una acción), `actualizar`, `al_salir`, `texto_ayuda`, `titulo_visible` y `lineas` (parte visual) o `dibujar`.
4. Hable con `app.decir(texto, interrumpir, canal)` o `app.decir_menu(texto)`; suene con `app.sonar("interfaz/…")`. No llame a la voz ni al motor de sonido directamente.
5. Todo texto con `_()`. Si la pantalla atiende una tecla a mano, márquela con `# atajo: F5 (qué hace)` y documéntela en `data/docs/teclas.md`.
6. Añada su prueba en `tests/test_reproductor_*.py`; la prueba general que recorre todos los menús la visitará sola si se llega a ella desde el menú principal.

## La partida (`PantallaJuego`)

Es la misma pantalla para una actividad, la exploración libre (sin actividad), el tutorial (actividad propia, sin grabación) y el modo recorrido (sin actividad ni grabación).

- **Ajustes.** Base: las preferencias del alumno (`Aplicacion.ajustes_juego()`). Encima, `actividad.ajustes(base)`. Encima, lo que el profesor fija en vivo (`ayudas`). Cuando el alumno cambia una opción a mitad de partida se recalcula todo en ese orden: no puede saltarse lo que fijó el profesional.
- **Pausas.** Un conjunto de motivos (`menu`, `profesor`). Con el primero se pausan la sesión, la grabadora y los sonidos del mundo; al quitar el último, siguen. Cualquier pantalla abierta encima del juego lo pausa.
- **Grabación.** `Grabadora` con el alias, el entorno, la actividad y el modo; `muestra` en cada fotograma (la grabadora guarda cuatro por segundo), todos los `EvRegistro`, las pausas, las intervenciones del profesor (sin el texto de los mensajes), las marcas, las puntuaciones y el resultado. La exploración libre se graba como `exploracion`, modo `practica`. El fichero se escribe al salir de la pantalla de fin, al abandonar, al reiniciar y al cerrar el reproductor a mitad.
- **Fin.** Actividad terminada → pantalla de fin. Abandonada o exploración libre → resumen corto y menú principal. Tutorial → frase final y menú principal. Recorrido → se cierra el reproductor.
- **Parte visual.** `plano.dibujar` (F5 la quita y la pone; F6, pantalla en negro). Nunca hay información solo visual.
- **Complementos que faltan.** Se dice una vez al empezar; los objetos siguen ahí como cajas con sus medidas.

### Tutorial

`pantallas/tutorial.py` construye por código dos habitaciones con una puerta cerrada, una mesa y un premio, y una `ActividadTutorial` con nueve pasos: avanzar, chocar, girar, rodear, dónde estoy, alrededor, bastón sonoro, abrir la puerta y encontrar el premio. Cada paso se da por hecho mirando contadores del motor; «objetivo» repite el paso y «pista» dice hacia dónde ir. Sus frases nombran la tecla o el botón reales (`Entrada.control_de`).

## Alumno y perfil

El reproductor solo conoce un **alias**. `Perfil` guarda en `data/config/alumnos/<alias>.json`:

- `preferencias`: las claves de `ajustes.PREFERENCIAS_JUEGO` que el alumno ha cambiado (movimiento, direcciones, unidad, estilo y detalle);
- `premios`: tipo, nombre, entorno, actividad y fecha;
- `actividades`: veces jugada, veces completada y mejor marca de estrellas, por `entorno/actividad`;
- `ultima`: ruta del paquete y actividad, para «Continuar»;
- `tutorial_hecho`;
- `niveles`: el nivel de ayudas con el que empieza cada actividad, por `entorno_id/actividad_id`. `PantallaJuego` lo pide con `Aplicacion.nivel_actividad` al crear la actividad y lo devuelve con `Aplicacion.anotar_nivel(…, nivel_siguiente)` al terminarla;
- `ficha`: lo último que llegó de la ficha del Estudio por la sala (orden `alumno`, ver [supervision.md](supervision.md)): `ajustes`, `lista` (lista de trabajo), `niveles` (los últimos vistos de la ficha) y `recibida`. Sirve también los días sin sala.

**Quién manda en las preferencias de juego** (`Aplicacion.preferencia(clave)`): la ficha del Estudio; si no dice nada, el perfil del alumno; si tampoco, la configuración compartida (los valores de serie que pone el profesional en Preferencias). `Aplicacion.ajustes_juego()` construye `AjustesJuego` con esa capa, y la pantalla de opciones enseña y cambia lo mismo. Si el alumno cambia él mismo una opción que fijaba la ficha, vale la suya hasta que llegue otra ficha.

**Por qué las preferencias del alumno no van a `config.json`**: el fichero lo escriben también el Estudio y los demás alumnos del equipo. Antes, al elegir alias se volcaban ahí, y así pisaban los valores de serie del profesional y se heredaban de un alumno a otro. Ahora, con alias, solo se escriben en su perfil; en la configuración solo se apunta `juego.alias`. Sin alias (sin perfil), las opciones de juego siguen yendo a la configuración, como preferencia del equipo.

**Lista de trabajo**: «Elegir entorno» empieza por «Lo que te ha puesto tu profesor» si hay alguna; dentro de un entorno, las actividades asignadas van primero («…, te la ha puesto tu profesor»); «Continuar», si aún no se ha jugado nada, empieza la primera asignada. El paquete se busca entre los entornos del equipo por el id del entorno y, si no, por el nombre del fichero.

Ni el alias ni el nombre del fichero van al registro.

## Opciones en caliente

Las pantallas de opciones solo escriben preferencias con `Aplicacion.establecer(clave, valor)`. La aplicación está suscrita a la configuración compartida (`config.json`, el mismo fichero que usa el Estudio) y aplica cada cambio al momento, lo haga quien lo haga:

| Clave | Efecto inmediato |
|---|---|
| `sonido.motor` | `Aplicacion.cambiar_motor`: cierra el motor, abre el nuevo y, si no arranca, vuelve al anterior, repone la preferencia y lo dice. |
| `sonido.perfil_hrtf`, `sonido.modo_salida`, `sonido.dispositivo` | `poner_cabeza`, `poner_salida`, `cambiar_dispositivo` del motor. |
| `sonido.volumen_<bus>` | `motor.volumen_bus`. |
| `sonido.paquete` | Lo sigue `paquetes.conectar(banco)`; el presentador recarga el motor (el menú lo fuerza para oírlo ya). |
| `sonido.proteccion_auditiva`, `sonido.refuerzo_detras` | `motor.configurar`. |
| `sonido.seguimiento_cabeza` | Arranca o para `Cabeza`. |
| `voz.*` | `Voz.configurar`; `voz.detalle` recalcula los ajustes de la partida. |
| `juego.*` | Recalcula los ajustes de la partida (`Sesion.aplicar_ajustes`). |
| `mando.*` | Opciones de `Mandos` y de la vibración. |
| `general.idioma` | `i18n.cambiar_idioma`. |
| `general.alto_contraste`, `general.tamano_texto`, `juego.ver_plano`, `juego.pantalla_negra` | Se leen al dibujar. |

Las preferencias de juego del alumno no pasan por la configuración (ver «Alumno y perfil»): `establecer` las apunta en su perfil y llama al mismo manejador (`_config_cambiada`) para aplicarlas; lo mismo al cambiar de alumno o al llegar su ficha.

**Lo que cambia otro proceso.** El Estudio escribe el mismo `config.json`. `Configuracion.recargar()` lo vuelve a leer y avisa de cada clave cambiada a los suscriptores de siempre (los de esta tabla y `paquetes.conectar`), así que se aplica igual que un cambio hecho aquí. El reproductor relee (`Aplicacion.releer_configuracion`):

- con sala, al recibir la orden `releer_configuracion`, que el Estudio envía tras aceptar o aplicar Preferencias;
- sin sala, cada vez que se vuelve al menú principal (`volver_al_menu` y al quedar arriba el menú principal). Si el fichero no ha cambiado, no cuesta más que mirar su fecha.

Y ninguno pisa al otro al guardar: si el fichero ha cambiado en disco desde que se leyó, `Configuracion.guardar` toma lo del otro proceso y escribe encima solo las claves cambiadas aquí (ver `app/core/configuracion.py`).

Claves que añadió el reproductor a `app/core/configuracion.py`: `juego.ver_plano`, `juego.pantalla_negra`, `juego.posicion_menu`, `juego.alias` y `supervision.ultima_sala`. Los mapas reasignados se guardan en `teclado.mapa` y `mando.mapa` con el formato de `MapaTeclado.a_dict()` y `MapaMando.a_dict()`.

## Supervisión

`Enlace` envuelve a `ClienteSupervision` (que vive en su hilo y nunca bloquea):

- **Envía**: el estado cinco veces por segundo (posición, descripción de `Sesion.estado()`, qué tiene delante, contadores con el objetivo y lo que da `actividad.estado()`), cada `EvRegistro`, la voz que oye el alumno (gancho `Voz.al_hablar`, con su canal) y el fin.
- **Aplica**: `pausa`, `reanudar`, `recolocar`, `mensaje` (canal `profesional`, queda en el historial; además se le pasa a `actividad.orden_profesional` y se presentan sus eventos que no son voz, para que una visita narrada lo cuente), `pista`, `ayudas` y `premio` (primero `actividad.orden_profesional`; si no hay actividad, de forma genérica), `marca`, `reiniciar` y `terminar`.
- **Atiende la aplicación, haya partida o no**: `alumno` (`Aplicacion.recibir_ficha`: ajustes, lista de trabajo y niveles de la ficha; la partida en curso se recalcula) y `releer_configuracion` (`Aplicacion.releer_configuracion`). No se apuntan en la sesión grabada.
- **Dice**: conectado, conexión perdida («puedes seguir jugando»), recuperada, y cada motivo de rechazo en palabras llanas.
- **Huella**: la primera vez, en una conexión cifrada, dice la huella corta para compararla de viva voz; si cambia, no se ha enviado nada y abre un menú con «No conectar» primero.

Si la sala no está o se cae, se sigue jugando y el cliente reconecta solo.

### Modo recorrido

`--recorrido` abre la pantalla de juego sin actividad ni grabación, con toda la información y todas las ayudas. Además:

- **Menú de edición** (F4, el panel táctil del mando o la pausa): envía una `peticion` con el punto y el rumbo actuales y dice la `respuesta` cuando llega.

  | Opción | `accion` | `datos` |
  |---|---|---|
  | Colocar un objeto aquí (del catálogo, ver abajo) | `colocar_aqui` | `clase: "objeto"`, `objeto: "<complemento>/<id>"`, `nombre` |
  | Poner un premio aquí | `colocar_aqui` | `clase: "premio"`, `nombre` |
  | Poner aquí el inicio | `colocar_aqui` | `clase: "inicio"` |
  | Marcar este punto | `marcar_punto` | `nombre` |
  | Medir desde aquí | `medir_desde_aqui` | `fase: "desde"` |
  | Medir hasta aquí | `medir_desde_aqui` | `fase: "hasta"`, `distancia_m` (línea recta, que el reproductor ya dice) |

- **Catálogo** («Colocar un objeto aquí»): el catálogo de complementos cargado en el propio reproductor, con más de dos mil objetos, nunca como lista plana. El menú ofrece «Los que ya hay en este entorno», «Buscar por nombre» (una `EntradaTexto`; vale cualquier palabra del nombre, la categoría, las etiquetas o la descripción, sin tildes; se enseñan como mucho 40 resultados y, si hay más, la primera opción vuelve a la búsqueda para afinarla), «Otra vez» (el último colocado) y un submenú por complemento → categoría → subcategoría (las categorías de más de 15 objetos se abren por subcategorías). Al elegir, se quitan sin hablar los menús del catálogo y se envía la petición.
- **Recarga del entorno**: cuando el Estudio contesta con `datos.recargar = true`, o envía la orden `reiniciar`, el reproductor vuelve a leer el paquete del disco y sigue en el mismo punto.
- **Modo fantasma** (F7): los pasos no chocan; los giros siguen igual.
- **Saltar a un lugar** (F8): lista de plantas y lugares.

## Accesibilidad

- Todo se dice: títulos, opciones, valores, ayuda de cada opción, errores y cambios de conexión. Lo último dicho se escribe además abajo en la ventana.
- Menús: flechas o cruceta, Inicio y Fin, salto por inicial (sin distinguir tildes), aceptar y atrás, izquierda y derecha para los valores, posición «3 de 9» opcional y sonidos de mover, elegir, atrás, borde y ajuste.
- Los nombres de botón son los del mando conectado; con mando, las frases que nombran teclas se convierten (`Entrada.textos`).
- Nada depende del color: la opción elegida lleva un signo, los objetos su letra, los premios un rombo y el alumno una flecha.
- Los mensajes del profesor van por su canal (`profesional`) y quedan en el historial.
- El estilo cambia el tono de las frases, no el contenido; el adulto es sobrio.

## Probar

```
.venv\Scripts\python.exe -m pytest tests -q -k reproductor
```

`tests/test_reproductor_comun.py` tiene el `Robot` y las fixtures (se importan en cada fichero de pruebas, porque no se toca `conftest.py`):

```python
from .test_reproductor_comun import Robot, app, robot, actividades, sin_navegador  # noqa: F401

def test_algo(robot: Robot):
	robot.elegir("Opciones")            # va a la opción que empieza así y la acepta
	robot.ajustar("Volumen general", -1)
	robot.accion("menu_atras")          # una acción
	robot.tecla(pygame.K_F1)            # una tecla, por el camino real
	robot.esperar(10)                   # fotogramas
	assert "Volumen" in robot.dicho()   # lo que se habría dicho
```

- `Aplicacion(pruebas=True)`: controladores «dummy» de SDL, motor de sonido nulo (los demás, en memoria), `VozFalsa` y sin tocar los mandos reales.
- `Aplicacion.inyectar(accion)`, `tecla(codigo, mod, unicode)`, `evento(evento_pygame)` y `avanzar(fotogramas, dt)` manejan la aplicación sin teclado ni reloj.
- Un mando se simula con `app.entrada.mandos.conectar(objeto_con_name_y_rumble, id)` y eventos `CONTROLLERBUTTONDOWN` o `CONTROLLERAXISMOTION`.
- Las actividades se sustituyen por un doble (`actividades`), para probar el reproductor y no las reglas de cada tipo.
- La supervisión se prueba contra una `Sala` de verdad en `127.0.0.1`.
- `tests/test_integracion_proceso_real.py` lanza el reproductor como proceso hijo de verdad (`APP_SIN_VENTANA=1` y un guion) desde «Probar ahora», «Empezar sesión», «Recorrer el entorno» y «Colocar recorriendo»; `tests/test_integracion_recorrido_catalogo.py` recorre el catálogo del modo recorrido hasta que el Estudio coloca el objeto.

No se puede probar aquí, y hay que hacerlo a mano antes de publicar: un lector de pantalla real (NVDA, JAWS) y una línea braille, un mando físico de Xbox y otro de PlayStation (nombres, vibración, conexión en caliente), el sonido al oído con cada motor y el cambio en caliente con tarjeta de sonido, y la supervisión entre dos equipos de una red.
