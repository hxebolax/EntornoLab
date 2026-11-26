# Documentación técnica de EntornoLab

Esta carpeta es para quien programa, prueba, traduce o publica EntornoLab. No viaja con la aplicación: la documentación de usuario (manual, teclas, novedades, guías y licencias) está en `data/docs`. Las convenciones de código están en [CONTRIBUTING.md](../CONTRIBUTING.md) y la presentación general, en el [README](../README.md).

## Para empezar

- [arquitectura.md](arquitectura.md): el contrato entre módulos, las capas y qué puede importar cada una.
- [desarrollo.md](desarrollo.md): montar el entorno, ejecutar, probar, traducir, compilar y publicar.

## Las dos aplicaciones

- [estudio.md](estudio.md): el Estudio del profesional en wxPython: ventana, menús, operaciones, plano y accesibilidad.
- [estudio-seguimiento.md](estudio-seguimiento.md): las ventanas de alumnos, actividades, sesiones, informes y supervisión del Estudio.
- [reproductor.md](reproductor.md): Jugar, el reproductor del alumno en pygame: pantallas, menús, opciones y modo recorrido.

## Motor, sonido y entrada

- [motor.md](motor.md): el mundo, el movimiento, la percepción, la acústica, la dinámica de la calle y la sesión de juego.
- [sonido.md](sonido.md): motores de sonido, perfiles de cabeza, protección auditiva, catálogo de sonidos y paquetes.
- [voz.md](voz.md): voz por lector de pantalla o SAPI, canales, historial, braille y seguimiento de cabeza.
- [entrada.md](entrada.md): acciones con nombre, mapas de teclado y de mando, reasignación y vibración.

## Actividades, seguimiento y supervisión

- [actividades.md](actividades.md): los tipos de actividad, sus campos, premios, ayudas, niveles, exámenes y puntuación.
- [seguimiento.md](seguimiento.md): base de alumnos, cifrado, sesiones, medidas, informes y cuaderno de evaluación real.
- [supervision.md](supervision.md): la sala de supervisión en vivo: protocolo, emparejamiento, cifrado y órdenes.

## Formatos, importación y exportación

- [formato-de-entornos.md](formato-de-entornos.md): el formato de los ficheros `.elab`.
- [formato-de-complementos.md](formato-de-complementos.md): la referencia de cada clave de un complemento de objetos.
- [crear-un-complemento.md](crear-un-complemento.md): guía paso a paso para hacer un complemento a mano.
- [importar-y-exportar.md](importar-y-exportar.md): OpenStreetMap, DXF, SVG, imagen de fondo, GPX y todas las exportaciones.

## Publicación

- [actualizaciones.md](actualizaciones.md): el actualizador, la firma Ed25519, las claves y cómo publicar una versión.
- [catalogo-de-complementos.md](catalogo-de-complementos.md): el catálogo en línea de complementos y cómo publicar uno.
