# Manual de EntornoLab

## Sobre este manual

Este manual explica todo EntornoLab: el Estudio, donde el profesional construye los lugares y prepara el trabajo, y Jugar, donde el alumno los recorre. Está pensado para leerse con lector de pantalla.

- En el Estudio se abre con F1, o desde el menú Ayuda, «Manual de usuario».
- Si el visor lo muestra como página, la tecla H del lector salta de encabezado en encabezado, y las teclas 2, 3 y 4 saltan a los encabezados de ese nivel.
- Si lo muestra como texto, la lista «Secciones» lleva a cada apartado: elija uno y pulse Intro.
- Ctrl+F busca un texto y F3 busca la siguiente aparición. Escape cierra el visor.

El manual tiene cuatro partes: el Estudio, Jugar, el sonido, y los datos, la ayuda y la referencia. La lista completa de teclas está en un documento aparte: en el Estudio se abre con Ctrl+F1.

Junto a este manual, en la carpeta `data\docs` del programa, hay también guías breves: «guia-rapida-profesional.md», «guia-rapida-alumno.md», «guia-crear-complementos.md» y «preguntas-frecuentes.md». Se pueden abrir con cualquier editor de texto o con el navegador.

Los nombres de menús, botones y campos se escriben aquí tal como los anuncia el lector, entre comillas latinas. Las teclas se escriben unidas con un signo más: Ctrl+Mayús+S significa mantener Control y Mayúsculas y pulsar S.

## Qué es EntornoLab

EntornoLab es una aplicación de Windows, portable y sin conexión, para aprender lugares antes de visitarlos. Tiene dos caras que comparten el mismo motor:

- **El Estudio**, para el profesional de rehabilitación o de orientación y movilidad. En él se construyen entornos interiores (habitaciones, plantas, escaleras, rampas y ascensores) y exteriores (calles, aceras, cruces, pasos de peatones con semáforo y paradas). Después se amueblan con objetos, se preparan actividades, juegos y exámenes, se llevan las fichas de los alumnos, se supervisa en vivo y se sacan informes.
- **Jugar**, para el alumno ciego o con baja visión. Es un audiojuego en primera persona con sonido 3D. El alumno recorre el lugar con el teclado o con un mando de Xbox o de PlayStation, oye sus pasos, choca, abre puertas, sube escaleras, toma el ascensor, cruza la calle y busca premios escondidos.

El autor es Héctor J. Benítez Corredera. EntornoLab es software libre, con licencia GPL 3 o posterior.

### Para quién es

- **Profesionales de rehabilitación y de orientación y movilidad**, ciegos con lector de pantalla o videntes con ratón y plano gráfico. Todo el Estudio se maneja con el teclado y el lector de pantalla; el plano gráfico es un añadido para quien ve.
- **Alumnos con ceguera o con baja visión**, de cualquier edad: niños, jóvenes y adultos. Los mensajes cambian de tono según el estilo: infantil, juvenil o adulto.
- **Familias**, que pueden acompañar el juego en casa con el entorno que haya preparado el profesional.
- **Centros**, que pueden usar la misma carpeta del programa en varios equipos y supervisar a varios alumnos a la vez desde la red local.

### Qué puede hacer y qué no

EntornoLab sirve para:

- conocer la forma de un lugar antes de ir: qué espacios tiene, cómo se unen, dónde están las puertas, las escaleras y los objetos que estorban;
- practicar rutas, volver al origen, buscar la salida más cercana o seguir una línea guía, como juego o como práctica;
- entrenar decisiones en la calle, como esperar al verde de un semáforo sonoro, en un entorno simulado;
- hacer exámenes que registran lo que ocurre, sin pistas ni ayudas;
- llevar el seguimiento de cada alumno y anotar las pruebas en el lugar real.

EntornoLab no sirve para:

- diagnosticar ni tratar nada. Es una herramienta educativa y de entrenamiento;
- sustituir el aprendizaje en el lugar real con un profesional. Lo que se aprende en la simulación hay que comprobarlo y completarlo allí;
- decidir si un cruce real es seguro. El simulador no sabe cómo es el tráfico de verdad de un sitio;
- dar navegación en la calle. No usa GPS ni guía en tiempo real.

### Base científica y sus límites

EntornoLab se inspira en estudios sobre aprendizaje de lugares con entornos virtuales sonoros. Lo que dicen, con sus límites:

- **Lo más sólido.** En el trabajo con el juego AbES (Connors y otros, 2014), adultos con ceguera profunda entrenaron un edificio real de dos plantas con teclado y auriculares, en 3 sesiones de 30 minutos. Después, en el edificio real, los que habían jugado acertaron tanto como los que recibieron instrucción dirigida en rutas de un punto a otro (entre el 88 y el 93 por ciento), y les fue claramente mejor al buscar la salida más corta desde un punto cualquiera. El grupo que jugó en otro edificio no aprendió el edificio real: se aprende el lugar entrenado, no una habilidad general.
- **Con adolescentes** (7 participantes, sin grupo de control), tras 60 minutos de juego, la puntuación del juego se relacionó con el rendimiento en el edificio real.
- **Con niños** (7 participantes, sin grupo de control), el modo juego obtuvo la mejor representación del espacio, sin que la diferencia fuera estadísticamente significativa por el tamaño del grupo.
- **Cruce de calles** (Bowman y Liu, 2017, 12 personas con baja visión severa): el entrenamiento virtual para decidir cuándo cruzar se igualó al real.
- **Planos interactivos** (Giudice y otros, 2020): aprender un plano con sonido y vibración resultó equivalente a hacerlo con un mapa táctil.

Lo que no está demostrado:

- que un barrio entero se aprenda con un simulador;
- que el efecto dure meses;
- que el mando funcione igual que el teclado;
- que mejore la movilidad en lugares no entrenados.

Cautelas: casi todos los estudios tienen entre 4 y 17 participantes y un solo edificio, y recorrer un lugar virtual es varias veces más lento que el real. Por eso EntornoLab incluye lo que esos estudios señalan como más útil (recoger objetos y sacarlos por la salida más cercana, movimiento por pasos, «dónde estoy» sin dar la ruta, exámenes sin pistas con regla de parada, ayudas que se retiran poco a poco y un cuaderno para la prueba en el lugar real), pero no promete resultados. Las referencias completas están en el apartado «Licencias y créditos».

EntornoLab no se ha probado todavía con alumnos ni en un programa de rehabilitación. Tampoco se ha comprobado a mano con cada lector de pantalla ni con mandos físicos: lo que se ha comprobado son pruebas automáticas.

### Uso responsable y seguridad

- **No decida un cruce real por lo que pasó en la simulación.** En la calle manda lo que se oye y lo que dice el profesional.
- Un entorno construido a mano o importado de un mapa puede tener errores. Lo que el mapa no dice se marca como no comprobado, y hay que verificarlo en el lugar.
- Use volúmenes moderados y haga pausas. Con auriculares, deje activada la protección auditiva.
- Las estrellas, medallas y puntuaciones son parte del juego: motivan, pero no miden la competencia en el lugar real.
- Los informes describen lo que ocurrió en el simulador. No son una valoración clínica.

## Instalación y primeros pasos

### Requisitos

- Windows 10 u 11 de 64 bits.
- Auriculares estéreo: el sonido 3D está pensado para ellos.
- Un lector de pantalla, recomendado: NVDA, JAWS u otro compatible. Si no hay ninguno abierto, Jugar habla con la voz de Windows, salvo que se elija otra salida de voz o ninguna (apartado «Voz y braille»).
- Un mando de Xbox o de PlayStation, opcional.
- No hace falta conexión a Internet. Solo se usa si usted la pide: para buscar actualizaciones, descargar complementos, importar de OpenStreetMap o supervisar por la red local.

### Instalar la versión compilada

EntornoLab es portable: no se instala, se descomprime.

1. Descargue el ZIP de la versión más reciente desde la página de publicaciones del proyecto: <https://github.com/hxebolax/EntornoLab/releases>. Se llama `EntornoLab_v` seguido del número de versión.
2. Descomprímalo en una carpeta donde tenga permiso de escritura, por ejemplo en Documentos o en una memoria USB. No lo ponga en «Archivos de programa»: el programa guarda sus datos junto a él.
3. Abra la carpeta. Dentro están los dos programas y la carpeta `data`.

Para desinstalarlo, borre la carpeta. Para llevarlo a otro equipo, copie la carpeta entera.

### Los dos programas

- **EntornoLab.exe** es el Estudio, para el profesional.
- **EntornoLabJugar.exe** es Jugar, para el alumno.

Los dos comparten la carpeta `data`: los entornos guardados en el Estudio aparecen en Jugar. El Estudio puede abrir Jugar por sí mismo para probar una actividad, para recorrer el entorno o para empezar una sesión supervisada.

Si el Estudio ya está abierto, aunque esté oculto en la bandeja, al abrirlo otra vez se trae al frente la ventana que ya había.

### Qué hay en la carpeta del programa

Dentro de `data` hay carpetas que vienen con el programa y carpetas que crea al usarlo:

- vienen con el programa: `bin` (bibliotecas de sonido), `sounds` (paquetes de sonidos), `plugins` (complementos de objetos), `ejemplos` (entornos de ejemplo), `docs` (este manual y las licencias), `locales` (idiomas) e `icons`;
- se crean al usarlo: `entornos` (sus entornos), `config` (preferencias), `db` (fichas y sesiones de los alumnos), `sessions` (sesiones de Jugar sin incorporar), `backups` (copias de la base), `logs` (registros), `cache` y `temp`.

Para hacer una copia de seguridad completa, copie la carpeta del programa.

### Lector de pantalla, auriculares y mando

- **Lector de pantalla.** El Estudio usa controles estándar de Windows: el lector los lee como en cualquier aplicación. Jugar habla a través del lector que esté abierto y, si no hay ninguno, con la voz de Windows. En Jugar, Opciones, «Voz y braille», y en Preferencias del Estudio, pestaña Voz, se elige quién habla: automática, solo el lector de pantalla, siempre la voz de Windows o nadie (sin voz).
- **Auriculares.** Póngaselos con el lado izquierdo en el oído izquierdo. Con el motor de serie, los sonidos se oyen delante, detrás, a los lados, arriba y abajo. Con altavoces, elija en Opciones, Sonido, «Oigo por: altavoces».
- **Mando.** Conecte un mando de Xbox o de PlayStation antes o durante el juego. Jugar lo detecta solo y dice su nombre. La voz nombra siempre los botones del mando conectado.

### Primer arranque del Estudio

1. Abra `EntornoLab.exe`.
2. La primera vez, el programa pregunta si puede comprobar al arrancar si hay una versión nueva. El botón predeterminado es «No conectar». Si elige «Sí, comprobar al arrancar», lo hará como mucho una vez al día. Se puede cambiar después en Preferencias.
3. El foco empieza en el árbol del entorno. Para empezar, abra un ejemplo con Archivo, «Abrir ejemplo», o cree uno con Archivo, «Nuevo entorno» (Ctrl+N).

### Primer arranque de Jugar

1. Abra `EntornoLabJugar.exe`.
2. Jugar saluda y abre «¿Quién juega?». Elija un alias de la lista, «Soy nuevo: escribir mi alias» o «Jugar como invitado».
3. En el menú principal, empiece por «Tutorial»: enseña a andar, chocar, girar, rodear una mesa, preguntar dónde está, abrir una puerta y encontrar un premio.

Para moverse por los menús de Jugar se usan las flechas arriba y abajo, Intro para elegir y Escape para volver. F1 dice la explicación de la opción.

## Parte 1. El Estudio

### La ventana principal

#### Los menús

La barra de menús tiene, en este orden: Archivo, Editar, Insertar, Ver, Alumnos, Supervisión, Herramientas y Ayuda. Alumnos y Supervisión solo aparecen si está instalada la parte de seguimiento, que viene de serie.

- **Archivo**: «Nuevo entorno» (Ctrl+N), «Abrir» (Ctrl+O), «Abrir ejemplo», «Recientes», «Guardar» (Ctrl+S), «Guardar como» (Ctrl+Mayús+S), los submenús «Importar» y «Exportar», «Propiedades del entorno» y «Salir».
- **Editar**: «Deshacer» (Ctrl+Z), «Rehacer» (Ctrl+Y), «Propiedades del elemento» (F4), «Duplicar» (Ctrl+D), «Renombrar» (F2), «Mover» (Ctrl+M), «Girar» (Ctrl+G), «Cambiar medidas» (Ctrl+R), «Borrar», «Buscar elemento» (Ctrl+F) y «Poner aquí el inicio».
- **Insertar**: «Planta», «Habitación por medidas», «Habitación adosada a otra», «Espacio poligonal», «Puerta, hueco, ventana o portal», «Pared suelta», «Escalera», «Rampa», «Ascensor», «Objeto del catálogo», «Fuente de sonido», «Referencia», «Zona de suelo» y el submenú «Exteriores».
- **Ver**: los paneles, «Ir a planta», «Planta de arriba» y «Planta de abajo», el zoom del plano, «Herramienta del plano», «Cuadrícula», «Ajustar a la cuadrícula», «Mostrar el plano gráfico» y «Barra de estado».
- **Alumnos**: «Fichas de alumnos» (Ctrl+L), «Sesiones» (Ctrl+T), «Informes» (Ctrl+I), «Cuaderno de evaluación real» (Ctrl+U), «Cambiar la contraseña» y «Bloquear los datos de alumnos».
- **Supervisión**: «Sala de supervisión» (F7), «Empezar sesión en este ordenador» y «Anuncios por voz».
- **Herramientas**: «Comprobar el entorno» (F5), «Medir entre dos elementos» (Ctrl+Mayús+M), «Amueblar el espacio», «Recorrer el entorno» (F9), «Recorrer desde el elemento seleccionado» (Mayús+F9), «Detener el recorrido», «Complementos instalados», «Catálogo en línea de complementos», «Crear un complemento propio», «Abrir la carpeta de datos», «Abrir la carpeta de registros» y «Preferencias» (Ctrl+,).
- **Ayuda**: «Manual de usuario» (F1), «Lista de teclas» (Ctrl+F1), «Novedades de la versión», «Ayuda del control enfocado» (Ctrl+H), «Buscar actualizaciones», «Página del proyecto», «Avisar de un fallo», «Generar paquete de diagnóstico», «Invítame a un café si te gusta mi trabajo» y «Acerca de EntornoLab».

Mientras recorre un menú, la barra de estado muestra para qué sirve cada orden.

#### La página Entorno

La zona de trabajo es un cuaderno de páginas: «Entorno», «Descripción» y «Actividades». Ctrl+Tab pasa de una a otra.

La página Entorno tiene cuatro partes:

- **«Árbol del entorno»**: el entorno, sus plantas, los espacios de cada planta y lo que contiene cada espacio. Una puerta aparece bajo los dos espacios que une. Cada planta tiene además grupos como «Paredes sueltas», «Calles» y «Fuera de todo espacio», y al final está el grupo «Escaleras, rampas y ascensores». Cada nodo dice su nombre y su tipo.
- **«Lista de elementos»**: lo que hay dentro del nodo elegido en el árbol, con cuatro columnas: Nombre, Tipo, Medidas y Posición. Las flechas izquierda y derecha leen las columnas.
- **«Elemento elegido»**: un campo de solo lectura con una frase que dice qué es el elemento, cuánto mide y dónde está.
- **Propiedades**: el formulario del elemento elegido, con los botones «Aplicar cambios» y «Descartar cambios».
- **«Plano gráfico»**: el dibujo de la planta, para quien ve. Se puede ocultar con Ver, «Mostrar el plano gráfico».

#### Navegar entre paneles

- Alt+1 lleva al árbol, Alt+2 a la lista, Alt+3 a las propiedades, Alt+4 al plano y Alt+5 a la descripción.
- F6 pasa al panel siguiente y Mayús+F6 al anterior: árbol, lista, propiedades y plano.
- Alt+RePág y Alt+AvPág cambian a la planta de arriba y a la de abajo. Ver, «Ir a planta», enseña la lista de plantas.
- En el árbol y en la lista, Intro abre las propiedades, Supr borra con confirmación y la tecla Aplicaciones abre el menú contextual.

El menú contextual del árbol, de la lista y del plano tiene: «Propiedades», «Renombrar», «Duplicar», «Mover», «Girar», «Cambiar medidas», «Borrar», «Insertar un objeto del catálogo», «Poner aquí el inicio» y «Recorrer desde aquí».

#### Las páginas Descripción y Actividades

- **Descripción** (Alt+5) enseña el entorno entero en texto, una frase por línea: nombre y autor, cuántas plantas tiene, dónde se empieza, y cada espacio con sus vecinos, sus puertas, sus objetos, sus fuentes de sonido y sus referencias. Al final, las calles y los conectores entre plantas. Es el mismo texto que se exporta con Archivo, Exportar, «Descripción en texto». En un entorno grande (un barrio importado), la página dice primero «Componiendo la descripción del entorno…» y, cuando la tiene, se anuncia «Descripción lista» con su número de líneas; mientras tanto puede seguir usando el programa.
- **Actividades** enseña las actividades del entorno. Se explica en el apartado «Actividades».

#### Entornos grandes

Un barrio importado de OpenStreetMap puede tener miles de espacios, puertas y referencias. El Estudio está hecho para que con ellos siga respondiendo al momento:

- En el árbol, la planta enseña sus espacios, pero lo que hay dentro de cada espacio y de cada grupo aparece al desplegarlo con la flecha derecha. En un entorno pequeño el árbol se abre desplegado entero, como siempre.
- La lista de elementos de una planta puede tener miles de filas y se recorre sin esperas.
- En el plano, cuando se ve el barrio entero, se dibuja sin letras ni símbolos pequeños; al acercarse vuelven los detalles.
- Lo que revisa el entorno entero y con un barrio tarda unos segundos («Comprobar el entorno», exportar, la página Descripción) se hace en segundo plano. Un cuadro de progreso dice en su campo «Estado» qué se está haciendo y con qué cifras («Comprobando los objetos de Calle: 300 de 1424.») y el tiempo transcurrido; la voz anuncia cada fase nueva sin interrumpir y, si pasan 15 segundos sin novedades, recuerda que sigue. Escape o el botón para detener la tarea la cancelan.

Si alguna vez el programa se quedara sin responder más de tres segundos, lo anota en la carpeta de registros con lo que estaba haciendo; el paquete de diagnóstico (Ayuda) lo incluye.

#### Barra de estado y título

- La barra de estado repite el último aviso hablado y dice la planta actual. Se oculta con Ver, «Barra de estado».
- Cuando hay cambios sin guardar, el título de la ventana empieza por un asterisco.
- Al cerrar o al abrir otro entorno con cambios sin guardar, el programa pregunta, con los botones «Guardar», «No guardar» y «Cancelar».

#### Unidades y orientación

- Todas las medidas del Estudio son en metros. Se pueden escribir con coma o con punto decimal, y con la unidad detrás («3,5 m»).
- La x crece hacia el este y la y hacia el norte. El norte queda arriba en el plano.
- Los rumbos van en grados: 0 es el norte, 90 el este, 180 el sur y 270 el oeste.
- Las listas de puntos se escriben con x e y separadas por un espacio, y los puntos separados por punto y coma: «0 0; 4 0; 4 3».

### Tutorial: una vivienda desde cero

Este tutorial crea un piso pequeño: un pasillo, un salón, una cocina y un baño, con sus puertas y algunos muebles.

1. Pulse Ctrl+N. Se abre el formulario «Nuevo entorno».
2. En «Nombre del entorno» escriba «Mi piso». En «Punto de partida» deje «Interior en blanco». Pulse Intro.
   El programa anuncia que ha abierto el entorno con una planta.
3. Cree el pasillo: Ctrl+Mayús+H abre «Habitación por medidas».
   - En «Nombre» escriba «Pasillo» y en «Tipo de espacio» elija «Pasillo».
   - En «Ancho, de oeste a este (metros)» escriba 6 y en «Fondo, de sur a norte (metros)» escriba 1,2.
   - Deje las esquinas como están y pulse Intro. El pasillo queda seleccionado y el programa lo describe.
4. Cree el salón al norte del pasillo: Ctrl+Mayús+A abre «Habitación adosada a otra».
   - En «Junto a» elija «Pasillo» y en «Lado de ese espacio» elija «Norte».
   - En «Nombre de la habitación nueva» escriba «Salón», ancho 4 y fondo 3,5.
   - En «Colocación a lo largo de la pared» elija «Igualada por el extremo oeste o sur».
   - Deje marcada «Abrir una puerta en la pared compartida» y pulse Intro. Las dos habitaciones comparten la pared y ya tienen puerta.
5. Repita el paso 4 para la cocina, también al norte del pasillo pero «Igualada por el extremo este o norte», con 2 metros de ancho y 3,5 de fondo.
6. Repita para el baño al sur del pasillo, de 2 por 2 metros.
7. Ponga la puerta de la calle: Ctrl+Mayús+U abre «Puerta, hueco, ventana o portal».
   - En «Espacio» elija «Pasillo» y en «Pared» elija «Oeste».
   - En «Qué se abre» deje «Puerta». Marque «Cuenta como salida del edificio».
   - En «Nombre» escriba «Puerta de la calle» y pulse Intro.
8. Añada una ventana en el salón: otra vez Ctrl+Mayús+U, espacio «Salón», pared «Norte», «Qué se abre: Ventana».
9. Amueble el salón: elija Herramientas, «Amueblar el espacio». En «Espacio» elija «Salón» y en «Amueblarlo como» elija «Salón». Revise la lista «Mobiliario propuesto» y pulse «Aceptar la propuesta». Para la cocina, repita con «Cocina».
10. Añada un objeto suelto: Ctrl+Mayús+O abre el catálogo. Escriba «perchero» en «Buscar», baje a la lista de objetos y pulse Intro. En el formulario de colocación elija «Contra una pared», espacio «Pasillo», pared «Norte», y pulse Intro.
11. Añada una referencia sonora: Ctrl+Mayús+F abre «Fuente de sonido». Elija la planta, escriba «Reloj de pared», elija un sonido de la lista y acepte la posición propuesta.
12. Ponga el punto de inicio: elija «Puerta de la calle» en el árbol y luego Editar, «Poner aquí el inicio».
13. Compruebe el entorno con F5. Si la lista de problemas está vacía, el resultado dice «Sin problemas». Si hay algo, Intro sobre el problema lleva al elemento.
14. Guarde con Ctrl+S. La primera vez pregunta dónde; de serie, en la carpeta `entornos`.
15. Pulse F9 para recorrerlo con Jugar. Cuando termine, cierre Jugar o elija Herramientas, «Detener el recorrido».

El formulario «Nuevo entorno» también ofrece plantillas en «Punto de partida»: «Interior en blanco», «Exterior en blanco», «Vivienda tipo», «Aula», «Planta de oficinas», «Tramo de calle con cruce» y «Parada de autobús». La casilla «Amueblar con los complementos instalados» coloca muebles en las plantillas que los traen sugeridos.

### Tres formas de colocar las cosas

#### Por medidas

Todos los formularios del menú Insertar piden la posición en metros. Por ejemplo, «Esquina suroeste al este, x (metros)» y «Esquina suroeste al norte, y (metros)». Es la forma más exacta cuando se tiene un plano con cotas.

#### Por relación con otra cosa

Es la forma más cómoda sin plano. El programa calcula las coordenadas:

- «Habitación adosada a otra» pone una habitación pegada a un lado de otra, compartiendo pared, y puede abrir la puerta entre las dos.
- «Puerta, hueco, ventana o portal» se coloca en una pared de un espacio: centrada, o a una distancia de la esquina oeste o sur.
- Un objeto del catálogo se coloca «Contra una pared», «En una esquina» o «Junto a otro elemento». Solo la cuarta forma, «En un punto, por coordenadas», pide números.

#### Recorriendo

El profesional camina por el entorno con Jugar y coloca las cosas donde está:

1. Pulse F9 (o Mayús+F9 para empezar junto al elemento seleccionado). El Estudio guarda el entorno y abre Jugar en modo recorrido.
2. Camine hasta el sitio con las teclas de siempre. F7 activa el modo fantasma, que atraviesa paredes y objetos. F8 salta a cualquier lugar o planta.
3. Pulse F4 para abrir el «Menú de edición». Tiene estas opciones:
   - «Colocar un objeto aquí»: elige el objeto y lo deja donde está usted, mirando hacia donde mira. Si no cabe, no se coloca. Como hay más de dos mil objetos, no salen todos en una lista: elija «Los que ya hay en este entorno», «Buscar por nombre» (escriba una o varias palabras, como «paragüero» o «silla de ruedas», y pulse Intro), «Otra vez» para repetir el último, o un complemento y, dentro, su categoría y su subcategoría.
   - «Poner un premio aquí»: pide el nombre y lo añade a la actividad elegida en la página Actividades.
   - «Marcar este punto»: crea una referencia con nombre.
   - «Medir desde aquí» y «Medir hasta aquí»: dicen la distancia en línea recta y hacia dónde queda.
   - «Poner aquí el inicio»: su posición y su rumbo pasan a ser el inicio del entorno.
4. Cada cambio se hace en el Estudio, queda en el historial de Deshacer y Jugar recarga el entorno en el mismo punto.
5. Para terminar, cierre Jugar o elija Herramientas, «Detener el recorrido». El Estudio anuncia «Recorrido terminado». Si Jugar se cierra solo por un fallo, el Estudio lo dice («se ha cerrado de forma inesperada»).

Solo hay un recorrido a la vez. «Colocar recorriendo» del editor de premios usa el mismo: si ya hay uno abierto, lo aprovecha en lugar de abrir otro Jugar.

Con mando, el panel táctil de PlayStation o el botón extra abren el menú de edición.

### Editar lo que ya está hecho

- **Propiedades del elemento** (F4 o Intro): el formulario completo. Los de espacio y de entorno tienen pestañas. En un espacio se cambian el tipo, el suelo, la acústica («Seca», «Habitación», «Sala grande», «Pasillo», «Baño», «Escalera», «Nave», «Exterior», «Calle» o «Parque»), el material de las paredes, si tiene paredes y si es macizo.
- **Duplicar** (Ctrl+D): crea una copia medio metro al este. Una planta se duplica entera, encima de la más alta.
- **Renombrar** (F2).
- **Mover** (Ctrl+M): «Desplazarlo unos metros» o «Llevar su centro a un punto». La casilla «Llevarse lo que contiene» mueve también sus puertas y muebles. Las escaleras, rampas y ascensores no se mueven: hay que borrarlos y crearlos de nuevo.
- **Girar** (Ctrl+G): en grados, en el sentido del reloj. Con -90 gira a la izquierda.
- **Cambiar medidas** (Ctrl+R): los campos dependen del elemento. En un objeto también el alto.
- **Borrar** (Supr en el árbol o la lista): pregunta antes. Borra también lo que depende del elemento: las puertas de una pared, las aceras y los pasos de una calle, o todo el contenido de una planta. Se puede deshacer.
- **Buscar elemento** (Ctrl+F): busca por nombre, tipo o identificador, sin distinguir tildes. Intro en el texto pasa a la lista y Intro en la lista selecciona el elemento.
- **Deshacer y Rehacer** (Ctrl+Z y Ctrl+Y): el menú dice qué operación deshará. De serie se recuerdan 100 operaciones.
- **Propiedades del entorno** (menú Archivo): nombre, descripción, autor, procedencia y la pestaña «Punto de inicio», con la planta, la posición y hacia dónde mira al empezar.

### Plantas, escaleras, rampas y ascensores

- **Planta** (Ctrl+Mayús+P): nombre, «Es un plano de calle», nivel y altura del suelo. Si deja el nivel vacío, va encima de la más alta.
- **Escalera**: une la «Planta de abajo» con la «Planta de arriba». Se dice dónde está la boca de abajo, «Hacia dónde se sube» (ocho rumbos), la «Longitud en planta», los peldaños, la anchura y el pasamanos («A la izquierda», «A la derecha», «A los dos lados» o «Sin pasamanos»). La boca de arriba queda en línea recta, a esa longitud.
- **Rampa**: igual que la escalera, sin peldaños.
- **Ascensor**: se marcan las «Plantas en las que para» (al menos dos), el punto que está delante de la puerta, que es el mismo en todas las plantas, «Hacia dónde se mira para entrar» y si «Dice la planta al llegar».

Las bocas de escaleras y rampas y la parada del ascensor tienen que caer dentro de un espacio; si no, Comprobar da un error. En el árbol aparecen en el grupo «Escaleras, rampas y ascensores».

#### Tutorial: un edificio de dos plantas

1. Cree un entorno nuevo con «Interior en blanco». Ya tiene una planta baja.
2. En la planta baja, cree un «Vestíbulo» de 8 por 6 metros y un «Hueco de escalera» adosado al este, de 3 por 6 metros, con su puerta.
3. Cree la planta de arriba con Ctrl+Mayús+P. Nombre «Planta primera», deje el nivel vacío.
4. Pase a la planta primera con Alt+RePág. Cree un «Pasillo» y un hueco de escalera en el mismo sitio que el de abajo.
5. Inserte la escalera: Insertar, «Escalera». «Planta de abajo», la baja; «Planta de arriba», la primera. Ponga la boca de abajo dentro del hueco de escalera, «Hacia dónde se sube: Norte», 4 metros de longitud y 16 peldaños.
6. Inserte el ascensor: Insertar, «Ascensor». Marque las dos plantas y ponga el punto delante de la puerta dentro del vestíbulo de abajo y del pasillo de arriba.
7. Compruebe con F5 y recorra con F9. Al subir, Jugar dice los peldaños y, al llegar, la planta.

El ejemplo «Centro de dos plantas», en Archivo, «Abrir ejemplo», tiene una escalera de 18 peldaños y un ascensor ya hechos.

### Exteriores

Los exteriores se construyen sobre una planta que es un plano de calle. Se crea con la plantilla «Exterior en blanco» o con Insertar, «Planta», marcando «Es un plano de calle». Todas las órdenes del submenú Insertar, «Exteriores», necesitan un plano de calle.

- **«Calle con aceras»**: los «Puntos del eje», el ancho de la calzada, el ancho de cada acera (0 no crea aceras), los carriles, el sentido («Doble sentido», «Sentido único, de inicio a fin» o «Sentido único, de fin a inicio»), el tráfico («Sin tráfico», «Tráfico escaso», «Tráfico moderado» o «Tráfico intenso») y la velocidad de los coches. Crea la calzada y las dos aceras.
- **«Cruce»**: resuelve el cruce de dos calles que ya existen y recorta las aceras en tramos.
- **«Paso de peatones»**: la calle que cruza, el punto (se ajusta solo al eje), el ancho, «Tiene semáforo», «El semáforo es sonoro», «Tiene pulsador», «Tiene isleta en medio» y «Poner pavimento táctil a cada lado». Con semáforo crea un poste a cada lado.
- **«Edificio con portal»**: un edificio macizo, en el que no se entra, con su portal en una fachada como referencia para orientarse.
- **«Manzana»**: una manzana maciza de cualquier forma.
- **«Parada»**: una referencia de tipo «Parada de transporte».

El semáforo de un paso tiene siempre 25 segundos de verde, 5 de intermitente y 45 de rojo. Hoy no se pueden cambiar esos tiempos. Semáforo, sonoro, pulsador e isleta sí se pueden cambiar después en las propiedades del paso.

#### Tutorial: una calle con cruce, paso con semáforo y parada

1. Pulse Ctrl+N y elija el punto de partida «Exterior en blanco».
2. Elija Insertar, Exteriores, «Calle con aceras». Nombre «Calle Mayor», eje «-30 0; 30 0», calzada de 6 metros, aceras de 2, «Doble sentido» y «Tráfico moderado».
3. Repita con «Calle del Río», eje «0 -30; 0 30» y «Sentido único, de inicio a fin».
4. Elija Insertar, Exteriores, «Cruce». Primera calle «Calle Mayor», segunda «Calle del Río». Las aceras se recortan en tramos.
5. Elija Insertar, Exteriores, «Paso de peatones». Calle «Calle Mayor», punto x 10 e y 0. Marque «Tiene semáforo», «El semáforo es sonoro» y «Tiene pulsador».
6. Elija Insertar, Exteriores, «Parada». Nombre «Parada de autobús Calle Mayor», en x 20 e y 4, sobre la acera norte (la calzada llega hasta y 3 y la acera, hasta y 5).
7. Ponga el inicio en la acera, compruebe con F5, guarde y recorra con F9. Al acercarse al paso, Jugar lo anuncia, y al pasar de la acera a la calzada dice «Bordillo».

Las plantillas «Tramo de calle con cruce» y «Parada de autobús», y el ejemplo «Barrio de ejemplo», traen esto hecho.

#### Unir interior y exterior

- La forma de entrar andando en un edificio desde la calle es poner sus salas interiores en la misma planta de calle: cree una habitación con «Habitación por medidas» sobre el plano de calle y abra en su pared un «Portal» o una «Puerta» que dé a la acera. Así se cruza andando, sin cambiar de planta. El «Barrio de ejemplo» lo hace con el vestíbulo del centro cívico.
- También se puede unir el plano de calle con una planta interior mediante una escalera, una rampa o un ascensor.
- Un «Edificio con portal» es macizo: su portal es solo una referencia y no lleva a ningún interior.

### Objetos y complementos

Los objetos (muebles, electrodomésticos, mobiliario urbano, obstáculos) vienen en complementos. Cada complemento es una carpeta con sus fichas de objetos, sus imágenes y sus sonidos. EntornoLab trae varios complementos de serie y se pueden añadir más. El listado completo de objetos de serie está en el fichero `CATALOGO.md` de la carpeta `data\plugins`, cuando la versión lo incluye.

Cada objeto tiene medidas normales con un mínimo y un máximo, una forma, dónde se suele colocar, si corta el paso, a qué altura está su base, si se detecta con el bastón, su material, sus sonidos y, a veces, estados y acciones, como abrir y cerrar.

Si un entorno usa un complemento que no está instalado, se abre igual: sus objetos aparecen como cajas con sus medidas. Al abrirlo, el Estudio avisa una vez con un mensaje que nombra los complementos que faltan y pregunta si se quieren buscar en el catálogo en línea. «Buscar en el catálogo en línea» abre el catálogo (filtrado por ese complemento si solo falta uno); «Cerrar» sigue sin conectarse a Internet.

#### Insertar un objeto del catálogo

1. Pulse Ctrl+Mayús+O. Se abre «Insertar objeto del catálogo» con el foco en «Buscar».
2. Escriba parte del nombre, por ejemplo «mesa». La lista se filtra sola al poco de dejar de escribir; Intro filtra al momento.
3. Baje con Tab a la lista «Objetos». Sus columnas son Nombre, Categoría, Medidas y Complemento. Debajo, un texto dice cuántos objetos hay.
4. El campo «Descripción» dice todo sobre el objeto elegido: medidas, forma, dónde se coloca, si corta el paso, la altura de la base, si se detecta con el bastón, si puede esconder un premio, sus sonidos y sus estados. En «Variante» se elige un tamaño.
5. Pulse Intro en la lista, o el botón «Aceptar». Se abre el formulario «Colocar», con el nombre del objeto.
6. Elija «Forma de colocarlo»: «Contra una pared», «En una esquina», «Junto a otro elemento» o «En un punto, por coordenadas». Los demás campos cambian según la forma:
   - contra una pared: espacio, «Pared» (la que queda a la espalda del objeto), «Sitio a lo largo de la pared» y «Separación de la pared»;
   - en una esquina: espacio y esquina;
   - junto a otro elemento: «Elemento de referencia», «A qué lado del elemento» y «Separación del elemento»;
   - por coordenadas: metros al este, metros al norte y «Rumbo del frente, en grados».
7. Si quiere, escriba un «Nombre propio» y pulse Intro.

Ctrl+D marca el objeto elegido como favorito, o lo quita. Con el botón «Objetos relacionados» se ven otros parecidos.

#### Buscar y filtrar por clasificación

- El árbol «Clasificación» tiene «Todos», «Favoritos», «Usados recientemente» y cada complemento con sus categorías y subcategorías. Cada rama dice cuántos objetos tiene.
- «Ámbito» filtra por «Interior» o «Exterior». Empieza con el ámbito de la planta actual.
- «Lugar», «Estancia», «Función» y «Tipo de obstáculo» filtran por esa clasificación. Solo aparecen si algún objeto la declara.
- Las casillas «Puede esconder un premio» y «Tiene sonido propio» dejan solo los contenedores o los objetos que suenan solos.
- La búsqueda no distingue tildes ni mayúsculas, y mira el nombre, las palabras clave, la descripción y la clasificación.

#### Ajuste a escala

Antes de colocar, el programa ensaya la colocación en una copia del entorno:

- si el objeto no cabe con sus medidas, prueba una variante menor o lo encoge dentro de su rango, y lo dice;
- si ni así cabe, avisa «No cabe» y no cambia nada;
- si cabe pero tapa una puerta o deja un paso estrecho, pregunta, con los botones «Dejarlo así» y «Quitarlo».

El paso libre mínimo es de 0,8 metros de serie y se cambia en Preferencias, Editor. Para cambiar el tamaño después, use «Cambiar medidas» (Ctrl+R).

#### Obstáculos colgantes y riesgos

La faceta «Tipo de obstáculo» dice a qué altura estorba el objeto: «A ras de suelo: se pisa», «Bajo: por debajo de la rodilla», «A media altura: de la rodilla al pecho», «Alto: de cuerpo entero», «En voladizo: el bastón pasa por debajo», «A la altura de la cabeza» y «Por encima de la cabeza». Si la ficha no lo dice, se deduce de la altura de su base.

Los objetos colgados o en voladizo son importantes en orientación y movilidad porque el bastón no los detecta. En Jugar, el bastón sonoro tampoco los detecta: se encuentran al chocar con ellos o con «mirar delante». La descripción de cada objeto dice además sus riesgos, como «Se mueve», «Desnivel o hueco», «Quema» o «Resbala o moja».

#### Amueblar un espacio

1. Elija Herramientas, «Amueblar el espacio».
2. Elija la planta, el espacio y «Amueblarlo como»: «Dormitorio», «Salón», «Cocina», «Baño», «Aula» u «Oficina».
3. El programa propone los muebles típicos de ese uso, con los complementos instalados, repartidos por paredes y esquinas sin tapar puertas.
4. Revise la lista «Mobiliario propuesto», con las columnas Objeto, Medidas y «Dónde queda».
5. Pulse «Aceptar la propuesta» para colocarlo todo de una vez, o «Descartar». Lo colocado se deshace con una sola orden.

#### Gestionar los complementos instalados

Herramientas, «Complementos instalados», enseña la lista con Nombre, Versión, Objetos, Categorías, Estado y Origen («De serie» o «Del usuario»).

- «Activar o desactivar»: un complemento desactivado no aparece en el catálogo. No hace falta reiniciar.
- «Añadir desde fichero»: instala un complemento compartido (fichero `.elabc`).
- «Comprobar»: revisa medidas, sonidos e imágenes.
- «Detalles» (o Intro): la ficha del complemento.
- «Quitar» (o Supr): solo los del usuario. Los de serie se pueden desactivar, pero no quitar.

#### El catálogo en línea de complementos

Herramientas, «Catálogo en línea de complementos», descarga la lista oficial de complementos.

- Se busca con «Buscar» y «Categoría». La lista dice el estado de cada uno: «Disponible», «Hay actualización», «Al día», «Solo en este equipo» o «Necesita una versión más nueva de la aplicación».
- Botones: «Instalar», «Actualizar», «Actualizar todos», «Desinstalar», «Versión anterior», «Detalles», «Refrescar» (F5) y «Cerrar».
- Cada paquete se comprueba antes de instalarlo: la lista va firmada, cada paquete se verifica y solo se admiten datos (fichas, imágenes, sonidos y textos), nunca programas.
- Antes de actualizar se guarda la versión anterior, y «Versión anterior» vuelve a ella.

Si dio permiso para buscar actualizaciones al arrancar y está marcada «Mirar también el catálogo de complementos», el programa solo avisa por voz de que hay complementos con actualización. No instala nada solo.

#### Crear un complemento propio

Herramientas, «Crear un complemento propio», abre un diálogo con tres pestañas. Ctrl+Tab pasa de una a otra.

1. **Ficha**: «Nombre del complemento», «Identificador» (se saca del nombre si se deja vacío), «Versión», «Autor», «Licencia» y «Descripción».
2. **Objetos**: la lista de objetos, con «Añadir», «Editar», «Duplicar» y «Quitar». Cada objeto tiene nombre, categoría, palabras para buscarlo, descripción hablada, forma, medidas con mínimo, normal y máximo, variantes, dónde se coloca, si corta el paso, la altura de su base, si se detecta con el bastón, si puede esconder un premio, el material, los sonidos y los estados y acciones. «Escuchar el sonido elegido» lo hace sonar.
3. **Guardar**: «Comprobar» lo revisa sin guardar, «Guardar en este equipo» lo deja en el catálogo sin reiniciar y «Exportar para compartir» crea un fichero `.elabc` que otra persona instala con «Añadir desde fichero».

El asistente ofrece los sonidos de serie. Para usar grabaciones propias, y para todo el detalle del formato, vea la guía «guia-crear-complementos.md» de la carpeta `data\docs`. El asistente siempre empieza vacío: no abre un complemento ya hecho para editarlo.

### El plano gráfico

El plano es para quien ve. Todo lo que se hace en él se puede hacer también desde el árbol, la lista y los menús. El plano no habla: para el lector de pantalla, lo elegido se dice en el campo «Elemento elegido», el árbol, la lista y las propiedades.

Herramientas del plano, en Ver, «Herramienta del plano»:

- **«Seleccionar y mover»**: el clic selecciona, arrastrar mueve, el doble clic abre las propiedades y el botón derecho abre el menú contextual.
- **«Dibujar una habitación»**: arrastrando un rectángulo se abre «Habitación por medidas» con las medidas puestas.
- **«Dibujar una pared»**: con dos clics se abre «Pared suelta» con los extremos puestos.
- **«Colocar un objeto del catálogo»**: un clic abre el catálogo y coloca el objeto en ese punto.

Con el ratón, la rueda amplía y reduce, y el botón central, o Espacio mantenido más arrastrar, desplaza la vista.

Equivalentes de teclado, con el foco en el plano:

- las flechas mueven el elemento seleccionado un paso de cuadrícula (0,5 metros de serie) y Mayús con las flechas lo mueve un paso fino (0,05 metros de serie). Tras moverlo se anuncia la posición nueva;
- Ctrl++ y Ctrl+- acercan y alejan, y F8 enseña la planta entera;
- Ctrl+Mayús+G muestra u oculta la cuadrícula;
- Escape cancela el dibujo o el arrastre en curso.

El elemento seleccionado se dibuja con trazo grueso y asas en los vértices, no solo con otro color. El plano dibuja también la escala, la marca del norte, la imagen de fondo si la hay y los premios y el inicio de la actividad elegida en la pestaña Actividades; un premio escondido dentro de un objeto se dibuja en el centro del objeto con trazo discontinuo. Lo mismo se lee en texto al final de la página Descripción (Alt+5) y con Ctrl+H en el plano. Con el alto contraste de Windows usa los colores del sistema.

### Comprobar el entorno

Herramientas, «Comprobar el entorno» (F5), revisa el entorno y sus actividades. Los problemas de una actividad empiezan por su nombre («Actividad «Busca las llaves»: …»); entre ellos, el aviso de un premio cuyo audio grabado no está guardado en el entorno.

- «Resultado» dice «Sin problemas» o cuántos errores y avisos hay.
- La lista «Problemas encontrados» tiene las columnas Gravedad, Problema, Sugerencia y Dónde.
- Intro sobre un problema cierra el diálogo y lleva al elemento. «Volver a comprobar» repite la revisión.

Son errores, entre otros: una planta sin espacios donde haga falta, una puerta que no está sobre ninguna pared, una escalera con la boca fuera de todo espacio, un ascensor con menos de dos plantas, el inicio fuera de los espacios o dentro de un objeto, y un objeto que atraviesa una pared o se solapa con otro.

Son avisos, entre otros: un espacio cerrado sin puerta, una puerta de menos de 0,6 metros, un complemento no instalado, una fuente de sonido fuera de los espacios, una escalera sin peldaños y un objeto que tapa una puerta o deja un paso estrecho.

### Medir

Herramientas, «Medir entre dos elementos» (Ctrl+Mayús+M):

1. Elija «Desde» y «Hasta».
2. Pulse «Calcular la medida».
3. «Medida» dice la distancia de centro a centro, hacia dónde queda y la separación libre. Por ejemplo: «De Mesa a Puerta: 3,2 metros hacia el noreste (separación libre: 1,5 metros)». Si están en plantas distintas, lo dice.

En el modo recorrido se mide también con «Medir desde aquí» y «Medir hasta aquí».

### Importar

Archivo, «Importar», crea un borrador. Al terminar se abre un informe con lo importado, lo deducido, lo que la fuente no dice y lo que conviene revisar, con los botones «Usar este borrador» y «Descartar».

#### OpenStreetMap

Crea un exterior con las calles de un lugar real.

1. Elija Archivo, Importar, «OpenStreetMap».
2. La primera vez, el aviso «Conexión a OpenStreetMap» explica qué se envía: solo el texto buscado o las coordenadas del recuadro. Pulse «Conectar» o «No conectar».
3. En «Buscar un lugar» escriba la dirección y pulse Intro. Elija en «Lugares encontrados».
4. Revise «Latitud», «Longitud» y «Radio en metros» (de 20 a 400; se propone 150).
5. Escriba el «Nombre del entorno» y revise «Opciones de la importación»: aceras del mapa, deducir aceras, edificios, lugares de interés y paradas, obstáculos y mobiliario urbano, vías de servicio, terreno de base e interiores de edificios.
6. Pulse «Descargar e importar». Escape cancela.

La regla es **no inventar nada**. Lo que el mapa no dice se escribe «el mapa no lo dice»: por ejemplo, si un paso de peatones tiene semáforo sonoro. Las aceras deducidas se marcan como supuestas y Jugar lo avisa al pisarlas. Nunca se crean sonidos que el mapa no tenga. Todo lo importado lleva la atribución «© colaboradores de OpenStreetMap», que se conserva al exportar.

Sin conexión, el botón «Abrir un fichero» importa un fichero `.osm` o de Overpass guardado antes.

**Importar una zona grande.** Si el radio pasa de 200 metros, antes de descargar se le dice cuánto mide la zona, cuántos espacios saldrán aproximadamente, cuántos megas se descargarán y cuánto puede tardar; puede seguir con «Descargar» o volver con «Cambiar el radio». Durante la importación, el campo «Estado» dice en todo momento qué se está haciendo y con qué cifras: a qué servidor se piden los datos, cuánto lleva esperando a que los prepare, cuántos kilobytes han llegado, si se reintenta o se prueba con otro servidor, y después cada fase de la conversión («Convirtiendo calles: 12 de 30»), con el tiempo transcurrido debajo. La voz anuncia cada fase nueva sin interrumpir y, si pasan 15 segundos sin novedades, recuerda que sigue trabajando y cuánto tiempo lleva. La parte que más puede tardar es la espera al servidor de OpenStreetMap, sobre todo si está ocupado; la conversión tarda unos segundos. Escape o el botón «Detener la tarea» cancelan en cualquier momento, también mientras se espera al servidor, y no se crea nada.

#### Planos DXF y SVG

1. Elija Archivo, Importar, «Plano DXF» o «Plano SVG».
2. En «Fichero del plano», use «Examinar».
3. En «Capas del plano», elija cada capa y diga su uso: «Paredes», «Espacios», «Puertas», «Textos» o «Ignorar».
4. Diga las «Unidades del dibujo» (milímetros, centímetros, metros, pulgadas, pies u otra). «Propuesta del programa» dice lo que dedujo.
5. En «Destino», elija «Un entorno nuevo» o «Una planta nueva del entorno abierto», y pulse «Importar».

El DXF tiene que estar guardado como texto, no en binario. En SVG la escala es obligatoria y las puertas no se detectan.

#### Imagen de fondo

Pone un plano escaneado debajo del plano gráfico, para calcar encima con el ratón. No se convierte en paredes.

1. Elija Archivo, Importar, «Imagen de fondo».
2. Elija la imagen (PNG o JPG) y la planta.
3. Dé dos puntos de calibración: para cada uno, su píxel horizontal y vertical en la imagen y sus metros al este y al norte en el plano.
4. Ajuste la «Opacidad de la imagen».

#### Ruta GPX

Coloca una ruta grabada (GPX o GeoJSON) sobre un exterior importado de OpenStreetMap. Con «Dejar referencias en los vértices de la ruta», cada punto queda como referencia. Lo que cae a más de 50 metros del entorno se deja fuera.

### Exportar

Archivo, «Exportar»:

- **«Paquete para el alumno»**: comprueba el entorno y guarda un fichero `.elab` con el entorno, sus actividades y sus recursos, listo para llevar a otro equipo. Si hay errores, pregunta con «Exportar de todos modos» y «No exportar».
- **«Descripción en texto»**: el entorno descrito entero, en texto, Markdown o «Página web accesible».
- **«Plano SVG visual»**: un dibujo a escala de cada planta, en A4 o A3, con su leyenda en texto. Se imprime al 100 por cien.
- **«Plano táctil»**: un dibujo de cada planta preparado para lámina en relieve (papel de microcápsulas o impresora de relieve), sin color, con tramas, paredes gruesas, claves numéricas en braille y una esquina rellena para orientar la hoja. Va con su leyenda en texto y en braille español de grado 1, en un fichero `.brf`.
- **«GeoJSON»**: para programas de mapas.
- **«DXF»**: para programas de CAD, por capas y en metros. Se puede volver a importar.

Al terminar, el programa ofrece «Abrir la carpeta». Los planos se exportan solo en SVG: no hay PDF ni PNG.

Para llevar un entorno al alumno, copie el `.elab` en la carpeta `data\entornos` de su EntornoLab. Jugar lo enseña en «Elegir entorno».

### Actividades

Las actividades son lo que el alumno hace en un entorno: juegos, prácticas y exámenes. Viven dentro del fichero del entorno y se preparan en la página «Actividades» (Ctrl+Tab desde la página Entorno).

#### La lista de actividades

La lista «Actividades de este entorno» tiene las columnas Nombre, Tipo, Modo y Resumen. Sus botones son:

- «Nueva actividad»: elige el «Grupo» (Juegos, Prácticas o Exámenes) y el «Tipo de actividad», con su descripción, y abre el formulario con valores razonables ya puestos.
- «Editar» (o Intro).
- «Duplicar»: copia la actividad debajo, como «Copia de» su nombre.
- «Borrar» (o Supr): las sesiones jugadas con ella se conservan.
- «Subir» y «Bajar»: el orden es el que verá el alumno.
- «Comprobar»: dice los errores y avisos de la actividad.
- «Probar ahora»: guarda el entorno y abre Jugar con esa actividad.
- «Asignar a alumnos»: la pone en la lista de trabajo de las fichas elegidas.
- «Paquete para el alumno»: guarda un `.elab` solo con las actividades elegidas, sin datos de alumnos.

La tecla Aplicaciones abre un menú con las mismas acciones.

#### El formulario de una actividad

Se titula «Actividad:» seguido del tipo. Tiene pestañas, que se cambian con Ctrl+Tab. Ctrl+H explica cada campo. El botón «Comprobar» revisa la actividad sin guardarla.

- **General**: «Nombre», «Descripción» (solo para el profesional), «Modo», «Estilo de presentación», «Punto de inicio» (con «Elegir punto de inicio» y «Quitar punto de inicio») y «Contrarreloj (segundos)».
- Las pestañas propias del tipo: **Premios**, **Objetivos**, **Examen** o **Puntuación**.
- **Mensajes**: «Mensaje de inicio», «Mensaje de logro», «Mensaje final», «Con personaje acompañante» y «Nombre del acompañante».
- **Ayudas**: «Ayudas permitidas», los niveles de retirada, «Baliza sonora hacia el objetivo», «Retirar las ayudas por niveles», «Nivel de partida» y «Fallos seguidos antes de ofrecer ayuda».
- **Final**: «Preguntar al terminar», «Recompensa que se desbloquea» y «Estrellas necesarias para desbloquearla».

Al aceptar, si hay errores, pregunta con «Corregir» y «Guardar de todos modos».

En «Modo», Juego y Práctica se comportan igual; sirven para ordenar y para los informes. «Examen» quita pistas, celebraciones, contrarreloj y niveles.

#### Los juegos

- **Búsqueda del tesoro**: encontrar todos los premios escondidos. Opciones: «En orden», «Decir cuántos hay» y el travieso.
- **El recadero**: coger algo en un sitio y llevarlo a otro; los «Encargos» se encadenan.
- **Sacar los tesoros**: recoger los tesoros de uno en uno y sacarlos por la salida más cercana. Cada salida puntúa 3, 2, 1 o 0 según lo cerca que esté. Es el juego que más se parece al de los estudios de AbES.
- **El escondite**: encontrar un personaje escondido que hace ruido cada pocos segundos, durante varias rondas.
- **Sigue al guía**: seguir a un guía por el sonido de sus pasos hasta un destino. El guía espera si el alumno se queda atrás.
- **El explorador**: descubrir todos los espacios, o la parte que se diga.
- **Pistas encadenadas**: cada premio da la pista del siguiente. El programa puede redactar las pistas que falten.
- **Cruza con el pitido**: en la calle, decidir cuándo cruzar, un número de veces. Cada cruce puntúa según si se esperó al verde y si pasaban coches. Es un simulador: no dice si un cruce real es seguro.

#### Las prácticas

- **Exploración libre**: recorrer el entorno sin objetivo ni puntuación.
- **Visita guiada**: oír un texto en cada zona, en orden o no. Se puede narrar en vivo desde la supervisión.
- **Ruta**: ir de un punto a otro, con paradas intermedias si se quiere.
- **Ruta inversa**: ir y volver por donde se vino.
- **Volver al origen**: pasar por varios lugares y volver al punto de partida.
- **Ruta alternativa**: llegar a un destino con un paso cortado.
- **Localizar un espacio**: encontrar un espacio sabiendo solo su nombre. Con «Confirmar la llegada», el alumno tiene que decir que ha llegado con la acción «Confirmar» (tecla M).
- **Familiarización de sala**: recorrer primero el perímetro y después el interior de una sala.
- **Seguir una línea guía**: seguir una pared o un bordillo sin separarse.

#### Los exámenes

- **Examen de rutas**: ir de un punto a otro, con las variantes «Rutas», «Ruta inversa» o «Atajos».
- **Examen de salida más corta**: salir por la salida más cercana desde un punto; puntúa 3, 2, 1 o 0.
- **Examen de señalar**: girarse hacia un lugar y confirmar. Cuenta el error en grados.
- **Examen de distancias**: elegir cuál de dos lugares está más lejos, andando o en línea recta.
- **Examen de reconstrucción**: elegir la respuesta correcta sobre cómo es el lugar.

Todos los exámenes comparten estos campos: «Número de pruebas», «Pruebas definidas a mano», «Límite de tiempo por prueba (segundos)», «Semilla», «Regla de parada», «Se miran las primeras», «Aciertos mínimos para seguir» y «Decir el resultado al final».

Cómo es un examen para el alumno:

- empieza con «Empieza el examen. No hay pistas y no se dice si aciertas. Hazlo a tu ritmo»;
- cada prueba lo coloca en un punto, dice dónde está y qué tiene que hacer;
- confirma su respuesta con la acción «Confirmar» (tecla M, o el gatillo izquierdo más Y o Triángulo en el mando): «ya he llegado», «miro hacia ahí» o «esta es mi respuesta». En el examen de salida no se confirma: salir es la respuesta. En los exámenes con pregunta (distancias y reconstrucción) se abre solo un menú con las respuestas; se elige una y se acepta, y «Confirmar» lo vuelve a abrir;
- tras cada prueba solo oye «Anotado». Nunca se le dice si ha acertado;
- la regla de parada termina el examen en cuanto ya no se puede llegar al mínimo de aciertos, para no frustrar;
- con la misma semilla y el mismo entorno, el examen se repite igual.

En un examen no hay pistas, baliza, travieso, estrellas ni ayuda ofrecida. De serie tampoco hay «dónde estoy», descripción, lista de lo cercano ni lugares descubiertos; el profesional puede volver a permitir esas cuatro. No hay aprobado ni suspenso: el informe dice lo que pasó.

Hoy, las pruebas escritas a mano desde el formulario solo valen bien en el examen de salida más corta. En los demás exámenes es mejor dejar que el programa las genere con la semilla.

#### Premios escondidos

Los premios se ponen en la pestaña Premios de la actividad, en la lista «Premios escondidos», con las columnas Premio, Dónde está, Visibilidad, Sonido y Mensaje. Hay cuatro formas de ponerlos:

1. **A mano**, con «Añadir premio». En el diálogo «Premio escondido» se escribe el «Nombre del premio» y se elige el lugar: planta, espacio y «Dónde, dentro del espacio» («Dentro de un objeto (armario, cajón...)», «Junto a un objeto, una puerta o una referencia», «En el centro del espacio», «En una esquina del espacio» o «En unas coordenadas concretas»).
2. **Dentro de objetos**: con la opción «Dentro de un objeto». Solo se ofrecen los objetos que pueden esconder algo. El alumno tiene que usar el objeto para encontrarlo.
3. **Repartidos**, con «Repartir automáticamente». Se dice cuántos, en qué plantas, su visibilidad y si se esconden algunos dentro de objetos. «Generar la vista previa» da otro reparto cada vez. El reparto empieza por los espacios más lejanos del inicio.
4. **Recorriendo**, con «Colocar recorriendo». Se abre Jugar en modo recorrido; el profesional camina hasta el sitio, pulsa F4 y elige «Marcar este punto». Después se abre el diálogo del premio.

Cada premio tiene además:

- «Sonido del premio», con el botón «Escuchar»;
- «Visibilidad»: «Se oye de lejos», «Solo se oye de cerca» u «Oculto hasta abrir o usar algo»;
- «Mensaje al encontrarlo» y «Pista para encontrarlo», opcionales;
- «Audio grabado», opcional: un fichero WAV, OGG o FLAC que suena tras encontrarlo. Se guarda dentro del entorno.

Una actividad nueva de Búsqueda, Pistas o Sacar los tesoros ya trae unos premios repartidos. En Búsqueda, Pistas y Sacar los tesoros hacen falta todos los premios; en otros tipos son premios de regalo por el camino. El profesional puede añadir premios también en vivo, desde la supervisión.

#### Objetivos

Las listas de objetivos (encargos, escondites, zonas de la visita, paradas, lugares por los que pasar) se rellenan con «Añadir objetivo». Cada objetivo dice «Qué hay que hacer» («Ir a un lugar», «Recoger algo en un lugar», «Entregar lo recogido en un lugar», «Salir por una salida», «Localizar un espacio por su nombre» o «Señalar hacia un lugar»), «Dónde» (con «Elegir un elemento» o «Elegir un punto») y un texto opcional para el alumno.

La casilla «Hay que cumplirlos en este orden» solo tiene efecto hoy en la visita guiada; el recadero y las rutas van siempre en orden.

#### Ayudas, límites y niveles

En la pestaña Ayudas, la tabla «Ayudas permitidas» tiene las catorce ayudas: «Dónde estoy», «Descripción del lugar», «Mirar a los lados y detrás», «Qué hay delante», «Qué hay alrededor», «Bastón sonoro», «Lista de lo cercano», «Lugares descubiertos», «Brújula», «Eco», «Recordar el objetivo», «Pista», «Baliza sonora» y «Avisos automáticos».

- Cada ayuda está «Como en la ficha del alumno», «Permitida» o «Prohibida».
- «Límite de usos» la deja permitida un número de veces.
- Si el alumno pide una ayuda prohibida, oye «Esa ayuda no está disponible en esta actividad».

Los **niveles de retirada progresiva** quitan ayudas poco a poco. Los de serie son cuatro, del más fácil al más difícil: «Con baliza», «Baliza solo al pedirla», «Sin baliza» y «Sin baliza y sin «dónde estoy»». Se editan con «Editar los niveles». Con «Retirar las ayudas por niveles», el alumno supera un nivel al completar la actividad sin pedir pistas. Jugar recuerda el nivel alcanzado en cada actividad, por alias: la primera vez se empieza en el «Nivel de partida» y después en el que se llegó. Al incorporar las sesiones, el nivel pasa a la ficha del alumno, y desde la ficha vuelve a Jugar por la sala; si el profesional cambia el nivel en la ficha, manda el de la ficha.

«Fallos seguidos antes de ofrecer ayuda» hace que, tras varios tropiezos seguidos o mucho tiempo sin avanzar, el juego diga «Si lo necesitas, puedes pedir una pista». Nunca en un examen.

#### Estilos, mensajes y acompañante

- «Estilo de presentación»: «El de la ficha del alumno», «Infantil», «Juvenil» o «Adulto». El infantil celebra y puede tener un acompañante, que de serie se llama Tiko. El juvenil habla de misiones y dice la marca de tiempo. El adulto es sobrio.
- Si los mensajes de inicio, de logro y final se dejan vacíos, se usan los de serie del estilo.

#### Tiempo

- «Contrarreloj (segundos)»: 0 es sin límite. Al empezar se dice el tiempo; si es más de un minuto, se avisa cuando queda uno; al llegar a cero, la actividad termina. Las pausas no cuentan.
- En los exámenes hay un «Límite de tiempo por prueba (segundos)».

#### El travieso

En Búsqueda del tesoro y Sacar los tesoros, la casilla «Con el travieso» añade un personaje que de vez en cuando cambia de sitio un premio sin recoger, para obligar a volver a recorrer. Se ajusta con «Segundos entre travesuras» y «Travesuras como mucho». Al actuar se oye un aviso. Nunca actúa en un examen.

#### Lo que oye el alumno al terminar

Al terminar, Jugar dice si la actividad se completó, las estrellas, cuántos objetivos se hicieron, los puntos, el tiempo y la distancia, los choques y las ayudas pedidas, y los premios nuevos. Las estrellas se ganan por motivos como completar, pedir pocas ayudas, no chocar o explorar todo; los exámenes no dan estrellas. Con «Preguntar al terminar», el alumno puede contestar tres preguntas voluntarias sobre esfuerzo, confianza y agrado.

#### Ejemplos de actividades

Los tres entornos de ejemplo traen actividades hechas. Para usarlas como plantilla, abra el ejemplo, elija la actividad y pulse «Duplicar».

### Alumnos

El menú Alumnos guarda las fichas, las sesiones, los informes y el cuaderno de evaluación real. Esta parte está protegida con una contraseña.

#### La contraseña del profesional

1. La primera vez que entra en Alumnos, Sesiones, Informes o Cuaderno, el programa pide crear la contraseña, de 8 caracteres como mínimo, y repetirla.
2. Después la pide una vez cada vez que se abre el programa.
3. «Bloquear los datos de alumnos» cierra esas ventanas y olvida la clave hasta la próxima vez.
4. «Cambiar la contraseña» vuelve a cifrar todo con la nueva.

**Muy importante: la contraseña no se guarda en ningún sitio. Si la olvida, no hay forma de recuperar los datos cifrados.** Anótela en un lugar seguro.

Con la contraseña se cifran el nombre real, las notas de la ficha, las notas de las sesiones, el texto de las marcas y las observaciones del cuaderno. El alias, las medidas y los recorridos no se cifran. El cifrado usa AES-256-GCM y la clave se deriva de la contraseña: por eso los datos viajan cifrados con la carpeta a otro equipo.

#### Las fichas

Alumnos, «Fichas de alumnos» (Ctrl+L), abre la ventana «Alumnos» con «Buscar por alias», la casilla «Mostrar también los archivados» y la lista con Alias, Perfil, Estilo, Última sesión, Sesiones y Estado.

Para crear una ficha, pulse «Nuevo». La pestaña Ficha tiene:

- «Alias (obligatorio)»: el nombre con el que se le reconoce. **No use el nombre completo**: es lo que viaja por la red y lo que aparece en Jugar;
- «Nombre real (opcional, se guarda cifrado)»;
- «Año de nacimiento (opcional)»;
- «Perfil de movilidad»: «Bastón», «Perro guía», «Baja visión» u «Otro»;
- «Estilo de presentación»: «Infantil», «Juvenil» o «Adulto»;
- «Notas (opcionales, se guardan cifradas)».

El resto de botones: «Editar la ficha», «Archivar o recuperar», «Recompensas», «Lista de trabajo», «Sesiones», «Informes», «Cuaderno real», «Exportar datos», «Borrar por completo», «Cambiar contraseña» y «Bloquear los datos».

#### Ajustes de juego y calcular el paso

La pestaña «Ajustes de juego» de la ficha guarda la forma de moverse, la longitud del paso, el giro, la velocidad, el formato de las direcciones, la unidad de las distancias y el nivel de detalle.

«Calcular el paso» ayuda a medir el paso real del alumno:

1. El alumno camina en línea recta una distancia conocida, por ejemplo 10 metros, a su ritmo, y cuenta los pasos.
2. Escriba «Metros caminados» y «Pasos contados».
3. El programa divide y pone el resultado en el campo del paso. Si sale fuera de lo normal (menos de 0,25 o más de 1,5 metros), avisa.

Estos ajustes llegan a Jugar por la sala de supervisión: cuando Jugar se conecta con el alias de un alumno que tiene ficha, y los datos de alumnos están abiertos, recibe sus ajustes de juego, el estilo, su lista de trabajo y el nivel en que va en cada actividad. Pasa con «Empezar sesión en este ordenador», con «Probar ahora» eligiendo un alumno y con Jugar en otro equipo conectado a la sala. Si cambia la ficha mientras el alumno juega, el cambio le llega al momento, también a mitad de partida. Lo que dice la ficha manda sobre lo que el alumno tenga puesto en Opciones; si después el alumno cambia él mismo una opción, vale la suya hasta que llegue otra vez la ficha. Jugar guarda lo recibido en el perfil del alias, así que se usa también los días que juegue sin conexión. Nunca viaja el nombre real, las notas, el año de nacimiento ni el perfil de movilidad. El Estudio usa además el paso de la ficha para contar en pasos al repetir un recorrido.

#### Lista de trabajo y recompensas

- La «Lista de trabajo» enseña las actividades asignadas con «Asignar a alumnos» en la página Actividades. «Quitar de la lista» no borra la actividad. Jugar la recibe por la sala con la ficha: en «Elegir entorno» sale la primera la opción «Lo que te ha puesto tu profesor», dentro de cada entorno las actividades asignadas van delante, y «Continuar» empieza la primera asignada si el alumno aún no ha jugado nada. Para jugarla, el entorno tiene que estar en ese equipo (por ejemplo, copiado con «Paquete para el alumno»).
- «Recompensas» enseña la colección del alumno y deja dar una a mano («Estrella», «Medalla» u «Objeto»). Las recompensas motivan; no son una medida del aprendizaje.

#### Exportar y borrar los datos de un alumno

- «Exportar datos» guarda un ZIP con todos los datos del alumno: ficha, sesiones, evaluaciones y recompensas, con tablas CSV. **El ZIP no está cifrado**: entréguelo o guárdelo con cuidado.
- «Borrar por completo» dice qué se va a borrar (ficha, sesiones, evaluaciones, recompensas, ficheros de sesión y todas las copias de seguridad de la base), pide escribir el alias y no se puede deshacer. Si quiere conservar algo, exporte antes.

### Supervisión en vivo

La supervisión deja seguir y ayudar a uno o varios alumnos mientras juegan, en el mismo equipo o en otros de la red local. No usa Internet.

#### Abrir la sala

1. Pulse F7. Se abre «Supervisión en vivo».
2. En «Modo de conexión» elija «Solo este ordenador» o «Red local, con conexión cifrada».
3. Pulse «Abrir la sala». El programa anuncia el código de emparejamiento, de 6 cifras, que cambia cada vez. «Copiar el código» lo copia.
4. En red local, «Estado de la sala» dice además la dirección de este ordenador, el puerto y la huella. Dícteselos al alumno.

La primera vez en red tarda unos segundos, porque crea su certificado.

#### Código y huella

- El código no viaja por la red: cada lado demuestra que lo conoce. Tras 5 códigos incorrectos en un minuto, esa dirección queda bloqueada un minuto.
- La huella identifica a la sala. La primera vez que un alumno se conecta en red, Jugar le deletrea una clave: compárenla con la «Huella» del estado de la sala. Si un día cambia, Jugar no se conecta sin preguntar.
- Pueden conectarse hasta 16 alumnos.

#### El alumno se conecta

En Jugar, el alumno elige «Conectar con mi profesor» y después:

- «Buscar salas en la red», que muestra las salas abiertas en red local;
- «Escribir la dirección de la sala», por ejemplo 192.168.1.20, o con el puerto detrás de dos puntos;
- «El profesor está en este mismo ordenador».

Luego escribe el código. Si se corta la conexión, Jugar vuelve a conectarse solo y el juego sigue.

#### Empezar una sesión en este ordenador

Supervisión, «Empezar sesión en este ordenador», elige el alumno (o «Invitado (sin ficha)»), el entorno y la actividad, y abre Jugar ya conectado a una sala local. Al conectarse, Jugar recibe los ajustes de juego, la lista de trabajo y los niveles de la ficha del alumno.

Si un Jugar abierto desde el Estudio se cierra, el Estudio lo dice («El reproductor de Luna se ha cerrado») y lo apunta en los sucesos del alumno. Si se ha cerrado inesperadamente, lo dice siempre, aunque no se hayan elegido los anuncios de conexión, y añade que se puede volver a abrir.

#### Qué se ve y qué se oye

- La lista «Alumnos conectados» tiene las columnas Alias, Estado, Entorno, Actividad, Dónde está, Rumbo, Tiempo activo, Choques, Ayudas y Objetivos. Se actualiza sin mover el foco.
- Para el alumno elegido: «Posición del alumno elegido», «Lo último que ha oído», «Historial de lo que ha oído» y «Sucesos del alumno».
- Un plano pequeño enseña su posición si el entorno del alumno está abierto en el Estudio.
- F6 dice el estado del alumno elegido sin mover el foco.
- No se transmite el sonido del juego por la red. Si el alumno está en el mismo ordenador y se usa el motor de sonido clásico, la casilla «Enviar el sonido del alumno a la segunda salida de audio» deja al profesional oír lo mismo por otros auriculares.

#### Órdenes

Con un alumno elegido en la lista:

- «Pausar o reanudar» (Ctrl+P);
- «Enviar mensaje» (Ctrl+M): el juego le dice la frase;
- «Dar una pista» (Ctrl+I): un texto, o una baliza sonora hacia el objetivo durante 10, 20, 30 o 60 segundos;
- «Recolocar» (Ctrl+R): lo lleva a un punto. Necesita tener abierto su entorno;
- «Cambiar ayudas» (Ctrl+U);
- «Añadir un premio» (Ctrl+E). Necesita tener abierto su entorno;
- «Marcar este momento» (Ctrl+K): una nota que queda en la sesión;
- «Reiniciar» (Ctrl+Mayús+R) y «Terminar» (Ctrl+Mayús+T), con confirmación.

Una prueba de examen en la que el profesional da una pista queda marcada «con ayuda profesional». En una visita narrada, la actividad también cuenta los mensajes del profesional.

Además de estas órdenes, el Estudio envía solo otras dos, sin que el profesional haga nada:

- **la ficha del alumno**, al conectarse y cada vez que cambia (ajustes de juego, lista de trabajo y niveles);
- **«releer la configuración»**, al aceptar o aplicar Preferencias con algún cambio que use Jugar (paquete de sonidos, motor de sonido, volúmenes, voz, movimiento, mando, teclado, idioma, tamaño del texto o alto contraste): cada Jugar conectado vuelve a leer las preferencias y aplica al momento solo lo que ha cambiado, sin reiniciarse ni cortar la partida.

#### Anuncios por voz

Supervisión, «Anuncios por voz», elige qué se dice por voz al profesional: conexiones, choques, ayudas pedidas, premios encontrados, objetivos cumplidos, cruces inseguros, final de la sesión, códigos incorrectos, cambios de espacio y, si se quiere, todo lo que oye el alumno.

#### El cortafuegos de Windows

En red local, el cortafuegos de Windows tiene que dejar a EntornoLab aceptar conexiones en redes privadas. La primera vez que se abre la sala en red, Windows lo pregunta: hay que contestar «Permitir». La sala usa el puerto TCP 47900 (se cambia en Preferencias) y el UDP 47901 para que los alumnos la encuentren.

### Sesiones, informes y cuaderno

#### Las sesiones

Jugar graba cada partida (no el tutorial ni el modo recorrido): la posición cuatro veces por segundo y los sucesos, como choques, ayudas, objetivos y premios. La sesión se guarda en el equipo donde se juega. Cuando el profesional abre los datos de alumnos en ese equipo, las sesiones pasan a la base y se asignan a la ficha con el mismo alias; si no existe, se crea una ficha con solo el alias. Con cada sesión pasan también a la ficha las recompensas ganadas (estrellas, medallas y objetos) y el nivel de ayudas con el que el alumno empezará la próxima vez esa actividad. Si en ese momento el alumno está conectado a la sala, su Jugar recibe la ficha puesta al día.

Alumnos, «Sesiones» (Ctrl+T), enseña la lista con filtros por alumno, entorno, actividad, modo y fechas. Botones: «Buscar con estos filtros», «Ver el detalle», «Repetir el recorrido», «Informes» y «Quitar la sesión». El detalle tiene el resumen, las «Notas del profesional (se guardan cifradas)» y las marcas.

Si el alumno juega en otro equipo, sus sesiones se quedan en la carpeta `data\sessions` de ese equipo. Hoy no hay una orden para traerlas: se incorporan al abrir los datos de alumnos en ese mismo equipo.

#### Repetir el recorrido

«Repetir el recorrido» cuenta lo que hizo el alumno, paso a paso, en una lista: «Empieza en Sala de estar, mirando al este», «Avanza 4,0 metros», «Gira a la izquierda, unos 90 grados», «Choca con la mesa». Con la flecha abajo se recorre. Las distancias se pueden decir en metros o en pasos del alumno. No es una repetición con sonido.

#### Informes

Alumnos, «Informes» (Ctrl+I):

1. Elija el «Tipo de informe»: «Informe de una sesión», «Comparación de varias sesiones», «Evolución de un alumno en el tiempo», «Informe de un examen» o «Evaluación real frente a sesiones en el simulador».
2. Elija el alumno. Para comparar, marque dos o más sesiones con Espacio.
3. Pulse «Generar la vista previa» y lea el resultado.
4. Guarde en texto, HTML o CSV, o pulse «Abrir en el navegador». **Los informes guardados no están cifrados.**

#### Cómo leer las cifras

- **Tiempo activo**: el tiempo de juego, sin las pausas.
- **Tiempo en movimiento** y **tiempo parado**.
- **Distancia recorrida**: la suma de lo andado. Los saltos (volver al inicio, recolocar) no cuentan y se dicen aparte.
- **Velocidad media**: distancia entre tiempo activo.
- **Choques**: cuántos, dónde y con qué.
- **Ayudas**: cuántas de cada tipo.
- **Camino real dividido entre camino más corto**: 1 significa que el alumno anduvo lo mismo que el camino más corto; 2, el doble.
- **Espacios visitados y sin visitar**, con el tiempo en cada uno.
- **Forma de explorar**: «Por el perímetro», «En cuadrícula», «De objeto en objeto» o «Sin patrón reconocible», con una confianza alta, media o baja. Es una descripción aproximada, no una valoración.
- **Puntuaciones del examen**: aciertos, tiempos y lo propio de cada examen.

Lo que no significan:

- Más choques no quiere decir peor orientación: chocar es una forma de explorar.
- Un cociente alto no es un fallo: puede ser exploración.
- Las comparaciones entre entornos o actividades distintas no valen; el informe lo avisa.
- Los umbrales de la forma de explorar son convenciones, no medidas validadas con alumnos.
- Ninguna cifra es un diagnóstico ni equivale a la competencia en el lugar real. Todos los informes lo recuerdan al final.

#### El cuaderno de evaluación real

Alumnos, «Cuaderno de evaluación real» (Ctrl+U), sirve para anotar las pruebas en el lugar físico. El programa no puntúa ni interpreta.

Cada evaluación tiene fecha, lugar, el entorno del simulador relacionado, los días desde el último entrenamiento (se calcula), las rutas hechas con su resultado («Conseguida sin ayuda», «Conseguida con ayuda», «No conseguida» o «No intentada»), el «Nivel de ayuda», el «Tipo de recorrido», las ayudas de movilidad usadas y unas «Observaciones (se guardan cifradas)». Las notas de cada ruta no se cifran: no escriba en ellas datos personales.

El informe «Evaluación real frente a sesiones en el simulador» pone juntas las dos cosas, sin calcular correlaciones.

### Preferencias

Herramientas, «Preferencias» (Ctrl+,). Ctrl+Tab cambia de pestaña. Las preferencias valen para el Estudio y para Jugar.

- **General**: «Idioma», «Enseñar las novedades tras actualizar», «Colores» (los de Windows, claros u oscuros), «Tamaño del texto, en porcentaje», «Alto contraste en el plano y en el reproductor», «Decir «Iniciando» al arrancar», «Minimizar a la bandeja del sistema», «Ocultar en la bandeja al cerrar» y «Empezar oculta en la bandeja».
- **Sonido**: «Motor de sonido», «Perfil de cabeza», «Paquete de sonidos» y su descripción, «Igualar el volumen de los paquetes», «Salida de sonido», «Segunda salida, para el profesional», «Tipo de salida», «Protección auditiva», «Reforzar lo que suena detrás», «Seguimiento de cabeza con OpenTrack» y «Puerto de OpenTrack».
- **Volúmenes**: General, Efectos, Pasos, Ambiente, Sonidos de ayuda, Interfaz, Música de fondo y Voz.
- **Voz**: «Salida de voz» (automática, solo el lector de pantalla, siempre la voz de Windows o sin voz; vale para el Estudio y para Jugar), «Voz de Windows», «Rapidez de la voz de Windows», «Fuerza de la voz de Windows», «Enviar los mensajes a la línea braille», «Un mensaje nuevo corta el anterior», «Mensajes que se guardan para repasar», «Detalle de las descripciones» y «Canales de voz activados» (juego, ayudas, avisos y mensajes del profesional).
- **Juego**: «Forma de moverse», «Longitud del paso», «Giro por pulsación, en grados», «Velocidad en modo continuo, en metros por segundo», «Forma de decir las direcciones», «Unidad de las distancias», «Estilo de los mensajes», «Dibujar el plano en el reproductor», «Pantalla en negro en el reproductor» y «Decir la posición en los menús del reproductor».
- **Teclado y mando**: cómo se cambian las teclas (desde Jugar), «Restablecer el mapa de teclas de serie al aceptar», «Restablecer los botones del mando de serie al aceptar», «Zona muerta de las palancas», «Vibración del mando» y «Fuerza de la vibración».
- **Editor**: «Enseñar el plano gráfico», «Ajustar a la cuadrícula al dibujar y mover», «Separación de la cuadrícula», «Desplazamiento fino», «Paso libre mínimo», «Operaciones que se pueden deshacer», «Minutos entre autoguardados», «Carpeta de los entornos», «Entornos recientes que se recuerdan» y «Olvidar los entornos recientes al aceptar».
- **Supervisión y privacidad**: «Puerto de la sala de supervisión», «Decir lo que le ocurre al alumno», «Oír al alumno por la segunda salida», «Cifrar los datos personales de las fichas» y «Días que se conservan las sesiones» (0, no caducan).
- **Accesibilidad**: «Columnas que se leen en las listas», «Decir el nombre de la columna», «Anunciar el avance de las tareas largas», «Puntos de porcentaje entre anuncios» y «Sonidos de la interfaz del Estudio».
- **Red y registro**: «Buscar actualizaciones al arrancar», «Versiones que se ofrecen», «Mirar también el catálogo de complementos», «Dirección del catálogo de complementos», «Servidor Overpass propio», «Servidor Nominatim propio», «Radio que se propone al importar de OpenStreetMap, en metros» y «Detalle del registro».

Ctrl+H explica cada preferencia. Muchas se aplican al momento; el idioma de los menús ya abiertos cambia al reiniciar.

Las preferencias del Estudio y las de Jugar están en el mismo fichero, y también llegan a un Jugar que ya está abierto, sin reiniciarlo: si está conectado a la sala, al momento (el Estudio le pide «releer la configuración»); si no, en cuanto el alumno vuelve a su menú principal. Ninguno de los dos programas borra al guardar lo que acaba de guardar el otro. Las opciones de juego de cada alumno (movimiento, direcciones, distancias, detalle y estilo) se guardan en su perfil y no cambian las preferencias del Estudio: las de la pestaña Juego son los valores de serie para quien no tiene las suyas.

### Actualizaciones

Ayuda, «Buscar actualizaciones», abre el diálogo «Actualizaciones»:

- «Estado» y «Novedades de la versión nueva»;
- la casilla «Comprobar al arrancar si hay una versión nueva (una vez al día)»;
- «Canal»: «Estable» o «Pruebas (versiones preliminares)»;
- los botones «Comprobar ahora», «Actualizar ahora», «Saltar esta versión» y «Cerrar».

Al actualizar, el programa descarga la versión nueva desde las publicaciones del proyecto en GitHub, comprueba su firma y su integridad, se cierra, se sustituye y se vuelve a abrir. Si la versión nueva no arranca, vuelve sola a la anterior. Nunca toca sus entornos, preferencias, fichas, sesiones ni registros, ni los complementos que usted añadió. Si Jugar está abierto, pide cerrarlo antes.

#### Si la actualización no sale bien

Antes de cerrarse, el programa comprueba que puede escribir en su carpeta, que hay espacio libre en el disco y que las rutas no son demasiado largas. Si algo falla, lo dice en ese momento y no cierra nada. Por ejemplo, si EntornoLab está en «Archivos de programa», el mensaje le pide moverlo a una carpeta suya, como Documentos.

Ya cerrado, antes de cambiar ningún archivo espera a que se cierren el Estudio y todos los Jugar de esa carpeta, también el que abrió la sala. No los cierra a la fuerza. Si alguno sigue abierto pasado un minuto y medio, la actualización se cancela sin tocar nada.

Si el antivirus o el indexador de Windows tienen abierto un archivo, el programa lo vuelve a intentar durante unos segundos. Si otro programa no lo suelta, no se actualiza y la instalación queda como estaba.

Si algo falla a mitad, el programa devuelve cada archivo a su sitio, comprueba que la versión anterior está completa y la abre. Si se va la luz a mitad, al abrir EntornoLab otra vez se deshace lo empezado y se abre la versión anterior. Si ni siquiera llegara a abrirse, ejecute `recuperar.bat`, en la carpeta `data\temp\actualizacion`, y hará lo mismo.

En todos los casos, al volver a abrirse el programa le dice en un mensaje qué ha pasado: por ejemplo, «No se pudo actualizar a la versión 0.1.1 porque otro programa tenía en uso el archivo lib\…. Sigue en la versión 0.1.0 y sus datos no se han tocado». Puede volver a intentarlo desde Ayuda, «Buscar actualizaciones». Si fue la versión nueva la que no arrancó, no se le vuelve a ofrecer sola. Cada paso queda anotado en `data\logs\actualizacion.log`.

De serie, el programa no se conecta a Internet por su cuenta. Las novedades de cada versión se enseñan una vez, la primera vez que se abre la versión nueva, y siempre están en Ayuda, «Novedades de la versión».

### Copias de seguridad y recuperación

- **Copia de recuperación.** Cada 5 minutos, si hay cambios sin guardar, el Estudio guarda una copia aparte (se cambia en «Minutos entre autoguardados»; 0 la desactiva). Si el programa se cierra mal, al abrirlo otra vez pregunta «Recuperar el trabajo», con «Recuperar», «Descartar la copia» y «Cancelar». Tras recuperar, guarde el entorno.
- **Copia del fichero.** Cada vez que guarda, la versión anterior queda al lado con la terminación `.bak`. Si un entorno está dañado y existe su copia, el programa ofrece «Abrir la copia de seguridad».
- **Base de alumnos.** Se copia sola en `data\backups` antes de cambios importantes, como cambiar la contraseña o borrar un alumno.
- **Copia completa.** Copie la carpeta del programa entera, con el programa cerrado.

## Parte 2. Jugar

Jugar es la parte del alumno. Todo lo que aparece en pantalla se dice por voz, y todo se hace con el teclado o con el mando. Esta parte del manual sirve al alumno, a su familia y al profesional.

### Arrancar y elegir quién juega

1. Abra `EntornoLabJugar.exe`. También se abre desde el Estudio con «Probar ahora», F9 o «Empezar sesión en este ordenador».
2. Jugar saluda y dice con qué teclas se mueve uno por el menú.
3. Si es la primera vez, se abre «¿Quién juega?»:
   - la lista de alias que ya han jugado en este equipo;
   - «Soy nuevo: escribir mi alias»: se escribe un alias de hasta 40 caracteres. Mejor un apodo que el nombre y apellidos de verdad;
   - «Jugar como invitado».

Cada alias guarda en ese equipo sus opciones, sus premios y su última actividad. No tiene contraseña.

Para abrir directamente un entorno, se puede arrastrar su fichero `.elab` sobre `EntornoLabJugar.exe`.

### El menú principal

Se titula «EntornoLab. Menú principal». Sus opciones son:

- **«Continuar»**: vuelve a empezar la última actividad jugada. No guarda partidas a medias.
- **«Elegir entorno»**: los entornos de la carpeta `entornos`, de la carpeta de entornos del Estudio y los de ejemplo. Al elegir uno se ven sus actividades y, al final, «Exploración libre». F1 dice la descripción de cada uno.
- **«Mis premios»**: las estrellas, medallas y objetos ganados, del último al primero.
- **«Aprender los sonidos»**: para oír cada sonido y su explicación.
- **«Practicar los controles»**: cada tecla o botón dice para qué sirve, sin que pase nada.
- **«Tutorial»**.
- **«Opciones»**.
- **«Conectar con mi profesor»**: para la supervisión en vivo.
- **«Cambiar de jugador»**: abre «¿Quién juega?».
- **«Ayuda»**: las teclas o botones del juego.
- **«Acerca de»**: versión, autor, licencia, enlaces y avisos.
- **«Salir»**.

Con las flechas arriba y abajo se pasa de opción, con Intro se elige, con Escape se vuelve, con Inicio y Fin se va a la primera y a la última, y con una letra se salta a la opción que empieza por ella. F1 explica la opción. Si está activado, cada opción dice su posición, por ejemplo «3 de 9».

### El tutorial

El tutorial pasa en una sala pequeña con una mesa en el centro y un cuarto con un premio detrás de una puerta cerrada. Enseña, por este orden:

1. avanzar dos pasos;
2. seguir hasta chocar con la mesa («Chocar no es malo: te dice dónde están las cosas»);
3. girar;
4. rodear la mesa;
5. preguntar dónde estás;
6. preguntar qué te rodea;
7. usar el bastón sonoro;
8. abrir la puerta;
9. caminar hacia el sonido del premio hasta llegar a él.

En cualquier momento, la tecla de objetivo (O) repite lo que hay que hacer y la de pista (P) dice hacia dónde ir. El tutorial no se graba como sesión y se puede repetir siempre.

### Entornos grandes

Cuando un entorno es grande (por ejemplo, un barrio importado de OpenStreetMap con cientos o miles de lugares), Jugar lo prepara en segundo plano antes de empezar la partida y va diciendo cómo va: primero «Cargando el entorno…» con cuántos espacios tiene; después cada fase («Preparando los caminos…», «Preparando el sonido…») y, si una fase se alarga, un recordatorio cada pocos segundos. En pantalla se ve «Cargando…», el estado y «Escape: cancelar.». Mientras carga, la ventana sigue respondiendo: Intro o F1 dicen cómo va, y Escape cancela y vuelve a donde estaba. Si el profesor reinicia la actividad o el Estudio actualiza el entorno, pasa lo mismo, y si se cancela se sigue en la partida que había. Ya en la partida, Jugar sigue calculando poco a poco los caminos de alrededor, así que la lista de cercanos y las rutas responden al momento. Un entorno pequeño se abre al instante, sin aviso.

### Cómo se juega

#### Moverse y girar

- **Avanzar y retroceder**: flecha arriba y flecha abajo. En la forma «por pasos» de serie, cada pulsación es un paso; si se mantiene, se sigue andando. Cada paso suena según el suelo.
- **Girar**: flecha izquierda y flecha derecha. De serie, 45 grados por pulsación. Al girar se dice hacia dónde se mira, por ejemplo «Noreste».
- **Paso lateral**: Mayúsculas con flecha izquierda o derecha.
- **Media vuelta**: U.

Formas de moverse, en Opciones, Movimiento:

- «por pasos», la de serie;
- «continuo»: se anda mientras se mantiene la tecla;
- «brújula»: cada flecha es un punto cardinal: arriba va al norte, derecha al este, abajo al sur e izquierda al oeste;
- «por salas»: girar elige una salida del espacio y avanzar la cruza;
- «por aceras, de novedad en novedad»: se anda recto hasta que pasa algo, como un cruce o un bordillo.

#### Chocar y rodear

- Al chocar de frente suena el golpe del material y se dice qué es: «Pared», «Mesa», «Puerta cerrada». El mando vibra.
- Al rozar una pared se resbala por ella: suena el roce y vibra el lado del mando que toca.
- No hay una orden de rodear: se rodea girando y avanzando, como en la realidad.
- Chocar no hace perder: solo cuenta en el resultado.
- En el borde del entorno se dice «Aquí termina el entorno».

#### Puertas

- Intro o Espacio delante de una puerta la abre o la cierra: «Puerta de la cocina: abierta».
- Una puerta cerrada con llave no se puede abrir: suena y se dice.
- Las puertas automáticas se abren solas al acercarse.
- Si no hay nada delante, se dice «No hay nada que usar aquí».

Interactuar también acciona objetos con estados, como abrir un armario, y coge un premio que esté cerca.

#### Escaleras y rampas

- Se entra en una escalera andando hacia su boca. Se dice «Escalera, sube 12 peldaños» y los pasamanos.
- Cada peldaño suena, más agudo según se sube, y el mando da un toque.
- Dentro, interactuar dice cuántos peldaños llevas.
- Al llegar se dice «Has llegado a» y la planta.

#### Ascensor

1. Delante de la puerta del ascensor, pulse Intro para llamarlo. Se oye «llamado. Espera».
2. Cuando llega, se dice «El ascensor ha llegado. Avanza hacia la puerta para entrar».
3. Dentro, gire a la izquierda o a la derecha para elegir planta: se dice cada una.
4. Pulse Intro para ir. Se oye el viaje.
5. Al llegar se dice la planta y «Puerta abierta. Avanza para salir».

#### La calle

- Al pasar de la acera a la calzada suena el bordillo y se dice «Bordillo».
- Los pasos de peatones se anuncian al acercarse: con semáforo sonoro, sin sonido o sin semáforo, y si tienen pulsador o isleta.
- Los cruces se describen por su forma: en te, en cruz, rotonda.
- Una acera que el mapa no tenía y que el programa ha supuesto se avisa al pisarla.
- Las paradas de autobús son objetos para orientarse. Los autobuses no paran.

#### Semáforos y coches

- Los semáforos sonoros suenan distinto en verde, en intermitente y en rojo.
- Con el pulsador, Intro junto al poste acorta la espera del rojo.
- Si las calles tienen tráfico, pasan coches, motos y autobuses. Paran en el verde de los peatones y ceden el paso en los pasos sin semáforo.
- Cruzar en rojo o con coches pasando se avisa («Has cruzado con coches pasando») y queda registrado, pero no hace perder.

Recuerde: es un simulador. No sirve para decidir un cruce real.

### Las ayudas

Cada ayuda es una pregunta que el alumno puede hacer. Una actividad puede prohibir alguna o limitar sus usos; entonces se oye «Esa ayuda no está disponible en esta actividad» o «Ya no quedan usos de esa ayuda».

- **Dónde estoy** (C): dice el espacio, la planta si hay varias y hacia dónde miras. Nunca dice la ruta. Pulsada dos veces seguidas, añade la descripción del lugar, el suelo y cuántas puertas tiene.
- **Mirar delante, a la izquierda, detrás y a la derecha** (W, A, S y D): dicen lo que hay en esa dirección y a qué distancia, hasta 20 metros. Por ejemplo: «A tu derecha: puerta abierta hacia Cocina a 2 metros; Pared a 4 metros». Mirar delante añade lo que hay cerca, delante.
- **Alrededor** (Q): describe por partes lo que te rodea: delante, a la derecha, detrás y a la izquierda.
- **Lista de lo cercano** (Tab y Mayús+Tab): recorre lo que hay cerca, de lo más cercano a lo más lejano andando. Cada cosa suena desde su sitio: «Mesa, a 3 metros, a las 2».
- **Lugares descubiertos** (L): los lugares que ya conoces y cuáles no has explorado del todo.
- **Brújula** (K): suena el norte desde el norte y se dice hacia dónde miras.
- **Bastón sonoro** (B): una serie de tonos, uno por cada paso, recorre lo que hay delante. Cada tono cambia si cruza una puerta, un bordillo o un escalón, y al final suena lo que hay. Contar los tonos es contar los pasos que faltan. Si se mantiene, se repite. No detecta lo que está colgado.
- **Eco** (E): un chasquido cuyo eco da idea del tamaño del lugar y de lo cerca que están las paredes.
- **Objetivo** (O): repite lo que hay que hacer.
- **Pista** (P): da una ayuda para el objetivo; cada vez dice algo más. Según la actividad, enciende un rato la baliza.
- **Confirmar** (M): en un examen o al localizar un lugar, dice que ya has llegado, que miras hacia ahí o que esa es tu respuesta. Si hay una pregunta, abre sus respuestas. Si no hay nada que confirmar, lo dice.
- **Volver al inicio** (Inicio): lleva al punto de partida.
- **Repetir y repasar** (F2, F3 y Mayús+F3): repite el último mensaje o recorre los anteriores.
- **Callar la voz** (Control).

Además:

- **La baliza** es un sonido que sale del destino. Suena distinto si miras hacia él, si queda detrás, si estás cerca o si has llegado. Solo la encienden la actividad o el profesor.
- **Los avisos automáticos** dicen, según el nivel de detalle, las escaleras, ascensores, pasos de peatones, puertas y objetos que tienes cerca. Con «Cuánto cuenta el juego» en 0 no se dice nada.

### Entender los sonidos

En el menú principal, **«Aprender los sonidos»** enseña cada sonido por grupos: orientación (balizas, bastón, brújula y eco), pasos sobre cada suelo, choques y roces, puertas, escaleras y ascensor, premios y logros, la calle, cosas que suenan en los lugares, ambientes y menús. Intro hace sonar el sonido y F1 dice qué significa.

Es buena idea pasar por aquí antes de jugar, sobre todo para la baliza y el bastón sonoro. Los sonidos se oyen con el paquete elegido en Opciones.

### Juegos, premios y exámenes

- En «Elegir entorno», cada actividad dice su tipo. Los exámenes se anuncian como «examen».
- Al empezar, la actividad dice qué hay que hacer. Con O se repite.
- Los premios suenan desde su sitio: unos se oyen de lejos, otros solo de cerca, y otros están dentro de un objeto y hay que usarlo para encontrarlos. Al encontrar uno se oye, por ejemplo, «¡Has encontrado la llave!».
- En un examen no hay pistas ni se dice si se acierta. Cuando creas que has llegado o que miras hacia el lugar pedido, pulsa M (Confirmar). Si la prueba es una pregunta, se abren sus respuestas: elige una con las flechas y acéptala con Intro. Después de cada prueba solo se oye «Anotado».
- Si el profesor está conectado, puede enviar mensajes, pistas o premios nuevos: se oyen como mensajes del profesor.

### La pausa y el final

- **Escape** abre la pausa: «Continuar», «Recordar el objetivo», «Repetir las instrucciones», «Opciones rápidas», «Volver al inicio», «Ayuda» y «Abandonar la actividad» (o «Terminar la exploración»). Con la pausa se para el tiempo. Si la ventana pierde el foco, el juego se pausa solo.
- **Al terminar** se dice el resultado: si se completó, las estrellas, lo conseguido, los puntos, el tiempo, la distancia, los choques, las ayudas y los premios nuevos. Después se puede oír otra vez, responder unas preguntas si la actividad lo pide, repetir, elegir otra actividad o volver al menú.

### Opciones de Jugar

Las opciones se cambian con las flechas izquierda y derecha, se oyen al momento y se guardan solas, también en mitad de una partida.

- **Sonido**: «Motor de sonido», «Oigo por» (auriculares o altavoces), «Perfil de cabeza», «Paquete de sonidos», «Salida de sonido», los volúmenes (general, efectos, tus pasos, ambiente, ayudas, menús, música y voces grabadas), «Protección auditiva», «Apagar un poco lo que suena detrás», «Seguimiento de cabeza» y «Centrar el seguimiento de cabeza».
- **Voz y braille**: «Habla» («automática», «solo tu lector de pantalla», «siempre la voz de Windows» o «nadie: sin voz»), «Voz de Windows», su velocidad y su volumen, «Mensajes en la línea braille», «Un mensaje nuevo corta al anterior», «Cuánto cuenta el juego» (de «0, solo sonidos» a «3, todo») y «Decir la posición en los menús».
- **Movimiento**: «Forma de moverse», «Longitud del paso» (de 25 a 150 centímetros), «Cada giro» (15, 30, 45 o 90 grados), «Velocidad al andar seguido», «Las direcciones se dicen» (como un reloj, por lados, por puntos cardinales o en grados) y «Las distancias se dicen en» (metros o pasos).
- **Mando**: el mando conectado, «Zona muerta de las palancas», «Vibración», «Fuerza de la vibración», «Probar la vibración» y las órdenes para cambiar los botones.
- **Teclado**: «Cambiar las teclas para jugar», «Cambiar las teclas de los menús», «Oír las teclas que he cambiado» y «Restablecer las teclas de serie».
- **Estilo e idioma**: «Estilo» (infantil, juvenil o adulto) e «Idioma».
- **Pantalla**: «Ver el plano mientras juego», «Pantalla en negro», «Alto contraste» y «Tamaño del texto».

Desde la pausa, «Opciones rápidas» da lo más usado: el volumen general y el del ambiente, cuánto cuenta el juego, las direcciones, las distancias y el paquete de sonidos.

### Teclado y mando

Las tablas completas están en la lista de teclas (Ctrl+F1 en el Estudio). Resumen de las teclas de serie para jugar: flechas para andar y girar, Intro o Espacio para interactuar, C dónde estoy, W, A, S y D para mirar, Q alrededor, Tab lista de lo cercano, L lugares, K brújula, B bastón, E eco, O objetivo, P pista, M confirmar, F2 repetir, Control callar, Inicio volver al inicio, F1 ayuda y Escape pausa.

Con el mando, la palanca izquierda anda y gira, A o Equis interactúa, X o Cuadrado dice dónde estás, Y o Triángulo mira delante, el gatillo derecho es el bastón sonoro y el botón Menú u Options pausa. El gatillo izquierdo, mantenido, da a cada botón una segunda función.

#### Cambiar una tecla

1. Abra Opciones, Teclado, «Cambiar las teclas para jugar» (o «de los menús»).
2. Elija la acción y pulse Intro. Se oye «Pulsa la tecla que quieres usar. Escape cancela».
3. Pulse la tecla nueva. Si ya hacía otra cosa, las dos se intercambian y se dice.

No se pueden cambiar Escape, Intro, F1 ni las teclas de la pantalla. «Restablecer las teclas de serie» lo deja todo como venía.

#### Cambiar un botón del mando

1. Abra Opciones, Mando, «Cambiar los botones para jugar», «Cambiar los botones con la segunda función» o «Cambiar los botones de los menús».
2. Elija el botón y pulse aceptar. Se abre la lista de acciones.
3. Elija la acción. Si otro botón la tenía, se intercambian.

#### Practicar los controles

En el menú principal, «Practicar los controles» dice qué hace cada tecla o botón al pulsarlo, sin que pase nada. Respeta lo que se haya cambiado. Se sale pulsando Escape dos veces seguidas.

### Conectar con el profesor

1. En el menú principal, elija «Conectar con mi profesor».
2. Elija «Buscar salas en la red», «Escribir la dirección de la sala» o «El profesor está en este mismo ordenador».
3. Escriba el código que le diga el profesor y pulse Intro.
4. La primera vez en red, Jugar deletrea una clave. Compárela con la que ve el profesor en su pantalla.

Si no encuentra la sala, pida la dirección al profesor y escríbala. Si se corta, Jugar vuelve a conectarse solo. Para salir de la sala, vuelva a «Conectar con mi profesor» y elija «Desconectar».

### La pantalla y la baja visión

- **F5** muestra u oculta el plano de la planta: vista desde arriba, a escala, con el norte arriba. Las paredes son trazos gruesos, las puertas cerradas un trazo doble, las ventanas un trazo discontinuo, los objetos su forma con una letra, los premios un rombo y el alumno una flecha que apunta adonde mira. No hay destellos ni animaciones.
- **F6** pone la pantalla en negro, para quien no la usa o no quiere pistas visuales. Vuelve a pulsar para verla.
- En Opciones, Pantalla, «Alto contraste» usa blanco y amarillo sobre negro, y «Tamaño del texto» lo agranda hasta el 300 por ciento.
- Siempre se ven el título y las últimas líneas de lo que ha dicho la voz.

### Consejos para familias

- Siga el entorno y las actividades que haya preparado el profesional. Jugar no sustituye las clases de orientación y movilidad.
- Sesiones cortas, de 15 a 30 minutos, con descansos. Mejor varios días seguidos que una tarde larga.
- Use auriculares cómodos y un volumen bajo. Deje activada la protección auditiva.
- Empiece por el tutorial y por «Aprender los sonidos».
- Deje que el alumno choque y explore. Chocar es información, no un error.
- Pregunte en voz alta: «¿Dónde está la cocina?», «¿Por dónde saldrías?». Así se comprueba la imagen del lugar.
- Para los más pequeños, el estilo infantil celebra los logros y trae un compañero de juego.
- Después de jugar, si se puede, visite el lugar real con el profesional.
- No use Jugar para decidir si es seguro cruzar una calle real.

## Parte 3. El sonido

### Auriculares y altavoces

El sonido 3D se oye mejor con auriculares estéreo, bien puestos: izquierdo a la izquierda. Con ellos, los sonidos se sitúan delante, detrás, a los lados y, con el motor de serie, arriba y abajo. Con altavoces, elija «Oigo por: altavoces» en Jugar, o «Tipo de salida: Altavoces» en Preferencias del Estudio: el sonido pasa a ser un panorama de izquierda a derecha.

La distancia se oye como en la realidad: un sonido a 2 metros suena a la mitad que a 1 metro. Mientras habla la voz, el ambiente baja un poco.

### Motores de sonido

El motor de sonido se elige en Jugar, Opciones, Sonido, «Motor de sonido», o en Preferencias, Sonido. Si el elegido falla, se usa el siguiente.

- **«Binaural (OpenAL Soft, para auriculares)»**, el de serie. Sitúa delante, detrás, arriba y abajo, y añade el eco de cada lugar (una habitación, un pasillo, un baño, una nave o la calle suenan distinto). Elíjalo con auriculares.
- **«Clásico (mezcla propia, admite segunda salida)»**. Sitúa a izquierda y derecha y algo de delante y detrás, sin arriba ni abajo ni eco del lugar. Es el único que deja al profesional oír lo mismo por una segunda salida, con el alumno en el mismo ordenador.
- **«Estéreo simple (equipos modestos y altavoces)»**. Panorama sencillo. Para equipos muy modestos o altavoces.
- **«3D con BASS (panorama sin HRTF; solo uso no comercial)»**. Panorama 3D, sin arriba ni abajo ni eco. Úselo si OpenAL da problemas.

Aviso sobre BASS: la biblioteca BASS, de Un4seen Developments, no es software libre y es gratuita solo para uso no comercial. Para un uso comercial hace falta su licencia de pago, o bien elegir otro motor y borrar el fichero `bass.dll`. El resto del programa funciona igual sin ella.

### Perfiles de cabeza

Cada persona oye la dirección de los sonidos según la forma de su cabeza y sus orejas. Con el motor binaural se puede elegir el «Perfil de cabeza»: «la integrada», «maniquí con oreja normal», «maniquí con oreja grande», «cabeza artificial de estudio» y «persona 1» a «persona 4». Pruebe varios con «Aprender los sonidos», por ejemplo con la baliza, y quédese con el que mejor distinga delante de detrás.

### Seguimiento de cabeza con OpenTrack

Con un sensor o una cámara web y el programa libre OpenTrack, el giro de la cabeza se suma al del personaje: los sonidos se quedan en su sitio al mover la cabeza.

1. En OpenTrack, elija la salida «UDP over network», con la dirección 127.0.0.1 y el puerto 4242.
2. En Jugar, active Opciones, Sonido, «Seguimiento de cabeza».
3. Mire al frente y elija «Centrar el seguimiento de cabeza».

El puerto se cambia en Preferencias del Estudio, «Puerto de OpenTrack». Si no llegan datos durante un segundo, se considera que la cabeza mira al frente. Esta función no se ha probado con un sensor real.

### Protección auditiva

Activada de serie. Pone un techo al volumen de cada sonido y de la mezcla, hace graduales las subidas (el sonido arranca en silencio) y silencia todo si el juego se queda colgado. Si se desactiva, la protección no desaparece: solo se relaja. Úsela siempre con auriculares.

### Salidas de sonido y segunda salida

- «Salida de sonido» elige por dónde suena Jugar. De serie, «la de Windows», y el programa la sigue si Windows cambia de salida, por ejemplo al conectar unos auriculares.
- La «Segunda salida, para el profesional» sirve para que el profesional oiga lo mismo que el alumno, en el mismo ordenador, por otros auriculares. Solo funciona con el motor clásico. Se elige en Preferencias, Sonido, y se activa con «Oír al alumno por la segunda salida», en Supervisión y privacidad, o con la casilla de la ventana de supervisión.

### Paquetes de sonidos

Un paquete de sonidos es una colección completa de los sonidos del juego. Hay tres:

- **«Sintético (por defecto)»**: sonidos limpios, cortos y muy distintos entre sí, sintetizados uno a uno.
- **«Natural»**: instrumentos acústicos y objetos con cuerpo, como marimba, xilófono y campanas, y pasos, golpes y puertas hechos con modelos físicos.
- **«Grabado»**: grabaciones reales de uso libre para pasos, golpes, puertas, agua, tráfico y ambientes. Es parcial: lo que no trae suena con los de serie. A propósito, no cambia los avisos que llevan información, como la baliza, el bastón, la brújula, los semáforos o los peldaños.

Para cambiar de paquete, en Jugar elija Opciones, Sonido, «Paquete de sonidos», con las flechas izquierda y derecha. Intro hace sonar una muestra. En el Estudio está en Preferencias, Sonido. El cambio se oye al momento. «Igualar el volumen de los paquetes», en Preferencias, lleva todos al nivel de los de serie.

#### Crear un paquete propio

1. Cree una carpeta dentro de `data\sounds`. Su nombre solo puede tener minúsculas, cifras, guion y guion bajo.
2. Copie dentro los sonidos que quiera cambiar, con el mismo nombre y la misma subcarpeta que en la carpeta `por_defecto`, por ejemplo `puerta\abrir.ogg`. Valen OGG, FLAC y WAV.
3. Si quiere, añada un fichero `pack.json` con el nombre, la descripción, el autor y la licencia, y un `CREDITOS.txt` con la procedencia de cada sonido.
4. El paquete aparece en la lista sin reiniciar. Lo que no traiga suena con los de serie.

Consejos: los sonidos que se sitúan en el espacio deben ser mono; los bucles deben empalmar sin chasquido; un suelo necesita sus seis pasos; y los avisos que llevan un código (por ejemplo, el número de pitidos del bastón o las notas de la brújula) deben conservarlo o no incluirse. El detalle está en el fichero `LEEME.md` de la carpeta `data\sounds`.

### Voz y braille

- Quién habla se elige en Jugar, Opciones, Voz y braille, «Habla», o en Preferencias del Estudio, pestaña Voz, «Salida de voz». La preferencia es la misma para el Estudio y para Jugar:
  - **Automática** (de serie): el lector de pantalla abierto y, si no hay ninguno, la voz de Windows.
  - **Solo el lector de pantalla**: si no hay ningún lector abierto, no se habla; nunca se usa la voz de Windows. Si el lector se abre con Jugar en marcha, se nota en un par de segundos.
  - **Siempre la voz de Windows**: aunque haya lector, con la voz, la velocidad y el volumen elegidos.
  - **Nadie (sin voz)**: no se habla nunca. Los mensajes se siguen guardando en el historial (F2 y F3), Jugar los escribe abajo en la pantalla, el Estudio en la barra de estado y, si hay un lector abierto y está activado el braille, llegan a la línea braille. Al elegirlo en Jugar suena un aviso y se escribe en la pantalla cómo volver a la voz.
- **Control+F12**, en cualquier pantalla de Jugar, vuelve a la voz automática. Sirve si alguien se ha quedado sin voz y no puede llegar a las opciones a oídas. F12 no se puede asignar a otra acción.
- Con «Mensajes en la línea braille», cada mensaje se envía también a la línea braille, a través del lector.
- Con «Un mensaje nuevo corta al anterior» desactivado, los mensajes se dicen uno detrás de otro. Es útil con línea braille o para personas sordociegas.
- F2 repite el último mensaje y F3 recorre los anteriores. El historial guarda 50 mensajes de serie.
- En Preferencias del Estudio, «Canales de voz activados» puede silenciar un tipo de mensaje (juego, ayudas, avisos o mensajes del profesional). Lo silenciado queda en el historial.

## Parte 4. Datos, ayuda y referencia

### Privacidad y datos

EntornoLab no tiene cuentas, ni nube, ni telemetría. Todo se guarda en la carpeta `data` junto al programa.

Qué se guarda y dónde:

- `entornos`: los entornos (ficheros `.elab`).
- `config`: las preferencias, las opciones de cada alias de Jugar, los datos de la contraseña (nunca la contraseña), el certificado de la sala y las salas conocidas.
- `db`: la base de seguimiento: fichas, sesiones incorporadas, evaluaciones y recompensas.
- `sessions`: las sesiones de Jugar que aún no se han incorporado. No están cifradas y solo llevan el alias.
- `backups`: copias de la base. `logs`: los registros. `cache` y `temp`: datos temporales.

Qué se cifra: con la contraseña del profesional, el nombre real y las notas de la ficha, las notas de las sesiones, el texto de las marcas y las observaciones del cuaderno. No se cifran el alias, el año de nacimiento, los ajustes, los recorridos ni las medidas. Las exportaciones ZIP y los informes guardados no están cifrados. Para cifrar todo el disco, use las herramientas de Windows.

Qué conexiones hace, y cuándo:

- **Actualizaciones y catálogo de complementos**: solo si usted lo pide, o si dio permiso para comprobarlo al arrancar. Se conecta a GitHub. No envía datos personales: solo pide ficheros y se identifica como «EntornoLab» y su versión.
- **OpenStreetMap**: solo al importar, y tras avisar la primera vez. Envía el texto buscado o las coordenadas del recuadro.
- **Supervisión**: solo en el propio equipo o en la red local, cifrada en red. Por la sala viajan el alias, la posición, lo que oye el alumno, los sucesos, las órdenes y, de la ficha, solo lo necesario para jugar (ajustes de juego, estilo, lista de trabajo y niveles); nunca el nombre real, las notas, el año de nacimiento ni el perfil de movilidad.

Los registros de `data\logs` no guardan alias, nombres, notas ni textos de los alumnos.

Para exportar todos los datos de un alumno, use «Exportar datos» en su ficha. Para borrarlos, «Borrar por completo». Las sesiones pueden caducar solas con «Días que se conservan las sesiones».

### Accesibilidad

- El Estudio usa controles estándar de Windows con etiquetas, letras de acceso y ayuda por control (Ctrl+H).
- Las listas de varias columnas se leen columna a columna con las flechas izquierda y derecha, o con Ctrl y un número.
- Las tareas largas anuncian su avance y se pueden cancelar con Escape.
- Nada depende solo del color: el plano gráfico usa trazos y formas, y todo lo del plano se puede hacer sin él.
- Jugar dice todo lo que muestra, se maneja entero con teclado o mando, y tiene alto contraste, texto grande y pantalla en negro.
- La interfaz está en español y en inglés, igual que este manual y la lista de teclas. El idioma se elige en Preferencias; por defecto, el de Windows.

El diseño sigue pautas de accesibilidad para lectores de pantalla, pero no se ha comprobado a mano con cada lector. Si algo no se lee bien, avise (apartado «Avisar de un fallo»).

### Solución de problemas

#### No se oye nada en Jugar

1. Compruebe el volumen de Windows y que los auriculares están conectados.
2. En Jugar, Opciones, Sonido, revise «Volumen general» y «Salida de sonido» (pruebe «la de Windows»).
3. Cambie de «Motor de sonido». Si el binaural no suena, pruebe «Clásico» o «Estéreo simple».
4. Compruebe que existe `data\bin\openal\soft_oal.dll`. Si falta, vuelva a descomprimir el programa.

#### El lector lee de más o de menos

- Si Jugar habla demasiado, baje «Cuánto cuenta el juego» a «1, lo esencial».
- Si se pisan los mensajes, desactive «Un mensaje nuevo corta al anterior», o al revés.
- Si el lector y Jugar hablan a la vez, elija «Habla: siempre la voz de Windows».

#### Jugar o el Estudio no hablan

- Pulse Control+F12 en Jugar: vuelve a la voz automática.
- Mire «Habla» en Jugar, Opciones, Voz y braille, o «Salida de voz» en Preferencias del Estudio. Con «nadie» no se habla nunca; con «solo el lector de pantalla», solo si hay un lector abierto.
- Lo que no se ha oído sigue en el historial: F2 repite el último mensaje y F3 los anteriores.
- En el Estudio, si las listas leen demasiado, cambie en Preferencias, Accesibilidad, «Columnas que se leen en las listas» y «Decir el nombre de la columna».

#### El mando no responde

1. Desconéctelo y vuelva a conectarlo con Jugar abierto. Jugar dice su nombre al detectarlo.
2. Mire en Opciones, Mando, si aparece «Mando conectado».
3. Si el personaje se mueve solo, suba «Zona muerta de las palancas».
4. Use «Practicar los controles» para oír qué hace cada botón.

Solo se admiten mandos de Xbox y de PlayStation. Los mandos se han probado con pruebas automáticas, no con mandos físicos.

#### No conecta la supervisión

- Compruebe que la sala está abierta y que el código es el último: cambia cada vez que se abre.
- Para otro equipo, el modo tiene que ser «Red local, con conexión cifrada» y los dos equipos tienen que estar en la misma red.
- La primera vez, conteste «Permitir» al aviso del cortafuegos de Windows. Si contestó que no, cambie el permiso de EntornoLab en el cortafuegos para las redes privadas.
- Si «Buscar salas en la red» no encuentra nada, escriba la dirección que dice el estado de la sala.
- Tras cinco códigos incorrectos, espere un minuto.

#### Un entorno no se abre

- Si el fichero está dañado y tiene copia `.bak`, el programa ofrece «Abrir la copia de seguridad».
- Si el programa se cerró mal, al abrirlo ofrece recuperar el trabajo.
- En Jugar, un entorno dañado aparece como «no se puede abrir».

#### Paquete de diagnóstico y registros

Si avisa de un fallo, adjunte el paquete de diagnóstico:

- En el Estudio, Ayuda, «Generar paquete de diagnóstico». Se prepara en segundo plano; al terminar, un mensaje dice cómo se llama el fichero y en qué carpeta está (`data\diagnostico`) y ofrece «Abrir la carpeta».
- En Jugar, en la ayuda (la lista de teclas), la última línea es «Generar paquete de diagnóstico». Al terminar dice el nombre del fichero y la carpeta.

El paquete es un ZIP con los últimos registros del Estudio y de Jugar, `incidencias.log`, los avisos de cierre inesperado y `sistema.txt` (versión del programa, de Windows y de Python, y los lectores de pantalla abiertos). No lleva la configuración, las fichas, las sesiones, los entornos ni las contraseñas, y en las rutas el nombre de su cuenta de Windows se cambia por `<usuario>`.

Herramientas, «Abrir la carpeta de registros», abre `data\logs` por si prefiere adjuntar un registro suelto: el fichero `sesion_` más reciente (o el `jugar_` más reciente si falló Jugar) y `arranque_fallido.log` si existe, junto con la versión que aparece en Ayuda, «Acerca de». Los registros no contienen datos de los alumnos.

#### Comprobar Jugar sin ventana ni sonido

Para saber si Jugar arranca, si carga el sonido binaural o si un entorno tiene todos sus complementos sin abrir la tarjeta de sonido ni ninguna ventana, se le puede dar un guion: un fichero de texto con los pasos que daría el alumno. Desde la carpeta del programa, en una ventana de órdenes:

```
EntornoLabJugar.exe --guion comprobar.json --informe informe.json data\ejemplos\vivienda-de-ejemplo.elab --actividad busqueda-del-tesoro
```

Un `comprobar.json` sencillo:

```json
{"motor": "openal", "pasos": [{"hasta": "partida"}, {"comprobar": "hrtf"}, {"comprobar": "sin_complementos_que_faltan"}, {"salir": true}]}
```

Jugar no se ve ni suena: sigue los pasos, se cierra y deja `informe.json` con lo que habría dicho, el motor de sonido que ha quedado y si el sonido binaural (HRTF) se ha activado, los paquetes de sonidos y los complementos que faltan. Termina con 0 si todo fue bien y con 4 si falló alguna comprobación. El motor se abre «en memoria», sin tocar la tarjeta, y no cambia sus preferencias. Para no ensuciar sus datos, ponga antes `set APP_DATA_DIR=C:\una\carpeta\de\pruebas`. Puede adjuntar el informe al avisar de un fallo.

#### No recuerdo la contraseña

No hay forma de recuperar los datos cifrados. Los datos no cifrados (alias, sesiones, medidas) siguen en la base, pero el programa la abre solo con la contraseña. Si tiene una copia de la carpeta `data` de antes de cambiar la contraseña, sus datos se abren con la contraseña de entonces.

### Glosario de orientación y movilidad

- **Alrededor**: descripción de lo que rodea a la persona, por partes, sin moverse.
- **Autofamiliarización**: conocer un lugar nuevo explorándolo uno mismo, con un método.
- **Baliza sonora**: un sonido que sale del destino para guiarse hacia él.
- **Bastón**: el bastón largo blanco, que detecta lo que hay en el suelo delante. No detecta lo que está colgado.
- **Bordillo**: el escalón entre la acera y la calzada.
- **Cociente de camino**: el camino andado dividido entre el más corto posible.
- **Ecolocalización**: percibir el espacio por el eco de un sonido propio, como un chasquido.
- **Exploración en cuadrícula**: recorrer un espacio en franjas paralelas.
- **Exploración por el perímetro**: recorrer primero el borde de un espacio, siguiendo las paredes.
- **Línea guía**: un borde continuo que se sigue para no perderse: una pared, un bordillo, una franja de pavimento táctil.
- **Mapa mental o cognitivo**: la imagen del lugar que se forma una persona: qué hay y cómo se relaciona.
- **Obstáculo en voladizo o a la altura de la cabeza**: lo que sobresale por encima del alcance del bastón.
- **Pavimento táctil**: el suelo con botones (aviso, por ejemplo antes de un paso de peatones) o con rayas (dirección).
- **Punto de referencia**: algo fijo y reconocible que ayuda a saber dónde se está: un sonido, un olor, un cambio de suelo.
- **Rumbo**: hacia dónde se mira, en grados o en puntos cardinales.
- **Ruta inversa**: volver por el mismo camino que se vino.
- **Semáforo sonoro**: el que emite un sonido distinto cuando los peatones pueden cruzar.
- **Transferencia**: usar en el lugar real lo aprendido en el simulador.

### Licencias y créditos

EntornoLab, Copyright 2026 Héctor J. Benítez Corredera, es software libre con la Licencia Pública General de GNU, versión 3 o posterior, con un permiso adicional para usarlo junto a la biblioteca BASS. Se distribuye sin ninguna garantía.

- Las bibliotecas de terceros conservan sus licencias. La lista y los textos están en la carpeta `data\docs\licencias`, con su `LEEME.md`.
- OpenAL Soft, el motor binaural de serie, tiene licencia LGPL.
- BASS es gratuita solo para uso no comercial (apartado «Motores de sonido»).
- Los paquetes de sonidos «Sintético» y «Natural» tienen la misma licencia que EntornoLab. Las grabaciones del paquete «Grabado» son de dominio público (CC0); el detalle está en su `CREDITOS.txt`.
- Los complementos de serie tienen la licencia que dice cada uno en su ficha (Herramientas, «Complementos instalados», «Detalles»).
- Los datos importados de OpenStreetMap son de los colaboradores de OpenStreetMap, con licencia ODbL.

EntornoLab se inspira en estudios y proyectos sobre aprendizaje de lugares por sonido, sin que sus autores lo avalen. Las referencias principales:

- Sánchez, Sáenz, Pascual-Leone y Merabet (2010). Enhancing Navigation Skills through Audio Gaming.
- Merabet, Connors, Halko y Sánchez (2012). Teaching the Blind to Find Their Way by Playing Video Games.
- Connors, Chrastil, Sánchez y Merabet (2014). Action video game play and transfer of navigation and spatial cognition skills in adolescents who are blind.
- Connors, Chrastil, Sánchez y Merabet (2014). Virtual environments for the transfer of navigation skills in the blind.
- Lahav, Schloerb y Srinivasan (2015). Rehabilitation program integrating virtual environment.
- Bowman y Liu (2017). Entrenamiento virtual para cruzar calles con baja visión.
- Giudice y otros (2020). Aprendizaje de planos con mapas de audio y vibración.
- Façanha, Darin, Viana y Sánchez (2020). Revisión sistemática de entornos virtuales para la orientación de personas ciegas.

### Avisar de un fallo o proponer una mejora

1. En el Estudio, elija Ayuda, «Avisar de un fallo». En Jugar, elija «Acerca de» y «Avisar de un fallo o proponer una mejora». Se abre la página de incidencias del proyecto: <https://github.com/hxebolax/EntornoLab/issues>.
2. Diga qué hacía, qué esperaba y qué pasó, la versión (Ayuda, «Acerca de») y su lector de pantalla.
3. Adjunte el paquete de diagnóstico (Ayuda, «Generar paquete de diagnóstico»), como se explica en «Paquete de diagnóstico y registros».

**Nunca publique datos de alumnos** (nombres, notas, sesiones o informes) en una incidencia. Un problema de seguridad o de privacidad no se publica: se avisa en privado, como explica el fichero SECURITY.md del proyecto.

### Invitar a un café al autor

EntornoLab es gratuito. Si le resulta útil y quiere apoyar su desarrollo, en el Estudio elija Ayuda, «Invítame a un café si te gusta mi trabajo», o en Jugar, «Acerca de». Se abre la página de donaciones del autor: <https://www.paypal.com/paypalme/hjbcdonaciones>. Gracias.
