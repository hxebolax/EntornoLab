# Actualizaciones de EntornoLab

Cómo se actualiza la aplicación desde GitHub, cómo se publica una versión y qué garantías de seguridad y privacidad tiene. Este documento es para quien programa y publica; no viaja con la aplicación.

## Resumen

- La aplicación lee de GitHub un fichero pequeño y firmado, `version.json`. Si la versión es más nueva que la instalada, descarga el ZIP, lo verifica y sustituye la carpeta del programa sin tocar los datos del usuario.
- La firma es Ed25519. La clave pública va en el código; la privada está fuera del proyecto y de GitHub.
- Si la versión nueva no arranca, se restaura sola la anterior.
- Nada se comprueba sin permiso: la comprobación al arrancar está apagada de fábrica y se pregunta una sola vez.

Código: `app/core/red.py`, `app/core/descargas.py`, `app/services/actualizador.py`, `app/ui/dialogo_actualizacion.py`. Herramientas: `tools/generar_claves.py`, `tools/firmar_version.py`, `tools/publicar_version.py` y `tools/probar_actualizacion_real.py` (prueba con la compilación real). Arranque: `main.py` llama a `actualizador.recuperar_al_arrancar()` antes de abrir ninguna ventana.

## De dónde se lee la versión

Repositorio: `https://github.com/hxebolax/EntornoLab`. Hay dos canales.

- Estable: `https://github.com/hxebolax/EntornoLab/releases/latest/download/version.json`. Para GitHub, «latest» es la última publicación que no está marcada como preliminar.
- Pruebas: `https://github.com/hxebolax/EntornoLab/releases/download/pruebas/version.json`. Es una única publicación, de etiqueta `pruebas`, marcada como preliminar; sus recursos se sustituyen en cada versión de pruebas.

Quien elige el canal estable solo consulta la primera dirección. Quien elige el de pruebas consulta las dos y recibe la versión más alta; si no existe la publicación de pruebas, usa la estable. Un `version.json` con `"canal": "pruebas"` colocado en la dirección estable se rechaza aunque su firma sea buena.

Se eligió un `version.json` como recurso de la publicación, y no la API de GitHub, por tres motivos: la dirección no tiene límite de peticiones por hora, el fichero va firmado por el autor (la API no firma nada) y es el mismo esquema que ya usa Puerto Bravo.

## Formato de `version.json`

```json
{
	"app": "EntornoLab",
	"version": "1.2.0",
	"canal": "estable",
	"file": "EntornoLab_v1.2.0.zip",
	"sha256": "64 caracteres hexadecimales",
	"size": 123456789,
	"date": "2026-11-26",
	"url": "https://github.com/hxebolax/EntornoLab/releases/download/v1.2.0/EntornoLab_v1.2.0.zip",
	"novedades": "Texto de las notas de la versión.",
	"firma_ed25519": "firma en base64"
}
```

- `app`: debe ser `EntornoLab`; un manifiesto de otra aplicación se rechaza.
- `version`: `1.2.0`, `1.2.0-beta.1`, `1.2.0rc1`. Se comparan como números, no como texto.
- `canal`: `estable` o `pruebas`.
- `file`: nombre del ZIP, sin carpetas.
- `sha256` y `size`: huella y tamaño exactos del ZIP.
- `url`: dirección permanente del ZIP. Si falta, se busca junto al `version.json`.
- `novedades`: lo que se enseña al usuario antes de actualizar.
- `firma_ed25519`: firma de todo lo anterior. Se firma el JSON con las claves ordenadas, sin espacios y sin el propio campo de firma. Cambiar cualquier campo invalida la firma.

La aplicación comprueba la firma antes de mirar ningún otro campo.

## Qué hace la aplicación, paso a paso

1. Comprobar: descarga `version.json` (256 KB como máximo), verifica la firma, valida los campos y compara versiones. Rechaza una versión menor que la última que arrancó bien en este equipo (`data/config/actualizaciones.json`).
2. Descargar: baja el ZIP a `data/temp/actualizacion/descarga`. Si se corta, continúa donde se quedó. Nunca escribe más bytes que los firmados.
3. Verificar: tamaño y SHA-256. Si no coinciden, borra el fichero.
4. Extraer: revisa todas las entradas del ZIP antes de escribir ninguna. Una sola ruta absoluta, con `..`, con nombre reservado de Windows, enlace simbólico o entrada repetida rechaza el paquete entero.
5. Comprobar antes de cerrar nada: que no hay otra actualización a medias, que se puede crear, renombrar y borrar un fichero en la carpeta de la aplicación, en cada subcarpeta del programa, en `data\temp` y en las carpetas de recursos (falla en Archivos de programa sin permisos de administrador), que hay espacio libre (el ZIP por cuatro más 64 MB antes de descargar, y 64 MB después de extraer) y que ninguna ruta de la versión nueva pasa de 259 caracteres si Windows no tiene activadas las rutas largas. Después anota el inventario: `original.txt` (cada fichero instalado del programa y de los recursos, con su tamaño) y `nuevos.txt` (cada fichero que escribirá la versión nueva).
6. Comprobar los reproductores: si hay un reproductor abierto, avisa de que la sesión del alumno se perderá y pide permiso para cerrarlo. Sin permiso no se actualiza.
7. Sustituir: un script `.bat` espera a que se cierren el Estudio y cualquier otro proceso de esa carpeta (reproductores, también el que abre la sala, o un segundo Estudio), sin matarlos nunca. El motor (un guion de PowerShell) comprueba sin tocar nada que se puede escribir y que ningún otro programa tiene abierto un fichero que haya que sustituir. Después aparta cada elemento del programa a `data\temp\version_anterior` RENOMBRÁNDOLO y coloca el nuevo en su sitio, también renombrando. Por último relanza la versión nueva con `--tras-actualizar`.
8. Confirmar: la versión nueva escribe un marcador unos segundos después de abrir su ventana. Si el marcador no llega, el script devuelve cada elemento a su sitio, comprueba con el inventario que la versión anterior está entera y la relanza. La versión anterior avisa de lo ocurrido.

El registro de cada paso del script está en `data\logs\actualizacion.log`. El motor anota también cada reintento, cada carpeta que tuvo que sustituir fichero a fichero y cada resto que no se dejó borrar.

## Protección contra ficheros que no se dejan borrar

Windows no deja sobrescribir ni borrar un fichero que tiene abierto otro programa, y el antivirus y el indexador abren los ficheros recién escritos. Tampoco deja sobrescribir una DLL que otro proceso tiene cargada, ni borrar un fichero de solo lectura. Con `robocopy` encima de la instalación, cualquiera de esos casos dejaba la copia a medias. Ahora:

- Nada se copia encima de nada. Renombrar dentro del mismo disco es instantáneo, no necesita espacio y funciona con una DLL cargada y con ficheros de solo lectura. La versión nueva ya está descomprimida en `data\temp\actualizacion\nueva`, en el mismo disco.
- Primero se renombran las carpetas enteras (`lib` es una sola operación). Si una carpeta tiene algo abierto, no se deja renombrar y se sustituye fichero a fichero. Un fichero en uso que la versión nueva ya no trae se deja donde está y se anota.
- Antes de tocar nada, cada fichero que hay que sustituir se abre con el mismo permiso que pide renombrar (DELETE). Así se detecta un fichero abierto sin compartir, y no da falsa alarma con una DLL cargada, que sí se puede renombrar.
- Reintentos con espera creciente (0,25 s, 0,5 s, 1 s, 2 s, 4 s, 8 s, 8 s: unos 24 segundos) ante errores pasajeros: 5 (acceso denegado), 32 (en uso), 33 (región bloqueada), 145 y 1224. Si el fichero sigue en uso, la actualización no se aplica, la instalación no se toca y el mensaje dice qué fichero era.
- Todas las rutas del motor llevan el prefijo `\\?\`: no hay límite de 260 caracteres. Las rutas llegan por variables de entorno, nunca en la línea de órdenes, y el motor se ejecuta como bloque de órdenes, no como fichero `.ps1`, para que no le afecte la directiva de ejecución de scripts. La aplicación se vuelve a abrir con `Start-Process` y no con `start`, porque `start` vuelve a interpretar la orden y una carpeta con «&» la partía.
- Lo que no se deja borrar después (la copia de seguridad con una DLL que otro proceso sigue usando, restos de un intento anterior) se borra quitando el atributo de solo lectura, con reintentos. Si aun así no se puede, se aparta a `data\temp\actualizacion\por_borrar` y se vuelve a intentar en cada arranque. Como último recurso se pide a Windows que lo borre al reiniciar (`MoveFileExW` con `MOVEFILE_DELAY_UNTIL_REBOOT`), lo que solo funciona con permisos de administrador. Si no hay permisos, se anota y se reintenta en el siguiente arranque.
- Si la carpeta `nueva` de un intento anterior no se deja borrar, se aparta y se sigue. Solo si tampoco se puede apartar, el mensaje dice qué carpeta borrar a mano. Es la misma solución que se aplicó en otro proyecto del autor para el error «Acceso denegado» (WinError 5).

## Vuelta atrás y corte de luz

Mientras la instalación está a medias existe `data\temp\actualizacion\diario.txt`, con el estado (`aplicando`, `confirmando` o `restaurando`) y las dos versiones. El script deja su PID en `pid_script.txt`.

- La vuelta atrás devuelve a su sitio lo que haya en `data\temp\version_anterior`, aparta lo que ocupa su lugar y quita lo que la versión nueva trajo y antes no existía (según `nuevos.txt`). Al final comprueba que cada fichero de `original.txt` está en su sitio y con su tamaño. Se puede repetir sin riesgo: si se corta a mitad, se ejecuta otra vez.
- Si se va la luz, o alguien mata el script, el diario se queda. Al arrancar, antes de abrir ninguna ventana, el Estudio lo ve. Si el script ya no está vivo (su PID no es un `cmd.exe` que arrancó antes de escribirlo), lanza `recuperar.bat` y se cierra. `recuperar.bat` espera a que se cierre, deshace la sustitución, la comprueba y vuelve a abrir la versión anterior. Si la versión nueva ya había confirmado su arranque (estado `confirmando` y marcador correcto), la da por buena.
- Los ejecutables se colocan los últimos. Así, aunque el corte llegue a mitad, lo que arranca lleva el código que sabe recuperar la instalación.
- `recuperar.bat` se conserva mientras haya diario. Si la aplicación no llegara a arrancar, se puede ejecutar a mano con doble clic.
- Si la recuperación tampoco termina (resultado `rota`), no se vuelve a lanzar sola. El usuario recibe un mensaje que le dice que ejecute `recuperar.bat`.
- La versión que lanza el propio script (con `--tras-actualizar`) no lanza la recuperación: arranca con el diario presente a propósito.

## Qué ve el usuario

Antes de cerrarse: si falla una comprobación previa, un mensaje en el diálogo de actualizaciones. Ejemplos: «Windows no deja modificar la carpeta…» (con la recomendación de moverla fuera de Archivos de programa), «No hay espacio libre suficiente… hacen falta N MB y quedan M MB», «La carpeta… está demasiado honda» o «Hay una actualización anterior a medias…».

Al volver a abrirse, un mensaje accesible (`mostrar_mensaje`) con lo que pasó. Siempre dice en qué versión sigue y que los datos no se han tocado:

| Resultado | Mensaje |
| --- | --- |
| Correcta | Ninguno: la versión nueva lo anuncia por voz al arrancar y enseña sus novedades. |
| La versión nueva no arrancó | «La versión X no arrancó correctamente y se ha vuelto a la versión Y…». La versión X se salta en la comprobación automática. |
| Fichero en uso | «No se pudo actualizar a la versión X porque otro programa tenía en uso el archivo lib\… (suele ser el antivirus, el indexador de Windows o una copia de EntornoLab abierta). Sigue en la versión Y…». |
| Sin permiso | «… porque Windows no deja modificar la carpeta de EntornoLab; si está en Archivos de programa, muévala…». |
| Disco lleno, ruta larga | «… porque el disco se ha llenado» o «… porque la carpeta está demasiado honda…». |
| Corte de luz | «… porque se interrumpió antes de terminar, por ejemplo por un corte de luz…». |
| Reproductor abierto | «La actualización a la versión X no se aplicó porque la aplicación o un reproductor seguían abiertos…». |
| Otro fallo a mitad | «No se pudo terminar de actualizar a la versión X y se ha vuelto a la versión Y…». |
| No se pudo restaurar | «… ejecute recuperar.bat, que está en la carpeta data\temp\actualizacion…». |

Solo se salta la versión cuando no arrancó. Un fallo pasajero, como un fichero en uso o un corte de luz, se puede reintentar enseguida.

## Qué se toca y qué no

Se sustituye el programa: los dos ejecutables (`EntornoLab.exe` y `EntornoLabJugar.exe`), `lib` y cada elemento de la raíz que trae la versión nueva. `lib` queda exactamente como el de la versión nueva: lo que solo tenía la anterior se va con la copia de seguridad, que se borra cuando la versión nueva confirma su arranque. Un fichero de la raíz que la versión nueva no trae, como un acceso directo que puso el usuario, no se toca.

De `data` solo se refrescan los recursos que viajan con la aplicación: `bin`, `sounds`, `locales`, `docs`, `icons`, `ejemplos` y `plugins`. Se añaden o reemplazan ficheros; nunca se borra.

No se tocan jamás: `data\config`, `data\db`, `data\sessions`, `data\entornos`, `data\logs`, `data\backups`, `data\cache` ni ninguna otra carpeta de `data`. Si el ZIP trae algo para ellas, se descarta al extraer.

Complementos de `data\plugins`. La versión nueva trae sus complementos de serie, y con cada uno se sigue esta regla:

- No está instalado: se copia.
- El del ZIP es más nuevo que el instalado: se copia.
- Misma versión y no lo instaló el usuario: se copia, para repararlo.
- El instalado es más nuevo, o es del usuario con la misma versión: se conserva el instalado.

Los complementos que solo tiene el usuario no aparecen en el ZIP y no se tocan. El ZIP incluye además `data\plugins\de_serie.json`, la lista de complementos de serie, que escribe `tools\publicar_version.py`.

## Opciones del usuario

Están en el diálogo «Actualizaciones», que se abre con el menú Ayuda, «Buscar actualizaciones», y se guardan en `data\config\config.json`, sección `actualizaciones`:

- `comprobar_al_arrancar`: apagada de fábrica.
- `preguntado`: indica que ya se hizo la pregunta de permiso.
- `canal`: `estable` o `pruebas`.
- `version_saltada`: versión que no se vuelve a ofrecer en la comprobación automática. La comprobación manual siempre informa.
- `ultima_comprobacion`: fecha de la última comprobación correcta. La automática se hace como mucho una vez cada 24 horas.

Valor por defecto de la comprobación al arrancar: apagada. Motivo: EntornoLab trata datos de salud y de menores y promete no conectarse sin permiso. La primera vez que se abre el Estudio se pregunta, con «No conectar» como botón predeterminado; la respuesta se guarda y no se vuelve a preguntar.

## Integración en la ventana principal

```python
from app.ui import dialogo_actualizacion, dialogo_complementos_en_linea

# Tras mostrar la ventana principal, una sola vez:
dialogo_actualizacion.al_arrancar(
	ventana,
	al_haber_permiso=dialogo_complementos_en_linea.buscar_actualizaciones_en_segundo_plano,
)

# Menú Ayuda, «Buscar actualizaciones...»:
dialogo_actualizacion.mostrar_dialogo_actualizacion(ventana)

# Menú Herramientas, «Catálogo en línea de complementos...»:
dialogo_complementos_en_linea.mostrar_complementos_en_linea(ventana, al_cambiar=self.recargar_catalogo)
```

`al_arrancar` explica cómo acabó la actualización anterior, confirma el arranque, pregunta el permiso la primera vez y, solo con permiso, comprueba en segundo plano. `main.py` ya ignora el argumento `--tras-actualizar`.

Al compilar con cx_Freeze deben viajar los paquetes `cryptography` (ya incluido) y `certifi`.

## Claves de firma

- Generar el par, una sola vez: `.venv\Scripts\python.exe tools\generar_claves.py`.
- La clave privada se guarda fuera del proyecto: en la carpeta de la variable de entorno `ENTORNOLAB_CLAVES` o, si no está definida, en `%USERPROFILE%\.entornolab\claves\firma_ed25519.key`. La herramienta se niega a escribirla dentro del proyecto, y `.gitignore` excluye además `tools/claves/`.
- Con la variable `ENTORNOLAB_FIRMA_CONTRASENA` definida, la clave se guarda cifrada y hay que definirla también al firmar.
- La clave pública se pega en `CLAVES_PUBLICAS_ED25519` de `app/services/actualizador.py`. Verla otra vez: `tools\generar_claves.py --publica`.
- Guarde una copia de la privada fuera del equipo. Sin ella no se pueden publicar versiones ni catálogos que acepten las instalaciones ya repartidas.

Rotar la clave, si se pierde o se filtra:

1. Genere un par nuevo en otra carpeta: `tools\generar_claves.py --carpeta <carpeta nueva>`.
2. Añada la pública nueva a `CLAVES_PUBLICAS_ED25519`, sin quitar la antigua.
3. Publique una versión firmada todavía con la clave antigua. Las instalaciones que se actualicen ya conocen la nueva.
4. Pasado un tiempo, firme con la nueva y retire la antigua del código.

Si la clave antigua se perdió, las instalaciones existentes no pueden actualizarse solas: hay que avisar para que descarguen la versión a mano.

## Publicar una versión, paso a paso

1. Cambie `APP_VERSION` en `app\core\version.py` y `version` en `pyproject.toml`.
2. Añada `## Versión X.Y.Z - AAAA-MM-DD` en `data\docs\novedades.md`. Sin notas no se publica.
3. `entorno.bat pruebas` y `entorno.bat comprobar`, sin fallos.
4. `entorno.bat compilar`. Genera `build\entornolab` con los dos ejecutables.
5. Ensaye: `.venv\Scripts\python.exe tools\publicar_version.py --simular`. No escribe nada en `build` ni llama a GitHub; dice qué haría.
6. Prepare: `.venv\Scripts\python.exe tools\publicar_version.py`. Deja en `build\publicar` el ZIP, `version.json` firmado y verificado, y `notas_version.md`, y escribe las órdenes para subirlos.
7. Suba, de una de estas formas:
   - `tools\publicar_version.py --subir`, con GitHub CLI instalado e identificado (`gh auth login`).
   - Copie la orden `gh release create ...` que imprime el paso 6.
   - A mano: en GitHub, Releases, «Draft a new release», etiqueta `vX.Y.Z`, adjunte el ZIP y `version.json`, marque «Set as the latest release» y publique.
8. Compruebe con una copia instalada de la versión anterior: Ayuda, «Buscar actualizaciones», «Comprobar ahora», «Actualizar ahora». Confirme que la configuración, los alumnos y los entornos siguen ahí.

Para una versión de pruebas, use un número preliminar (`1.3.0-beta.1`) y añada `--canal pruebas` en los pasos 5 a 7. La herramienta crea la publicación `pruebas` si no existe o sustituye sus recursos. Borre de vez en cuando los ZIP antiguos de esa publicación.

La primera vez hay que crear el repositorio público `hxebolax/EntornoLab` en GitHub y subir el código. Hasta que exista una publicación, la comprobación responde «El servidor no tiene publicada esa información todavía».

## Privacidad: qué viaja por la red

Ningún dato personal. En concreto:

- Solo se hacen peticiones `GET` a `github.com` y a los servidores a los que GitHub redirige las descargas. No se envía ningún cuerpo, formulario ni galleta.
- Las únicas cabeceras son `User-Agent: EntornoLab/<versión>`, `Accept`, `Accept-Encoding`, `Cache-Control` y, al continuar una descarga, `Range` e `If-Range`. No hay identificador de instalación, nombre del equipo, usuario de Windows, idioma ni sistema operativo.
- No se envían nombres de alumnos, entornos, sesiones ni estadísticas de uso. La aplicación no tiene telemetría.
- Como en cualquier descarga, GitHub ve la dirección IP desde la que se conecta el equipo y la versión del `User-Agent`.
- Solo se admite `https`, con el certificado y el nombre del servidor verificados. Una redirección a `http` se rechaza. `http` solo se admite contra el propio equipo, para las pruebas.

Las pruebas comprueban las cabeceras enviadas (`tests\test_core_red.py` y `tests\test_complementos_en_linea_servicio.py`).

## Seguridad: qué protege cada medida

- Firma Ed25519 del manifiesto: quien entre en la cuenta de GitHub no puede publicar una versión que las instalaciones acepten, porque no tiene la clave privada.
- SHA-256 y tamaño firmados: el ZIP no se puede cambiar por otro.
- Rechazo de retrocesos: no se puede reinstalar una versión antigua con fallos conocidos.
- Canal firmado: una versión de pruebas no puede aparecer en el canal estable.
- Extracción segura: un ZIP no puede escribir fuera de su carpeta.
- Datos del usuario descartados: un ZIP no puede sustituir la configuración ni la base de datos.
- Copia de seguridad, marcador de salud, diario e inventario: ni una versión que no arranca, ni un fichero bloqueado, ni un corte de luz dejan la aplicación inservible.
- Nunca se mata un proceso para actualizar: si el Estudio o un reproductor no se cierran, la actualización se cancela sin tocar nada.
- Desde el código fuente no se sustituye nada: solo se informa de que hay versión nueva.

## Si algo va mal

- «No se pudo conectar» o «no ha respondido a tiempo»: no hay conexión o GitHub no responde. Se puede reintentar; la descarga continúa donde se quedó.
- «No está firmada» o «la firma no es válida»: `version.json` no se firmó con la clave que lleva la aplicación. Vuelva a prepararla con `tools\publicar_version.py`.
- «No supera la verificación de integridad» o «no tiene el tamaño anunciado»: el ZIP subido no es el que se firmó. Suba el ZIP y el `version.json` generados juntos.
- «La versión X no arrancó correctamente y se ha vuelto a la versión Y»: mire `data\logs\actualizacion.log` y `data\logs\arranque_fallido.log`. La versión nueva que no arrancó queda unos momentos en `data\temp\actualizacion\descartada`; se borra en el siguiente arranque.
- «La aplicación o un reproductor seguían abiertos»: cierre todos los reproductores y vuelva a intentarlo.
- «Otro programa tenía en uso el archivo…»: el registro dice qué fichero y con qué error. Suele ser el antivirus. Espere un poco o añada la carpeta a sus exclusiones.
- «Ejecute recuperar.bat»: la vuelta atrás no terminó, por ejemplo porque un fichero siguió bloqueado. Cierre todo y ejecute `data\temp\actualizacion\recuperar.bat`. Mientras exista `diario.txt`, la aplicación no limpia esa carpeta.

## Escenarios probados

`tests\test_actualizador_escenarios.py` usa instalaciones falsas con la forma de la compilación (`tests\_instalacion_falsa.py`): dos ejecutables, una biblioteca en la raíz, `lib` con una DLL de verdad, recursos de serie y datos del usuario. Están en «Mis cosas\EntornoLab (copia) & 100% ñ'». El programa falso, con `--comprobar-arranque`, dice su versión y detecta una mezcla de versiones. Los bloqueos son reales: los pone otro proceso, cuya línea de órdenes no nombra la carpeta, como un antivirus. En todos los casos se comparan las huellas SHA-256 del programa y de los datos del usuario. Las pruebas marcadas `lento` ejecutan el `.bat` de verdad.

| Escenario | Cómo se prueba | Resultado esperado |
| --- | --- | --- |
| Actualización normal | `.bat` real | Programa idéntico al de la versión nueva, que arranca. Datos intactos. |
| Versión igual, más antigua o saltada | Servidor local | No se ofrece. La saltada solo se respeta en la comprobación automática. |
| Canal estable y de pruebas | Servidor local | Cada canal recibe la suya. |
| Firma mala, SHA malo, ZIP dañado, rutas `..` | Servidor local | Se rechaza sin tocar nada. |
| Descarga cortada y sin red | Servidor local | Error con «Reintentar». Al reintentar sigue con `Range`. |
| Sin permiso de escritura | Denegación real con icacls | Se para antes de descargar. |
| Disco lleno antes o durante la extracción | Simulado | Se para sin dejar restos. |
| Rutas largas sin `LongPathsEnabled` | Simulado | Se rechaza la versión. |
| Rutas de más de 260 caracteres | `.bat` real | Actualiza, y también vuelve atrás. |
| Restos de solo lectura o en uso de otra vez | Real | Se borran o se apartan. |
| Ficheros y carpetas de solo lectura, copia de seguridad vieja | `.bat` real | Actualiza. La copia vieja no vuelve a su sitio. |
| Fichero abierto sin compartir que no se suelta | `.bat` real | No se aplica, sin tocar nada. El mensaje nombra el fichero. |
| Fichero abierto unos segundos | `.bat` real | Reintenta y actualiza. |
| DLL cargada por otro proceso | `.bat` real | Actualiza. La DLL vieja se borra cuando la sueltan. |
| Carpeta con un fichero en uso | `.bat` real | Se sustituye fichero a fichero. |
| Permiso de borrar denegado en un fichero | icacls y `.bat` real | No se aplica, sin tocar nada. |
| Fallo forzado a mitad | `.bat` real | Vuelve atrás, idéntica byte a byte, y arranca. |
| Corte de luz (script matado a mitad) | `.bat` real | Al arrancar se lanza `recuperar.bat`, vuelve atrás y arranca. |
| `recuperar.bat` a mano | `.bat` real | Igual que el caso anterior. |
| La versión nueva no arranca | `.bat` real | Vuelve atrás y la versión se salta. |
| Reproductor abierto que se cierra, o que no se cierra | `.bat` real | Espera sin matarlo. Si no se cierra, cancela. |
| Segundo Estudio abierto | `.bat` real | Espera y actualiza. |
| Mensaje al volver a abrir | Cada estado y motivo | Dice la versión en que sigue. Solo se salta la versión si no arrancó. |

## Prueba con la compilación real

`tools\probar_actualizacion_real.py` hace la prueba de punta a punta con los ejecutables reales, en una carpeta temporal propia que borra al terminar:

1. Compila la versión actual (con `--compilar`; si no, usa `build\EntornoLab_v<versión>.zip`). Copia el proyecto, sube la versión SOLO en la copia (con su apartado de novedades), la compila y la empaqueta con `tools\empaquetar.py`. Este la firma con la clave de desarrollo, que está fuera del proyecto. La herramienta solo comprueba que `version.json` salió firmado: nunca lee, copia ni imprime la clave.
2. Instala la versión actual en «Mis cosas\EntornoLab (copia)», con datos del usuario y un complemento suyo. Sirve la versión nueva desde `tests\servidor_http_prueba.py`.
3. Escenario A: abre el Estudio y un reproductor reales. Otro proceso carga una DLL de `lib` y otro abre sin compartir otro fichero de `lib` durante 25 segundos. Prepara la actualización, lanza el script, cierra el Estudio y, 8 segundos después, el reproductor.
4. Escenario B: instalación limpia y fallo forzado a mitad.
5. Escenario C: instalación limpia. Se mata el script a mitad y se abre el Estudio real.

La comprobación y la descarga las hace el código del proyecto, el mismo que va compilado, porque la versión instalada solo consulta GitHub. La sustitución, el arranque con `--tras-actualizar`, el marcador de salud y la recuperación son los de los ejecutables reales.

Resultado del 26 de noviembre de 2026, de la 0.1.0 a la 0.1.1, unos 6 minutos sin contar la primera compilación:

- A: el script esperó al reproductor. El fichero bloqueado se consiguió tras 6 reintentos (unos 16 segundos). Se comprobaron 5161 ficheros y se colocaron 20 elementos del programa y 3181 recursos. La 0.1.1 confirmó su arranque a los 10 segundos. Resultado `correcta`. Los 1980 ficheros del programa son idénticos a los de la compilación 0.1.1. Los datos del usuario están intactos. `--comprobar-arranque` de los dos ejecutables, correcto. La copia de seguridad, con la DLL todavía cargada, quedó apartada en `por_borrar` para el siguiente arranque.
- B: resultado `revertida` (`fallo_copia`). La 0.1.0 volvió a abrirse y confirmó su arranque. El programa es idéntico al de la compilación 0.1.0 y los datos están intactos.
- C: el Estudio real vio el diario, lanzó `recuperar.bat` y se cerró. Resultado `revertida` (`interrumpida`). La 0.1.0 volvió a abrirse. El programa es idéntico y los datos están intactos. El mensaje fue: «No se pudo actualizar a la versión 0.1.1 porque se interrumpió antes de terminar, por ejemplo por un corte de luz o porque se cerró el proceso a la fuerza. Sigue en la versión 0.1.0 y sus datos no se han tocado. Puede volver a intentarlo desde el menú Ayuda.»

## Lo que las pruebas no pueden comprobar

Las pruebas usan un servidor local y nunca salen a Internet. Queda por verificar a mano, con una publicación real:

- La dirección `releases/latest/download/version.json` y sus redirecciones, con el repositorio ya creado.
- La verificación de certificados en la versión compilada, en un Windows recién instalado.
- La descarga a través de un proxy corporativo.
- El diálogo de actualizaciones de la versión compilada con un lector de pantalla: la prueba real hace de diálogo con el código del proyecto.
- El borrado al reiniciar (`MOVEFILE_DELAY_UNTIL_REBOOT`). Exige permisos de administrador y un reinicio real. Sin permisos solo se comprueba que se informa y se sigue.
- Un disco lleno de verdad y un antivirus real. Se simulan, el primero sustituyendo la escritura y el segundo con un proceso que abre el fichero sin compartir.
- Un corte de luz real. Se simula matando el script y sus procesos hijos. Una escritura a medias en el disco no se puede provocar así, pero el script solo renombra, y cada renombrado es atómico en NTFS.
