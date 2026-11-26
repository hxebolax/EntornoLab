# Voz, braille, vibración y seguimiento de cabeza

Complemento de `docs/sonido.md`. Describe `app/audio/voz.py`, `app/audio/linea_braille.py`, `app/audio/haptica.py` y `app/audio/cabeza.py`.

## Voz (`app/audio/voz.py`)

### Salidas

La preferencia `voz.salida` (sección `voz` de `app/core/configuracion.py`) vale para el reproductor y para el Estudio, que comparten `config.json`. Tiene cuatro valores:

| Valor | Quién habla | Sin lector de pantalla |
|---|---|---|
| `automatica` (de serie) | el lector de pantalla abierto (NVDA, JAWS…) | la voz de Windows (SAPI) |
| `lector` | solo el lector de pantalla | no se habla; nunca SAPI |
| `sapi` | siempre la voz de Windows, aunque haya lector | la voz de Windows |
| `ninguna` | nadie: no se habla nunca | nadie |

- **Automática**: `accessible_output2` (`Auto`). Se pregunta qué lector hay cada vez que se habla y cada dos segundos en `tic()`, porque se puede abrir o cerrar con el juego en marcha; el cambio queda en el registro.
- **Solo el lector**: el mismo `Auto`, pero se recorren sus salidas saltando las del sistema (`SAPI5`, `SAPI4`, o las que tienen `system_output`): `primer_lector(auto, permitir_sistema=False)` en `app/core/voz.py`. Así, ni al hablar ni al redetectar el lector en `tic()` se acaba en la voz de Windows. `callar()` tampoco la toca.
- **SAPI directo**: la voz de Windows, con `sapi_voz` (nombre o parte del nombre), `sapi_velocidad` (-10 a 10) y `sapi_volumen` (0 a 100). Si SAPI no arranca, se cae a la automática y se registra.
- **Ninguna**: no se habla. `decir` devuelve 0.0 (no se atenúa el ambiente) y no se llama a `al_hablar`, pero el mensaje **entra en el historial**, el reproductor lo escribe abajo en la pantalla (`ultimo`) y, si hay un lector de pantalla abierto y el braille está activado, va a la línea braille (solo el braille: al lector no se le pide que hable ni que se calle). Sirve para quien lee en braille o en la pantalla, o no quiere voz.
- Cambiar entre `automatica`, `lector` y `ninguna` no vuelve a abrir nada (las tres usan el mismo `Auto`). Al pasar a `ninguna` no se corta lo que se esté diciendo: suele ser el aviso de que la voz se apaga.
- **Migración**: hasta la versión 1 del esquema de configuración, `lector` quería decir lo que hoy es `automatica`. `_migrar_a_2` cambia un `lector` guardado por `automatica`, así nadie cambia de comportamiento al actualizar.
- `APP_SIN_VOZ=1` desactiva la voz (pruebas automáticas).

#### Cómo se vuelve a la voz

- En el reproductor, Opciones, Voz y braille, «Habla». Al elegir «nadie» suena `interfaz/cerrar` y se da UNA vez el aviso (con la voz que había, y escrito en la pantalla y en el historial) de que el juego deja de hablar y de cómo volver.
- **Control+F12**, en cualquier pantalla del reproductor: vuelve a `automatica` (sonido `interfaz/abrir`). Se atiende en `Aplicacion._evento` antes que la pantalla y que el mapa de teclas (`es_tecla_restablecer_voz`), y F12 está en `teclado.FIJAS`: no se puede asignar a otra acción.
- En el Estudio, Preferencias, pestaña Voz, «Salida de voz».

#### En el Estudio (`app/core/voz.py`)

Todo lo que dice el Estudio pasa por `app.core.voz.hablar`: el aviso de arranque, `ContextoEstudio.anunciar` (también los anuncios de la supervisión) y la voz de accesibilidad (`app/ui/accesibilidad/voz.py`, que delega en ella). `main.py` llama a `voz.aplicar_configuracion(configuracion)` antes del aviso de arranque: aplica `voz.salida`, `voz.braille`, `voz.voz_sapi`, `voz.velocidad` y `voz.volumen`, y se suscribe a `voz.*` para aplicar cada cambio al momento (Preferencias, o lo que llegue de otro proceso con `Configuracion.recargar`). Cada texto queda en `historial()` aunque no se diga; el Estudio lo deja además en la barra de estado.

**Hilo de voz con su propio apartamento COM.** `hablar` no llama nunca a accessible_output2 en el hilo de wx: deja el texto en una cola (en orden; la interrupción la hace el lector con `interrupt=True`) y vuelve enseguida. Un hilo propio (`voz-com`, con `CoInitializeEx` multihilo) crea `Auto` y SAPI y habla. Motivo: en la versión compilada, hablar (o tener los objetos COM de la voz en el hilo de wx) justo al abrir un diálogo hacía que Windows registrara `Windows fatal exception: code 0x8001010d` (`RPC_E_CANTCALLOUT_ININPUTSYNCCALL`: llamada COM saliente mientras se atiende una llamada síncrona de entrada, la activación o el foco de la ventana) y el anuncio podía perderse. Por lo mismo, la lista de voces SAPI de Preferencias se pide al hilo (`voces_sapi()`). El aviso de arranque usa `hablar(..., esperar=2.0)` para decirse antes de las importaciones pesadas; `main.py` llama a `detener()` al cerrar.

```
aplicar_configuracion(configuracion) -> Callable[[], None]   aplica y se suscribe; devuelve cómo cancelar
hablar(texto, interrumpir=False, esperar=0.0) -> bool        sin esperar: True si se va a decir (salida no «ninguna»)
voces_sapi() -> list[str]   esperar_cola(segundos) -> bool   detener()
configurar(salida=None, braille=None, voz_sapi=None, velocidad=None, volumen=None)   velocidad de 0 a 100
salida_actual() -> str

historial() -> list[str]    ultimo() -> str
primer_lector(auto, permitir_sistema) / es_voz_del_sistema(salida)   compartidas con app/audio/voz.py
usar_salidas(auto, sapi)    dobles para las pruebas
```

En el reproductor, el cambio de `voz.salida` llega a `Voz.configurar` por la suscripción de `Aplicacion._config_cambiada`, también cuando lo cambia el Estudio (orden `releer_configuracion` de la sala, o al volver al menú principal).

### API

```
Voz(opciones: dict | None = None, *, salida: object | None = None)
  decir(texto, interrumpir=False, canal="juego") -> float   duración estimada en segundos; 0.0 si no se dice
  callar() -> None
  repetir() -> float        el último mensaje
  anterior() -> float       historial hacia atrás; en el borde dice «Primero.»
  siguiente() -> float      historial hacia delante; en el borde dice «Último.»
  activar_canal(canal, si) -> None
  configurar(opciones) -> None      en caliente: salida, voz, velocidad, volumen, braille, canales
  salida: str               automatica, lector, sapi o ninguna
  voces_sapi() -> list[str]
  instalar_ventana(hwnd) -> None    para el braille fijo (ver más abajo)
  tic() -> None             una vez por fotograma, en el hilo principal
  cerrar() -> None
  historial: deque[str]     historial_canales: deque[str] (el canal de cada mensaje)
  ultimo: str   nombre: str (lector en uso)   canales: dict[str, bool]
  al_hablar: Callable[[str, float], None] | None     gancho (texto, duración) para la supervisión

VozFalsa(opciones=None)     misma interfaz; no habla; registro: list[(texto, canal, interrumpir)]
estimar_duracion(texto, velocidad=0) -> float
sintetizar_a_fichero(texto, ruta, voz=None, velocidad=0) -> bool
```

Opciones (dict): `activa`, `salida`, `sapi_voz`, `sapi_velocidad`, `sapi_volumen`, `braille`, `nunca_interrumpir`, `canales` (`{canal: bool}`), `historial_max`. Los valores fuera de rango o de tipo incorrecto se sanean.

### Canales

`juego`, `ayuda`, `aviso` y `profesional`, cada uno activable por separado. Lo que llega por un canal desactivado **no se dice pero sí queda en el historial**, con su canal en `historial_canales`: el alumno puede repasarlo y el informe de la sesión no pierde nada. En ese caso `decir` devuelve 0.0 y no se llama a `al_hablar`.

### Historial

- Lo que se dice al repasar no entra en el historial (en `VozFalsa` se apunta con el canal `historial`).
- Mientras se repasa, y durante 20 segundos (`REPASO_PAUSA`), los mensajes nuevos no mueven el cursor: si no, con el juego hablando, «anterior» diría siempre el mismo mensaje. Al llegar al último se deja de repasar.

### Duración estimada

Un lector de pantalla no avisa de cuándo termina de hablar. `decir` devuelve `min(9, 0,7 + letras / 15)` segundos (con SAPI directo se corrige por la velocidad: cada diez puntos, el triple o un tercio). El presentador lo pasa a `MotorAudio.atenuar_por_voz` para bajar el ambiente y la música mientras tanto.

### Voz posicionada

`sintetizar_a_fichero` escribe un WAV de 44,1 kHz, 16 bits, mono con SAPI (`SpFileStream`), sin que suene nada. El motor de sonido lo carga y lo coloca en el espacio como cualquier otro sonido (por ejemplo, un personaje que habla desde su sitio).

## Braille

Modos (opción `braille`):

- `temporal` (de serie): mensaje de braille del lector (`lector.braille`), que lo quita a los pocos segundos. Funciona con NVDA, JAWS y System Access.
- `fijo`: el mensaje se queda en la línea hasta el siguiente. Solo con NVDA; con otro lector se comporta como `temporal`. Hay que llamar a `Voz.instalar_ventana(hwnd)` con el identificador de la ventana de pygame (`pygame.display.get_wm_info()["window"]`), a ser posible con la ventana recién creada y aún oculta, y a `Voz.tic()` en cada fotograma.
- `nada`: solo voz.

`linea_braille.py` viene de Reconocedor de Ciudades (allí se probó con una línea braille virtual). Crea un control de texto oculto dentro de la ventana, le pone el mensaje como nombre accesible y avisa a NVDA sin que lo repita en voz alta. No usa wx: solo ctypes.

`nunca_interrumpir` (línea braille o sordoceguera): ningún mensaje corta al anterior.

## Vibración (`app/audio/haptica.py`)

Vocabulario pequeño y constante:

| Patrón | Sensación | Significado |
|---|---|---|
| `choque` | golpe seco y fuerte | has chocado |
| `premio_cerca` | pulso suave | hay un premio cerca |
| `pared_izquierda` | vibra el lado izquierdo | pared a la izquierda |
| `pared_derecha` | vibra el lado derecho | pared a la derecha |
| `objetivo` | doble pulso | objetivo alcanzado |
| `peldano` | toque corto | un peldaño |
| `aviso` | tres toques | aviso del juego o del profesional |

Convención de lados: en los mandos de Xbox y PlayStation el motor grave está en la empuñadura izquierda y el agudo en la derecha. «Izquierda» usa solo el grave; «derecha», solo el agudo, algo más fuerte y largo porque se nota menos.

```
Haptica(emisor: Callable[[float, float, int], None] | None = None, opciones: dict | None = None)
  vibrar(grave, agudo, ms) -> None        directa (EvVibrar); recortada a 0..1 y multiplicada por la fuerza
  patron(nombre, intensidad=1.0) -> bool  falso si el nombre no existe
  tic(dt=None) -> None                    avanza las secuencias (doble pulso)
  parar() -> None
  configurar(opciones) -> None            activa (bool), fuerza (0,2 a 1)
  registro: list[(grave, agudo, ms)]      lo emitido cuando no hay emisor (pruebas)
  pendiente: bool
PATRONES: dict[str, tuple[Pulso, ...]]    Pulso(grave, agudo, ms, pausa_ms)
nombres_patrones() -> dict[str, str]      nombre visible traducido
```

El emisor normal es `Mando.vibrar`. Un patrón nuevo sustituye a la secuencia pendiente.

## Seguimiento de cabeza (`app/audio/cabeza.py`)

Opcional. [OpenTrack](https://github.com/opentrack/opentrack) (libre, con webcam o sensor) envía la postura de la cabeza por UDP.

Puesta en marcha:

1. En OpenTrack, salida «UDP over network», dirección `127.0.0.1`, puerto `4242`.
2. En EntornoLab, activar el seguimiento de cabeza.
3. Mirar al frente y pulsar «centrar».

```
Cabeza(puerto=4242, invertir=False, direccion="127.0.0.1", suavizado=0.0)
  iniciar() -> bool     falso si el puerto está ocupado (se registra)
  parar() -> None
  giro() -> float       grados a la derecha respecto del centro, -180 a 180; 0 si no llega nada en un segundo
  cabeceo() -> float
  centrar() -> None     la postura actual pasa a ser «al frente»
  recibiendo: bool
  poner(giro, cabeceo=0.0) -> None    para pruebas
leer_paquete(datos: bytes) -> tuple | None    seis dobles little-endian: x, y, z, giro, cabeceo, alabeo
```

El giro se suma al rumbo del oyente antes de llamar a `MotorAudio.oyente`: al girar la cabeza a la derecha, lo que sonaba delante pasa a oírse a la izquierda. `invertir` sirve para cámaras que dan el giro al revés; `suavizado` (0 a 0,95) quita el temblor de una webcam a cambio de algo de retraso.

## Pruebas

`tests/test_audio_voz.py`, `tests/test_core_voz.py`, `tests/test_audio_haptica.py` y `tests/test_audio_cabeza.py`. Ninguna hace hablar al lector de pantalla: usan `VozFalsa`, un lector de mentira inyectado con `Voz(salida=...)`, dobles de `Auto` y `SAPI5` de accessible_output2 (cada una de las cuatro salidas, y la redetección con `lector`) o `app.core.voz.usar_salidas`. La opción «Habla» y Control+F12 se prueban en `tests/test_reproductor_opciones.py`; «Salida de voz» de Preferencias, en `tests/test_ui_estudio_preferencias.py`; la migración, en `tests/test_core_configuracion.py`. La síntesis a fichero se prueba de verdad con SAPI (se salta si no está) y el seguimiento de cabeza con un socket UDP real en un puerto libre.
