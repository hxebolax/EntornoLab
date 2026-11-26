# Sistema de sonido

Documentación de desarrollo de `app/audio/`. La voz, el braille, la vibración y el seguimiento de cabeza se detallan en [voz.md](voz.md); el teclado y el mando, en [entrada.md](entrada.md).

## Piezas

| Módulo | Qué hace |
|---|---|
| `base.py` | Interfaz `MotorAudio`, clase común `MotorBase`, buses, ley de distancia, filtro, conversión de coordenadas. |
| `motor_openal.py` | Motor principal: OpenAL Soft con HRTF (binaural), reverberación y filtros EFX. |
| `_openal.py` | Capa ctypes sobre `data/bin/openal/soft_oal.dll`. |
| `motor_clasico.py` | Mezclador propio con numpy y sounddevice. Admite segunda salida. |
| `motor_estereo.py` | `pygame.mixer` con paneo simple. |
| `motor_bass.py` | BASS en 3D (panorama, sin HRTF) a través de `basskit`, que viene incluido. Elegible; solo uso no comercial. |
| `motor_nulo.py` | No suena; apunta las llamadas. Pruebas y última reserva. |
| `fabrica.py` | `crear_motor(config, banco)` con cadena de reserva, y `motores_disponibles()`. |
| `proteccion.py` | Protección auditiva: techos, subidas graduales, vigilante. |
| `salidas.py` | Salidas de sonido de Windows (cuál hay y cuál es la de por defecto). |
| `banco.py` | Resuelve nombres de sonido, paquetes de sonidos y `catalogo_sonidos()`. |
| `paquetes.py` | Listar los paquetes de sonidos, elegir uno en caliente y escuchar una muestra (lo que usan los menús). |
| `niveles.py` | Igualado de sonoridad entre paquetes y medidas de un sonido (nivel, costura, notas, toques). |
| `sintesis.py` | Sintetiza todos los sonidos del paquete por defecto; leer, escribir y remuestrear audio. |
| `presentador.py` | Traduce los eventos del juego a sonido, voz y vibración. |
| `voz.py`, `linea_braille.py`, `haptica.py`, `cabeza.py` | Ver [voz.md](voz.md). |

Uso típico en el reproductor:

```python
banco = Banco()
motor = crear_motor(config_sonido, banco)          # nunca falla: en el peor caso, motor nulo
voz = Voz(config_voz)
haptica = Haptica(entrada.vibrar, config_vibracion)
presentador = Presentador(motor, voz, haptica, cabeza, banco=banco)
desconectar = paquetes.conectar(banco)              # paquete de sonidos de la configuración, y lo sigue en caliente

# al abrir un entorno
banco.poner_entorno(paquete.recurso)

# una vez por fotograma
presentador.aplicar(sesion.avanzar(dt), sesion, dt)
```

`Presentador.aplicar` ya llama a `motor.tic`, `voz.tic` y `haptica.tic`: no hay que llamarlos por otro lado. Si no hay sesión (menús), se llama igual con `aplicar([], None, dt)` para que el sonido siga actualizándose (ver «Protección auditiva»).

## Coordenadas

Todo el programa usa metros, **x al este, y al norte, z hacia arriba**, y rumbo en grados con **0 = norte en el sentido del reloj**. Los motores reciben siempre esas coordenadas y cada uno convierte:

- OpenAL (mano derecha, x derecha, y arriba, −z adelante): posición `(x, z, −y)`; mirar con rumbo `r` es el vector `(sen r, 0, −cos r)`, con «arriba» `(0, 1, 0)`.
- BASS (mano izquierda, x derecha, y arriba, z adelante): posición `(x, z, y)`; frente `(sen r, 0, cos r)`, con «arriba» `(0, 1, 0)`.
- Clásico y estéreo: ángulo relativo `atan2(dx, dy) − rumbo` (0 delante, 90 derecha).

Un sonido se puede pedir de tres maneras:

- `pos=(x, y, z)`: anclado al mundo. Si el oyente gira o se mueve, el sonido se queda en su sitio.
- `relativo=(angulo, distancia)`: respecto del oyente (0 delante, 90 derecha). Gira con él.
- sin nada: sin posición (interfaz). Suena igual por los dos oídos.

## Motores

| | `openal` | `clasico` | `estereo` | `bass` | `nulo` |
|---|---|---|---|---|---|
| Delante/detrás | HRTF (timbre y retardo) y filtro | filtro y volumen | sonido apagado y volumen | filtro | — |
| Izquierda/derecha | HRTF | panorama y retardo entre oídos | panorama | panorama de BASS (a 90° el oído lejano queda mudo) | — |
| Arriba/abajo | HRTF | no | no | no | — |
| Reverberación por acústica | sí (EFX) | no | no | no | — |
| Oclusión (`filtro`) | paso bajo EFX | mezcla con versión apagada | versión apagada al empezar | ecualizador de tres bandas | — |
| Tono variable mientras suena | sí | sí | no (se fija al empezar) | sí | — |
| Cambio de salida en caliente | sí, sin cortes | sí (reabre) | no | sí, sin cortes | — |
| Segunda salida | no | **sí** | no | no | — |
| Modo en memoria para pruebas | sí (`renderizar`) | sí (`renderizar`) | con `SDL_AUDIODRIVER=dummy` | sí (`renderizar`, en tiempo real) | sí |
| Viene incluido | sí | sí | sí | sí (**solo uso no comercial**) | sí |

> **Aviso de licencia de BASS.** Los cinco motores vienen con el programa, pero BASS (`bass.dll`, de Un4seen Developments) no es software libre: es gratuita **solo para uso no comercial**. Si alguien quisiera usar EntornoLab con fines comerciales, BASS exige una licencia de pago de Un4seen; en ese caso basta con **elegir otro motor y retirar `bass.dll`**. Detalles en «Licencias», al final.

### Cómo se elige

`crear_motor(config, banco)` prueba el motor de `config["motor"]` y, si no está disponible o no arranca, el siguiente:

```
openal → clasico → estereo → nulo        (bass → openal → clasico → estereo → nulo)
```

El motor de serie es `openal`. `bass` se elige en las preferencias y **no está en la cadena de reserva**: nadie cae en él sin haberlo pedido (no es binaural, y su licencia solo permite el uso no comercial). Si se pide y no arranca —por ejemplo, porque se ha retirado `bass.dll`—, se sigue por `openal`.

Cada caída queda en el registro con su motivo. El motor devuelto tiene `nombre` (el que suena) y `pedido` (el que se pidió): las preferencias pueden avisar de que está sonando una reserva. `motores_disponibles()` devuelve, para cada motor, `{"id", "nombre", "disponible", "motivo"}` sin abrir ningún dispositivo. `APP_SIN_SONIDO=1` fuerza el motor nulo.

Recomendación para el usuario:

- **Auriculares**: `openal` (de serie).
- **El profesional quiere oír lo mismo por otro dispositivo**: `clasico` con `segunda_salida`.
- **Altavoces**: `openal` con `salida: "altavoces"`, o `estereo`.
- **Equipo muy modesto o sin OpenAL**: `estereo`.
- **OpenAL da problemas en un equipo concreto y se quiere 3D con cambio de salida en caliente**: `bass` (sin HRTF: izquierda y derecha se distinguen muy bien; delante y detrás, solo por el filtro).

### Configuración (dict)

`crear_motor` y `MotorAudio.iniciar(dispositivo, opciones)` reciben un dict; no leen la configuración global. Claves (todas opcionales):

| Clave | Valor de serie | Motores | Significado |
|---|---|---|---|
| `motor` | `"openal"` | fábrica | `openal`, `clasico`, `estereo`, `bass`, `nulo` |
| `dispositivo` | `""` | todos | Nombre de la salida; vacío = la de Windows (y se la sigue si cambia) |
| `segunda_salida` | `""` | clásico | Salida del profesional, con la misma mezcla |
| `salida` | `"auriculares"` | openal | `auriculares` (HRTF) o `altavoces` (estéreo sin HRTF) |
| `cabeza` | `""` | openal | Perfil HRTF; vacío = el integrado |
| `refuerzo_detras` | `1.0` | todos | 0 a 1: cuánto se apaga lo que queda detrás |
| `reverberacion` | `true` | openal | Activa la reverberación por acústica |
| `nivel_reverberacion` | `1.0` | openal | 0 a 1,5 |
| `volumenes` | ver abajo | todos | `{bus: 0..1}` |
| `distancia_referencia` | `1.0` | todos | Metros hasta los que un sonido suena a su volumen nominal |
| `distancia_caida` | `1.0` | todos | Pendiente; 0 = sin atenuación por distancia |
| `distancia_maxima` | `60.0` | todos | Más allá no sigue bajando |
| `mono` | `false` | todos | Los dos oídos oyen lo mismo (quien oye por uno solo) |
| `atenuar_voz` | `true` | todos | Bajar ambiente y música mientras habla la voz |
| `proteccion` | ver abajo | todos | Límites de la protección auditiva |
| `fuentes` | `48` | openal | Tamaño de la reserva de fuentes (8 a 128) |
| `holgado` | `false` | clásico, estéreo | Búfer grande: más retardo, sin chasquidos en equipos lentos |
| `memoria` | `false` | openal, clásico, bass | Sin tarjeta de sonido (pruebas) |

En caliente: `motor.configurar(opciones)`, `motor.volumen_bus(bus, valor)`, `motor.cambiar_dispositivo(nombre)`, y en OpenAL `poner_cabeza(nombre)` y `poner_salida("auriculares" | "altavoces")`; en el clásico, `cambiar_segunda_salida(nombre)`.

### Buses

`maestro`, `efectos`, `pasos`, `ambiente`, `ayudas`, `interfaz`, `musica`, `voz`. Volúmenes de serie: maestro 0,8; efectos 1; pasos 0,8; ambiente 0,6; ayudas 1; interfaz 0,8; música 0,5; voz 1.

- `atenuar_por_voz(segundos)`: `ambiente` y `musica` bajan al 45 % en unas décimas y vuelven en torno a un segundo después de que termine la voz.
- `pausar(True)` detiene todo menos `interfaz` y `voz`.

### Reserva de fuentes y prioridades

OpenAL trabaja con un número fijo de fuentes (48 de serie). Cuando no queda ninguna libre se roba la del canal **menos importante** (y, entre iguales, el más viejo), siempre que no sea más importante que el sonido nuevo; si lo es, el sonido nuevo no suena y `reproducir` devuelve 0.

Prioridad por bus: voz 100, interfaz 90, ayudas 80, pasos 60, efectos 50, ambiente 30, música 20; los bucles suman 5 y el volumen hasta 4. `reproducir(..., prioridad=n)` la fija a mano. El presentador vuelve a pedir un bucle continuo al que le hayan robado la fuente.

## Motor OpenAL en detalle

### HRTF pedido y verificado

El contexto se crea con `ALC_HRTF_SOFT = 1`, `ALC_OUTPUT_MODE_SOFT = ALC_STEREO_HRTF_SOFT` y `ALC_HRTF_ID_SOFT` con el perfil elegido. Después **se consulta el estado real** (`ALC_HRTF_STATUS_SOFT` y `ALC_HRTF_SPECIFIER_SOFT`) y queda en:

- `motor.hrtf_activo` (bool), `motor.estado_hrtf` (texto) y `motor.perfil_hrtf`;
- `motor.estado()` (dict para las preferencias);
- el registro: «HRTF activado con el perfil …» o un aviso si OpenAL no lo activó.

Se pide HRTF aunque Windows no diga que la salida son auriculares: es una decisión del usuario (`salida: "auriculares"`).

### Perfiles de cabeza

Ocho: el integrado en la DLL y siete ficheros `.mhr` de `data/bin/openal/hrtf`:

| Id | Nombre visible | Origen |
|---|---|---|
| `""` | la integrada | OpenAL Soft («Built-In HRTF») |
| `kemar_oreja_normal` | maniquí con oreja normal | MIT KEMAR |
| `kemar_oreja_grande` | maniquí con oreja grande | MIT KEMAR |
| `ku100` | cabeza artificial de estudio | SADIE II, Neumann KU100 |
| `persona_1` … `persona_4` | persona 1 … 4 | SADIE II, sujetos H3 a H6 |

`cabezas_disponibles()` las enumera (incluye cualquier `.mhr` que el usuario añada) y `nombre_cabeza(id)` da el texto traducido. `motor.poner_cabeza(id)` cambia en caliente con `alcResetDeviceSOFT` y devuelve si ese perfil quedó activo de verdad. Cada persona localiza mejor con una cabeza distinta: conviene ofrecer una prueba de calibración («¿de dónde viene este sonido?») en las preferencias del alumno.

### Reverberación

Efecto de reverberación EFX estándar, un preset por acústica (`PRESETS` en `motor_openal.py`):

| Acústica | Envío | Cola (s) | Carácter |
|---|---|---|---|
| `seca` | 0 | — | sin eco |
| `habitacion` | 0,32 | 0,5 | reflexiones cercanas |
| `sala_grande` | 0,40 | 1,4 | |
| `pasillo` | 0,40 | 0,9 | reflexiones marcadas, poca difusión |
| `bano` | 0,45 | 1,1 | muy brillante (azulejos) |
| `escalera` | 0,45 | 2,0 | |
| `nave` | 0,50 | 3,0 | cola larga |
| `exterior` | 0,05 | 0,7 | casi nada |
| `calle` | 0,18 | 1,1 | fachadas lejanas |
| `parque` | 0,08 | 0,9 | |

Hay dos ranuras de efecto: al cambiar de acústica, la nueva entra por la ranura libre mientras la otra se apaga, en 0,6 s (si la biblioteca solo diera un envío por fuente, baja, cambia y sube). Lo que suena tras una pared excita menos el eco y sin sus agudos. Los sonidos de `interfaz`, `voz` y `musica` no llevan eco (`eco=False`).

### Cambio de salida en caliente

- `cambiar_dispositivo(nombre)` usa `alcReopenDeviceSOFT`: la mezcla pasa a la otra salida sin cortar lo que suena.
- Cada 1,5 s se mira si la salida se ha desconectado, si la de Windows ha cambiado (cuando se sigue a Windows) o si ha vuelto la elegida, y se reabre donde toque (`salidas.py`, API `winmm`).
- Un nombre de salida guardado con un motor sirve para los demás (se comparan por el principio, sin el prefijo «OpenAL Soft on »).

### Modo en memoria

Con `{"memoria": True}` se abre un dispositivo *loopback* (44,1 kHz, estéreo, coma flotante) y `motor.renderizar(n)` devuelve una matriz `(n, 2)` con lo que llegaría a cada oído. Es lo que usan las pruebas: no hace falta tarjeta de sonido y no suena nada.

## Motor BASS en detalle

`motor_bass.py` usa la API nativa de BASS 2.4 a través de `basskit` (`basskit.dlls.bass`, `basskit.constantes`, `basskit.estructuras`). La rueda que viaja en `__pip__` es un basskit **recortado**: solo `bass.dll`, sin BASSmix, BASS_FX, codificadores ni FFmpeg. Todo lo que hace el motor sale del núcleo de BASS.

| Qué | Cómo |
|---|---|
| Oyente | `BASS_Set3DPosition` con posición `(x, z, y)`, frente `(sen r, 0, cos r)` y arriba `(0, 1, 0)`. Se mueve y gira por el mundo, igual que en OpenAL. |
| Fuente con `pos` | Flujo `BASS_SAMPLE_3D` (mono) en modo `BASS_3DMODE_NORMAL`, en su sitio del mundo. |
| Fuente con `relativo` | Modo `BASS_3DMODE_RELATIVE`: BASS la mantiene respecto de la cabeza aunque el oyente gire o se mueva. |
| Sin posición | Flujo normal, sin 3D (conserva sus dos canales si el sonido es estéreo). |
| Distancia | La de BASS, que es la misma ley inversa recortada: distancia mínima = `distancia_referencia`, máxima = `distancia_maxima`, `rolloff` de `BASS_Set3DFactors` = `distancia_caida`. Sin `BASS_SAMPLE_MUTEMAX`: no hay borde de corte. La altura cuenta como distancia. Sin Doppler. |
| Izquierda/derecha | Panorama de potencia constante de BASS: una fuente justo a un lado deja mudo el oído contrario (el motor clásico nunca lo hace). Una fuente centrada suena 3 dB más baja en cada oído que un sonido sin posición. |
| Volumen | `BASS_ATTRIB_VOL` por canal (volumen pedido × bus × atenuación por voz, con el techo por fuente) y `BASS_CONFIG_GVOL_STREAM` como ganancia maestra, con su subida gradual. |
| Tono | `BASS_ATTRIB_FREQ`, también mientras suena. |
| Filtro | Tres efectos `BASS_FX_DX8_PARAMEQ` por canal, creados solo cuando hacen falta. |
| Pausa | `BASS_ChannelPause` / `BASS_ChannelPlay` de cada canal del mundo. |
| Latencia | `BASS_ATTRIB_BUFFER = 0` en cada flujo: los cambios de filtro y de tono se oyen al momento (con el búfer de serie de BASS tardarían medio segundo). |
| Protección | Vigilante (calla con `GVOL_STREAM = 0`) y un compresor `BASS_FX_DX8_COMPRESSOR` en la mezcla final (flujo `STREAMPROC_DEVICE`), 6 dB por debajo del techo de mezcla. Es un compresor, no un limitador exacto: suaviza la suma de muchos sonidos, pero no garantiza un pico máximo. |
| Salidas | `dispositivos()` da las salidas conectadas. `cambiar_dispositivo(nombre)` abre la nueva, pasa a ella todos los flujos con `BASS_ChannelSetDevice` y cierra la anterior, sin cortar lo que suena. Sin nombre se abre la entrada «Default» de BASS, que sigue sola a la salida de Windows. Si la elegida se desconecta se pasa a la de Windows, y cuando vuelve, a ella (se mira cada 1,5 s). La salida se abre siempre en estéreo. |
| Modo en memoria | `{"memoria": True}` abre el dispositivo 0 de BASS («No sound») y un DSP copia la mezcla final; `motor.renderizar(n)` devuelve `(n, 2)`. BASS mezcla en tiempo real: renderizar un segundo tarda un segundo. |

Lo que **no** hace, y por qué:

- **HRTF, arriba/abajo**: BASS no trae binaural.
- **Reverberación por acústica**: el núcleo de BASS tiene `BASS_FX_DX8_I3DL2REVERB` por canal, pero no un envío común como EFX; no se ha implementado. `acustica()` recuerda el preset y no suena distinto.
- **Segunda salida** con la misma mezcla: haría falta BASSmix, que no viaja en la rueda recortada.

Dónde se busca `bass.dll`: dentro del propio paquete (`basskit/data/dlls/x64`), que es donde está tanto desde el código (`.venv`) como compilado (`lib/basskit`, fuera del zip de bibliotecas). Si ahí no está, el motor mira `data/bin/bass/bass.dll` (permite reponerla sin tocar las bibliotecas). Si no la encuentra, `MotorBass.disponible()` devuelve `False` con el motivo y la fábrica sigue por `openal`.

## Fórmulas

### Distancia

Ley inversa recortada, la misma en todos los motores (`base.ganancia_distancia`; en OpenAL es `AL_INVERSE_DISTANCE_CLAMPED` con los mismos parámetros):

```
d' = min(max(d, ref), maxima)
ganancia = ref / (ref + caida · (d' − ref))
```

Con `ref = 1 m` y `caida = 1`: 1 m → 1; 2 m → 0,5; 4 m → 0,25; 10 m → 0,1. Es la ley física de una fuente puntual (6 dB menos al doblar la distancia).

Principio: **ninguna pista de distancia engañosa**.

- Por debajo de la distancia de referencia la ganancia no pasa de 1: acercarse más no «sube» el sonido de forma irreal.
- No hay borde de corte: más allá de `maxima` el sonido deja de bajar, pero no desaparece de golpe. Quien decide que una fuente ya no se oye es el motor del juego (deja de listarla en `sesion.fuentes()` y el presentador la apaga con un fundido).
- La referencia es de 1 m porque el programa es sobre todo de interiores (en Puerto Bravo, pensado para calles, eran 5 m). Es ajustable.
- No se añade absorción del aire ni efecto Doppler.
- La reverberación de una fuente lejana también baja, con la mitad de pendiente (`AL_ROOM_ROLLOFF_FACTOR = caida / 2`).

Reparto de responsabilidades con el motor del juego: `FuenteActiva.volumen` debe llevar la oclusión y el camino por puertas, **no** la atenuación por distancia en línea recta, que la pone la capa de sonido a partir de `pos`. Si el motor del juego prefiere calcularla él, basta con `distancia_caida = 0`.

### Oclusión y refuerzo «detrás»

`filtro` (0 a 1) lo calcula el motor del juego. La capa de sonido lo convierte en un paso bajo (`base.ganancias_filtro`), combinado con el refuerzo de lo que queda detrás:

```
detras         = max(0, (|ángulo| − 70°) / 110°)              0 delante y a los lados, 1 justo detrás
ganancia_hf    = max(0,02, (1 − filtro)²) · (1 − 0,85 · detras · refuerzo_detras)
ganancia       = 1 − 0,25 · filtro
```

- En OpenAL son `AL_LOWPASS_GAINHF` y `AL_LOWPASS_GAIN` del filtro directo de la fuente (referencia de agudos de OpenAL: 5 kHz). Se recalcula cada fotograma, porque al girar el oyente cambia qué queda detrás.
- El clásico mezcla el sonido con una versión pasada por un paso bajo de 900 Hz, en proporción `1 − ganancia_hf`.
- El estéreo elige al empezar la versión apagada si `1 − ganancia_hf > 0,5` y baja el volumen de lo de detrás hasta un 30 %.
- BASS usa tres bandas de su ecualizador paramétrico (4, 9 y 15 kHz), que juntas hacen de paso bajo: cada una baja `20·log10(ganancia_hf) / 2,4` dB, con un tope de −15 dB (unos −36 dB entre 4 y 12 kHz). Se recalcula cada fotograma.

El HRTF ya distingue delante de detrás por el timbre; el filtro es un **refuerzo** (apartado 12.5 del informe) que se puede bajar o quitar con `refuerzo_detras`.

### Motor clásico: panorama y retardo

```
pan      = sen(ángulo) · min(1, distancia / 0,75 m)
a        = (pan + 1) · π / 4
izquierda = g · 1,3 · (0,15 + 0,85 · cos a)        el oído lejano nunca queda mudo
derecha   = g · 1,3 · (0,15 + 0,85 · sen a)
retardo del oído lejano = 28 muestras · |pan|      (0,63 ms a 44,1 kHz)
```

## Protección auditiva (`proteccion.py`)

| Defensa | Valor de serie | Qué hace |
|---|---|---|
| `techo_fuente` | 1,0 | Ganancia máxima de una fuente, pida lo que pida el entorno o el complemento |
| `techo_mezcla` | 0,9 | Tope de la ganancia maestra; en el clásico, además, limitador de la suma con rodilla suave. OpenAL usa su limitador de salida (`ALC_OUTPUT_LIMITER_SOFT`) |
| `subida_maestro` | 0,8 por segundo | La ganancia maestra arranca en 0 y sube poco a poco (al iniciar, al subir un deslizador, al volver de un silencio). Bajar es inmediato |
| `subida_fuente` | 5 por segundo | Los bucles entran desde el silencio y una subida de volumen de una fuente se oye en unas décimas |
| `silencio_sin_tic` | 0,75 s | Si el juego deja de llamar a `tic` (se ha colgado, un diálogo lo bloquea), un vigilante calla la salida; al volver, sube poco a poco |

Los rangos están acotados al leer la configuración (`Proteccion.de_dict`): se pueden ajustar, pero no quitar. Consecuencia para quien use los motores: **hay que llamar a `tic` (o a `Presentador.aplicar`) en cada fotograma, también en los menús**; si no, el sonido se calla a los 0,75 s.

## Banco de sonidos (`banco.py`)

`Banco.sonido(nombre)` busca, por este orden:

1. el paquete del entorno (`sonidos/<nombre>` del `.elab`, con `Banco.poner_entorno(paquete.recurso)`);
2. un complemento (`<complemento>/<sonido>` → `data/plugins/<complemento>/sonidos/`);
3. el **paquete de sonidos elegido** (`data/sounds/<paquete>`), si no es el de por defecto;
4. el **paquete por defecto** (`data/sounds/por_defecto`): un paquete puede ser parcial;
5. una reserva sintetizada: el propio sonido si es de serie y falta su fichero, o uno neutro de su familia. Se avisa en el registro una vez.

`Sonido.origen` dice de dónde ha salido: `entorno`, `complemento`, `paquete` (el paquete elegido), `serie` (el de por defecto), `sintetizado` o `reserva`; `Sonido.paquete` y `Sonido.ganancia`, de qué paquete y con qué ganancia. Por compatibilidad, un sonido suelto en `data/sounds` (como en las instalaciones anteriores a los paquetes) se sigue encontrando, detrás del paquete por defecto.

Detalles:

- Extensiones admitidas: `.ogg`, `.flac`, `.wav`. El nombre puede llevarla o no.
- Un nombre genérico (`pasos/baldosa`, `pasos/baldosa_izq`) se resuelve a una variante al azar.
- Se rechazan rutas absolutas y `..` (los nombres vienen de entornos y complementos, que son datos de terceros).
- Lo leído se guarda en memoria; cambiar de entorno vacía la caché.
- `crear_motor(config, banco)` conecta `banco.datos` como `motor.resolver`: los motores cargan cada sonido la primera vez que se pide. `banco.precargar(motor, nombres)` los carga de antemano.
- Los sonidos de serie y la DLL se buscan primero en la carpeta `data` activa y después en la `data` que está junto al programa, para que sigan encontrándose con `APP_DATA_DIR` redirigida.

`catalogo_sonidos()` devuelve los grupos y, de cada sonido, nombre visible, explicación y grupo (traducidos), para el menú «Aprender los sonidos». El catálogo (`data/sounds/catalogo.json`) es **común a todos los paquetes**: los nombres, las explicaciones y los grupos no dependen del paquete. Su campo `fichero` es relativo a la carpeta del paquete.

## Paquetes de sonidos

```
data/sounds/
    catalogo.json          común: nombre hablado, explicación y grupo de cada sonido
    LEEME.md               cómo crear un paquete (para quien no programa)
    por_defecto/           pack.json, CREDITOS.txt, niveles.json y los 198 sonidos sintetizados
    natural/               pack.json, CREDITOS.txt, receta.json, medidas.json y sus sonidos
    grabado/               lo mismo, con grabaciones reales (paquete parcial: 113 sonidos)
    <otro>/                cualquier carpeta que alguien copie aquí
```

Un paquete es una carpeta con ficheros que se llaman igual que los sonidos del catálogo (`puerta/abrir.flac`) y, si quiere, un `pack.json` (`id`, `nombre`, `descripcion`, `autor`, `licencia`, `version`, `generado`, y opcionalmente `igualar` y `volumenes`). El identificador del paquete es el nombre de su carpeta (minúsculas, cifras, `_` y `-`). **Puede ser parcial**: lo que no trae suena con el de por defecto. Un `pack.json` que falta o está dañado no impide usar el paquete (se avisa en el registro y se llama como su carpeta).

Los paquetes se buscan en la `data/sounds` activa (la del usuario, con `APP_DATA_DIR`) y en la que está junto al programa (`carpetas_de_serie("sounds")`): para añadir uno propio basta con copiar su carpeta. Si el mismo paquete está en las dos, manda la del usuario. Los sonidos propios de los complementos (`data/plugins/<id>/sonidos`) no son parte de los paquetes.

### API

| Qué | Cómo |
|---|---|
| Paquetes instalados | `banco.paquetes_disponibles()` o `paquetes.listar(banco)` → lista de dicts `{"id", "nombre", "descripcion", "autor", "licencia", "version", "generado", "sonidos", "total", "completo", "parcial", "defecto", "actual", "carpeta"}`, el de por defecto primero |
| Paquete en uso | `banco.paquete_actual()`; el guardado, `paquetes.actual()` |
| Elegir (bajo nivel) | `banco.poner_paquete(id) -> bool`: vacía la caché y avisa a los suscritos. Si no existe, queda el de por defecto y devuelve `False` |
| Elegir (menús) | `paquetes.elegir(id) -> bool`: escribe `sonido.paquete`; devuelve `False` sin cambiar nada si no está instalado |
| Seguir la configuración | `paquetes.conectar(banco) -> cancelar`: aplica lo guardado y sigue `sonido.paquete`, `sonido.igualar_paquetes` y `sonido.volumen_sonidos` |
| Recargar el motor | `banco.recargar_en(motor, fundido=0.25, forzar=False) -> int` (lo llama solo el presentador) |
| Escuchar una muestra | `paquetes.escuchar(id, motor, banco) -> canal`; las muestras, `paquetes.muestra(id, banco) -> (datos, frecuencia)` |
| Un sonido de otro paquete | `banco.sonido_de_paquete(id, nombre) -> Sonido`, sin cambiar el paquete en uso |
| Frase para el menú | `paquetes.describir(paquete)` |
| Volumen de un sonido | `paquetes.poner_volumen(nombre, factor)` (guarda) o `banco.poner_volumen_sonido(nombre, factor)`; de 0,3 a 2 |
| Avisos de cambio | `banco.suscribir(funcion) -> cancelar`; `funcion(motivo)` con `"paquete"`, `"igualado"` o `"volumenes"` |

Configuración (`app/core/configuracion.py`, sección `sonido`): `paquete` (`"por_defecto"`), `igualar_paquetes` (`true`) y `volumen_sonidos` (`{}`: nombre → factor).

### Cambio en caliente

Cambiar `sonido.paquete` se oye al momento, también en mitad de una partida:

1. `paquetes.conectar` recibe el aviso de la configuración y llama a `banco.poner_paquete`, que vacía su caché y avisa a sus suscritos.
2. El `Presentador` (creado con `banco=banco`) solo apunta que hay una recarga pendiente: el aviso puede llegar desde el hilo de la ventana, y el motor de sonido solo se toca desde el hilo del juego.
3. En el siguiente `Presentador.aplicar`, `banco.recargar_en(motor)` vuelve a resolver cada sonido que el motor tenía cargado (`motor.sonidos_cargados()`). Los que **no cambian** (los propios del entorno, los de un complemento, lo que el paquete nuevo hereda del de por defecto) no se tocan. Los que cambian se sustituyen con `motor.recargar_sonido(nombre, datos, frecuencia, fundido)`.
4. `MotorBase.recargar_sonido` carga las muestras nuevas (`cargar`) y, para cada **bucle** que esté sonando con ese sonido (un ambiente, el frigorífico de la cocina), arranca un canal nuevo con el sonido nuevo, en el mismo sitio y con el mismo volumen, tono, filtro, bus y prioridad, que entra desde el silencio, mientras el antiguo se apaga en 0,25 s. Es un fundido cruzado: no hay corte ni hueco. El número de canal que tenía el juego **sigue valiendo**: el motor recuerda que lo «releva» el canal nuevo, y `actualizar`, `parar` y `suena` con el número antiguo actúan sobre el nuevo. Un sonido corto que esté sonando termina con el sonido antiguo.

Si no queda ninguna fuente libre para solapar los dos canales, el antiguo se corta y arranca el nuevo. En un menú que no llame a `aplicar` se puede forzar con `presentador.recargar_sonidos()`. Un motor que no herede de `MotorBase` solo necesita `sonidos_cargados()` y `cargar()`.

### Igualado de sonoridad

Cada paquete viene a su volumen. Para que al cambiar no suba ni baje el volumen general, ni un paso tape a una baliza, cada sonido de un paquete que no es el de por defecto se lleva, al cargarlo, al **nivel del sonido de serie del mismo nombre** (`app/audio/niveles.py`, la misma idea que `packs.py` de Puerto Bravo):

- **nivel** = media cuadrática del tramo de 0,3 s más intenso (del sonido entero si es más corto). Así un golpe con mucha cola o una grabación con silencio alrededor no salen perjudicados;
- **referencia** = `por_defecto/niveles.json`, `{nombre: [nivel, pico]}`, que escribe `tools/sintetizar_sonidos.py`. Si falta, se mide el sonido de serie al vuelo;
- **ganancia** = referencia / nivel, acotada entre 0,1 y 10 y sin dejar que el pico pase de 0,9.

Se desactiva para todos con `sonido.igualar_paquetes = false`, o para un paquete con `"igualar": false` en su `pack.json`. Encima, el autor del paquete puede retocar sonidos suyos (`"volumenes"`) y el usuario cualquier sonido (`sonido.volumen_sonidos`), de 0,3 a 2.

El paquete «Natural» ya se escribe igualado (la herramienta que lo genera usa las mismas funciones), así que al cargarlo la ganancia es prácticamente 1.

### Crear un paquete

A mano: una carpeta en `data/sounds` con los sonidos que se quieran cambiar (ver `data/sounds/LEEME.md`, que es la explicación para el usuario). Lo que hace útil un sonido para orientarse y conviene respetar: mono y con contenido por encima de 3 kHz lo que se sitúa; bucles sin clic; duraciones parecidas; y que los avisos que codifican algo (distancia del bastón, brújula, plantas del ascensor, peldaños) conserven su código, o **no incluirlos** para que suenen los de serie.

Con el Generador de sonidos del autor: `tools/generar_paquete_sonidos.py` (más abajo). Para otro paquete basta otra receta: un módulo en `tools/` con `ID`, `FICHA` y `recetas()`, y `--receta <módulo>`.

Con grabaciones: `tools/montar_paquete_grabado.py` (más abajo), que recorta, pasa a mono, remuestrea, hace los bucles e iguala a partir de una tabla, y deja fuera lo que no pasa las medidas.

## Los tres paquetes que vienen

### Por defecto: síntesis con numpy

Todos se sintetizan con numpy (`app/audio/sintesis.py`); no hay grabaciones. Para regenerarlos (`entorno.bat sonidos`):

```
.venv\Scripts\python.exe tools\sintetizar_sonidos.py [--carpeta data/sounds] [--formato flac|ogg|wav] [--solo patrón]
```

Escribe en `data/sounds/por_defecto` 198 ficheros FLAC (44,1 kHz, 16 bits; mono los que se posicionan), `pack.json`, `CREDITOS.txt` y `niveles.json`, y en `data/sounds`, el `catalogo.json` común.

Lección aprendida en Reconocedor de Ciudades: **el HRTF distingue delante de detrás por los agudos**. Todo sonido que haya que localizar lleva contenido por encima de 3 kHz (un chasquido de aire de 2 a 14 kHz en balizas, sondas, premios y fuentes graves). Una prueba lo comprueba.

| Grupo | Sonidos |
|---|---|
| Orientación | `baliza/` pulso, alineado, detras, cerca, llegada · `sonda/` pared, puerta, objeto, libre, escalon, bordillo, cerca, media, lejos · `brujula/` norte, noreste, este, sureste, sur, suroeste, oeste, noroeste · `eco/chasquido` |
| Pasos | `pasos/<suelo>_<izq\|der>_<1..3>` para baldosa, madera, moqueta, alfombra, hormigon, asfalto, acera, adoquin, tierra, hierba, grava, metal, arena, agua, tactil_botones, tactil_rayas (96) |
| Choques y roces | `golpe/<material>` y `roce/<material>`: ladrillo, madera, metal, cristal, plastico, tela, piedra |
| Puertas, escaleras y ascensor | `puerta/` abrir, cerrar, con_llave, automatica · `escalera/` subir, bajar, rampa · `ascensor/` llamada, puerta, viaje (bucle), llegada, planta_0 … planta_9 |
| Premios y logros | `premio/` aparece, cerca (bucle), recogido, tesoro · `logro/` logro, estrella_1 … 3, medalla, error, pista |
| Calle | `semaforo/` verde, intermitente, rojo (bucles), pulsador · `trafico/` coche, moto, autobus, ambiente_leve, ambiente_medio, ambiente_intenso (bucles estéreo) · `exterior/bordillo` |
| Fuentes de los lugares (bucles mono) | `fuente/` frigorifico, reloj, grifo, ventilador, television, fuente_agua, maquina_expendedora, campanas, pajaros |
| Ambientes (bucles estéreo de 10 s) | `ambiente/` casa, oficina, pasillo, calle, parque, cocina |
| Interfaz | `interfaz/` mover, elegir, atras, borde, abrir, cerrar, ajuste |

Para sustituir un sonido de serie en un entorno concreto, se mete en el paquete del entorno (el `.elab`) como `sonidos/<mismo nombre>.ogg`.

### Natural: Generador de sonidos, sin inteligencia artificial

`data/sounds/natural` se genera con el *Generador de sonidos* del autor (otro proyecto suyo), **solo con su motor procedural**: modelos físicos (pasos, impactos, puertas, vehículos, agua) e instrumentos (marimba, xilófono, glockenspiel, celesta, kalimba, vibráfono, campanas tubulares, trompeta, ocarina). No se usa ninguno de sus motores de inteligencia artificial, ni grabaciones, ni las voces de Windows.

```
.venv\Scripts\python.exe tools\generar_paquete_sonidos.py [--exe ruta\sonido.exe] [--solo patrón] [--conservar]
.venv\Scripts\python.exe tools\generar_paquete_sonidos.py --desde-receta data\sounds\natural\receta.json
```

La ruta de `sonido.exe` (la línea de órdenes compilada del generador) se da con `--exe` o con la variable `GENERADOR_SONIDOS_EXE`. La herramienta:

1. arma una especificación JSON por sonido a partir de `tools/receta_natural.py` y del catálogo (bucle, mono o estéreo, duración);
2. llama a `sonido.exe renderizar lote.json --json`, con `APP_DATA_DIR` redirigida a la carpeta de trabajo (no escribe nada en la carpeta del generador);
3. **ajusta los agudos**: si un sonido que hay que situar no llega al 3,5 % de su energía por encima de 3 kHz, sube 4 dB la capa (`"_aire"`: unas maracas, el roce de la ropa, el siseo de un ventilador) o el efecto (`agudos`, `"_auto"`) que la receta marca para eso y vuelve a pedirlo, hasta seis veces;
4. **comprueba midiendo** (no reproduce nada): canales, duración (entre 0,5 y 1,75 veces la de serie; exacta en los bucles), pico, bordes en silencio, costura de los bucles, agudos, y —en los avisos que codifican algo— que están sus notas (energía en la fundamental o en sus armónicos) y su número de toques. **Lo que no cumple no entra en el paquete** y se hereda del de por defecto, con el motivo apuntado en `CREDITOS.txt` y en `pack.json` (`heredados`);
5. iguala cada sonido al nivel del de serie (techo de pico 0,8) y lo escribe en FLAC de 16 bits. Es lo único que la herramienta le hace al audio: una ganancia;
6. escribe `pack.json`, `CREDITOS.txt`, `receta.json` (las especificaciones exactas enviadas, con sus semillas: `--desde-receta` regenera el paquete idéntico) y `medidas.json`.

Carácter: más cálido y con más cuerpo que el de por defecto (el centro del espectro queda más abajo en casi todos los sonidos). Lo que se conserva: los nombres, las duraciones (las puertas duran 1,2 s en vez de 0,7; los pasos, un 30 a 50 % más), los bucles sin costura, los agudos de todo lo que se sitúa, y las notas exactas, el número de toques y el ritmo de balizas, bastón sonoro, brújula, plantas del ascensor, premios, menús y semáforos: solo cambia el instrumento que los toca.

### Grabado: grabaciones reales de uso libre

`data/sounds/grabado` es un paquete **parcial** hecho con grabaciones de terceros dedicadas al dominio público (**CC0 1.0** todas). Trae 113 de los 198 sonidos; los otros 85 suenan con el paquete por defecto: 68 a propósito, porque codifican información, y 17 porque no había una grabación válida.

```
.venv\Scripts\python.exe tools\montar_paquete_grabado.py [--fuentes carpeta] [--descargadas carpeta] [--solo patrón]
.venv\Scripts\python.exe tools\montar_paquete_grabado.py --comparar
```

**Los originales no están en el repositorio.** La herramienta los lee de dos carpetas: la de los que el autor ya tenía (`--fuentes` o la variable `ENTORNOLAB_FUENTES_SONIDO`, obligatoria una de las dos: el autor usa la carpeta `adjuntos` de Puerto Bravo) y la de lo **descargado para este paquete** (`--descargadas`, la variable `ENTORNOLAB_FUENTES_DESCARGADAS` o, por defecto, `adjuntos/fuentes_sonido` de este proyecto, con su `inventario.json`: página, enlace de descarga, autor, licencia y SHA-256 de cada fichero). Las colecciones que salen de la segunda llevan `"raiz": "descargadas"` en la tabla; si esa carpeta falta, esos sonidos se heredan y quedan pendientes con su motivo. En el paquete solo quedan los FLAC finales, ya recortados (11,6 MB). Sin los originales el paquete no se puede rehacer, pero sí usar.

La tabla está en `tools/receta_grabado.py` y reparte **todo** el catálogo en tres grupos, sin solapes (una prueba lo comprueba):

| Grupo | Qué es | Cuántos |
|---|---|---|
| `SONIDOS` | Sale de una grabación: colección, fichero original, tramo (`inicio`, `duracion`) y fundidos (`entrada`, `salida`) o fundido cruzado del bucle (`cruce`) | 113 (todos pasan las medidas) |
| `FUNCIONALES` | Codifica información y **no se sustituye**: balizas, bastón sonoro, brújula, las diez plantas del ascensor, su llamada y su llegada, fases y pulsador del semáforo, peldaños y rampa, pavimento táctil, bordillo, menús con notas, premios y logros con melodía | 68 |
| `PENDIENTES` | No hay grabación de licencia clara que sirva; lleva la descripción de lo que habría que buscar | 17 |

Qué le hace la herramienta a cada grabación, y nada más: a mono lo que es mono de serie (los ambientes siguen en estéreo, y una grabación mono no vale para un ambiente); remuestreo a 44,1 kHz; recorte del tramo, afinado al primer ataque; fundidos de entrada y de salida, o **fundido cruzado** del final con el principio en los bucles (a potencia constante si los dos trozos no se parecen, lineal si se parecen); y una ganancia para igualarlo al sonido de serie (primero lleva el pico a 0,8, porque muchas grabaciones vienen muy bajas, y después `niveles.igualar`). **No filtra, no ecualiza, no mezcla y no añade nada.**

Después comprueba midiendo con las mismas varas que el paquete «Natural» (`generar_paquete_sonidos.comprobar`: canales, duración de 0,5 a 1,75 veces la de serie y exacta en los bucles, pico, bordes, costura, componente continua, y un 2 % de energía por encima de 3 kHz en lo que se sitúa) y una más, propia de las grabaciones: que no quede más de 6 dB por debajo del de serie por culpa de sus picos. Lo que no cumple no se escribe y pasa a la lista de pendientes con su motivo (le ocurría a `premio/recogido` con las monedas de Kenney, muy picudas, 7,2 dB por debajo; ahora sale de otra grabación).

Lecciones de este paquete:

- **Una licencia impecable no basta.** Los pasos y los impactos de Kenney («Impact Sounds», «RPG Audio»: moqueta, hormigón, hierba, madera, cristal, tela) son CC0 con su fichero de licencia, pero tienen entre un 0 y un 1,9 % de energía por encima de 3 kHz: no se podrían situar delante o detrás. No se usan, y no se «arreglan» con ruido ni con ecualización.
- **Una grabación no puede contradecir la explicación del catálogo**, que es común a todos los paquetes («dos campanadas», «un golpe por segundo», «la manilla traquetea dos veces y la puerta no cede»). Por eso `fuente/campanas` es un tramo con dos campanadas y `puerta/con_llave` es una manilla cerrada que se prueba y no cede (no la puerta que se abre con llave de la primera versión).
- **Lo que sale de Freesound es la vista previa de alta calidad (OGG)**, lo único que se descarga sin iniciar sesión. Para cada suelo se toman, de una sola grabación, las seis pisadas con más de un 3 % de energía por encima de 3 kHz más parecidas a la mediana de su perfil. La mayoría de las pisadas grabadas con zapato plano sobre madera, moqueta u hormigón no llegan al 2 %: por eso la madera es de tacones y la moqueta y el adoquín siguen pendientes.
- **Un suelo entra entero o no entra**: con sus seis pasos. Los nombres genéricos (`pasos/arena`) eligen una variante al azar, y mezclar pasos grabados y sintetizados en un mismo suelo despistaría.
- **La licencia tiene que constar.** En `COLECCIONES`, el campo `constancia` dice dónde figura la de cada colección. Fichero de licencia dentro de la colección o inventario del autor con título, autor y página de cada grabación (Kenney, Corsica_S, BigSoundBank, las primeras de Freesound, «Ticking clock»); la página de OpenGameArt, leída el 26 de noviembre de 2026 («License(s): CC0»: los pasos de Fantozzi y las tres colecciones de rubberduck); y, en lo descargado para este paquete, la página de Freesound de cada grabación («Creative Commons 0»), que va en su línea de los créditos. Lo descargado sin licencia ni inventario («MoreSounds», «SoundPack01», «all-in-one», «beeps», «Cardsounds», «GUI Sound Effects by Lokif» y las páginas de `oga2` que `crear_packs.py` no cita) no se usa, y tampoco lo que es CC BY sin autor identificable.

Separación entre suelos y entre materiales (perfil de ocho bandas, en dB; `medidas.json`, clave `separacion`, y `--comparar`). «Dentro» es lo que varían los seis pasos de un mismo suelo; «entre», la distancia entre dos suelos; el margen es la menor distancia entre dos suelos dividida por la variación de dentro (por encima de 1 se distinguen):

| Paquete | Suelos | Dentro | Entre, mínima | Entre, media | Margen | Golpes: mínima entre materiales |
|---|---|---|---|---|---|---|
| Grabado, primera versión | acera, grava, arena, agua | 1,52 | 2,47 (acera y arena) | 4,69 | 1,62 | 5,95 (4 materiales) |
| Grabado, ahora | 12: los 4 anteriores, baldosa, madera, alfombra, hormigón, asfalto, tierra, hierba y metal | 1,58 | 2,11 (grava y madera) | 5,54 | 1,34 | 5,50 (5 materiales: ladrillo y madera) |
| Natural, esos mismos 12 | los mismos 12 | 1,09 | 1,51 (hormigón y madera) | 4,20 | 1,39 | 3,91 |
| Por defecto, esos mismos 12 | los mismos 12 | 0,69 | 1,06 (asfalto y tierra) | 6,28 | 1,54 | 6,39 |
| Natural, todo | 16 | 1,12 | 1,51 (hormigón y madera) | 4,09 | 1,35 | 3,91 (7 materiales) |
| Por defecto, todo | 16 | 0,67 | 1,06 (asfalto y tierra) | 5,84 | 1,57 | 6,39 (7 materiales) |

Roces (mínima entre materiales): Grabado 3,14 dB (madera y tela, 6 materiales); por defecto 1,77; Natural 4,23.

Leído con honradez: con doce suelos, las grabaciones separan los suelos casi como la síntesis (margen 1,34 frente a 1,39 y 1,54 con los mismos suelos), y la menor distancia entre dos suelos es mayor que en los otros dos paquetes (2,11 dB frente a 1,51 y 1,06); pero cada pisada real es distinta de la anterior, así que la variación de dentro es la más alta. Lo que aportan es un timbre reconocible, que esta medida no recoge.

Qué falta por grabar o por encontrar está, sonido a sonido y con la descripción de lo que hay que buscar, en `data/sounds/grabado/CREDITOS.txt` y en `receta.json` (clave `pendientes`).

## Seguimiento de cabeza

Opcional, con OpenTrack por UDP (`cabeza.py`, ver [voz.md](voz.md)). El presentador suma `cabeza.giro()` al rumbo del oyente en cada fotograma: al girar la cabeza los sonidos se quedan en su sitio, como si se girara el cuerpo. `cabeza.centrar()` toma la postura actual como «de frente».

## Licencias

### OpenAL Soft

- `data/bin/openal/soft_oal.dll`: OpenAL Soft 1.25.2, 64 bits. Licencia **GNU LGPL** (texto en `data/bin/openal/LICENCIA_OpenAL_Soft_LGPL.txt`). Código fuente: <https://github.com/kcat/openal-soft>.
- Para cumplirla, la DLL va como **fichero suelto y sustituible**: se carga con ctypes desde `data/bin/openal`, nunca se enlaza ni se incrusta en el ejecutable. Al compilar con cx_Freeze hay que conservarla como fichero dentro de `data/bin/openal` (la carpeta `bin` ya está en la lista de `data` distribuible de `setup_cx.py`) y mencionar OpenAL Soft y su licencia en «Acerca de» y en el manual.
- El programa fija, solo dentro de su proceso, `ALSOFT_LOCAL_PATH` (carpeta `hrtf`) y `ALSOFT_CONF` (`alsoft.ini`). No escribe nada fuera de su carpeta. OpenAL Soft puede leer además un `alsoft.ini` que el usuario tenga en `%APPDATA%`; el de EntornoLab se carga después.
- Es el mismo binario que usan Puerto Bravo y Reconocedor de Ciudades (las dos copias del autor son idénticas, SHA-256 `3963b06e…fab5b4`).

### Perfiles HRTF

Convertidos con `makemhr` de OpenAL Soft 1.25.2 a 44,1 kHz desde ficheros SOFA públicos (direcciones exactas en `data/bin/openal/LEEME.txt`):

- **MIT KEMAR** (Bill Gardner y Keith Martin, MIT Media Lab, 1994): uso libre citando a los autores.
- **SADIE II** (Universidad de York): licencia Apache 2.0.

Conviene revisar las condiciones vigentes de cada base de datos antes de publicar una versión.

### BASS: solo uso no comercial

> **Importante.** EntornoLab es software libre (GPL-3.0-or-later), pero **BASS no lo es**: `bass.dll` es de Un4seen Developments y es gratuita **únicamente para uso no comercial**. Si alguien quisiera usar o distribuir EntornoLab con fines comerciales, BASS exige una **licencia de pago de Un4seen** (<https://www.un4seen.com>). En ese caso basta con **elegir otro motor de sonido y retirar `bass.dll`**: el resto del programa no depende de ella y el motor de serie (OpenAL Soft) es libre.

- BASS viene incluida a través de `basskit` 0.8.12+reconocedor, una rueda propia y recortada (solo `bass.dll` 2.4 y la API nativa) que está en `__pip__/` y se instala con `entorno.bat instalar` (va en `requirements.txt`). El código Python de basskit es MIT; la DLL conserva la licencia de BASS.
- Para retirarla: borrar `lib\basskit\data\dlls\x64\bass.dll` (versión compilada) o desinstalar `basskit` del entorno virtual (código fuente). El motor `bass` aparece entonces como no disponible en las preferencias y, si estaba elegido, se usa `openal`.
- Como BASS no es compatible con la GPL, `LICENSE` incluye un **permiso adicional** (sección 7 de la GPLv3) para distribuir EntornoLab combinado con BASS sin tener que dar el código fuente de BASS. Solo cubre BASS.
- El texto de la licencia de BASS viaja en `data/docs/licencias/BASS.txt` (apartado «Licence») y dentro del propio paquete (`basskit/data/licenses/bass24/bass.txt`). Hay que mencionar BASS y esta condición en «Acerca de» y en el manual.

### Textos de las licencias

`LICENSE` (raíz; `LICENSE.txt` junto a los ejecutables en la versión compilada) es la GPL 3 con el permiso adicional. Los avisos y textos de todo lo que viaja con el programa (BASS, OpenAL Soft, perfiles HRTF, pygame-ce, wxPython, NumPy, sounddevice y PortAudio, soundfile y libsndfile, accessible_output2, cryptography, Python-Markdown y demás) están en `data/docs/licencias`; la lista es `data/docs/licencias/LEEME.md`. `tools/verificar_build.py` comprueba que viajan.

### Otras

- Los sonidos de `data/sounds/por_defecto` son síntesis propia del proyecto. Los de `data/sounds/natural` están generados por procedimiento con el Generador de sonidos del mismo autor (sin grabaciones ni modelos de terceros). Los dos van con la licencia del programa; cada paquete lleva su `CREDITOS.txt`.
- Los de `data/sounds/grabado` son recortes de grabaciones de terceros, todas **CC0 1.0** (dominio público), que es compatible con la GPL y no exige citar al autor; aun así, su `CREDITOS.txt` dice de cada sonido el fichero original, la colección, el autor, la licencia y la página de origen, y el resumen viaja en `data/docs/licencias/sonidos-grabado.txt`. No hay nada con cláusula «no comercial» o «sin obra derivada», ni «solo para uso personal», ni sacado de juegos comerciales, ni de procedencia desconocida. Si la licencia de alguna resultara no ser la que consta, basta con borrar sus ficheros: esos sonidos vuelven a sonar con el paquete por defecto.

## Pruebas

`tests/test_audio_*.py`. Ninguna hace sonar nada: OpenAL y el clásico se prueban en memoria, el estéreo con el controlador «dummy» de SDL, BASS con su dispositivo «sin sonido» y la captura de la mezcla final, y la voz con dobles.

```
.venv\Scripts\python.exe -m pytest tests -q -k "audio or entrada"
```

Lo que se mide con BASS (`tests/test_audio_bass.py`, que se salta entero con un mensaje claro si `basskit` no está instalado): izquierda y derecha, delante igual en los dos oídos, giro y movimiento del oyente, fuentes relativas, ley de distancia y altura, volumen por canal, por bus y maestro, tono mientras suena, filtro y «detrás», bucles que se mueven, final de los sonidos cortos, pausa, fundidos, atenuación por voz, vigilante, techo por fuente, compresor y robo de fuentes. Como BASS mezcla en tiempo real, ese fichero tarda unos 20 segundos. El cambio de salida en caliente abre la tarjeta (con el volumen a cero) y solo se prueba pidiéndolo: `APP_PRUEBA_SALIDA_REAL=1`.

Paquetes de sonidos (`tests/test_audio_paquetes.py`): listado y fichas, herencia de lo que falta, igualado, volumen por sonido, cambio en caliente con el motor nulo (qué se recarga y qué no, bucles relevados con el mismo número de canal) y con OpenAL en memoria (el bucle cambia de nota sin hueco, sin chasquido y al mismo volumen), paquete del usuario en la carpeta de datos, fichas dañadas, y las medidas del paquete «Natural» (forma, agudos, costuras, notas y toques de los avisos, suelos y materiales distinguibles, sin capas de IA en su receta).

Paquete «Grabado» (`tests/test_audio_paquete_grabado.py`): que la tabla reparte todo el catálogo sin solapes y no sustituye ningún aviso que codifique información; el tratamiento (recorte, mono, remuestreo, bucles sin costura, igualado) con «grabaciones» sintéticas; la herramienta entera sobre una carpeta de originales de mentira (no copia los originales, descarta lo que no tiene agudos, apunta lo que falta, rechaza una licencia «no comercial», lee también la segunda carpeta de fuentes, la de lo descargado, y hereda lo que sale de ella si falta); y el paquete que viaja: estructura, una línea de crédito con licencia admitida por cada sonido, misma forma que el de serie, agudos, igualado, herencia de lo que no trae, suelos enteros y distinguibles, y cambio en caliente con el motor nulo.

### Estabilidad al cerrar (memoria nativa)

Los motores OpenAL y BASS hablan con DLL por ctypes; un orden de liberación equivocado no da un error de Python, sino un cierre del proceso («Windows fatal exception: access violation» o «code 0xc0000374», corrupción del montículo). Reglas que siguen los motores y que hay que mantener:

- **OpenAL**: al cerrar se borran primero las fuentes, después filtros, efectos y búferes, y por último el contexto y el dispositivo. Un búfer sustituido mientras un bucle lo usa (cambio de paquete en caliente) no se puede borrar: queda apartado en `_retirados` y se borra en el primer `tic` en que ya nadie lo usa, o al cerrar (antes se olvidaba y solo lo recogía OpenAL al cerrar el dispositivo). `_sigue` pone el contexto propio antes de preguntar por una fuente, por si hay otro motor abierto.
- **BASS**: abre cada dispositivo una vez por proceso; un segundo motor lo comparte. Se cuenta cuántos motores usan cada dispositivo y solo el último hace `BASS_Free` (antes el primero que cerraba dejaba al otro sin dispositivo). Al cerrar un motor que no es el último se quitan solo su compresor y su DSP de captura. La retrollamada DSP (una `CFUNCTYPE`) se guarda en `_retrollamadas_vivas` hasta que se libera el dispositivo, aunque el motor desaparezca: si el recolector la liberase mientras el hilo de mezcla de BASS la llama, se ejecutaría memoria liberada. El WAV en memoria de cada flujo vive en el propio flujo (`_Flujo.memoria`) mientras suene, aunque el sonido se sustituya.

Pruebas de estrés: `tests/test_estabilidad_audio.py` (marcadas `lento`): dos motores BASS sobre el mismo dispositivo y cerrar uno, abrir y cerrar motores intercalados muchas veces, sustituir un bucle de OpenAL que suena y dos motores OpenAL a la vez.

Lo que se comprobó (noviembre de 2026, Python 3.15, wxPython 4.3.2): el cierre con 0xc0000374 que se vio una vez **no viene del sonido**. Se repitió en procesos nuevos con `python -X faulthandler -m pytest -p no:cacheprovider`: las pruebas de audio completas (`tests/test_audio_*.py`, con las lentas) 5 pasadas sin ningún cierre anómalo; las de la ventana principal del Estudio 35 pasadas con 3 cierres y la batería de interfaz 4 pasadas con 1, siempre al destruir la ventana de la cuarta prueba de `test_ui_estudio_ventana.py` y en un proceso que no había cargado ninguna biblioteca de sonido (ni `soft_oal.dll` ni `bass.dll` ni sounddevice). La causa es un temporizador de wx del catálogo de objetos que sigue en marcha cuando su diálogo ya se ha liberado; está explicada, con su prueba, en `tests/test_estabilidad_ui.py`.

Lo que se mide en memoria con OpenAL: HRTF activo con cada cabeza, derecha más fuerte en el oído derecho y con retardo en el izquierdo, delante igual en los dos oídos, giro del oyente, filtro que atenúa agudos, detrás más apagado, ley de distancia, robo de fuentes por prioridad, reverberación con cola, atenuación por voz, techo y subida gradual, y silencio si el juego deja de actualizar.
