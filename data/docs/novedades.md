# Novedades de EntornoLab

## Versión 0.1.1 - 2026-11-27

Versión de mejoras de rapidez y de una corrección al cerrar el Estudio.

### Mejoras

- Deshacer y rehacer son mucho más rápidos y gastan muy poca memoria: cada cambio guarda solo lo que se ha modificado. Con un barrio grande, mover un espacio, cambiar una propiedad, deshacer o rehacer tarda una fracción de segundo, y cien pasos de deshacer ocupan unos pocos megas en lugar de cientos.
- Tras deshacer o rehacer, la selección vuelve al elemento afectado y se anuncia qué se ha deshecho o rehecho.

### Correcciones

- Al cerrar el Estudio con un entorno abierto podía aparecer un aviso de error del árbol del entorno. Ya no ocurre; los entornos se guardaban bien igualmente.

## Versión 0.1.0 - 2026-11-26

Primera versión pública de EntornoLab: una aplicación portable y sin conexión para aprender lugares antes de visitarlos.

### Novedades

- Estudio del profesional, accesible con lector de pantalla y con ratón: construya interiores con habitaciones, plantas, puertas, escaleras, rampas y ascensores, y exteriores con calles, aceras, cruces, pasos de peatones con semáforo y paradas.
- Tres formas de colocar las cosas: con medidas, en relación con otra cosa (adosada, contra una pared, en una esquina, junto a otro elemento) o recorriendo el entorno con Jugar y pulsando F4.
- Catálogo de objetos en complementos, con búsqueda, filtros por clasificación, favoritos, ajuste a escala automático, aviso de obstáculos colgantes y propuesta de mobiliario para amueblar un espacio.
- Gestión de complementos, catálogo en línea con complementos firmados y un asistente para crear complementos propios y compartirlos.
- Comprobar el entorno (F5), medir entre dos elementos, plano gráfico con cuadrícula y descripción completa del entorno en texto.
- Importar de OpenStreetMap sin inventar nada de lo que el mapa no dice, y de planos DXF y SVG, imagen de fondo y rutas GPX.
- Exportar el paquete para el alumno, la descripción en texto, Markdown o HTML, el plano visual, el plano táctil con leyenda en braille, GeoJSON y DXF.
- 22 tipos de actividad entre juegos, prácticas y exámenes, con premios escondidos (a mano, dentro de objetos, repartidos o colocados recorriendo, con mensaje y audio grabado), objetivos, ayudas permitidas con límite de usos, niveles de retirada de ayudas, estilos infantil, juvenil y adulto, contrarreloj y el travieso.
- Fichas de alumnos protegidas con contraseña y cifradas, con ajustes de juego, cálculo del paso, lista de trabajo, recompensas, exportación y borrado completo.
- Supervisión en vivo en el mismo equipo o en la red local, cifrada, con código de emparejamiento y huella: mensajes, pistas, premios en directo, recolocar, pausar y marcar momentos.
- Sesiones grabadas, repetición del recorrido paso a paso, informes de sesión, comparación, evolución, examen y evaluación real, y cuaderno para las pruebas en el lugar real.
- Jugar, el audiojuego del alumno: sonido 3D, teclado o mando de Xbox o PlayStation, tutorial, «Aprender los sonidos», «Practicar los controles», catorce ayudas, semáforos, coches, ascensores, escaleras y conexión con el profesor.
- Cuatro motores de sonido, perfiles de cabeza, seguimiento de cabeza con OpenTrack, protección auditiva y tres paquetes de sonidos: Sintético, Natural y Grabado.
- Manual completo (F1), lista de teclas (Ctrl+F1), ayuda de cada control (Ctrl+H) y búsqueda de actualizaciones firmadas, apagada mientras no se dé permiso.

### Lo que falta probar

- Esta versión se ha comprobado con pruebas automáticas. Todavía no se ha probado con alumnos, a mano con cada lector de pantalla ni con mandos físicos. Sus avisos ayudarán a mejorarla.
