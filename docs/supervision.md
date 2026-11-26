# Supervisión en vivo: sala, cliente, protocolo y seguridad

Documentación técnica del paquete `app/supervision`. El contrato general está en `docs/arquitectura.md`.

El Estudio abre una **sala** (servidor TCP); cada reproductor se conecta como **cliente** con un código de emparejamiento. No hay nube ni servidores externos: todo ocurre en el mismo ordenador o en la red local. El paquete no importa `wx` ni `pygame`.

## Módulos

| Módulo | Qué hace |
| --- | --- |
| `protocolo.py` | Mensajes, validación, codificar y decodificar, troceado de líneas |
| `seguridad.py` | Código de emparejamiento, límite de intentos, certificado propio, huellas recordadas |
| `sala.py` | `Sala`: servidor asyncio en su hilo (lado Estudio) |
| `cliente.py` | `ClienteSupervision`: hilo del reproductor |
| `descubrimiento.py` | Búsqueda de salas por UDP y dirección escrita a mano |

## La sala (lado Estudio)

Patrón «motor en un hilo + foto + pedir»: la ventana no toca nada del servidor.

```python
sala = Sala(nombre="Aula 3")
sala.iniciar(puerto=47900, codigo="", red=False)     # codigo vacío: se genera; queda en sala.codigo
foto = sala.foto()                                   # dict nuevo con todo el estado
for suceso in sala.eventos_pendientes(): ...         # vacía la cola de sucesos
sala.pedir("Luna", "mensaje", texto="Sigue la pared")   # vuelve al momento
sala.responder("Profe", id_peticion, True, "Mesa colocada")
sala.expulsar("Luna"); sala.olvidar("Luna"); sala.detener()
```

`iniciar(puerto=47900, codigo="", *, red=False, host=None, puerto_local=0, anunciar=True, puerto_descubrimiento=47901)`:

- `red=False` (un solo ordenador): escucha solo en `127.0.0.1`, sin TLS.
- `red=True`: escucha con TLS en todas las interfaces (o en `host`) y, además, sin TLS en `127.0.0.1:puerto_local` para el reproductor que el Estudio lanza en el mismo ordenador. Fuera de `127.0.0.1` nunca se acepta una conexión sin cifrar. La primera vez crea el certificado (alrededor de un segundo; llamar desde un hilo de trabajo).
- Lanza `ErrorSala` con un mensaje para mostrar si el puerto está ocupado o falla el certificado.

`foto()` devuelve `activa`, `nombre`, `red`, `puerto`, `puerto_local`, `codigo`, `huella`, `huella_legible`, `direcciones` (las IP que hay que dictar), `bloqueados` y `alumnos`. Cada alumno: `id`, `alias`, `conectado`, `cifrada`, `recorrido`, `entorno`, `actividad`, `modo`, `planta`, `x`, `y`, `rumbo`, `espacio`, `posicion` (descrita en palabras), `delante`, `ultimo_texto`, `voces` (historial de 50), `contadores`, `pausado`, `tiempo_activo`, `eventos` (últimos 50), `terminado`, `resultado`, `segundos_sin_contacto`, `conectado_desde`, `errores_protocolo`, `reconexiones`. Es una copia: modificarla no afecta a la sala.

`eventos_pendientes()` devuelve y vacía la cola. Cada suceso es `{"tipo", "alumno", "alias", "hora", "datos"}`:

| Tipo | Datos |
| --- | --- |
| `conectado`, `reconectado` | `recorrido`, `cifrada` |
| `desconectado` | `motivo` (`corte`, `sin_latido`, `protocolo`, `expulsado`, `sustituida`, `cierre`, `saturado`), `terminado` |
| `evento` | `t`, `tipo`, `datos` (un `EvRegistro` del alumno) |
| `voz` | `t`, `texto`, `canal` |
| `fin` | `completada`, `resultado` |
| `peticion` | `id`, `accion`, `planta`, `x`, `y`, `rumbo`, `datos` |
| `codigo_incorrecto` | `direccion`, `intentos_restantes` (sin alias: no ha entrado) |
| `bloqueado` | `direccion`, `espera_s` |

`pedir(alumno, orden, **datos)` valida la orden y sus datos (lanza `ValueError` / `ErrorProtocolo` si son incorrectos: es un fallo de quien llama) y devuelve `False` si ese alumno no está conectado.

**Identidad de los alumnos.** El `id` es el alias. Si el mismo reproductor se reconecta (misma `instancia`) conserva su ficha, su historial y sus contadores. Si otro reproductor llega con un alias que ya está conectado, recibe otro id («Luna (2)»).

## El cliente (lado reproductor)

```python
cliente = ClienteSupervision(host, puerto, codigo, alias, entorno="…", actividad="…", modo="juego", recorrido=False)
cliente.iniciar()                             # vuelve al momento
# en cada fotograma:
cliente.estado(sesion.estado())               # se envía el último 5 veces por segundo
for tipo, datos in cliente.ordenes_pendientes(): ...
for tipo, datos in cliente.avisos_pendientes(): ...
# cuando ocurren:
cliente.evento(ev.tipo, ev.datos); cliente.voz(texto, canal); cliente.fin(completada, resultado)
ident = cliente.peticion("colocar_aqui", planta="p0", x=3.0, y=4.0, rumbo=90.0, objeto="mobiliario/mesa")
cliente.detener()
```

- **Nunca bloquea el bucle del juego**: todas esas llamadas solo tocan colas en memoria. Conectar, enviar, recibir y reconectar ocurre en el hilo del cliente.
- `tls=None` decide solo: sin TLS únicamente si el host es `127.0.0.1`, `localhost` o `::1`.
- **Reconexión**: si se corta, reintenta con espera creciente (0,5 s, 1 s, 2 s… hasta 10 s). Los eventos, el `fin` y las peticiones ocurridos mientras tanto (hasta 500) se envían al volver; la voz atrasada se descarta.
- **No reintenta** tras `codigo`, `huella`, `sala`, `version`, `protocolo` o `expulsado`: queda en `estado_conexion == "rechazado"` con `motivo_rechazo`, hasta `cambiar_codigo(codigo)`, `aceptar_huella_nueva()` o `reintentar()`. Tras `bloqueado` espera lo que indica la sala y vuelve a probar.
- `estado()` acepta el diccionario de `Sesion.estado()` tal cual: los campos que no son del protocolo se descartan y los de tipo inesperado se omiten (con un aviso en el registro, una vez por campo).
- `avisos_pendientes()`: `conectado`, `desconectado` (`motivo`) y `rechazado` (`motivo`, `espera_s`).
- `detener()` envía antes lo pendiente y, si había un `fin`, espera hasta un segundo el acuse de la sala.
- `fin()` olvida además el último estado: el hilo no lo reenvía tras el `fin` hasta que llega otro `estado()` (otra partida). Antes, una sesión de menos de un segundo volvía a quedar «no terminada»: la sala tomaba el estado repetido, con `tiempo_activo` < 1, por el primero de una sesión reiniciada.

Atributos útiles: `conectado`, `estado_conexion` (`parado`, `conectando`, `conectado`, `esperando`, `rechazado`), `motivo_rechazo`, `huella_sala`, `alumno_en_sala`, `nombre_sala`, `tls`.

## Protocolo

TCP. **Una línea JSON por mensaje**, UTF-8, terminada en `\n`, de 32 KiB como máximo.

```json
{"v": 1, "tipo": "estado", "seq": 42, "t": 12.5, "datos": {"...": "..."}}
```

- `v`: versión del protocolo (`protocolo.VERSION`, ahora 1).
- `tipo`: uno de los tipos del sentido en que viaja.
- `seq`: contador del emisor, desde 0 en cada conexión.
- `t`: segundos desde que el emisor abrió la conexión.
- `datos`: campos del tipo.

### Validación

`protocolo.decodificar(linea, sentido)` devuelve un `Mensaje` o lanza `ErrorProtocolo`, cuyo `codigo` no contiene datos del mensaje (se puede registrar): `tamano`, `json`, `sobre`, `version`, `tipo`, `campo`.

- Se rechazan: líneas de más de 32 KiB, JSON no válido, `NaN` e `Infinity`, sobres que no son objetos, versión distinta, tipos desconocidos o del otro sentido, campos obligatorios ausentes, y campos con tipo, longitud o rango incorrectos (los lógicos no valen como números).
- Los campos **desconocidos** de `datos` se descartan (compatibilidad hacia delante dentro de la versión).
- Los diccionarios libres (`contadores`, datos de un evento, `ayudas`, `resultado`) se acotan: 4 niveles, 300 elementos, textos de 2000 caracteres, claves de 64.
- `protocolo.codificar` valida también lo que sale.
- `LectorLineas` trocea lo recibido; una línea desmesurada se descarta entera sin acumularla en memoria y se entrega `None` en su lugar.

**Un mensaje mal formado no rompe la conexión**: la sala lo cuenta (`errores_protocolo`) y sigue. Solo tras más de 20 seguidos corta, con `rechazo` de motivo `protocolo`. El cliente ignora los mensajes rotos de la sala. Antes del emparejamiento, en cambio, un saludo no válido cierra la conexión.

### Emparejamiento

```
reproductor                                   sala
    | --- conexión TCP (TLS salvo en 127.0.0.1) --> |
    | <-- reto {nonce, nombre} -------------------- |
    |   (comprueba la huella del certificado)        |
    | --- hola {alias, nonce, prueba, …} ----------> |
    |                       (comprueba la prueba)    |
    | <-- bienvenida {prueba, alumno, …} ---------- |   o   rechazo {motivo, espera_s}
    |   (comprueba la prueba de la sala)             |
```

```json
{"v":1,"tipo":"reto","seq":0,"t":0.0,"datos":{"nonce":"5f1c…","nombre":"Aula 3"}}
{"v":1,"tipo":"hola","seq":0,"t":0.0,"datos":{"alias":"Luna","instancia":"9a2e…","nonce":"77b0…","prueba":"c41d…","entorno":"Casa de ejemplo","actividad":"Buscar la llave","modo":"practica","recorrido":false,"version_app":"1.0.0"}}
{"v":1,"tipo":"bienvenida","seq":1,"t":0.01,"datos":{"prueba":"0be3…","alumno":"Luna","nombre":"Aula 3","latido_s":2.0}}
{"v":1,"tipo":"rechazo","seq":1,"t":0.01,"datos":{"motivo":"codigo","espera_s":0.0}}
```

Motivos de `rechazo`: `codigo`, `bloqueado`, `version`, `lleno`, `protocolo`, `expulsado`, `cierre`.

### Reproductor → Estudio

| Tipo | Datos | Cuándo |
| --- | --- | --- |
| `hola` | `alias`\*, `nonce`\*, `prueba`\*, `instancia`, `entorno`, `actividad`, `modo`, `recorrido`, `version_app` | Al conectar |
| `estado` | `planta`, `x`, `y`, `rumbo`, `espacio`, `descripcion`, `delante`, `pausado`, `tiempo_activo`, `contadores`, `entorno`, `actividad`, `modo` | 5 veces por segundo |
| `evento` | `tipo`\*, `datos` | Cada `EvRegistro` |
| `voz` | `texto`\*, `canal` | Cada frase que oye el alumno |
| `fin` | `completada`, `resultado` | Al terminar la sesión |
| `latido` | — | Si no hay otra cosa que enviar en 2 s |
| `peticion` | `id`\*, `accion`\*, `planta`, `x`, `y`, `rumbo`, `datos` | Modo recorrido |

(\* obligatorio)

```json
{"v":1,"tipo":"estado","seq":57,"t":11.4,"datos":{"planta":"p0","x":3.5,"y":2.0,"rumbo":90.0,"espacio":"Cocina","descripcion":"Cocina, planta baja, mirando al este","delante":"Una mesa a dos metros","pausado":false,"tiempo_activo":12.5,"contadores":{"distancia_m":8.2,"choques":1,"ayudas":2}}}
{"v":1,"tipo":"evento","seq":58,"t":11.6,"datos":{"tipo":"choque","datos":{"con":"mesa","x":3.9,"y":2.0}}}
{"v":1,"tipo":"voz","seq":59,"t":11.7,"datos":{"texto":"Mesa.","canal":"juego"}}
{"v":1,"tipo":"fin","seq":120,"t":64.0,"datos":{"completada":true,"resultado":{"estrellas":3}}}
{"v":1,"tipo":"peticion","seq":12,"t":30.2,"datos":{"id":1,"accion":"colocar_aqui","planta":"p0","x":3.0,"y":4.0,"rumbo":90.0,"datos":{"objeto":"mobiliario/mesa"}}}
```

### Estudio → reproductor

| Tipo | Datos |
| --- | --- |
| `reto`, `bienvenida`, `rechazo` | Emparejamiento (arriba) |
| `pausa`, `reanudar`, `reiniciar`, `terminar` | — |
| `recolocar` | `planta`\*, `x`\*, `y`\*, `rumbo` |
| `mensaje` | `texto`\* (se dice con la voz del canal «profesional») |
| `pista` | `texto`, `baliza_s` (segundos de baliza), `destino` |
| `ayudas` | `ayudas`\* = `{ayuda: {"permitida": bool, "limite": int o null}}` |
| `premio` | `nombre`\*, `id`, `planta`, `x`, `y`, `sonido`, `mensaje`, `visibilidad` |
| `marca` | `texto` (el reproductor la pasa a `Grabadora.marca`) |
| `alumno` | `ajustes`, `lista`, `niveles`: lo que dice la ficha del Estudio (abajo) |
| `releer_configuracion` | — (el Estudio ha cambiado `config.json`; el reproductor lo relee) |
| `respuesta` | `id`\*, `aceptada`\*, `texto`, `datos` (a una `peticion`) |
| `latido` | `visto`: `seq` del último mensaje del reproductor ya tratado |

```json
{"v":1,"tipo":"recolocar","seq":9,"t":40.1,"datos":{"planta":"p0","x":1.5,"y":2.5,"rumbo":180}}
{"v":1,"tipo":"mensaje","seq":10,"t":41.0,"datos":{"texto":"Muy bien, sigue por la pared"}}
{"v":1,"tipo":"ayudas","seq":11,"t":45.3,"datos":{"ayudas":{"baliza":{"permitida":false,"limite":null}}}}
{"v":1,"tipo":"respuesta","seq":12,"t":50.0,"datos":{"id":1,"aceptada":true,"texto":"Mesa colocada","datos":{"objeto_id":"mesa_7"}}}
{"v":1,"tipo":"latido","seq":13,"t":52.0,"datos":{"visto":120}}
```

### La ficha del alumno (`alumno`)

La ficha vive en la base cifrada del Estudio, que el reproductor no lee. Lo necesario para jugar le llega por la sala:

```json
{"v":1,"tipo":"alumno","seq":3,"t":0.4,"datos":{"ajustes":{"paso_m":0.8,"giro_grados":30.0,"unidad":"pasos","estilo":"juvenil","detalle":3},"lista":[{"entorno_id":"casa","entorno_nombre":"Casa","actividad_id":"busca","actividad_nombre":"Busca la llave","paquete":"casa.elab"}],"niveles":{"casa/busca":2}}}
```

- `ajustes`: `modo_movimiento`, `paso_m` (0,25 a 1,5), `giro_grados` (0 a 180), `velocidad_ms` (0,3 a 3), `formato_direccion`, `unidad`, `estilo` (el de la ficha) y `detalle` (entero de 0 a 3). Son los rangos de `AjustesJuego`. Las claves desconocidas se descartan; un valor de tipo o rango incorrecto rechaza el mensaje entero (`ErrorProtocolo("campo")`): `protocolo._validar_alumno`.
- `lista`: la lista de trabajo, como mucho `LISTA_MAXIMA` (60) entradas con los cinco textos de `CAMPOS_LISTA`; `actividad_id` es obligatorio.
- `niveles`: «`entorno_id`/`actividad_id`» → nivel (entero de 0 a 99), como mucho 200. La clave no pasa de 64 caracteres (las del Estudio que no caben no se envían).
- **Nunca** viajan el nombre real, las notas, el año de nacimiento ni el perfil de movilidad (`presentador_alumnos.datos_para_reproductor`).

Quién la envía: `ServicioSeguimiento` (app/ui/seguimiento/servicio.py) escucha la sala y, con cada suceso `conectado` o `reconectado` de un alias que tiene ficha (no archivada, base desbloqueada y fuera del modo recorrido), la envía. La reenvía cuando cambia: al guardar la ficha o su lista de trabajo, al asignar una actividad y al abrir los datos de alumnos (que incorpora sesiones y, con ellas, niveles). No repite un envío idéntico al mismo reproductor.

Qué hace el reproductor (`Aplicacion.recibir_ficha`): la guarda en el perfil del alias (`Perfil.recibir_ficha`) para los días sin sala, aplica los ajustes encima de las preferencias locales (`Aplicacion.preferencia`: ficha, después perfil, después configuración) y la partida en curso se recalcula al momento. Un nivel de la ficha sustituye al local solo si es distinto del último que llegó de la ficha: así una ficha aún sin poner al día no hace retroceder al alumno que acaba de subir de nivel jugando.

### Releer la configuración (`releer_configuracion`)

Estudio y reproductor comparten `data/config/config.json`. Tras aceptar o aplicar Preferencias con algún cambio que use el reproductor (secciones `sonido`, `voz`, `juego`, `mando`, `teclado`, y `general.idioma`, `general.tamano_texto`, `general.alto_contraste`, `supervision.segunda_salida`), el Estudio envía `releer_configuracion` a todos los conectados (`preferencias.avisar_reproductores`). El reproductor llama a `Configuracion.recargar()`, que avisa de cada clave cambiada a los mismos suscriptores que un cambio hecho en él (paquete de sonidos, motor, volúmenes, voz…). Sin sala, el reproductor relee al volver a su menú principal.

`alumno` y `releer_configuracion` los atiende la aplicación, haya partida o no; no se apuntan en la sesión grabada como intervenciones.

### Modo recorrido

El profesional recorre el entorno con el reproductor y pide cosas al Estudio:

- `colocar_aqui`: colocar un objeto donde está (en `datos`, cuál).
- `marcar_punto`: crear una referencia en ese punto (en `datos`, su nombre).
- `medir_desde_aqui`: fijar el origen de una medida, o medir hasta aquí.

`cliente.peticion(accion, …)` devuelve un `id`. La sala entrega el suceso `peticion` a la interfaz; el Estudio hace el cambio en el entorno y contesta con `sala.responder(alumno, id, aceptada, texto, **datos)`. La respuesta llega al reproductor por `ordenes_pendientes()` como `("respuesta", {...})` y el reproductor dice `texto`.

### Latido y desconexión

- Cada lado envía `latido` si lleva 2 segundos sin enviar nada. El estado, a 5 por segundo, ya cumple esa función en el reproductor.
- Si un lado no recibe nada en 6 segundos da la conexión por caída: la sala marca al alumno como desconectado (`motivo: sin_latido`) y el cliente pasa a reconectar.
- **Acuse del fin**: la sala contesta a `fin` con un `latido` inmediato con `visto`. El reproductor espera ese acuse (hasta un segundo) antes de cerrar. Motivo: en Windows se ha observado, también en `127.0.0.1`, que un cierre que se cruza con datos recién enviados hace que el otro lado vea la conexión cortada y pierda esas líneas.
- Por lo mismo, la sala no cierra de golpe tras un `rechazo`: espera hasta un segundo a que cierre el reproductor. Así el reproductor recibe el motivo y no lo confunde con un fallo de red.

## Seguridad

### Qué viaja y qué no

Por la red solo viaja el **alias**, nunca el nombre real, las notas ni los demás datos personales de la ficha: de ella solo viajan los ajustes de juego, el estilo, la lista de trabajo y los niveles (orden `alumno`). Viajan además la posición, los textos que oye el alumno, los eventos y las órdenes del profesional; por eso fuera de `127.0.0.1` la conexión va siempre cifrada. Los registros no contienen alias, direcciones ni textos de mensajes.

### Código de emparejamiento

- Seis cifras (`seguridad.generar_codigo`), o el que elija el profesional. Al comparar se ignoran espacios y guiones.
- **No viaja por la red.** Cada lado demuestra que lo conoce con un HMAC-SHA256 cuya clave es el código y cuyo mensaje incluye los dos números aleatorios (el `nonce` de la sala y el del reproductor), el papel («cliente» o «sala») y la **huella del certificado** que ha visto el reproductor.
- La prueba es **mutua**: una sala que no conozca el código no puede dar una `bienvenida` válida, y el reproductor la rechaza (`motivo: sala`).
- Al ir atada a la huella, un intermediario que presente otro certificado no puede reenviar la prueba a la sala verdadera.

### Límite de intentos

`ControlIntentos`: 5 códigos incorrectos desde una dirección en un minuto la bloquean un minuto (valores configurables en `Sala`). Hay además un tope global de diez veces esa cifra, por si se prueba desde muchas direcciones. A una dirección bloqueada se le responde `rechazo` con `motivo: bloqueado` y `espera_s`, sin llegar a enviarle un reto. Cada código incorrecto genera un suceso para la interfaz. Un saludo mal formado no cuenta como intento.

### TLS y certificado

- TLS 1.2 como mínimo, con el módulo `ssl` de la biblioteca estándar.
- El certificado es **autofirmado y se genera en Python puro** (`seguridad.crear_certificado`: RSA de 2048 bits, X.509, firma SHA-256; adaptado del generador del autor en JuegoGTA). No hace falta `openssl` ni el paquete `cryptography`. Se guarda en `data/config/sala_certificado.pem` y `sala_llave.pem`, y se reutiliza; si está dañado se crea otro.
- No lo firma ninguna autoridad y la sala no tiene nombre de dominio, así que el cliente no valida cadena ni nombre: comprueba la **huella** (SHA-256 del certificado).

### Huella recordada

El cliente guarda la huella de cada sala la primera vez (`data/config/salas_conocidas.json`, clave `host:puerto`), y solo después de un emparejamiento correcto. Si un día la huella es otra, **no envía nada** (ni el alias ni la prueba), queda en `rechazado` con `motivo: huella` y expone `huella_sala` para enseñársela a la persona; `aceptar_huella_nueva()` la sustituye. `seguridad.huella_legible` da los primeros 16 caracteres en grupos de cuatro para compararla de viva voz con la que muestra el Estudio (`foto()["huella_legible"]`).

### Límites que hay que conocer

- Un código de 6 cifras frena conexiones accidentales y curiosos, y el límite de intentos impide adivinarlo en línea. **No resiste** a un atacante activo en la misma red que intercepte el primer emparejamiento: recibiría una prueba y podría buscar el código sin conexión (un millón de posibilidades). Contra eso sirve comparar la huella en la primera conexión, o usar un código largo. Un intercambio de claves autenticado por contraseña (PAKE) lo resolvería, pero no hay ninguno en la biblioteca estándar.
- La clave privada se guarda sin cifrar en `data/config`: quien copie esa carpeta puede suplantar la sala.
- En `127.0.0.1` no hay TLS: cualquier programa del mismo ordenador puede leer ese tráfico. Es el modo «un solo ordenador».
- La huella se recuerda por dirección. Si la sala cambia de IP se trata como nueva; si otra sala ocupa la IP de una conocida, salta el aviso de huella cambiada.
- La sala no cierra por sí sola la conexión de quien envía mucho: admite hasta 16 conexiones y corta al que no lee (más de 1 MiB pendiente) o envía más de 20 mensajes rotos seguidos, pero no limita el ritmo de mensajes válidos.

## Búsqueda de salas (`descubrimiento.py`)

```python
salas = buscar_salas(espera=1.5)            # bloquea ese tiempo: llamar desde un hilo
host, puerto = analizar_direccion("192.168.1.20:47900")
direcciones_locales()                        # las IP que el profesional puede dictar
```

Difusión UDP en el puerto 47901. Solo responden las salas abiertas con `red=True`.

```json
{"v": 1, "app": "EntornoLab", "tipo": "buscar"}
{"v": 1, "app": "EntornoLab", "tipo": "sala", "nombre": "Aula 3", "puerto": 47900, "tls": true, "huella": "…64 hexadecimales…"}
```

- La pregunta se envía a `255.255.255.255`, a la difusión de cada red local (suponiendo máscara /24) y a `127.0.0.1`, y **se repite** a los 0,15 y 0,5 segundos, porque UDP no garantiza la entrega.
- La respuesta va directa a quien preguntó. No lleva el código ni datos de alumnos. La huella que viaja aquí es informativa; la que cuenta es la del certificado al conectar.
- La sala responde como mucho 5 veces por segundo a una misma dirección e ignora lo que no sea una búsqueda de EntornoLab de la misma versión.
- Si no se puede abrir el puerto UDP, la sala funciona igual; solo deja de ser encontrable.
- **Siempre hay que ofrecer escribir la dirección a mano**: muchas redes de centros bloquean la difusión, y una lista vacía no significa que no haya salas.

## Pruebas

`tests/test_supervision_protocolo.py`, `_seguridad.py`, `_sala.py` y `_descubrimiento.py`. La sala y el cliente se conectan de verdad por `127.0.0.1` en puertos libres, con y sin TLS. `tests/_supervision_util.py` tiene `ConexionCruda`, un reproductor «a mano» para enviar lo que un cliente correcto nunca enviaría.

No se ha podido probar aquí: dos ordenadores reales, el cortafuegos de Windows (preguntará la primera vez que la sala escuche en red), la difusión UDP entre equipos y redes con aislamiento de clientes.
