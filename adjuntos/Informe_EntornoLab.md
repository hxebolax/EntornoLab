# EntornoLab: informe previo completo

Fecha: 26 de noviembre de 2026.
Estado: informe previo al desarrollo. No se ha escrito todavía ni una línea del producto.

## 1. Cómo leer este informe

Este documento responde a una pregunta: qué vas a tener cuando el proyecto termine, y en qué me baso para proponerlo.

Está organizado así:

- Apartados 2 y 3: resumen y qué se ha revisado.
- Apartados 4 a 8: lo que he encontrado (ciencia, repositorios, tus dos proyectos, tus agentes, productos parecidos).
- Apartados 9 a 20: el producto que propongo, función por función.
- Apartados 21 a 25: plan por fases, pruebas, riesgos, decisiones que necesito de ti y referencias.

Sobre la fiabilidad de lo que afirmo:

- Los 12 repositorios, ReconocedorCiudades, JuegoGTA y tus agentes se han leído directamente en disco, en solo lectura. No se ha ejecutado código de terceros ni se ha instalado nada.
- No se han ejecutado tus pruebas ni tus programas. Las cifras de pruebas son las que declaran tus propios documentos o un recuento de funciones.
- De las 14 fuentes científicas, 7 se leyeron a texto completo y el resto solo en resumen. Lo indico en cada una.
- Las versiones de bibliotecas se consultaron hoy en PyPI y GitHub. Lo que no se pudo comprobar va marcado como «sin verificar».
- Nada de lo que se propone está probado con NVDA, JAWS ni con un mando real. Eso se comprobará durante el desarrollo y lo diré cuando esté hecho, no antes.

## 2. Resumen: qué vas a tener

EntornoLab será una aplicación de escritorio para Windows, portable y sin conexión, en español, con dos caras que comparten un mismo motor:

1. **Para el profesional de rehabilitación.** Un estudio de creación donde construye entornos interiores y exteriores sin programar y sin ratón, define actividades, juegos y exámenes, lleva la ficha de cada alumno, supervisa en vivo una sesión y consulta informes.
2. **Para el alumno.** Un reproductor tipo audiojuego en primera persona, con sonido 3D por auriculares, que se maneja con teclado o con mando de Xbox o PlayStation, pensado para aprender un lugar jugando.

Lo que podrá construir el profesional:

- Interiores de cualquier tamaño: una habitación, una vivienda, una planta, o un edificio de varias plantas con escaleras, rampas y ascensores.
- Exteriores: calles, aceras, manzanas, plazas, cruces, pasos de peatones, semáforos con o sin señal sonora, paradas, portales y puntos de referencia.
- Interior y exterior unidos: salir del portal a la calle y llegar a la parada.
- Exteriores reales importados de OpenStreetMap, para corregirlos y completarlos a mano.
- Entornos amueblados con objetos a escala real (mobiliario, material de ciudad) que vienen en complementos ampliables y se colocan cuando el entorno ya está hecho.
- Todo con imagen para el profesional: plano a escala y miniatura de cada objeto, sin dejar de ser manejable sin ver.

Lo que hará el alumno:

- Recorrer el entorno paso a paso o de forma continua, girar, tocar paredes, abrir puertas, subir escaleras y llamar al ascensor.
- Preguntar dónde está, qué tiene delante y qué hay alrededor.
- Jugar: buscar premios que el profesional ha escondido, completar misiones, ganar medallas.
- Hacer exámenes sin ayudas, con resultado medido.

Lo que tendrá el profesional para el seguimiento:

- Supervisión en vivo: dónde está el alumno, hacia dónde mira, qué acaba de oír, con posibilidad de pausar, recolocar, mandar un mensaje o dar una pista.
- Registro de cada sesión con repetición del recorrido.
- Informes por alumno comparando sesiones, exportables.
- Un cuaderno para anotar la evaluación en el lugar real, que es lo que de verdad importa.

Las cuatro conclusiones principales del estudio:

1. **La idea tiene respaldo científico, con límites claros.** Está demostrado en edificios concretos que una persona ciega aprende la distribución con un audiojuego y la aplica después en el edificio real. No está demostrado para barrios enteros ni a largo plazo.
2. **Jugar enseña mejor que seguir rutas dictadas.** Los dos métodos sirven para llegar de A a B, pero quien aprendió jugando encuentra mucho mejor atajos y salidas alternativas. Esto respalda directamente tu petición de que sea lúdico.
3. **No hay nada igual en el mercado.** Ningún producto une editor accesible, interiores de varias plantas, exteriores, sonido binaural, exámenes y supervisión, todo sin conexión.
4. **Buena parte de la base ya la tienes hecha.** Entre ReconocedorCiudades y JuegoGTA hay motor de sonido 3D, voz, mando, menús hablados, editor por formularios, panel de servidor, misiones declarativas y empaquetado. Lo que no existe en ningún sitio, ni en tus proyectos ni en los 12 repositorios, es un modelo de edificio con paredes reales, plantas, escaleras y ascensores, ni un editor accesible para construirlo. Ese es el trabajo nuevo.

## 3. Qué se ha revisado

- Los tres ficheros de adjuntos: descripciones de repositorios, informe de videojuegos y ceguera, y prompt maestro.
- Los 12 repositorios de `adjuntos/RepositoriosOrientacion`, leyendo el código fuente real de cada uno.
- El proyecto ReconocedorCiudades del autor (versión 0.1.10).
- El proyecto JuegoGTA del autor (Puerto Bravo, versión 1.7.5).
- El repositorio de agentes del autor (17 agentes).
- 14 fuentes científicas del fichero de videojuegos, más una búsqueda complementaria de 2015 a 2026.
- Estado actual de bibliotecas, productos comparables y normativa.

No se ha clonado ningún repositorio nuevo: no ha hecho falta.

Una observación sobre el fichero `Descripciones_repositorios_orientacion.txt`: él mismo avisa de que se escribió sin clonar ni ejecutar nada. Al leer el código, varias descripciones no se sostienen. Las correcciones están en el apartado 5.

## 4. Base científica

### 4.1 Qué está demostrado

**AbES, el estudio más sólido (Connors y otros, 2014, texto completo leído).**

- Participantes: adultos con ceguera profunda de 18 a 45 años, repartidos en tres grupos. El artículo dice 38 personas, pero sus grupos suman 36 (15 jugadores, 14 con instrucción dirigida y 7 de control); es una incoherencia del propio artículo.
- Entorno: edificio real de dos plantas, 23 habitaciones, 2 escaleras y 3 salidas.
- Entrenamiento: 3 sesiones de 30 minutos, solo con teclado y auriculares.
- Resultado en rutas de A a B en el edificio real: sin diferencia entre grupos, en torno al 88 a 93 por ciento de aciertos.
- Resultado en la prueba de salir por el camino más corto desde un punto cualquiera: jugadores 2,71 puntos sobre 3; instrucción dirigida 1,66. La diferencia es grande y significativa.
- El grupo de control, que jugó en un edificio distinto, obtuvo un 0 por ciento. Es decir: se aprende el edificio entrenado, no una habilidad general.
- No hubo diferencia entre ceguera temprana y tardía.

**AbES con adolescentes (Connors y otros, 2014, texto completo leído).**

- 7 adolescentes de 16 y 17 años con ceguera temprana, sin grupo de control.
- Tras 60 minutos de juego: 70 por ciento de rutas correctas en el edificio real y 97 por ciento de salidas conseguidas.
- La puntuación obtenida durante el juego predijo el rendimiento real (correlaciones de 0,79 y 0,85).

**AbES con niños (Sánchez y otros, 2010, texto completo leído).**

- 7 niños de 10 a 12 años, sin grupo de control, medido con listas de observación.
- El modo juego obtuvo el mejor resultado en representación espacial (86 por ciento, frente a 42 a 59 en las otras actividades), sin significación estadística por el tamaño de la muestra.

**Cruce de calles (Bowman y Liu, 2017, solo resumen).**

- 12 personas con baja visión severa aprendieron a decidir el momento seguro de cruzar. El entrenamiento virtual igualó al real.

**Planos interactivos (Giudice y otros, 2020, solo resumen).**

- Aprender un plano de planta con un mapa de audio y vibración resultó equivalente a hacerlo con un mapa táctil.

### 4.2 Qué es solo exploratorio

- **BlindAid en un programa de rehabilitación real** (Lahav y otros, 2015, texto completo): 9 personas, 15 sesiones de 50 minutos integradas en la rehabilitación. Mejor señalamiento hacia objetos que el grupo de control (81 a 97 por ciento frente a 56 a 79). Sin estadística por el tamaño de la muestra.
- **Modo «mirar alrededor»** (Lahav y otros, 2018, solo resumen): explorar sin moverse favorece una imagen del lugar tipo mapa (60 por ciento frente a 30), pero lleva más tiempo y en espacios complejos algunos usuarios no llegaron a explorarlo todo.
- **VisionPulse** (2026, borrador leído): 12 personas. Diez de doce prefirieron descubrir el entorno por sí mismas a recibir un menú ya hecho. No midió mapa mental ni transferencia.
- **AudioDoom y AudioChile**: viabilidad con niños; no pude verificar cifras.

### 4.3 Qué no está demostrado

- Que un barrio entero se aprenda con un simulador.
- Que el efecto dure meses.
- Que funcione igual con mando que con teclado. No hay ningún ensayo de transferencia con mando de consola; es una propuesta técnica razonable, no un resultado.
- Que mejore la movilidad en lugares no entrenados.

### 4.4 Cautelas

- Casi todos los estudios tienen entre 4 y 17 participantes y un solo edificio.
- Recorrer el entorno virtual es de 2 a 6 veces más lento que el real.
- Los guiados por puntos de paso llevan antes al destino, pero los usuarios perciben que construyen peor el mapa mental.
- Una revisión sistemática de 2020 encontró solo 4 editores de mapas entre 51 artículos. Es justo el hueco que cubre EntornoLab.

### 4.5 Lo que la ciencia nos obliga a incluir

Por orden de respaldo:

1. Un modo juego que obligue a recorrerlo todo y a elegir salida: recoger objetos y sacarlos por una de varias salidas.
2. Movimiento por pasos, con un paso virtual equivalente a un paso real, y sonido después de cada paso.
3. Una tecla de «dónde estoy» que dice sala, planta y rumbo, pero nunca la ruta.
4. Examen de rutas no entrenadas con límite de tiempo, registrado automáticamente.
5. Examen de salida más corta con puntuación 3, 2, 1 o 0.
6. La misma puntuación calculada durante el juego, porque predice el rendimiento real.
7. Reglas de parada para no frustrar, y ninguna pista durante el examen.
8. Ayudas que se retiran poco a poco, y balizas siempre desactivables.
9. Un registro del profesional para la prueba en el lugar real.

## 5. Los 12 repositorios

Resumen rápido:

- Con licencia que permite reutilizar código: VisionPulse, Audio-Games, SoundArcade, subway_surfers_blind, soundscape y Project-Daredevil (todos MIT).
- Sin licencia, solo sirven como idea: audio-maze, audio-memory-maze, maze-game, AudioGame, EchoGraft y blind-accessible-game-engines.
- Ninguno está en Python moderno con una estructura que podamos copiar tal cual. En la práctica, de todos se aprovechan diseños y fórmulas, y de Soundscape además sonidos.
- Ninguno tiene editor accesible, plantas, escaleras, ascensores, perfiles de profesional y alumno, exámenes ni supervisión.

### 5.1 VisionPulse

- Revisión examinada: `a3dd4af`, 23 de octubre de 2026, 2 confirmaciones.
- Licencia: MIT para el código propio. Los 2,5 GB de modelos y los sonidos de terceros no traen licencia: no reutilizables.
- Qué es: proyecto Unity para gafas de realidad virtual, artefacto de un estudio. No es un producto.
- Lo aprovechable, como diseño:
  - Modelo región, secciones y objetos, con descubrimiento progresivo: lo que el alumno «ve» se añade a su lista de lugares conocidos.
  - Menú de lo descubierto ordenado por distancia de camino, con «no explorada del todo» y una entrada «zona sin descubrir» que lleva hasta el borde de lo desconocido.
  - Baliza reactiva: el volumen y el tono cambian en cuatro tramos según el ángulo entre la mirada y el objetivo.
  - Vibración según puntería y cercanía, y golpe seco al chocar.
  - Refinado de rutas: abrir las esquinas para no rozar la pared, un solo punto activo, «quedan N».
  - Cola de voz con «interrumpir y decir», y descripción de la sala una sola vez.
  - Plantilla de descripción de sala: tamaño, dos o tres referencias y materiales.
  - Registro de trayectoria cuatro veces por segundo.
- Advertencias: no tiene sonido binaural real, ni oclusión, ni teclado, ni mando de consola. Tal como está en el repositorio, la función que guarda los datos empieza con una salida inmediata y no guarda nada.

### 5.2 audio-maze

- Revisión: `b1925d0`, 28 de octubre de 2017. Abandonado.
- Licencia: ninguna. Solo ideas.
- Qué es: laberinto en Java con editor de niveles.
- Lo aprovechable:
  - La «canica acústica»: una sonda que rueda desde el jugador, suena distinto según lo que atraviesa y con otro timbre al chocar. Enseña distancias por el número de rodadas y por el volumen. Es la mejor idea de este repositorio.
  - Doble pasabilidad: cosas que bloquean al jugador pero no al sonido, y al revés.
  - Parámetros de dificultad: tiempo límite, número de sondas, penalizar los choques.
- Corrección a la descripción: el editor es solo de ratón y no es accesible. El formato de nivel es binario de Java y no sirve.

### 5.3 audio-memory-maze

- Revisión: `1083658`, 15 de julio de 2025.
- Licencia: ninguna.
- Qué es: demostración web con un único nivel fijo de 5 por 5.
- Lo aprovechable: la orden «dónde estoy y qué direcciones tengo libres», y el patrón de pruebas automáticas que leen un estado en texto.
- Corrección: anuncia «pistas de sonido espacial» pero no hay ninguna; el aviso de proximidad no indica dirección y atraviesa paredes. Sirve como ejemplo de lo que no hay que hacer.

### 5.4 maze-game

- Revisión: `7f0ee4a`, 20 de julio de 2025. Prototipo de fin de semana.
- Licencia: ninguna.
- Lo aprovechable, como fórmulas:
  - Baliza con mínimo audible garantizado.
  - Distancia codificada dos veces: volumen y brillo del sonido.
  - Más reverberación cuanto más lejos.
  - Transiciones suaves al moverse.
- Correcciones: no es audio 3D, es reparto izquierda y derecha. No usa síntesis de voz. No es compatible con lector de pantalla. La campana atraviesa paredes e indica la línea recta, no el camino, lo que induce a rutas imposibles.

### 5.5 Audio-Games

- Revisión: `cb18028`, 31 de marzo de 2016. Abandonado, Python 2.
- Licencia: MIT. La voz y los sonidos no tienen licencia propia.
- Lo aprovechable:
  - Diseño del registro de sesión para investigación: cada tecla y cada movimiento con su tiempo.
  - Semillas reproducibles, para repetir exactamente el mismo examen.
  - Recorrido por salas como grafo con opciones atrás, izquierda, delante y derecha: útil como modo muy simplificado para principiantes.

### 5.6 AudioGame

- Revisión: `3edef12`, 8 de enero de 2015. Unity 4, abandonado.
- Licencia: ninguna. AstoundSound y Phonon son propietarios.
- Corrección importante: la «propagación de sonido por NavMesh» no usa el sistema de navegación de Unity ni coloca ninguna fuente virtual. Es un grafo de nodos hecho a mano que convierte varios caminos en ecos, iguales en los dos oídos. No da dirección de llegada.
- Lo aprovechable:
  - La idea de un grafo acústico con nodos en puertas y cruces de pasillo, que nuestro editor puede generar solo.
  - Pasos por distancia recorrida, alternando pie y cambiando según el suelo.
  - Golpe y roce de pared situados en el punto de contacto.
  - Baliza por tramos con confirmación al llegar a cada uno.
  - Varios modos de control intercambiables.
- Propuesta mía derivada, que no está en el repositorio: cuando una fuente de sonido no tiene línea directa con el alumno, situarla en la última puerta visible, con volumen según el camino completo y sonido más apagado según las esquinas. Así se oye «por la puerta», que es lo que necesita un alumno de orientación y movilidad.

### 5.7 EchoGraft

- Revisión: `bd8b34c`, 2 de noviembre de 2026. Activo, un solo autor.
- Licencia: ninguna, marcado como privado.
- Correcciones: las «cámaras» son salas cuadradas sin obstáculos. El «escaneo acústico» es un pitido en el objetivo más un texto, no un sonar. El giro no cambia la dirección de avance, lo cual es un contraejemplo para nuestro caso.
- Lo aprovechable:
  - Un embudo único de anuncios con historial consultable.
  - Órdenes de información a demanda: objetivo, posición, límites, última frase.
  - Avisos de pared en dos umbrales, situados en la pared.
  - Capa de «intención» común a teclado y mando.
  - Pruebas que impiden retrocesos de accesibilidad.

### 5.8 SoundArcade

- Revisión: `4f03998`, 13 de julio de 2026. C#, desarrollo temprano.
- Licencia: MIT. Los sonidos no tienen procedencia documentada.
- Corrección: solo tiene un minijuego y la «modularidad» no es tal; añadir otro obliga a tocar el núcleo.
- Lo aprovechable:
  - El patrón más valioso de los doce para nuestra arquitectura: la sesión de juego no toca el sonido ni la voz; devuelve una lista de eventos («reproduce este sonido aquí», «di esto») que otra capa ejecuta. Así toda la lógica se prueba sin altavoces.
  - Bajar la música mientras habla la voz.
  - «Silencio significa despejado».

### 5.9 subway_surfers_blind

- Revisión: `4c393f0`, 20 de mayo de 2026.
- Licencia: MIT para el código. El propio README avisa de que dejará de ser código abierto.
- Los sonidos no se pueden usar: los nombres de fichero indican que proceden del juego comercial original.
- Qué es: la referencia técnica más cercana a nuestra pila (Python, pygame, OpenAL Soft, lector de pantalla, mando).
- Lo aprovechable, como patrones:
  - Arranque de OpenAL Soft con un fichero de configuración propio dentro de la carpeta de datos.
  - Caché de sonidos convertidos a mono y copia a rutas sin acentos, por un problema real con rutas con caracteres especiales.
  - Reserva automática a estéreo simple si el 3D falla.
  - Mando por la interfaz normalizada de SDL, con asignaciones por familia Xbox o PlayStation y nombres de botón correctos.
  - Doble vía de voz: lector de pantalla o voz de Windows.
- Advertencias: no comprueba que el modo binaural esté activo de verdad, no tiene vibración, y casi todo el texto del código está sustituido por índices, lo que lo hace difícil de reutilizar. Mejor reimplementar; además, tus dos proyectos ya resuelven lo mismo y mejor.

### 5.10 soundscape

- Revisión: `52dd215`, 25 de noviembre de 2026. Muy activo, 619 confirmaciones.
- Licencia: MIT, de la comunidad y de Microsoft. Los 80 sonidos de balizas y avisos están dentro del repositorio sin licencia aparte, así que quedan bajo la MIT. Conviene confirmarlo antes de redistribuirlos.
- Qué es: aplicación de iPhone de navegación real. Es el repositorio más valioso de los doce para exteriores.
- Lo aprovechable:
  - **Balizas por regiones.** Cada baliza son varios bucles; suena uno u otro según el ángulo entre tu rumbo y el objetivo: en eje (15 grados por defecto), cerca, lateral y detrás. El cambio se hace en el siguiente pulso, sin cortes.
  - **Llegada con margen.** Se entra a 10 metros y no se «sale» hasta 25, para que no parpadee.
  - **Avisos automáticos.** Sonido de categoría más nombre, situado en el lugar. No se repite hasta pasar 60 segundos o salir del radio. Lo que pide el usuario interrumpe; lo automático se pone en cola.
  - **Cuatro botones de exploración.** Mi ubicación, a mi alrededor (uno por cuadrante), por delante, y marcadores cercanos.
  - **Descripción de cruces.** «Se acerca un cruce. Tal calle va a la izquierda. Tal calle continúa de frente», y cada frase suena desde su lado.
  - **Vista previa de calle.** Un recorrido virtual por el grafo de calles: en cada cruce eliges por dónde seguir. Es lo más parecido a EntornoLab que existe en código abierto.
  - **Categorías.** Un fichero que clasifica cientos de tipos de lugar de OpenStreetMap en seis grupos.
  - Textos en español ya redactados, útiles como referencia de estilo.
- No aplicable: todo lo relativo al error del GPS. En un simulador la posición es exacta y los umbrales deben reducirse, sobre todo en interiores.

### 5.11 Project-Daredevil

- Revisión: `3695072`, 1 de agosto de 2026.
- Licencia: MIT. Los modelos de visión incluidos tienen otra licencia y no se usan.
- Lo aprovechable:
  - Fórmulas de distancia a sonido: cerca agudo y pulsos rápidos, lejos grave y pulsos lentos. Sirven para un «bastón virtual».
  - Protección auditiva: techo por fuente, techo de mezcla, subidas de volumen limitadas y silencio automático si faltan datos. Muy recomendable en una herramienta de rehabilitación que se usa con auriculares.
  - Voz solo cuando cambia el estado, con direcciones gruesas.

### 5.12 blind-accessible-game-engines

- Revisión: `55319fd`, 29 de enero de 2024. Sin actividad desde entonces.
- Licencia: ninguna. Son 5 ficheros de texto.
- Valor: casi nulo para Python y Windows. No cataloga audio 3D para Python, ni voz, ni mandos, ni mapas. Tiene un enlace erróneo y un dato de Godot desfasado.
- Lo único útil: las pautas de accesibilidad de Xbox como lista de comprobación.

## 6. Tus proyectos

### 6.1 ReconocedorCiudades

Aviso previo: no usa wxPython. Es pygame con todo «autohablado» por el lector de pantalla. Por eso su núcleo es muy reutilizable y su interfaz no sirve para formularios.

Licencia: GPL 3 o posterior, tuya. Puedes reutilizar tu propio código como quieras, salvo las traducciones aportadas por terceros.

**Reutilizable casi tal cual:**

- `app/ciudad/geometria.py`: distancia a segmento, cruce de segmentos, punto dentro de polígono. Son las primitivas para paredes y salas.
- `app/ciudad/texto.py`: todo el lenguaje de orientación. Rumbos, puntos cardinales, «a las 3», izquierda y derecha, grados, giros, y metros o pasos del usuario.
- `app/ciudad/cruces.py`: forma del cruce (en T, en Y, en cruz, rotonda) y ficha del paso de peatones. Además es el catálogo de lo que el editor debe ofrecer para un paso: tipo de control, señal sonora, pulsador, isleta, carriles, de dónde vienen los coches, bordillo y pavimento táctil.
- `app/ciudad/rutas.py`: cálculo de rutas «corta» o «segura». Sirve para las actividades de «ve a tal sitio» y para medir cuánto se desvía el alumno del camino óptimo.
- `app/ciudad/practica.py`: retos puntuados, historial, repaso espaciado e informe. Es la semilla de actividades y exámenes.
- `app/audio/sonidos.py` y tu rueda propia de OpenAL Soft 1.25.2 con siete perfiles de cabeza: motor binaural ya resuelto, con modo en memoria para probar sin tarjeta de sonido.
- `app/audio/voz.py`: voz y braille con historial.
- `app/audio/cabeza.py`: seguimiento de cabeza opcional.
- `data/sounds` y `tools/sintetizar_sonidos.py`: pasos de diez superficies, iconos sonoros y sonidos de movilidad, todos sintetizados por ti y sin problema de derechos.
- Infraestructura: rutas portables, registro, instancia única, diagnóstico, empaquetado.

**Adaptable, para importar exteriores:**

- Descarga por Nominatim y Overpass, cambiando el municipio entero por un recuadro pequeño.
- Los algoritmos que construyen el grafo de calles, agrupan calles por nombre, estiman anchuras, deducen aceras y enlazan portales con su calle.
- `app/ciudad/etiquetas.py`: traduce OpenStreetMap a palabras en español; sirve como catálogo de tipos de elemento.
- El modo «acera», que calcula qué calzadas hay que cruzar en cada esquina y por qué paso.

**Como referencia de diseño:**

- El explorador entero: cuatro modos de movimiento, qué se anuncia y cuándo, niveles de detalle, antirrepetición.
- El recorrido de interiores, que es un prototipo pequeño pero es el embrión conceptual de lo que haremos.
- Los documentos de `docs/` sobre movimiento y audio binaural. Una lección que recoges allí y que respetaré: los sonidos que hay que localizar necesitan agudos por encima de 3 kHz para distinguir delante de detrás.

**Lo que no sirve o hay que rehacer:**

- El modelo de datos es una base de solo lectura generada; EntornoLab necesita un documento editable.
- El sonido solo dispara efectos cortos relativos al oyente. Faltan fuentes continuas ancladas al mundo, oyente que se mueve y gira, oclusión por paredes y reverberación por sala.
- No hay nada dinámico: ni fases de semáforo ni tráfico.
- BASS es gratuita solo para uso no comercial: no la usaremos.

### 6.2 JuegoGTA (Puerto Bravo)

Licencia: MIT, tuya.

**Reutilizable casi tal cual:**

- `juego/audio_al.py`, `juego/audio.py` y `juego/salidas.py`: motor de sonido con modo binaural, reverberación por entorno, buses de volumen, bajada automática al hablar, cambio de dispositivo en caliente y una segunda salida de audio. Esta segunda salida es valiosa: permite que el profesional escuche lo mismo que el alumno.
- `juego/voz.py`: voz por lector o por Windows, braille, historial y un historial aparte para mensajes externos, que encaja con los mensajes del profesional.
- `juego/menus.py`: menús hablados y entrada de texto con el mando.
- `juego/mando.py`: detección de Xbox o PlayStation, nombres de botón correctos, zonas muertas, vibración, reasignación y sustitución de nombres de tecla por botones en las frases.
- `juego/teclado.py`: reasignación de teclas por intercambio.
- `juego/catalogo_sonidos.py` y el menú «Aprender los sonidos».
- `editor/formulario.py` y `editor/modelo.py`: formularios generados a partir de un esquema declarativo, con validación. Cambiando el esquema por habitación, puerta, escalera, ascensor, cruce y actividad, tenemos medio editor.
- `editor/accesibilidad/`: etiquetas, diálogos, ayuda contextual y el revisor automático de teclado.
- `panel_servidor/motor.py` y `ventana.py`: el patrón «motor en un hilo, ventana que lee una foto cada segundo» es exactamente el panel del profesional.
- `juego/red.py`, certificados y reconexión: red local con mensajes en texto.
- `juego/misiones.py`: misiones declarativas con pasos de ir, ruta, seguir, escoltar, práctica y decisión, con puntos de control y conteo de fallos.
- `pruebas/conftest.py`: el «robot» que maneja el juego con teclas, sin sonido.
- Los sonidos de orientación sintetizados: balizas, tonos de pared, cruce, semáforo.

**Adaptable, misma idea con otra geometría:**

- El escáner tipo bastón: un rayo que dice qué hay y a qué distancia, con tono más agudo cuanto más cerca.
- El radar por lista, la brújula, el guiado hablado y la baliza hacia el siguiente punto.
- El explorador de mapa con cursor virtual, que deja reconocer el plano sin mover al personaje. Sirve al alumno y sirve al profesional dentro del editor.
- Los dos modos de movimiento: «brújula» (cada flecha es un punto cardinal) y «giro».

**Lo que no sirve:**

- El modelo de mundo: una cuadrícula de calles sin paredes, sin interiores recorribles, sin plantas, escaleras ni ascensores.
- El sonido no tiene oclusión.
- Las voces generadas con Phonon tienen licencia no comercial: no se reutilizan.
- Todo el contenido de juego: conducción, combate, economía.

### 6.3 Conclusión sobre tus proyectos

Entre los dos cubren casi toda la infraestructura. La mejor estrategia es tomar el motor de sonido y la entrada de JuegoGTA, la geometría, el lenguaje de orientación y los exteriores de ReconocedorCiudades, y escribir de nuevo el modelo de edificio, el editor y la supervisión.

## 7. Tus agentes

Hay 17. En este equipo están instalados de forma global 6; en la carpeta de EntornoLab no hay ninguno todavía.

**Imprescindibles para EntornoLab:**

- `proyecto-nuevo`: genera el esqueleto.
- `entorno-virtual`: entorno, compilación y empaquetado.
- `accesibilidad-wx`: todas las pantallas de formularios y listas.
- `configuracion`: preferencias del profesional y del alumno.
- `pruebas`: desde el primer día.
- `documentacion-usuario`: manuales, lista de teclas y ayuda.
- `logging-profesional`: registro y diagnóstico.

**Útiles:**

- `hilos-y-tareas`: cargas, importaciones y lanzamiento del reproductor.
- `revision-egm`: para revisar el diseño del formato y del motor antes de programar.
- `auditoria-proyecto`: al cerrar cada fase.
- `base-datos-sqlite`: para las fichas de alumnos y los resultados.
- `traducciones`: si lo quieres en más idiomas.
- `actualizador`, `red-http` y `complemento-nvda`: más adelante, si hacen falta.

**No aplican:** los dos de Android.

**Reglas de tus agentes que condicionan el diseño:**

- Todo portable dentro de `data/`, nunca en carpetas del sistema.
- Etiqueta creada justo antes de cada control; letras de acceso sin repetir.
- Nada de campos numéricos con decimales nativos: las coordenadas y medidas irán en cuadros de texto validados.
- Listas en modo informe con lectura por columnas.
- La voz complementa, no sustituye, a los controles reales.
- No afirmar «probado con NVDA» sin haberlo probado.

**Lo que ningún agente cubre y habrá que resolver en el proyecto:**

1. Sonido 3D con OpenAL Soft.
2. Motor y bucle de juego con pygame.
3. Mandos.
4. Formato de escenarios con deshacer y rehacer.
5. Edición espacial sin vista.
6. Red y supervisión en tiempo real.
7. Pruebas del reproductor.
8. Datos personales y privacidad.

Si quieres, al terminar puedo convertir lo aprendido en agentes nuevos para tu colección. No lo haré sin que me lo pidas.

## 8. Productos parecidos y hueco real

- **Audiom:** mapas audibles en web, con editor. De pago, precio no publicado. Sin exámenes ni supervisión que yo haya encontrado.
- **Editor E3 (investigación brasileña, 2024):** editor web de interiores con objetivos y aplicación móvil. Es lo más cercano en concepto. No es un producto disponible.
- **BlindAid:** investigación, requiere un dispositivo háptico caro.
- **VoiceVista y Soundscape Community:** navegación real por GPS, no simulación ni editor.
- **TMAP y Touch Mapper:** mapas táctiles de calles.
- **Audiojuegos como Swamp o A Hero's Call:** entornos ficticios, sin editor profesional.
- **Sketchbook:** permite construir mapas; una revista del sector lo señaló en 2026 como prometedor para orientación y movilidad, sin evidencia.
- **NVGT y Godot:** motores, no productos. El editor de Godot sigue sin ser accesible del todo.

No encontré ningún producto que reúna estas seis cosas a la vez:

1. Editor de escritorio accesible, utilizable también por un profesional ciego.
2. Interiores de varias plantas y exteriores en un mismo modelo.
3. Primera persona con sonido binaural, mando y vibración.
4. Actividades, juegos y exámenes con medidas e informes.
5. Supervisión en vivo.
6. Sin conexión, portable y en español.

## 9. Arquitectura y la decisión sobre pygame

Me pediste que no descartara pygame y que valorase lo mejor para el profesional y para el alumno. Estas son las tres opciones.

**Opción A: todo en pygame, con todo autohablado.**

- A favor: una sola tecnología; es lo que ya usan tus dos proyectos; mando, voz y sonido probados.
- En contra para el profesional: rellenar decenas de campos, revisar tablas de resultados y editar textos largos en una interfaz autohablada es más lento que con controles reales. El braille depende de trucos. No hay cuadros de edición nativos, ni tablas que el lector recorra por columnas, ni copiar y pegar estándar.

**Opción B: todo en wxPython, leyendo el mando sin ventana de juego.**

- A favor: una sola ventana nativa.
- En contra para el alumno: es la vía sin probar. Habría que recibir teclas de juego dentro de una ventana con el lector de pantalla interceptando, y leer el mando por una ruta que ninguno de tus proyectos usa.

**Opción C, la que recomiendo: mixto, con un solo motor.**

- **pygame para todo lo que es recorrer.** El reproductor del alumno, y también el «modo recorrido» del profesional: el profesional entra en su entorno, camina por él con el mismo motor, y desde dentro puede marcar «pon aquí un premio», «aquí va una puerta», «esta pared llega hasta aquí». Es decir, se construye también explorando, como apuntabas.
- **wxPython para todo lo que es gestionar.** Árbol y listas de elementos, formularios de propiedades, fichas de alumnos, definición de actividades, panel de supervisión, informes y preferencias. Ahí los controles nativos son claramente mejores con NVDA y JAWS, y es lo que cubren tus agentes.
- **Un motor común sin interfaz.** El modelo del entorno, las colisiones, las reglas de las actividades y la evaluación no dependen ni de pygame ni de wx. Emite eventos («reproduce este sonido aquí», «di esto») que la capa de presentación ejecuta. Así se prueba todo sin altavoces ni ventanas.
- **Dos procesos del mismo ejecutable.** El estudio lanza el reproductor como proceso aparte y habla con él por una conexión local. Es el mismo canal que usará la supervisión por red, así que supervisar en el mismo ordenador o en otro es el mismo mecanismo. JuegoGTA ya lanza el juego desde su editor de forma parecida.

Ventaja añadida de la opción C: el alumno nunca ve el estudio. Tiene su propio acceso directo, que abre solo el reproductor con sus menús hablados.

Para un profesional que prefiera no salir del modo recorrido, las operaciones básicas (añadir, mover, borrar, renombrar) estarán también allí con menús hablados. Lo que no duplicaré son los formularios largos y las tablas.

## 10. El modelo de entornos

### 10.1 Principios

- Unidades en metros. Eje X hacia el este, eje Y hacia el norte. Rumbos en grados desde el norte, en el sentido del reloj. Es la misma convención que ya usan tus dos proyectos.
- Cada planta tiene su altura. El entorno es de «dos dimensiones y media»: plantas apiladas unidas por conectores.
- Cada elemento tiene identificador estable, nombre, descripción hablada, posición, medidas, orientación, material, propiedades acústicas, estado y notas.
- Una cuadrícula opcional ayuda a alinear, pero la geometría es libre: las paredes pueden ir en cualquier ángulo.

### 10.2 Elementos de interior

- Edificio y plantas.
- Espacios: habitación, pasillo, vestíbulo, hueco de escalera, cabina de ascensor.
- Paredes, con material y grosor.
- Aberturas: puerta (batiente, corredera, automática; abierta, cerrada o con llave), hueco sin puerta, ventana.
- Conectores entre plantas:
  - Escalera: tramos, número de peldaños, rellanos, pasamanos a un lado o a los dos, sentido de subida.
  - Rampa: pendiente y longitud.
  - Ascensor: plantas que sirve, botonera exterior e interior, puerta automática, aviso sonoro o hablado de planta.
  - Escalera mecánica.
- Mobiliario y obstáculos con volumen: mesa, cama, mostrador, columna, y también obstáculos a la altura de la cabeza, que el bastón no detecta.
- Suelos: material por zona, alfombras, cambios de textura, pavimento táctil.
- Fuentes de sonido fijas: frigorífico, reloj, fuente, máquina expendedora, ventana a la calle. Son los puntos de referencia sonoros que los estudios describen como útiles.
- Zonas acústicas: tamaño y materiales de la sala, que determinan su eco.
- Puntos de interés y referencias, distinguiendo las fijas de las pasajeras.

### 10.3 Elementos de exterior

- Calles con calzada, carriles y sentido.
- Aceras como superficie real, con anchura, bordillo y vados.
- Manzanas, fachadas, portales con número, entradas.
- Cruces, con su forma.
- Pasos de peatones: con o sin semáforo, señal sonora, pulsador, isleta, pavimento táctil, longitud.
- Semáforos con sus fases y tiempos.
- Tráfico: intensidad y sentido, como fuente de sonido en movimiento.
- Plazas, parques, senderos y zonas peatonales.
- Paradas y marquesinas.
- Mobiliario urbano y obstáculos: farolas, bolardos, terrazas, obras.
- Pendientes y escaleras exteriores.
- Referencias ambientales: una fuente, una cafetería, una iglesia con campanas.

### 10.4 Unión de interior y exterior

Un portal es una abertura que pertenece a la vez al edificio y a la calle. Se cruza andando, sin cambio de pantalla, y el sonido cambia de interior a exterior de forma coherente.

### 10.5 Formato de fichero

- Un paquete comprimido con extensión propia que contiene el entorno en JSON, los sonidos propios y los metadatos.
- Número de versión del formato y conversión automática de versiones antiguas.
- Esquema publicado y documentado.
- Guardado seguro: escritura atómica y copia de recuperación.
- Procedencia registrada: fuente, fecha, escala, licencia y autor.
- Sin rutas absolutas y sin código ejecutable dentro. Las actividades son reglas declarativas, nunca programas.
- Al abrir un paquete ajeno se validan tamaños, rutas y contenidos.

### 10.6 Importar y exportar

Importar:

- OpenStreetMap, por zona pequeña elegida por el profesional. El resultado es siempre un borrador para revisar. Los datos de aceras, bordillos y señales sonoras faltan muy a menudo y habrá que completarlos a mano.
- Planos en DXF y SVG, como base para trazar.
- Entornos de otros profesionales.

Exportar:

- Paquete para el alumno.
- Descripción en texto del entorno.
- Plano en SVG, apto para hacer una lámina en relieve.
- GeoJSON por planta.

### 10.7 Complementos de objetos

Los objetos que dan realismo al entorno (mobiliario, material de ciudad, elementos de transporte) no estarán metidos dentro del programa: vendrán en complementos que se añaden y se quitan con facilidad.

**Qué es un complemento.**

- Un paquete que se copia en la carpeta de complementos, o se instala desde el estudio con «Añadir complemento».
- Contiene una ficha general (nombre, autor, versión, licencia) y una ficha por objeto.
- Es solo datos: descripciones, medidas, sonidos e imágenes. No lleva código ejecutable, así que instalar un complemento de otra persona no supone un riesgo.
- Se activa y desactiva sin reiniciar. Si un entorno usa un complemento que falta, el programa lo avisa y conserva el objeto como una caja con sus medidas, sin romper nada.

**Qué define cada objeto.**

- Nombre, categoría y palabras para buscarlo.
- Medidas reales en metros: ancho, fondo y alto, con un mínimo y un máximo admitidos. Por ejemplo, una mesa de comedor de 1,20 a 2,40 metros de largo.
- Forma de su planta: rectangular, redonda, en L.
- Variantes: mesa de dos, de cuatro o de seis plazas.
- Cómo se comporta al andar: si corta el paso, si se puede rodear, si es detectable con el bastón o queda a la altura de la cabeza.
- Dónde se puede poner: suelo, contra una pared, en una esquina, sobre otro mueble, en acera, en calzada.
- Material y sonidos: al golpearlo, al usarlo, y su sonido propio si lo tiene (un frigorífico que zumba, un semáforo que pita).
- Acciones posibles, declaradas: abrir, cerrar, sentarse, pulsar, coger.
- Si puede contener premios dentro o debajo.
- Descripción hablada para el alumno.
- Imagen para el profesional: un dibujo en planta a escala y, opcionalmente, una ilustración o foto, siempre con su descripción en texto.

**Adaptación a la escala del entorno.**

Todo se mide en metros reales, así que un objeto nunca queda desproporcionado por error:

- Al colocar un objeto se comprueba que cabe en el hueco elegido.
- Si no cabe, el programa propone la variante más pequeña o lo ajusta dentro de su rango admitido. Si aun así no cabe, lo dice y no lo coloca. Una mesa nunca será más grande que la habitación.
- Avisa si un objeto tapa una puerta, o si deja un paso más estrecho que el mínimo que el profesional haya fijado.
- Los objetos se pegan a la pared o a la esquina que se indique, con la orientación correcta.
- En exteriores ocurre lo mismo: un banco se ajusta a la anchura de la acera y avisa si no deja paso libre.

**Colocación con el entorno ya hecho.**

Los objetos se añaden, se mueven y se quitan en cualquier momento, sin rehacer paredes ni habitaciones. Tres formas:

1. Desde el catálogo: se busca el objeto, se elige la habitación y la posición («contra la pared norte, centrado», «en la esquina sureste», «a 1 metro de la puerta»).
2. Recorriendo: se camina hasta el sitio y se pide «colocar aquí».
3. Amueblado asistido: «amuebla esta habitación como dormitorio», que propone una disposición razonable para revisar.

**Complementos de serie previstos.**

- Hogar: salón, cocina, dormitorio, baño.
- Colegio y oficina.
- Comercio y edificios públicos.
- Calle: farolas, bolardos, bancos, papeleras, contenedores, marquesinas, semáforos, alcorques, terrazas, vallas de obra.
- Transporte: andenes, tornos, máquinas de billetes.

**Crear complementos propios.**

- Un asistente en el estudio para definir un objeto nuevo rellenando un formulario, sin programar, y exportarlo para compartirlo.
- El formato estará documentado para que otras personas puedan crear catálogos.
- Un comprobador que revisa un complemento antes de publicarlo: medidas coherentes, sonidos presentes, imágenes con descripción.

**Imagen para el profesional.**

Todo tendrá representación visual, no solo los objetos:

- Un plano del entorno dibujado a escala, por plantas, con paredes, puertas, objetos con su símbolo, premios y recorrido del alumno.
- Miniatura de cada objeto en el catálogo y en su ficha.
- El plano se puede ampliar, recorrer, imprimir y exportar.
- En la supervisión, el alumno se ve moverse sobre el plano.

Dos precisiones honestas:

- La imagen complementa a la lista y a los formularios, nunca los sustituye, para que un profesional ciego pueda hacer exactamente lo mismo.
- Las imágenes de serie serán símbolos y dibujos sencillos generados por el propio programa. Si quieres ilustraciones elaboradas o fotos, habrá que aportarlas; el profesional podrá asociar una foto propia a cada objeto.

## 11. El estudio del profesional

### 11.1 Crear y editar

- Asistentes y plantillas: vivienda tipo, aula, planta de oficinas, tramo de calle con cruce, parada de autobús.
- Árbol del entorno: edificio, plantas, espacios y elementos.
- Lista de elementos del espacio actual, con columnas legibles una a una.
- Formulario de propiedades generado por tipo de elemento.
- Colocación por tres vías, a elegir:
  1. Por medidas: «habitación de 4 por 3 metros, puerta en la pared norte a 1,20 de la esquina oeste».
  2. Por relación: «al este del salón, compartiendo pared».
  3. Recorriendo: entrar en el modo recorrido y marcar posiciones andando.
- Herramientas: duplicar, mover, girar, alinear, medir la distancia entre dos elementos, buscar, deshacer y rehacer.
- Catálogo de objetos de los complementos instalados, con búsqueda, miniatura y colocación a escala (apartado 10.7).
- Plano gráfico a escala de todo el entorno, con sus objetos, para profesionales con resto visual o videntes. Nunca será la única forma de hacer algo.

### 11.2 Comprobar

Un validador que avisa, con la ubicación del problema y una sugerencia:

- Habitación sin puerta o inaccesible.
- Paredes que no cierran.
- Escalera o ascensor que no llega a una planta.
- Elementos solapados.
- Punto de inicio dentro de un muro.
- Objetivos o premios inalcanzables. Distingue lo imposible de lo bloqueado a propósito.
- Sonidos que faltan.

### 11.3 Probar

- Una tecla recorre el entorno al momento con el mismo motor que usará el alumno, empezando en el punto donde esté el cursor.
- Explorador de plano: un cursor que salta de sala en sala y de elemento en elemento sin mover al personaje.
- Escuchar un sonido colocado desde cualquier posición.

### 11.4 Actividades, alumnos e informes

Se detallan en los apartados 14, 16 y 17.

## 12. El reproductor del alumno

### 12.1 Movimiento

Modos, que el profesional fija o deja elegir:

- **Por pasos.** Cada pulsación es un paso de longitud ajustable (por defecto, la del propio alumno). Es el modo con respaldo científico y el recomendado para empezar.
- **Continuo.** Se mantiene pulsado o se inclina la palanca; velocidad de paseo real, no de videojuego.
- **Giros.** De 90, 45 o 15 grados, o giro libre con la palanca. Por defecto 90 en interiores.
- **Modo brújula.** Cada flecha es un punto cardinal. Útil para principiantes y para niños pequeños.
- **Por calles y por acera**, en exteriores, como en ReconocedorCiudades: se avanza de cruce en cruce y se elige salida.
- **Por salas**, muy simplificado, para una primera toma de contacto.

En todos los modos el giro afecta al avance, y un paso virtual equivale a un paso real.

### 12.2 Lo que se oye al moverse

- Pasos alternando pie, distintos según el suelo.
- Roce y golpe al tocar una pared, situados donde se produce el contacto, con vibración del mando.
- Puertas, escaleras (con tono que sube al subir), ascensor con su recorrido y aviso de planta.
- Las fuentes de sonido del entorno, situadas en su sitio.
- El eco propio de cada sala.
- Sonidos amortiguados cuando hay una pared en medio, y que llegan por la puerta.

### 12.3 Preguntas que el alumno puede hacer

- Dónde estoy: sala, planta y hacia dónde miro. Nunca dice la ruta.
- Qué hay delante.
- Qué hay alrededor, por cuadrantes.
- Mirar alrededor sin moverse: se apunta en una dirección y dice qué hay y a cuántos pasos.
- Bastón sonoro: una sonda que avanza y suena según lo que encuentra.
- Lista de lo cercano, ordenada por distancia.
- Lugares que ya he descubierto.
- Brújula.
- Repetir lo último e historial de mensajes.
- Chasquido para oír el eco de la sala.
- Volver al inicio.
- Pausa.

El profesional decide cuáles de estas ayudas están disponibles en cada actividad, y puede limitarlas en número.

### 12.4 Controles propuestos

Son una propuesta inicial; todos serán reasignables.

Teclado:

- Flecha arriba: avanzar. Flecha abajo: retroceder.
- Flechas izquierda y derecha: girar.
- Mayúsculas con flechas laterales: paso lateral.
- Intro o Espacio: interactuar (abrir, coger, llamar al ascensor).
- C: dónde estoy.
- W, A, S, D: mirar delante, izquierda, detrás y derecha.
- Tabulador: lista de lo cercano.
- K: brújula.
- B: bastón sonoro.
- F1: ayuda. F2: repetir. F3: historial.
- Control: callar la voz.
- Escape: pausa y menú.

He mantenido las letras que ya usas en JuegoGTA y ReconocedorCiudades para que te resulten familiares.

Mando de Xbox o PlayStation:

- Palanca izquierda: moverse.
- Palanca derecha: mirar alrededor en la dirección apuntada.
- A o Equis: interactuar.
- B o Círculo: atrás o cancelar.
- X o Cuadrado: dónde estoy.
- Y o Triángulo: qué hay delante.
- Botones superiores: girar un paso a izquierda o derecha.
- Gatillo derecho: bastón sonoro.
- Gatillo izquierdo: segunda función de los demás botones.
- Cruceta: recorrer la lista de lo cercano.
- Botón de menú: pausa.
- Botón de vista o compartir: ayuda.

La voz dirá siempre el nombre correcto del botón según el mando conectado.

Vibración, con un vocabulario pequeño y constante:

- Golpe seco: choque.
- Pulso suave: premio cerca.
- Lado izquierdo o derecho: pared a ese lado.
- Doble pulso: objetivo alcanzado.

### 12.5 Sonido

- Binaural por auriculares, con varios perfiles de cabeza a elegir y una prueba de calibración al empezar.
- Alternativa en estéreo simple, que es lo que usó AbES y con lo que se demostró la transferencia.
- Sonidos que suenan detrás algo más apagados, como refuerzo.
- Volúmenes independientes para entorno, pasos, voz, ayudas, interfaz y música.
- Protección auditiva: techo de volumen y subidas graduales.
- La música y el ambiente bajan cuando habla la voz.
- Ninguna pista de distancia engañosa: lo que suena lejos está lejos.

### 12.6 Menús del alumno

Hablados, muy pocos y simples: continuar, elegir actividad, mis premios, aprender los sonidos, practicar los controles, ajustes básicos y salir.

Antes de la primera actividad hay un tutorial jugable que enseña los controles y los sonidos uno a uno.

## 13. Aprender jugando: la parte lúdica

Este apartado recoge tu petición de que sea muy lúdico y a la vez práctico. Además, es lo que mejor respalda la evidencia: quien aprendió jugando encontró mejor los atajos.

### 13.1 Premios escondidos por el profesional

- El profesional coloca premios donde quiera: dentro de un armario, debajo de la cama, en el rellano del segundo piso, junto a la parada.
- Cada premio tiene nombre, sonido propio, y opcionalmente un mensaje de voz grabado por el profesional o por la familia.
- Puede ser visible desde lejos por su sonido, oírse solo de cerca, o estar totalmente oculto hasta abrir algo.
- Puede exigir una acción: abrir el cajón, llamar al timbre.
- El profesional elige cuántos hay y si se dicen de antemano.
- Colocación asistida: «reparte seis premios de modo que haya que pasar por todas las habitaciones».

### 13.2 Tipos de juego

- **Búsqueda del tesoro.** Encontrar todos los premios.
- **El recadero.** Coger algo en un sitio y llevarlo a otro.
- **Sacar los tesoros.** Recoger y sacar por la salida más cercana, de uno en uno. Es el juego de AbES, y su puntuación predice el rendimiento real.
- **El escondite.** Un personaje se esconde y hace ruido de vez en cuando.
- **Sigue al guía.** Seguir a alguien por el sonido de sus pasos.
- **El explorador.** Descubrir todas las habitaciones; cada una nueva suena a hallazgo.
- **Pistas encadenadas.** Cada premio da la pista del siguiente: «el próximo está en la habitación que queda al norte de la cocina».
- **El travieso.** Un personaje que recoloca premios, para obligar a volver a recorrer.
- **Contrarreloj**, siempre opcional.
- **Cruza con el pitido.** En exteriores, decidir cuándo cruzar.

### 13.3 Recompensas

- Estrellas por actividad, que premian cosas distintas: completarla, hacerlo con pocas ayudas, encontrar un atajo.
- Medallas y colección de objetos encontrados, que el alumno puede repasar.
- Sonidos y fanfarrias de logro.
- Recompensas que el profesional define: «al conseguir cinco estrellas se desbloquea la casa del árbol».
- Un personaje acompañante opcional que anima.

### 13.4 Adaptación por edad

Tres estilos de presentación, con el mismo contenido de aprendizaje:

- **Infantil:** personajes, sonidos divertidos, frases cortas, mucha celebración.
- **Juvenil:** misiones, retos, clasificación personal.
- **Adulto:** sobrio, con objetivos prácticos («prepara la visita: encuentra las llaves, el abrigo y el paraguas») y sin tono infantil.

El profesional elige el estilo por alumno.

### 13.5 Reglas para que jugar no estropee el aprendizaje

- Ganar nunca depende solo de seguir una baliza.
- No se penalizan las pausas.
- Las prisas son opcionales; el tiempo límite se puede quitar.
- Chocar no «mata»: informa.
- Los premios obligan a recorrer todo el entorno, no solo el camino principal.
- Tras varios fallos seguidos el juego ofrece ayuda en lugar de insistir.

## 14. Actividades y exámenes

### 14.1 Cómo las define el profesional

Sin programar, con un formulario:

- Punto de inicio y orientación inicial.
- Objetivos, en orden obligatorio o libre.
- Condiciones de éxito.
- Ayudas permitidas y cuántas veces.
- Pistas y cuándo se ofrecen.
- Límite de tiempo, si lo hay.
- Mensajes de inicio, de logro y de final.
- Estilo de presentación.

### 14.2 Tipos de actividad

- Exploración libre.
- Visita guiada, con el profesional narrando o con textos preparados.
- Búsqueda de objetos.
- Entregas.
- Localizar una habitación.
- Ruta de un punto a otro.
- Ruta inversa: volver por donde se vino.
- Volver al origen.
- Ruta alternativa con un paso cortado.
- Reconocer referencias.
- Familiarización de sala: primero el perímetro, luego el interior. Es la técnica habitual en orientación y movilidad.
- Seguir una línea guía: una pared, un bordillo.
- Estimar distancias y direcciones.
- Analizar un cruce.

### 14.3 Retirada progresiva de ayudas

Cada actividad puede tener niveles: con baliza, con baliza solo al pedirla, sin baliza, sin «dónde estoy». El alumno sube de nivel al superar el anterior.

### 14.4 Exámenes

En modo examen no hay pistas ni celebraciones intermedias.

- **Rutas no entrenadas.** Una serie de rutas de longitud y giros comparables, con límite de tiempo. Se registra acierto y tiempo.
- **Salida más corta.** Desde un punto cualquiera, salir por la salida más cercana. Puntuación de 3, 2, 1 o 0.
- **Señalar.** Girarse hacia un lugar que no se percibe. Se mide el error en grados.
- **Comparar distancias.** Qué queda más cerca.
- **Ruta inversa y cambio de perspectiva.**
- **Atajos.** Llegar por un camino no practicado.
- **Reconstrucción.** Colocar las habitaciones en su sitio relativo.

Reglas:

- Regla de parada configurable, por ejemplo tres de las cinco primeras rutas, para evitar la frustración.
- El mismo examen se puede repetir exactamente igual otro día.
- El tiempo en pausa no cuenta.

### 14.5 Valoración subjetiva

Al terminar, opcionalmente, unas preguntas breves sobre esfuerzo, confianza y disfrute.

## 15. Supervisión en vivo

### 15.1 Qué ve y oye el profesional

- Lista de alumnos conectados.
- Posición del alumno descrita en palabras: sala, planta, rumbo y qué tiene delante.
- Lo último que ha oído, en texto, con historial.
- Eventos al momento: choque, ayuda pedida, premio encontrado, objetivo cumplido.
- Indicadores: tiempo activo, distancia, choques, ayudas.
- Opcionalmente, un plano gráfico para quien tenga resto visual.
- Opcionalmente, el mismo sonido que oye el alumno por una segunda salida de audio.

Todo en controles nativos, con avisos por voz configurables para que no pisen el trabajo del profesional.

### 15.2 Qué puede hacer

- Pausar y reanudar.
- Recolocar al alumno en un punto.
- Enviar un mensaje hablado.
- Dar una pista o activar una baliza un momento.
- Quitar o añadir ayudas sobre la marcha.
- Añadir un premio en caliente.
- Marcar un momento con una nota.
- Reiniciar o terminar la actividad.

### 15.3 Dos formas de conexión

- **Mismo ordenador.** El alumno juega con mando y auriculares; el profesional trabaja con teclado y su lector por los altavoces u otros auriculares. Cada sonido va a su dispositivo.
- **Red local.** El alumno en un ordenador y el profesional en otro, con conexión cifrada y emparejamiento por código. Con búsqueda automática y también con dirección escrita a mano, porque muchas redes de centros bloquean la búsqueda automática.

No hay nube ni servidores externos.

## 16. Seguimiento e informes

### 16.1 Qué se registra en cada sesión

- Recorrido completo, varias veces por segundo.
- Tiempo activo y tiempo en pausa por separado.
- Distancia recorrida frente a la del camino óptimo.
- Choques, con lugar.
- Ayudas pedidas, cuáles y dónde.
- Objetivos y premios, con su momento.
- Salas visitadas y sin visitar.
- Forma de explorar: por el perímetro, en cuadrícula, de objeto en objeto o sin patrón.
- Intervenciones del profesional.

### 16.2 Qué puede hacer el profesional con ello

- Repetir un recorrido paso a paso, oyéndolo descrito.
- Comparar sesiones del mismo alumno.
- Ver la evolución en el tiempo.
- Exportar informes en texto, HTML y CSV, legibles con lector de pantalla.

### 16.3 El cuaderno de evaluación real

Una ficha aparte donde el profesional anota la prueba en el lugar físico: rutas hechas, nivel de ayuda, tipo de recorrido, observaciones y fecha. Permite comparar lo aprendido en el simulador con el desempeño real y anotar si se mantiene semanas después.

### 16.4 Lo que el programa no hará

- No equipara puntuación del juego con competencia real.
- No emite diagnósticos ni recomendaciones clínicas.
- No dice que un cruce real sea seguro.

Los informes son descriptivos: tiempos, errores y ayudas.

## 17. Datos y privacidad

Son datos de salud y a menudo de menores, así que:

- Los alumnos se identifican por alias. El nombre real es opcional y se guarda aparte.
- Fichas y resultados cifrados en disco, con contraseña del profesional.
- Sin telemetría y sin conexiones salientes. La única excepción es importar de OpenStreetMap, y solo cuando el profesional lo pide.
- Exportar y borrar todos los datos de un alumno con una orden.
- Los registros técnicos no contienen datos personales.
- En la supervisión por red solo viaja el alias, cifrado.
- Aviso visible: herramienta educativa y de entrenamiento; no diagnostica ni trata; no sustituye al aprendizaje real con profesional.

Sobre la normativa de productos sanitarios: con finalidad declarada educativa y de entrenamiento no debería considerarse producto sanitario. Si se presentara como herramienta de evaluación clínica, podría serlo. Esto es orientación, no asesoramiento jurídico; si piensas comercializarlo conviene confirmarlo con un experto.

## 18. Accesibilidad

- Todo lo esencial funciona sin ratón y sin visión, tanto para el alumno como para el profesional.
- El estudio usa controles nativos con etiqueta, letra de acceso, ayuda contextual y orden de foco lógico.
- El reproductor habla a través del lector de pantalla activo, o de la voz de Windows si no hay lector.
- Braille para los mensajes.
- Baja visión: alto contraste, tamaño de texto, vista del plano opcional, sin destellos, sin depender del color.
- Audición reducida asociada: vibración y texto como alternativas.
- Ritmo, cantidad de información y dificultad ajustables.
- Perfiles de alumno: bastón, perro guía, baja visión, principiante.

Objetivo de referencia: la norma europea EN 301 549 en su parte de programas de escritorio.

## 19. Pila técnica propuesta

- **Python 3.13 de 64 bits.** Todas las bibliotecas tienen versión para él.
- **wxPython 4.3.2** para el estudio, con 4.2.5 como alternativa si aparecen problemas, porque la 4.3 se apoya en una rama de wxWidgets aún no declarada estable.
- **pygame-ce 2.5.8** para el reproductor, el modo recorrido y los mandos.
- **OpenAL Soft 1.25.2** para el sonido 3D, con tu propia rueda y tu capa de enlace, que ya están hechas y probadas. Licencia LGPL: la biblioteca va como fichero suelto y sustituible, con su aviso.
- **accessible_output2** para la voz, detrás de una interfaz propia. Así se puede evaluar más adelante Prism, una alternativa nueva y muy activa pero todavía joven, sin tocar el resto.
- **shapely y networkx** para geometría y rutas, si las primitivas propias se quedan cortas.
- **SQLite** para fichas y resultados.
- **cx_Freeze** para el empaquetado portable.
- Red: biblioteca estándar de Python con cifrado.

Lo que se descarta y por qué:

- BASS y FMOD: licencias comerciales.
- Synthizer y Resonance Audio: abandonados.
- Unity y Godot: sus editores no son accesibles y no encajan con tu forma de trabajar.
- Voces de Phonon: licencia no comercial.

Sonidos:

- Base: los tuyos sintetizados, sin problemas de derechos.
- Balizas y avisos de Soundscape, si confirmamos su licencia.
- Ningún sonido de los demás repositorios.

## 20. Estructura del proyecto

Siguiendo las convenciones de tus agentes:

- `main.py`: arranque; decide si abre el estudio o el reproductor.
- `app/core`: rutas, configuración, registro, versión.
- `app/dominio`: modelo del entorno, geometría, validación y formato.
- `app/motor`: simulación, colisiones, navegación y eventos. Sin interfaz.
- `app/audio`: sonido 3D, voz y vibración.
- `app/entrada`: acciones con nombre, asignadas a teclado y mando.
- `app/actividades`: reglas, juegos, exámenes y puntuación.
- `app/seguimiento`: registro de sesiones, informes y fichas.
- `app/supervision`: protocolo y conexión.
- `app/reproductor`: pantallas en pygame.
- `app/estudio`: ventanas en wxPython.
- `app/importar`: OpenStreetMap, DXF, SVG.
- `data/`: sonidos, ejemplos, documentación; y, sin distribuirse, configuración, alumnos y registros.
- `tests/`, `tools/`, `docs/`.

Código con tabuladores, comentarios y documentación interna en español, y una instrucción por línea, como pide el prompt maestro y como ya haces.

## 21. Plan por fases y qué tendrás al final de cada una

**Fase 0. Cimientos.**
Esqueleto con tus agentes, formato de entorno, geometría, motor sin interfaz, sonido 3D básico y pruebas.
Al terminar: se puede cargar un entorno de ejemplo escrito a mano y recorrerlo en las pruebas automáticas.

**Fase 1. Primera vivienda completa.**
Estudio con árbol, lista y formularios para habitaciones, paredes, puertas y fuentes de sonido. Reproductor con teclado y mando. Una actividad de búsqueda de premios. Un informe.
Al terminar: creas una vivienda de una planta, escondes premios, la juegas y ves el resultado. Es el ciclo completo en pequeño.

**Fase 2. Interiores de verdad.**
Varias plantas, escaleras, rampas, ascensores, puertas con estado, suelos, eco por sala y sonido que pasa por las puertas. Sistema de complementos de objetos con ajuste a escala, complemento de hogar y plano gráfico. Validador. Modo recorrido para construir andando.
Al terminar: se puede modelar y amueblar un edificio real.

**Fase 3. Juego y aprendizaje.**
Todos los tipos de actividad y de juego, recompensas, estilos por edad, retirada de ayudas, exámenes, fichas de alumno y comparación de sesiones.
Al terminar: un profesional puede llevar el programa de trabajo de un alumno.

**Fase 4. Supervisión.**
En el mismo ordenador y por red local, con todas las acciones del profesional y la repetición de recorridos.

**Fase 5. Exteriores.**
Calles, aceras, cruces, pasos, semáforos con fases, tráfico, paradas. Unión con interiores. Importación de OpenStreetMap. Juego de cruzar.

**Fase 6. Intercambio.**
Importar DXF y SVG, exportar plano en relieve y descripción, biblioteca de plantillas, paquetes para compartir entre profesionales. Asistente para crear complementos propios y resto de complementos de serie (colegio, oficina, comercio, transporte; el de calle llega con la fase 5).

**Fase 7. Acabado.**
Manual del profesional, manual del alumno, lista de teclas, ayuda en la aplicación, empaquetado, auditoría y preparación de pruebas con usuarios.

El orden se puede cambiar. Si te interesan antes los exteriores que la supervisión, se intercambian las fases 4 y 5.

## 22. Pruebas y qué podré y no podré garantizar

**Pruebas automáticas que escribiré y ejecutaré:**

- Geometría, colisiones, orientación y conectividad.
- Formato, guardado, conversión de versiones y paquetes dañados o maliciosos.
- Reglas de actividades y puntuación de exámenes.
- Recorridos completos con un «robot» que pulsa teclas, comprobando lo que se dice y lo que suena.
- Posición de los sonidos, usando el modo en memoria de OpenAL.
- Formularios del estudio: etiquetas, letras de acceso y atajos.
- Mando simulado.
- Protocolo de supervisión.

**Lo que solo se puede comprobar a mano, y que no daré por hecho:**

- Comportamiento real con NVDA y con JAWS.
- Mandos físicos de Xbox y PlayStation, por cable y por Bluetooth, y su vibración.
- Calidad percibida del sonido binaural.
- Dos salidas de audio a la vez.
- Supervisión entre dos ordenadores reales.

Para estas te daré guiones de prueba paso a paso y anotaré el resultado que me digas.

**Lo que queda fuera del desarrollo:**

- Pruebas con alumnos y profesionales reales.
- Validación de que lo aprendido se transfiere al lugar físico.

Son una fase posterior imprescindible, y no se puede simular.

## 23. Riesgos y limitaciones

1. **Tamaño del proyecto.** Es grande. Por eso se entrega por fases que funcionan por sí solas.
2. **Editar espacio sin ver.** Es la parte más difícil y la menos resuelta en el mundo. La combinación de medidas, relaciones y recorrido es mi mejor propuesta, y habrá que afinarla contigo.
3. **Calidad del binaural.** Distinguir delante de detrás varía de una persona a otra. Se mitiga con varios perfiles, calibración, el giro del propio alumno y la alternativa en estéreo.
4. **Datos de OpenStreetMap incompletos.** Todo lo importado es un borrador.
5. **wxPython 4.3.** Posibles fallos por su base aún inestable; hay alternativa.
6. **Mando y lector de pantalla a la vez.** Hay que comprobar pronto que el lector no interfiere con las teclas del reproductor.
7. **Redes de centros.** Cortafuegos y bloqueos; por eso existe el modo de un solo ordenador.
8. **Expectativas.** La evidencia es de edificios concretos. El programa debe presentarse como complemento, no como sustituto del trabajo en el lugar real.
9. **Licencia de los sonidos de Soundscape.** Pendiente de confirmar.

## 24. Decisiones que necesito de ti

Para cada una indico qué haré si no dices nada.

1. **Arquitectura mixta** (pygame para recorrer, wxPython para gestionar, un solo motor). Por defecto: sí.
2. **Orden de las fases.** Por defecto: el del apartado 21.
3. **Supervisión por red en la primera versión**, o solo en el mismo ordenador de momento. Por defecto: las dos, en la fase 4.
4. **Distribución.** Gratuita, de pago o solo para tu centro. Afecta a la licencia y a qué sonidos se pueden usar. Por defecto: lo preparo para que sirva en cualquier caso, sin nada de uso no comercial.
5. **Idiomas.** Solo español, o preparado para traducir. Por defecto: español, con los textos ya marcados para traducir más adelante.
6. **Reutilizar código de ReconocedorCiudades**, que es GPL. Si EntornoLab va a tener otra licencia, como autor puedes autorizarlo. Por defecto: lo reutilizo, entendiendo que es tuyo.
7. **Versión de Python.** Por defecto: 3.13.
8. **Nombres.** Por defecto: EntornoLab Estudio y EntornoLab Jugar.
9. **Imágenes de los objetos.** Símbolos y dibujos sencillos generados por el programa, o ilustraciones que aportes tú. Por defecto: símbolos generados, con la opción de asociar una foto propia.

## 25. Referencias

### Científicas

Leídas a texto completo:

- Sánchez, Sáenz, Pascual-Leone y Merabet (2010). Enhancing Navigation Skills through Audio Gaming. https://pmc.ncbi.nlm.nih.gov/articles/PMC4259046/
- Merabet, Connors, Halko y Sánchez (2012). Teaching the Blind to Find Their Way by Playing Video Games. https://pmc.ncbi.nlm.nih.gov/articles/PMC3446956/
- Connors, Chrastil, Sánchez y Merabet (2014). Action video game play and transfer of navigation and spatial cognition skills in adolescents who are blind. https://pmc.ncbi.nlm.nih.gov/articles/PMC3949101/
- Connors, Chrastil, Sánchez y Merabet (2014). Virtual environments for the transfer of navigation skills in the blind. https://pmc.ncbi.nlm.nih.gov/articles/PMC4013463/
- Lahav, Schloerb, Kumar y Srinivasan (2012). A Virtual Environment for People Who Are Blind: A Usability Study. https://pmc.ncbi.nlm.nih.gov/articles/PMC3864668/
- Lahav, Schloerb y Srinivasan (2015). Rehabilitation program integrating virtual environment. https://doi.org/10.1016/j.compedu.2014.08.003
- Afonso-Jaco y Katz (2022). Spatial Knowledge via Auditory Information for Blind Individuals. https://pmc.ncbi.nlm.nih.gov/articles/PMC9268803/
- Lahav (2022). Virtual Reality Systems as an Orientation Aid for People Who Are Blind. https://pmc.ncbi.nlm.nih.gov/articles/PMC8963089/
- Martin, Fazli y Seifi (2026). VisionPulse. Borrador en arXiv 2607.21944. No pude confirmar que corresponda al DOI https://doi.org/10.1145/3797867.3828994

Leídas solo en resumen:

- Connors, Yazzolino, Sánchez y Merabet (2013). https://pmc.ncbi.nlm.nih.gov/articles/PMC3641639/
- Sánchez y Lumbreras (1999). AudioDoom. https://pubmed.ncbi.nlm.nih.gov/19178246/
- Sánchez y Sáenz (2006). AudioChile. https://repositorio.uchile.cl/handle/2250/124981 (leída por una transcripción)
- Lahav y otros (2014). Wiici. https://doi.org/10.1108/JAT-02-2014-0009
- Lahav y otros (2018). Modo mirar alrededor. https://pubmed.ncbi.nlm.nih.gov/28637136/
- Bălan, Moldoveanu y Moldoveanu (2015). https://doi.org/10.1515/ijdhd-2014-0018
- Bowman y Liu (2017). Cruce de calles. https://pmc.ncbi.nlm.nih.gov/articles/PMC5405961/
- Giudice y otros (2020). Mapas de audio y vibración. https://pmc.ncbi.nlm.nih.gov/articles/PMC7090157/
- Façanha, Darin, Viana y Sánchez (2020). Revisión sistemática. https://doi.org/10.1145/3395769
- Nair y otros (2021). NavStick. https://arxiv.org/abs/2109.01202

### Repositorios examinados

- https://github.com/teal-lab/VisionPulse
- https://github.com/santient/audio-maze
- https://github.com/ohylli/audio-memory-maze
- https://github.com/abdulhakkeempa/maze-game
- https://github.com/m-toman/Audio-Games
- https://github.com/ohokke/AudioGame
- https://github.com/Orinks/EchoGraft
- https://github.com/Bernard-Olivier/SoundArcade
- https://github.com/eleven-hits/subway_surfers_blind
- https://github.com/soundscape-community/soundscape
- https://github.com/MIT-Assistive-Technology/Project-Daredevil
- https://github.com/gamesforblindgamers/blind-accessible-game-engines

### Técnicas

- OpenAL Soft: https://github.com/kcat/openal-soft
- pygame-ce: https://github.com/pygame-community/pygame-ce
- wxPython: https://github.com/wxWidgets/Phoenix
- accessible_output2: https://github.com/accessibleapps/accessible_output2
- Prism: https://github.com/ethindp/prism
- Política de uso de Overpass: https://dev.overpass-api.de/overpass-doc/en/preface/commons.html
