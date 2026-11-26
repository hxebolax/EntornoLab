# Entrada: acciones, teclado y mando

El motor no sabe de teclas ni de botones: recibe **acciones con nombre**. El paquete `app/entrada` traduce los eventos de pygame a esas acciones.

- `acciones.py`: la tabla de acciones, con nombre visible, ayuda y contexto.
- `teclado.py`: mapa de teclas, reasignación por intercambio y pantalla lógica de captura.
- `mando.py`: mandos de Xbox y PlayStation, palancas, gatillos, vibración y frases con nombres de botón.
- `entrada.py`: la clase `Entrada`, que une teclado y mando.

Nada de esto lee ni escribe la configuración: los mapas y las opciones entran y salen como diccionarios.

## Uso desde el reproductor

```python
entrada = Entrada(mapa_teclado, mapa_mando, opciones)      # los tres, dict o None
contexto = "menu" if hay_menu_abierto else "juego"

for evento in pygame.event.get():
	for accion, pulsada in entrada.traducir(evento, contexto):
		...                                                # sesion.orden(accion) al pulsar
for accion, pulsada in entrada.actualizar(dt, contexto):   # palancas convertidas en acciones
	...
avance, lateral, giro, mirada = entrada.ejes(contexto)     # para Sesion.analogico
for frase in entrada.avisos():                             # «Mando conectado: ...»
	voz.decir(frase)
```

- Cada pulsación da `(accion, True)` y, al soltar, `(accion, False)`. Las acciones de un toque que salen de una palanca llegan como el par completo en la misma lista.
- `acciones.es_mantenida(accion)` dice si a la sesión le interesa cuándo se suelta (andar, girar, pasos laterales, bastón).
- Al cambiar de contexto, o si la ventana pierde el foco, lo que estuviera pulsado se suelta solo.
- `entrada.a_dict()` devuelve `{"teclado": ..., "mando": ..., "opciones": ...}` para guardarlo; `entrada.cargar(datos)` lo repone.

## Acciones

Contextos: `juego` (recorriendo el entorno) y `menu` (menús hablados y pausa).

| Acción | Nombre visible | Contexto | Mantenida |
|---|---|---|---|
| `avanzar` | Avanzar | juego | sí |
| `retroceder` | Retroceder | juego | sí |
| `girar_izquierda`, `girar_derecha` | Girar a la izquierda, a la derecha | juego | sí |
| `paso_izquierda`, `paso_derecha` | Paso lateral a la izquierda, a la derecha | juego | sí |
| `media_vuelta` | Media vuelta | juego | |
| `interactuar` | Interactuar | juego | |
| `donde_estoy` | Dónde estoy | juego | |
| `mirar_delante`, `mirar_izquierda`, `mirar_detras`, `mirar_derecha` | Mirar delante, a la izquierda, detrás, a la derecha | juego | |
| `alrededor` | Alrededor | juego | |
| `cercano_siguiente`, `cercano_anterior` | Cercano siguiente, anterior | juego | |
| `descubiertos` | Lugares descubiertos | juego | |
| `brujula` | Brújula | juego | |
| `sonda` | Bastón sonoro | juego | sí |
| `eco` | Eco | juego | |
| `objetivo` | Objetivo | juego | |
| `pista` | Pista | juego | |
| `confirmar` | Confirmar | juego | |
| `repetir` | Repetir | juego y menú | |
| `historial_anterior`, `historial_siguiente` | Mensaje anterior, siguiente | juego y menú | |
| `callar` | Callar la voz | juego y menú | |
| `volver_inicio` | Volver al inicio | juego | |
| `ayuda` | Ayuda | juego y menú | |
| `pausa` | Pausa y menú | juego | |
| `menu_arriba`, `menu_abajo` | Opción anterior, siguiente | menú | |
| `menu_izquierda`, `menu_derecha` | Disminuir, aumentar | menú | |
| `menu_aceptar`, `menu_atras` | Aceptar, atrás | menú | |

Los identificadores no se traducen (se guardan en los mapas). El nombre y la ayuda se marcan con `N_` y se traducen al pedirlos: `acciones.nombre_accion(id)`, `acciones.ayuda_accion(id)`. `nada` significa «sin asignar» (solo en el mando).

## Teclado de serie

Sigue el apartado 12.4 del informe; lo que el informe no fijaba va marcado con (propuesta).

Jugando:

| Tecla | Acción |
|---|---|
| Flecha arriba, flecha abajo | avanzar, retroceder |
| Flecha izquierda, flecha derecha | girar |
| Mayúsculas con flecha izquierda o derecha | paso lateral |
| U | media vuelta (propuesta) |
| Intro, Intro numérico, Espacio | interactuar |
| C | dónde estoy |
| W, A, S, D | mirar delante, izquierda, detrás, derecha |
| Q | alrededor (propuesta) |
| Tabulador, Mayúsculas Tabulador | cercano siguiente, anterior |
| L | lugares descubiertos (propuesta) |
| K | brújula |
| B | bastón sonoro |
| E | eco (propuesta) |
| O | objetivo (propuesta) |
| P | pista (propuesta) |
| M | confirmar (propuesta) |
| F2 | repetir |
| F3, Mayúsculas F3 | mensaje anterior, siguiente del historial |
| Retroceder página, Avanzar página | mensaje anterior, siguiente (propuesta) |
| Control (cualquiera de los dos) | callar la voz |
| Inicio | volver al inicio (propuesta) |
| F1 | ayuda |
| Escape | pausa y menú |

En los menús: flechas para moverse y ajustar; Intro o Espacio, aceptar; Escape o Retroceso, atrás; F1, ayuda; F2, repetir; F3 y las teclas de página, historial; Control, callar.

Detalles:

- Si una combinación con Mayúsculas o Control no tiene acción, vale la tecla sola (Mayúsculas más flecha arriba sigue andando).
- Alt con otra tecla se ignora: es del sistema.
- Al soltar una tecla se suelta la acción que se pulsó, aunque ya no esté Mayúsculas.

### Reasignar teclas

`MapaTeclado.cambiar(contexto, accion, nueva, vieja=None)` **intercambia**: la acción que estaba en `nueva` pasa a la tecla antigua, así ninguna se queda sin tecla. Devuelve un `Cambio(hecho, frase, combinacion, desplazada)` con la frase para decir.

- Teclas fijas, que ni se cambian ni sirven de destino: Escape, Intro, Intro numérico, F1, las dos Mayúsculas (solo modificador), Alt, Windows, bloqueos e Imprimir pantalla.
- Las acciones que solo tienen tecla fija (pausa, ayuda) no se reasignan.
- `MapaTeclado.cambios()` da frases con lo cambiado; `restablecer()` vuelve al mapa de serie.

`CapturaTecla(mapa, contexto, accion)` es la pantalla de «pulsa la tecla que quieres usar», sin dibujar ni hablar:

1. El reproductor dice `captura.al_entrar()`.
2. Le pasa cada evento a `captura.evento(ev)`; si devuelve un `ResultadoCaptura`, dice su `frase`.
3. Cuando `captura.terminada` es cierto, cierra la pantalla y guarda `mapa.a_dict()`.

Estados: `asignada`, `rechazada` (tecla reservada: se sigue esperando) y `cancelada` (Escape). Mayúsculas sola se ignora, a la espera de la tecla que la acompaña; Control solo se asigna al soltarlo, y con otra tecla forma una combinación.

### Formato del mapa de teclado

```json
{
  "juego": {"arriba": "avanzar", "mayus+izquierda": "paso_izquierda", "c": "donde_estoy"},
  "menu": {"arriba": "menu_arriba", "intro": "menu_aceptar"}
}
```

Clave: combinación con nombres propios y estables (`mayus+`, `ctrl+`, y la tecla: letras, cifras, `f1` a `f12`, `arriba`, `abajo`, `izquierda`, `derecha`, `espacio`, `intro`, `tabulador`, `escape`, `retroceso`, `inicio`, `fin`, `repag`, `avpag`, `insertar`, `suprimir`, `coma`, `punto`, `guion`, `control_izquierdo`, `control_derecho`, `numerico_0` a `numerico_9`; cualquier otra, `k` más su código). Valor: el identificador de la acción.

Al cargar se descartan (con aviso en el registro) las teclas y acciones desconocidas, se reponen las teclas fijas y se completan con su tecla de serie las acciones que falten, si esa tecla está libre.

## Mando de serie

Se usa `pygame._sdl2.controller`, que da la misma disposición a todos los mandos. La familia (Xbox o PlayStation) se deduce del nombre del mando y solo cambia cómo se **dicen** los botones.

| Botón (identificador) | Xbox | PlayStation | Jugando | Con el modificador | En un menú |
|---|---|---|---|---|---|
| `a` | A | Equis | interactuar | pista | aceptar |
| `b` | B | Círculo | callar la voz | volver al inicio | atrás |
| `x` | X | Cuadrado | dónde estoy | lugares descubiertos | repetir |
| `y` | Y | Triángulo | mirar delante | confirmar | ayuda |
| `lb` | LB | L1 | girar a la izquierda | paso lateral a la izquierda | mensaje anterior |
| `rb` | RB | R1 | girar a la derecha | paso lateral a la derecha | mensaje siguiente |
| `lt` | gatillo izquierdo | L2 | **modificador** | | |
| `rt` | gatillo derecho | R2 | bastón sonoro | eco | |
| `l3` | pulsar la palanca izquierda | L3 | alrededor | brújula | |
| `r3` | pulsar la palanca derecha | R3 | repetir | objetivo | |
| `arriba` | cruceta arriba | cruceta arriba | cercano anterior | repetir | opción anterior |
| `abajo` | cruceta abajo | cruceta abajo | cercano siguiente | media vuelta | opción siguiente |
| `izquierda` | cruceta izquierda | cruceta izquierda | brújula | mensaje anterior | disminuir |
| `derecha` | cruceta derecha | cruceta derecha | objetivo | mensaje siguiente | aumentar |
| `vista` | Vista | Crear o Share | ayuda | ayuda | ayuda |
| `menu` | Menú | Options | pausa | pausa | atrás |
| `panel`, `misc` | panel táctil, Compartir | panel táctil, micrófono | sin asignar | sin asignar | sin asignar |

Decisiones sobre lo que el informe dejaba abierto:

- **B o Círculo jugando** («atrás o cancelar»): calla la voz, que es cancelar lo que se está diciendo. En los menús es «atrás».
- **Cruceta**: arriba y abajo recorren la lista de lo cercano; izquierda y derecha dan la brújula y el objetivo.
- **Segunda capa** (gatillo izquierdo mantenido): lo que no cabe en la primera. Entre las dos capas y las palancas, todas las acciones del juego se pueden hacer con el mando (lo comprueba una prueba).
- **Confirmar** («ya he llegado», «es hacia ahí», «esta respuesta»): M en el teclado y gatillo izquierdo más Y (o Triángulo) en el mando. Es una acción aparte de `interactuar` para que en un examen no dependa de lo que haya al alcance de la mano. Antes, esa combinación del mando era «alrededor», que sigue en pulsar la palanca izquierda. Quien ya tenía guardado un mapa de mando conserva el suyo (cada botón guardado manda sobre el de serie) y puede poner «confirmar» en Opciones, Mando.

### Confirmar en la partida

La pantalla de juego atiende `confirmar` llamando a `actividad.confirmar(sesion)` y presenta lo que devuelva; si no hay nada que confirmar, lo dice. Si la actividad tiene una pregunta con opciones sin contestar (`actividad.estado()["pregunta"]`), `confirmar` abre el menú de respuestas en vez de confirmar (ver [actividades.md](actividades.md), «Exámenes»).

Palancas:

- **Izquierda**: adelante y atrás, avanzar; a los lados, girar (opción `palanca_izquierda = "giro"`) o paso lateral (`"lateral"`). Con el modificador mantenido, a los lados es siempre paso lateral. Va por `Entrada.ejes()`, no como acciones.
- **Derecha** (`palanca_derecha`):
  - `"mirar"` (de serie): al empujarla hacia un lado se emite una vez `mirar_delante`, `mirar_derecha`, `mirar_detras` o `mirar_izquierda`; no se repite hasta que vuelve al centro o cambia de sector. `mirada` es `None`.
  - `"analogica"`: no emite acciones; `ejes()` devuelve `mirada = (x, y)`, con x a la derecha e y hacia delante, de −1 a 1.
  - `"giro"`: a los lados gira.
- En un menú, la palanca izquierda mueve el cursor, con repetición al mantenerla; `ejes()` da todo a cero.

Ejes y gatillos:

- Cada eje se normaliza a ±1 dividiendo por 32767.
- Zona muerta circular (`zona_muerta`, 0,25 de serie), reescalada para que el movimiento empiece en cero al salir de ella.
- Los gatillos son botones con histéresis: se pulsan al pasar de `gatillo_pulsar` (0,3) y se sueltan al bajar de `gatillo_soltar` (0,15).

Opciones (`app.entrada.mando.OPCIONES_POR_DEFECTO`; se sanean con `sanear_opciones`):

| Clave | De serie | Qué es |
|---|---|---|
| `zona_muerta` | 0.25 | 0 a 0,95 |
| `gatillo_pulsar`, `gatillo_soltar` | 0.3, 0.15 | umbrales de los gatillos |
| `umbral_palanca` | 0.6 | inclinación que cuenta como pulsación (menús y mirar) |
| `repeticion_inicial`, `repeticion` | 0.45, 0.3 | segundos de la repetición en menús |
| `vibracion` | true | desactiva toda la vibración |
| `fuerza_vibracion` | 1.0 | 0 a 1; multiplica cada vibración |
| `palanca_izquierda` | "giro" | o "lateral" |
| `palanca_derecha` | "mirar" | o "analogica", o "giro" |
| `decir_botones` | true | con un mando conectado, las frases nombran botones |

Conexión en caliente: `Mandos.evento` atiende `CONTROLLERDEVICEADDED` y `CONTROLLERDEVICEREMOVED`. El aviso («Mando conectado: nombre.», «Mando desconectado. Puedes seguir con el teclado.») no se dice aquí: queda en `Entrada.avisos()`. Al desconectar se sueltan las acciones que el mando tuviera pulsadas. Con varios mandos, todos valen y la familia es la del último usado.

Vibración: `Entrada.vibrar(grave, agudo, ms)`, con los dos motores de 0 a 1. El vocabulario con nombre (choque, premio cerca...) está en `app/audio/haptica.py`.

### Reasignar botones

`MapaMando.cambiar(capa, boton, accion, familia)` pone la acción en el botón; si otro botón de esa capa ya la tenía, se **intercambian**. `accion = "nada"` deja el botón sin asignar. Capas: `juego`, `juego_2` (con el modificador) y `menu`.

- No se cambian: `menu` jugando (pausa), `a` y `b` en los menús, ni el botón modificador.
- `MapaMando.cambiar_modificador(boton)` elige otro botón de segunda función.
- `MapaMando.reasignables(capa)`, `cambios(familia)` y `restablecer()` sirven a la pantalla de botones.

### Formato del mapa de mando

```json
{
  "modificador": "lt",
  "juego": {"a": "interactuar", "r3": "nada"},
  "juego_2": {"a": "pista"},
  "menu": {"a": "menu_aceptar"}
}
```

Un botón que falta toma su valor de serie; `nada` lo deja sin asignar. Botones y acciones desconocidos se descartan.

## Decir botones en vez de teclas

`Entrada.textos(frase, contexto)` devuelve la frase con las teclas cambiadas por los botones del mando conectado: «Pulsa C para saber dónde estás» pasa a «Pulsa el botón X…» o «Pulsa el botón Cuadrado…». Una segunda función se dice con su modificador («el gatillo izquierdo más el botón A»). Lo que no tiene botón se deja como está, porque el teclado sigue funcionando.

- Sin mando, o con `decir_botones` desactivado, la frase no cambia.
- Reconoce «pulsa X», «con la tecla X», «usa X», «la tecla X», «… y X para …» y «las flechas». Las teclas deben ir con mayúscula inicial (o ser «flecha …»), para no confundir «con espacio de sobra» con la tecla Espacio.
- Solo funciona con el texto en español (idioma de origen); en otro idioma la frase se devuelve igual.

Para construir frases nuevas es más seguro no escribir la tecla a mano: `Entrada.control_de(accion, contexto)` devuelve el botón o la tecla que toca, y `Entrada.ayuda(contexto)` la lista completa.

## Pruebas

`tests/test_entrada_teclado.py` y `tests/test_entrada_mando.py`. No hace falta mando: los eventos se construyen con `pygame.event.Event` y `Mandos.conectar(mando, identificador)` acepta cualquier objeto con `name` y, si vibra, `rumble`.
