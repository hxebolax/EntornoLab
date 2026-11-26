# Preguntas frecuentes sobre EntornoLab

## Sobre la aplicación

### ¿Qué es EntornoLab?

Una aplicación de Windows, portable y sin conexión, para aprender lugares antes de visitarlos. El profesional construye el lugar en el Estudio y el alumno lo recorre en Jugar, un audiojuego con sonido 3D.

### ¿Cuánto cuesta?

Nada. Es software libre, con licencia GPL 3 o posterior. Si le resulta útil, puede invitar a un café al autor desde el menú Ayuda.

### ¿Sustituye a las clases de orientación y movilidad?

No. Es una herramienta educativa y de entrenamiento. No diagnostica ni trata, y no sustituye al aprendizaje en el lugar real con un profesional.

### ¿Está demostrado que funciona?

Hay estudios con juegos parecidos que muestran que se puede aprender un edificio concreto jugando, sobre todo a encontrar la salida más cercana. Son estudios pequeños, de un solo edificio. No está demostrado que sirva para barrios enteros, que dure meses ni que mejore la movilidad en lugares no entrenados. EntornoLab no se ha probado todavía con alumnos. El apartado «Base científica y sus límites» del manual lo explica.

### ¿Necesita Internet?

No. Solo se conecta si usted lo pide: para buscar actualizaciones, descargar complementos o importar de OpenStreetMap. La supervisión usa el propio equipo o la red local, no Internet.

### ¿En qué idiomas está?

En español y en inglés: la interfaz, el manual, la lista de teclas y las guías. El idioma se cambia en Preferencias, pestaña General; por defecto se usa el de Windows.

## Instalación y equipo

### ¿Cómo se instala?

No se instala: se descomprime el ZIP en una carpeta con permiso de escritura y se abre `EntornoLab.exe` (el Estudio) o `EntornoLabJugar.exe` (Jugar). Para quitarlo, se borra la carpeta.

### ¿Qué equipo hace falta?

Windows 10 u 11 de 64 bits y auriculares estéreo. Se recomienda un lector de pantalla. El mando de Xbox o de PlayStation es opcional.

### ¿Funciona con mi lector de pantalla?

El Estudio usa controles estándar de Windows y Jugar habla a través del lector abierto o con la voz de Windows (se puede elegir otra salida de voz, o ninguna). No se ha comprobado todavía a mano con cada lector; si algo no se lee bien, avise.

### ¿Puedo llevarlo en una memoria USB?

Sí. Todo, también los datos, está en la carpeta del programa.

## El Estudio

### ¿Necesito ver para construir un entorno?

No. Todo se hace con el teclado y el lector de pantalla, con medidas o en relación con lo que ya hay. El plano gráfico es un añadido para quien ve.

### ¿Puedo partir de un plano que ya tengo?

Sí: Archivo, Importar, acepta planos DXF y SVG, y una imagen de fondo para calcar encima. También puede importar las calles de un lugar real desde OpenStreetMap.

### ¿Por qué el entorno importado de OpenStreetMap dice «el mapa no lo dice»?

Porque el programa no inventa nada. Si el mapa no dice, por ejemplo, si un semáforo es sonoro, lo deja así para que usted lo compruebe en el lugar.

### ¿Puedo cambiar los tiempos de un semáforo?

En esta versión, no. Todos los semáforos tienen 25 segundos de verde, 5 de intermitente y 45 de rojo.

### ¿Cómo entro en un edificio desde la calle?

Ponga las salas del edificio en la misma planta de calle y abra en su pared un portal o una puerta que dé a la acera. Un «Edificio con portal» es macizo y su portal solo es una referencia.

### ¿Se pierde el trabajo si se va la luz?

El Estudio guarda una copia de recuperación cada 5 minutos si hay cambios, y al guardar deja la versión anterior con la terminación `.bak`. Al abrirlo después de un cierre inesperado, ofrece recuperar el trabajo.

## Alumnos y datos

### ¿Qué pasa si olvido la contraseña del profesional?

No se pueden recuperar los datos cifrados: el nombre real, las notas y las observaciones. La contraseña no se guarda en ningún sitio. Anótela en un lugar seguro.

### ¿Qué datos de los alumnos guarda y dónde?

Todo queda en la carpeta `data` del programa. El nombre real y las notas se cifran con la contraseña; el alias, los recorridos y las medidas no. No hay nube ni telemetría. El manual lo detalla en «Privacidad y datos».

### ¿Por qué el alias no debe ser el nombre del alumno?

Porque el alias no se cifra, aparece en Jugar y es lo único que viaja por la red en la supervisión.

### ¿Los ajustes de juego de la ficha llegan a Jugar?

Sí, por la sala de supervisión. Cuando Jugar se conecta con el alias de un alumno que tiene ficha (y los datos de alumnos están abiertos en el Estudio), recibe sus ajustes de juego, su estilo, su lista de trabajo y el nivel en que va en cada actividad, y mandan sobre lo que tenga en Opciones. Si cambia la ficha mientras juega, le llega al momento. Jugar lo guarda en ese equipo para los días sin conexión. Nunca viajan el nombre real ni las notas.

### ¿Jugar recuerda el nivel de ayudas de una partida a otra?

Sí. En las actividades con «Retirar las ayudas por niveles», Jugar empieza la siguiente partida en el nivel al que llegó el alumno. Al incorporar las sesiones, ese nivel pasa a la ficha, junto con las recompensas ganadas.

### ¿Tengo que reiniciar Jugar al cambiar las Preferencias del Estudio?

No. Si Jugar está conectado a la sala, el Estudio le pide que relea las preferencias y aplica al momento el paquete de sonidos, el motor, los volúmenes o la voz nuevos. Si no está conectado, lo aplica al volver a su menú principal.

### ¿Cómo traigo las sesiones de un alumno que juega en otro equipo?

Las sesiones se guardan en la carpeta `data\sessions` del equipo donde se juega y pasan a la base al abrir allí los datos de alumnos. En esta versión no hay una orden para importarlas desde otro equipo.

### ¿Qué significan las cifras de los informes?

Describen lo que pasó en el simulador: tiempo, distancia, choques, ayudas, camino andado frente al más corto y forma de explorar. No son una nota ni un diagnóstico. El manual explica cada una en «Cómo leer las cifras».

## Jugar

### ¿Por qué no oigo bien si un sonido está delante o detrás?

Pruebe otro «Perfil de cabeza» en Opciones, Sonido, y compruebe que los auriculares están bien puestos. El motor binaural de serie es el que mejor sitúa delante y detrás.

### Jugar habla demasiado.

Baje «Cuánto cuenta el juego» en Opciones, «Voz y braille».

### No tengo lector de pantalla ni quiero la voz de Windows. ¿Puedo jugar sin voz?

Sí. En Jugar, Opciones, «Voz y braille», ponga «Habla» en «nadie: sin voz» (o en Preferencias del Estudio, pestaña Voz, «Salida de voz», «Sin voz: no hablar nunca»). Los mensajes se ven abajo en la pantalla, quedan en el historial (F2 y F3) y, si hay un lector abierto, llegan a la línea braille. Con «solo el lector de pantalla», Jugar habla por el lector cuando lo hay y se calla cuando no, sin pasar nunca a la voz de Windows.

### Me he quedado sin voz en Jugar y no sé volver.

Pulse Control+F12 en cualquier pantalla: vuelve la voz automática (el lector de pantalla o, si no hay, la voz de Windows).

### ¿Puedo cambiar las teclas?

Sí, en Opciones, Teclado, y los botones del mando en Opciones, Mando. «Practicar los controles» dice qué hace cada tecla.

### ¿Qué mandos sirven?

Los de Xbox y PlayStation. No se han probado todavía con mandos físicos.

### ¿Se puede guardar una partida a medias?

No. «Continuar» vuelve a empezar la última actividad.

### ¿Qué pasa si cruzo en rojo?

Se avisa y queda anotado, pero no se pierde la partida. Es un simulador: no sirve para decidir un cruce real.

## Ayuda

### ¿Dónde aviso de un fallo?

En el Estudio, Ayuda, «Avisar de un fallo». Diga qué hacía, qué esperaba y qué pasó, y adjunte el registro de Herramientas, «Abrir la carpeta de registros». Nunca publique datos de alumnos.

### ¿Cómo se actualiza?

Ayuda, «Buscar actualizaciones». La actualización conserva sus entornos, fichas, sesiones y preferencias.
