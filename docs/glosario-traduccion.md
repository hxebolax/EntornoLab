# Glosario de traducción al inglés

Términos fijos de la traducción inglesa de EntornoLab (`data/locales/en/LC_MESSAGES/entornolab.po`) y de la documentación en inglés (`data/docs/en`, `README_en.md`). Úselos siempre igual: una persona ciega que aprende la aplicación con el lector de pantalla se orienta por las palabras, y un mismo concepto con dos nombres la confunde.

## Criterios

- Inglés internacional con ortografía estadounidense (color, center, catalog, gray).
- Frases cortas y claras, pensadas para oírse con un lector de pantalla. Sin abreviaturas raras.
- Mayúscula solo al principio de etiquetas, títulos y menús («Save as», no «Save As»), como en las guías de Microsoft.
- Se conservan exactamente los marcadores (`{nombre}`, `%s`, `%d`, `%(x)s`), los saltos de línea y los espacios del principio y del final.
- Se conserva un `&` por etiqueta. La letra elegida no se repite en la misma ventana ni dentro del mismo menú, ni coincide con la de un menú de la barra en la ventana principal.
- El atajo que sigue al tabulador de un menú (`\tCtrl+Shift+S`) se copia tal cual: ya está en inglés, que es como lo entiende wxWidgets.
- En el texto corrido los nombres de las teclas van en inglés: Enter, Escape, Delete, Shift, Backspace, Space, Home, End, Page Up, Page Down, arrow keys (flechas), Up Arrow, Down Arrow, Left Arrow, Right Arrow, Tab, Ctrl, Alt.
- Se tutea a la persona usuaria («you»), igual que en español.

## Nombres propios del producto

| Español | Inglés |
|---|---|
| EntornoLab | EntornoLab (no se traduce) |
| Estudio (el editor) | Studio |
| Jugar (el reproductor) | Play |
| reproductor | player |

## Barra de menús de la ventana principal

Letras de acceso fijas. Los controles de la ventana principal no pueden usar F, E, I, V, S, P, T ni H.

| Español | Inglés |
|---|---|
| &Archivo | &File |
| &Editar | &Edit |
| &Insertar | &Insert |
| &Ver | &View |
| A&lumnos | &Students |
| &Supervisión | Su&pervision |
| &Herramientas | &Tools |
| Ay&uda | &Help |

## Entorno y edición

| Español | Inglés |
|---|---|
| entorno | environment |
| planta (de un edificio o de un exterior) | level |
| plano | map |
| plano gráfico | visual map |
| plano táctil, lámina en relieve | tactile map, raised-line drawing |
| elemento | item |
| espacio | space |
| habitación | room |
| pared suelta | freestanding wall |
| abertura | opening |
| hueco (sin puerta) | doorway |
| portal (de un edificio) | entrance |
| escalera | stairs |
| rampa | ramp |
| ascensor | elevator |
| objeto del catálogo | catalog object |
| fuente de sonido | sound source |
| referencia, punto de referencia | landmark |
| punto de interés | point of interest |
| zona de suelo | surface zone |
| punto de inicio | start point |
| exterior | outdoor area |
| complemento | add-on |
| catálogo en línea | online catalog |
| comprobar el entorno | check the environment |
| recorrer el entorno, modo recorrido | walk through the environment, walkthrough mode |
| deshacer / rehacer | undo / redo |
| cuadrícula | grid |
| árbol del entorno | environment tree |

## Orientación y movilidad

| Español | Inglés |
|---|---|
| orientación y movilidad (OyM) | orientation and mobility (O&M) |
| técnico/a de rehabilitación, profesional | O&M instructor, instructor |
| alumno, alumna | student |
| bastón (largo) | (long) cane |
| perro guía | guide dog |
| rastreo | trailing |
| línea guía, línea de dirección | shoreline |
| encuadrarse, encuadre | square off, squaring off |
| direcciones horarias («a las 3») | clock directions («at 3 o'clock») |
| pista (sensorial: auditiva, táctil, olfativa) | clue (auditory, tactile, olfactory clue) |
| pista (ayuda en una actividad) | hint |
| orientarse | orient yourself |
| rumbo | heading |
| ecolocalización | echolocation |
| acera | sidewalk |
| calzada | roadway |
| bordillo | curb |
| paso de peatones | crosswalk |
| semáforo | traffic light |
| semáforo sonoro, acústico | accessible pedestrian signal (APS) |
| señal para peatones | pedestrian signal |
| pavimento táctil, podotáctil | tactile paving |
| cruce | intersection |
| manzana | block |
| parada (de autobús, tranvía, taxi) | stop (bus, tram, taxi stop) |
| orientación, búsqueda del camino | wayfinding |

## Actividades y seguimiento

| Español | Inglés |
|---|---|
| actividad | activity |
| objetivo | goal |
| ayuda (en una actividad) | help |
| premio, recompensa | reward |
| estrella / medalla / trofeo | star / medal / trophy |
| sesión | session |
| ficha del alumno | student record |
| informe | report |
| cuaderno de evaluación real | real-world assessment log |
| sala de supervisión | supervision room |
| supervisión en vivo | live supervision |
| contraseña | password |
| examen / práctica / juego | test / practice / game |
| prueba (de un examen) | trial |
| baliza (sonora) | (sound) beacon |
| bastón sonoro | sound cane |
| choque | bump (en la voz), collision (en los informes) |
| ayuda pedida | help request |
| nivel de ayuda (cuaderno) | level of assistance |
| ayudas de movilidad | mobility aids |
| invitado (alias del que juega sin ficha) | guest |
| profesor, profesional (dicho al alumno) | your instructor |

## Calle y mando

| Español | Inglés |
|---|---|
| pulsador (del semáforo) | push button |
| isleta | median island |
| marquesina | shelter |
| mando | controller |
| cruceta | D-pad |
| palanca | stick |
| panel táctil | touchpad |

## Números y teclas con dos sentidos

- Los decimales se escriben con punto en inglés («3.5 meters»): el código usa `separador_decimal()`. Los campos aceptan coma y punto.
- «Inicio» es Home cuando es una tecla (`pgettext("tecla", "Inicio")`) y Start cuando es la hora de comienzo de una sesión.
- «Mayúsculas» es Shift cuando es una tecla (`pgettext("tecla", "Mayúsculas")`) y Uppercase en la rueda de letras.

## Sonido y voz

| Español | Inglés |
|---|---|
| paquete de sonidos | sound pack |
| voz, síntesis de voz | speech, speech synthesizer |
| lector de pantalla | screen reader |
| sonido 3D, audio binaural | 3D sound, binaural audio |
| volumen | volume |

## Botones y órdenes comunes

| Español | Inglés |
|---|---|
| Aceptar | OK |
| Cancelar | Cancel |
| Cerrar | Close |
| Aplicar | Apply |
| Sí / No | Yes / No |
| Guardar / Guardar como | Save / Save as |
| Abrir | Open |
| Borrar, eliminar | Delete |
| Preferencias | Preferences |
| Opciones | Options |
| Manual de usuario | User manual |
| Lista de teclas | Keyboard shortcuts |
| Novedades | What's new |
