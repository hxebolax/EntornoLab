# Seguridad y privacidad

EntornoLab guarda datos de alumnos, que pueden ser menores de edad. Un fallo de seguridad o de privacidad puede exponerlos. Por eso, estos problemas se avisan en privado.

## Qué versiones se corrigen

Se corrige siempre la última versión publicada. No se publican correcciones para versiones anteriores: actualice con Ayuda, «Buscar actualizaciones».

## Qué se considera un problema de seguridad o de privacidad

Por ejemplo:

- que se puedan leer los datos cifrados de las fichas sin la contraseña;
- que la sala de supervisión acepte conexiones sin el código, o que se pueda suplantar;
- que el actualizador o el catálogo de complementos acepten un paquete sin firmar o modificado;
- que un entorno, una actividad o un complemento consigan ejecutar código o escribir fuera de su carpeta;
- que un registro, un informe o una exportación contengan datos personales que no deberían;
- que la aplicación se conecte a Internet sin que se le haya pedido.

## Cómo avisar

1. **No abra una incidencia pública** ni comente el problema en público.
2. Use el aviso privado de seguridad del repositorio en GitHub: en la página del proyecto, pestaña «Security», «Report a vulnerability». Si no está disponible, escriba al autor por el canal de contacto de su perfil de GitHub y pida un medio privado.
3. Explique el problema, la versión, los pasos para reproducirlo y qué datos podrían quedar expuestos.

## Nunca envíe datos de alumnos

- No adjunte bases de datos, fichas, sesiones, informes, exportaciones ni carpetas `data` reales.
- Si necesita un ejemplo, cree un alumno de prueba con un alias inventado y sin nombre real.
- Los registros de `data\logs` no deberían contener datos de alumnos; si encuentra alguno en ellos, eso mismo es un problema que hay que avisar, y no los adjunte sin revisarlos.

## Qué pasa después

El autor confirmará que ha recibido el aviso, lo estudiará y, si se confirma, publicará una corrección y lo contará en las novedades de la versión, sin datos de quien avisó salvo que lo pida. EntornoLab es un proyecto personal sin plazos garantizados, pero los problemas de privacidad tienen prioridad.
