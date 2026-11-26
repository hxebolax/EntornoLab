# Motor de simulación (`app/motor`)

Documentación de desarrollo. El motor recibe órdenes y devuelve eventos: no tiene interfaz, no suena y no habla. La capa de sonido (`app/audio/presentador.py`, ver [sonido.md](sonido.md)) convierte sus eventos en sonido, voz y vibración. Se prueba entero sin ventana ni altavoces (`tests/test_motor_*.py`).

```python
sesion = Sesion(entorno, catalogo, AjustesJuego.de_dict(ajustes_del_alumno), actividad=actividad, semilla=1234)

# una vez por fotograma
for accion, pulsada in entrada.traducir(evento):
    sesion.orden(accion, 1.0 if pulsada else 0.0)
sesion.analogico(avance, lateral, giro, mirada)
eventos = sesion.avanzar(dt)
presentador.aplicar(eventos, sesion, dt)      # usa sesion.oyente() y sesion.fuentes()
grabadora.muestra(*sesion.muestra())
```

## Piezas

| Módulo | Qué hace |
| --- | --- |
| `eventos.py` | `EvSonido`, `EvVoz`, `EvVibrar`, `EvAcustica`, `EvRegistro`, `EvFin`, `FuenteActiva` y los nombres de sonido. |
| `mundo.py` | Índice del entorno por planta (rejilla espacial) y estado dinámico de puertas y objetos. |
| `movimiento.py` | Pasos, giros, colisión con deslizamiento, puertas, modos, escaleras, rampas y ascensor. |
| `percepcion.py` | Ayudas con nombre, descubrimiento progresivo y avisos automáticos. |
| `acustica.py` | Fuentes continuas: oclusión, sonido por la puerta, otras plantas. |
| `navegacion.py` | Rutas, distancias de camino, salidas y grafo de espacios. |
| `lenguaje.py` | Frases de orientación en el formato, la unidad y el estilo del alumno. |
| `dinamica.py` | Semáforos, tráfico, cruces de calzada, puertas automáticas, objetos con fases o temporizador. |
| `sesion.py` | `Sesion` y `AjustesJuego`: la única puerta del motor. |

Reglas: solo biblioteca estándar; nada de wx, pygame ni sonido; todo texto con `_()`; todo el azar sale de `sesion.azar` (semilla).

## Sesión

```
Sesion(entorno, catalogo, ajustes=None, actividad=None, semilla=None, inicio=None)
  orden(accion, valor=1.0)                 valor 0 = soltar una acción mantenida
  analogico(avance, lateral, giro, mirada=None)      mirada = (derecha, delante) de la palanca de mirar
  avanzar(dt) -> list[Evento]
  oyente() -> (x, y, z, rumbo)
  fuentes() -> list[FuenteActiva]
  estado() -> dict
  muestra() -> (t, planta, x, y, rumbo)
  pausar(si) · recolocar(pos) · terminar(resultado=None) · resumen() -> dict
  terminado, pausado, t / tiempo_activo, tiempo_pausa, semilla, resultado, contadores
  aplicar_ajustes(ajustes) · permitir_ayuda(ayuda, permitida=True, limite=None)
  # para actividades
  decir(texto, canal="juego", pedida=False, prioridad=1, clave="", caduca=5.0, retardo=0.0, grupo="", vale=None)
  sonar(nombre, pos=None, relativo=None, volumen=1.0, tono=1.0, bus="efectos", filtro=0.0, retardo=0.0, grupo="")
  vibrar(patron, retardo=0.0, grupo="") · emitir(evento) · registrar(tipo, **datos)
  programar(retardo, evento_o_funcion, grupo="") · cancelar(grupo)
  anadir_fuente(id, sonido, pos, volumen=1.0, radio=12.0, bucle=True, intervalo=0.0, altura=1.0,
                bus="ambiente", ocluir=True, movil=False, tono=1.0) · quitar_fuente(id) -> bool
  baliza(pos | None, por_ruta=False, sonido="baliza/pulso") -> bool
  interactuables_cerca() -> list[dict] · distancia_a(lugar) -> float · pos3(x, y, altura) -> (x, y, z)
  # subsistemas
  mundo, nav, leng, movimiento, percepcion, acustica, dinamica, jugador, azar
```

- Las órdenes se apuntan y se atienden en el siguiente `avanzar`, que es quien devuelve los eventos.
- `dt` se recorta a 0,25 s. En pausa no corre el tiempo activo (`t`), se acumula `tiempo_pausa`, no se atienden órdenes y `fuentes()` queda vacía.
- Acciones que atiende el motor: `avanzar retroceder girar_izquierda girar_derecha paso_izquierda paso_derecha media_vuelta interactuar donde_estoy mirar_delante mirar_izquierda mirar_detras mirar_derecha alrededor cercano_siguiente cercano_anterior descubiertos brujula sonda eco objetivo pista volver_inicio`. Las de voz, ayuda, pausa y menús son del reproductor.
- El motor nunca modifica el `Entorno`: el estado de puertas y objetos de la partida vive en `Mundo`.

### `AjustesJuego`

Los valores de serie del movimiento, las direcciones, la unidad, el estilo y el detalle se toman de `VALORES_POR_DEFECTO` de `app/core/configuracion.py` (secciones `juego` y `voz`): son los que ve el usuario en las preferencias, y `tests/test_motor_sesion.py` vigila que no se separen.

| Campo | Serie | Valores |
| --- | --- | --- |
| `modo_movimiento` | `pasos` | `pasos`, `continuo`, `brujula`, `salas`, `aceras` |
| `paso_m` | 0,6 | 0,25 a 1,5 |
| `giro_grados` | 45 | 0 a 180; 0 = giro libre mientras se mantiene |
| `velocidad_ms` | 1,2 | 0,3 a 3 |
| `formato_direccion` | `reloj` | `reloj`, `lados`, `cardinal`, `grados` |
| `unidad` | `metros` | `metros`, `pasos` |
| `detalle` | 2 | 0 (solo sonidos) a 3 |
| `ayudas` | `{}` | ayuda → `{"permitida": bool, "limite": int o None}`; también vale `False` o un número |
| `estilo` | `adulto` | `infantil`, `juvenil`, `adulto` |
| `radio_m` | 0,25 | radio del alumno |
| `alcance_sonda` | 8 | metros |
| `trafico` | `true` | simular vehículos en las vías |

`AjustesJuego.de_dict(datos)` es tolerante (lo que falta o no vale toma el valor de serie, todo en rango); `a_dict()` es el inverso.

## Eventos

```
EvSonido(nombre, pos=None, volumen=1.0, tono=1.0, bus="efectos", filtro=0.0, relativo=None)
EvVoz(texto, interrumpir=False, canal="juego")          canales: juego, ayuda, aviso, profesional
EvVibrar(grave=0, agudo=0, ms=0, patron=None, intensidad=1.0)     patron: choque, pared_izquierda, pared_derecha, peldano, objetivo, aviso
EvAcustica(preset)
EvRegistro(tipo, datos)
EvFin(resultado)
FuenteActiva(id, sonido, pos, volumen=1.0, tono=1.0, filtro=0.0, bucle=True, eco=True, bus="ambiente")
```

Todo `EvRegistro.datos` lleva `t` (tiempo activo), `planta`, `x`, `y` y `espacio`, además de:

| Tipo | Datos propios |
| --- | --- |
| `inicio` | `entorno`, `semilla`, `modo`, `rumbo` |
| `entrada_espacio` | `nombre`, `primera`, `tipo` (`espacio` es el nuevo) |
| `salida` | `abertura`, `nombre`, `es_salida` (ha cruzado una abertura hacia fuera del entorno) |
| `cambio_suelo` | `suelo`, `anterior` |
| `choque` | `con`, `clase` (pared, puerta, ventana, macizo, objeto), `material`, `elemento`, `punto` |
| `limite` | — (ha intentado salirse del entorno) |
| `puerta` | `abertura`, `nombre`, `accion` (abrir, cerrar, con_llave, automatica_abre, automatica_cierra) |
| `interaccion` | `elemento`, `clase` (objeto), `nombre`, `accion`, `estado` |
| `objeto_termina` | `elemento`, `nombre`, `estado` (un temporizador ha acabado) |
| `conector` | `conector`, `accion` (entrar, salir), `tipo`, `sentido` |
| `cambio_planta` | `de`, `a`, `conector`, `tipo` |
| `ascensor` | `conector`, `accion` (llamar, entrar, viajar, salir), `espera`, `de`, `a`, `duracion` |
| `ayuda` | `ayuda`, `uso`, `restantes` |
| `ayuda_denegada` | `ayuda`, `motivo` (prohibida, agotada) |
| `aviso` | `clase`, `elemento`, `texto` (aviso automático dado) |
| `descubierto` | `clase` (espacio, objeto), `elemento`, `nombre` |
| `espacio_explorado` | `nombre` |
| `pulsador` | `paso`, `objeto`, `fase` |
| `cruce_empieza` | `via`, `por_paso` |
| `cruce_inseguro` | `via`, `paso`, `fase`, `distancia`, `vehiculo` |
| `cruce` | `via`, `paso`, `por_paso`, `fase`, `en_rojo`, `seguro`, `duracion`, `vuelve` |
| `baliza_llegada` | `destino` |
| `pausa` | `activa`, `tiempo_pausa` |
| `recolocar` | `rumbo` |
| `volver_inicio` | — |

`EvFin.resultado`: `tiempo_activo`, `tiempo_pausa`, `distancia_m`, `pasos`, `choques`, `ayudas`, `espacios_visitados`, `semilla`, más lo que devuelva `actividad.resultado(sesion)` y lo que se pase a `terminar`.

### Voz y sobrecarga

- `pedida=True` (lo ha pedido el alumno): se emite ya, con `interrumpir=True`, y vacía la cola de lo automático.
- Lo automático espera turno en una cola de cuatro frases como mucho. Sale primero la de más `prioridad`; una frase con la misma `clave` sustituye a la pendiente; se descarta si pasan `caduca` segundos o si `vale()` devuelve falso. La `prioridad` 3 (seguridad, llegadas) no espera.
- El motor no oye la voz: calcula lo que dura cada frase (0,3 s + 45 ms por carácter).
- En cada comprobación de proximidad se dan como mucho dos avisos.

## Movimiento

- El alumno es un círculo. Al avanzar se le saca de lo que pisa empujándolo en perpendicular: resbala por paredes y rodea esquinas y jambas. De frente es un **choque** (`golpe/<material>` en el punto de contacto, vibración `choque`, nombre de lo tocado si `detalle` ≥ 1, registro); resbalando es un **roce** (`roce/<material>`, vibración del lado).
- Los objetos de los complementos son obstáculos con su huella real. Con `altura_base` por debajo de 1,75 m se choca con ellos; el bastón solo los encuentra si son `detectable_baston` y su base está a 20 cm o menos. Un objeto con `paso_libre` deja pasar en esos estados.
- Fuera de todo espacio solo se puede estar a un metro de una abertura (para poder cruzar una salida); más allá suena `interfaz/borde`.
- `interactuar` usa lo que hay delante y al alcance: puerta (abre, cierra, con llave), parada de ascensor (llamar), pulsador de semáforo, objeto (acción desde su estado, gesto suelto, o decir qué es), boca de escalera (la describe). Un objeto que queda al otro lado de una pared o de una puerta cerrada no está al alcance, aunque esté a un palmo (por encima de otro mueble sí se alcanza). Después se llama a `actividad.al_interactuar(sesion, elemento)`.
- Modos: `pasos` (un paso por orden; mantenida, repite al ritmo de paseo), `continuo`, `brujula` (avanzar = norte, girar a la derecha = este, retroceder = sur, girar a la izquierda = oeste), `salas` (girar elige salida del espacio y avanzar la cruza), `aceras` (avanzar camina recto hasta la siguiente novedad).
- **Escaleras y rampas**: se entra al pasar por la boca en el rumbo del tramo. Un sonido por peldaño (`escalera/subir`, `escalera/bajar`, `escalera/rampa`) con tono de 0,8 a 1,4 según la altura. `media_vuelta` invierte el sentido. La escalera mecánica avanza sola y solo se entra por su lado.
- **Ascensor**: es un estado del alumno. `interactuar` en la parada lo llama; al llegar, `avanzar` hacia la puerta entra; dentro, girar elige planta e `interactuar` acepta; al llegar, `avanzar` sale.

## Ayudas

Nombres (claves de `AjustesJuego.ayudas`): `donde_estoy`, `descripcion`, `mirar`, `delante`, `alrededor`, `sonda`, `cercanos`, `descubiertos`, `brujula`, `eco`, `objetivo`, `pista`, `baliza`, `avisos`.

| Acción | Ayuda | Qué hace |
| --- | --- | --- |
| `donde_estoy` | `donde_estoy` (+ `descripcion`) | Espacio, planta y rumbo; nunca la ruta. Dos veces seguidas añade la descripción. |
| `mirar_delante` | `delante` | Lo que encuentra el rayo y lo que hay en un cono de 35°. |
| `mirar_izquierda/detras/derecha`, palanca de mirar | `mirar` | Aberturas, cambios de espacio y de suelo y primer obstáculo, con distancias. |
| `alrededor` | `alrededor` | Cuatro cuadrantes. |
| `sonda` | `sonda` | Un pulso por paso del alumno (`sonda/libre`, `puerta`, `bordillo`, `escalon`) y el final (`pared`, `objeto`, `puerta`, `lejos`). Mantenida se repite sin gastar usos. |
| `cercano_siguiente/anterior` | `cercanos` | Lista por distancia de camino; solo lo del mismo espacio, lo que está a la vista o lo ya descubierto. |
| `descubiertos` | `descubiertos` | Lugares conocidos, con «sin visitar» y «no explorada del todo». `percepcion.lugares_conocidos()` da los datos para un menú. |
| `brujula` | `brujula` | Rumbo y `brujula/norte` desde el norte. |
| `eco` | `eco` | Chasquido y sus rebotes en las cuatro direcciones. |
| `objetivo`, `pista` | `objetivo`, `pista` | Llaman a `actividad.al_pedir(sesion, accion)`. |
| — | `baliza` | `sesion.baliza(...)`. |
| — | `avisos` | Avisos automáticos de proximidad (sin límite de usos: solo permitir o prohibir). |

Avisos automáticos por nivel de detalle: 1, referencias a 1,5 m, bocas de escalera, ascensores, pasos de peatones y cruces; 2, además puertas cercanas, objetos que suenan, bordillo delante, ficha completa del paso y forma del cruce, referencias a 2,5 m; 3, además objetos delante y referencias a 4 m con distancia. Con 0 no se dice nada. El `aviso` que trae un objeto en su ficha se dice siempre que `detalle` ≥ 1, aunque `avisos` esté prohibida.

## Acústica

`FuenteActiva.volumen` y `filtro` llevan solo oclusión y camino; la distancia la pone la capa de sonido con `pos`.

- A la vista: en su sitio, sin filtro.
- Con una puerta cerrada o una ventana en la recta: en su sitio, apagada.
- Tras una pared: desde la abertura del camino más corto que el alumno tiene a la vista, con el volumen corregido a la longitud real del camino. Si no hay camino, a través del tabique (ganancia 0,28 por tabique, filtro 0,85).
- Otra planta: solo por las bocas de escalera y rampa.
- Una fuente deja de listarse cuando su camino pasa de su `radio` (se funde en el último cuarto).
- Las fuentes con `bucle` falso e `intervalo` llegan como `EvSonido`, ya con su oclusión.

## Navegación

```
Navegador(mundo, con_llave=False)
  ruta(origen, destino, evitar=()) -> Ruta | None        lugares: Posicion o (planta, x, y)
  distancia(origen, destino, evitar=()) -> float | None
  distancias_desde(origen, radio=None) -> Campo | None · distancia_en(campo, x, y) -> float | None
  salidas(origen, con_ruta=False) -> list[Salida] · salida_mas_cercana(origen) -> Salida | None
  grafo_espacios() -> dict[str, list[Enlace]] · enlaces(espacio_id) -> list[Enlace]
  espacios_alcanzables(origen) -> set[str] · ruta_espacios(origen_id, destino_id) -> list[str] | None
Ruta: puntos [(planta, x, y)], longitud, conectores; plantas(), puntos_de(planta), giros(minimo=30)
Salida: abertura, planta_id, distancia, ruta
Enlace: tipo (abertura, conector, abierto), id, origen, destino, punto, punto_destino, nombre
```

- Una puerta cerrada y un objeto con `paso_libre` cuentan como paso; una puerta con llave y una ventana, no.
- `evitar` admite ids de aberturas y de conectores.
- `Ruta.longitud` son metros andados: una escalera suma su longitud, el ascensor no. Es comparable con `sesion.movimiento.distancia`.
- Un destino dentro de un mueble (su centro) se alcanza desde la celda libre más cercana con la recta hasta él sin paredes ni puertas (los lados del propio mueble y otros muebles no cuentan); si no la hay, la más cercana de su mismo espacio. Así la ruta a un armario pegado a un tabique acaba en su habitación y no en la de detrás.
- `distancia_en` es aproximada cuando no hay línea recta (camino por celdas); `ruta` y `salidas` dan la del camino ya estirado.

## Qué puede hacer una actividad

Cualquier objeto con alguno de estos métodos (todos opcionales; devuelven una lista de eventos o nada):

| Gancho | Cuándo |
| --- | --- |
| `al_empezar(sesion)` | En el primer `avanzar`, antes del anuncio del lugar de inicio. |
| `tras_mover(sesion)` | Tras cada desplazamiento (en modo continuo, cada fotograma en que se mueve). |
| `al_interactuar(sesion, elemento)` | Tras `interactuar`; `elemento` es la `Abertura`, el `Objeto`, el `Conector`, el `Espacio` del paso o `None`. Si no había nada que usar y no devuelve eventos, el motor dice «No hay nada que usar aquí». |
| `tic(sesion, dt)` | Cada fotograma activo. |
| `al_pedir(sesion, accion)` | El alumno pide `objetivo` o `pista` (ya contado como ayuda). |
| `al_registrar(sesion, registro)` | Con cada `EvRegistro` que sale de la sesión: los del motor (choque, entrada_espacio, ayuda, cruce, cambio_planta…), los que registra la propia actividad, los que devuelve un gancho y los que llegan por `emitir`. Se llama en el momento, a veces a mitad de un paso: lo prudente es apuntar y actuar en `tic`. Un registro emitido mientras se atiende otro espera turno (nunca llega anidado). |
| `resultado(sesion) -> dict` | Al terminar; se mezcla en `EvFin`. |

Un fallo en un gancho se anota en el registro y la partida sigue. Lo que suele necesitar:

- Hablar y sonar: `sesion.decir`, `sesion.sonar`, `sesion.vibrar`, o devolver eventos.
- Premios y personajes: `anadir_fuente` y `quitar_fuente`; `distancia_a` para saber si se ha llegado; `registrar("premio", id=..., nombre=...)`.
- Guiar: `baliza(lugar)` o `baliza(lugar, por_ruta=True)`; llega el registro `baliza_llegada`.
- Puntuar: `sesion.nav` (ruta óptima, salidas), `sesion.movimiento.distancia`, `sesion.resumen()`, `sesion.contadores`.
- Estado del mundo: `mundo.estado_abertura`, `mundo.poner_abertura`, `mundo.estado_objeto`, `mundo.poner_estado_objeto`, `dinamica.fase(paso_id)`.
- Ayudas: `permitir_ayuda`, `percepcion.usos`, `percepcion.restantes`.
- Terminar: `sesion.terminar({...})`.

## Dinámica

- Semáforo en los datos de un paso de peatones (`semaforo`, `sonoro`, `pulsador`, `ciclo`) o como objeto de un complemento (`dinamica.tipo = "semaforo"`). Un objeto semáforo de peatones a menos de 4 m de un paso lo gobierna; si el paso ya tiene semáforo en sus datos, el objeto lo sigue y suena por él.
- `dinamica.tipo = "temporizador"`: pasa a `al_terminar` tras `segundos` en `estado`, con `sonido_al_terminar`.
- Tráfico: vehículos por cada vía según `trafico` y `sentido`; paran con el verde de peatones, ceden en los pasos sin semáforo y frenan ante el alumno. Un cruce es inseguro si un vehículo frena de golpe por él o le pasa al lado en marcha: aviso hablado y `cruce_inseguro`. No termina la partida.

## Entornos importados de un mapa

- Un espacio de tipo `escalera` en una planta exterior son unas escaleras de calle (no unen plantas): al entrar se dice «Escaleras, N peldaños» o que el mapa no dice cuántos, si suben o bajan (`datos.sube_hacia`) y, con `detalle` ≥ 2, el resto de su ficha; cada paso suena a peldaño y al salir se dice «Fin de las escaleras». Con `datos.rampa`, lo mismo como rampa.
- Pasos de peatones: se respeta `datos.segun_mapa` (sí, no, desconocido) con `app.exportar.fichas.estado_de`; «no tiene» y «el mapa no lo dice» son frases distintas.
- Cruces: manda `datos.forma` (t, y, cruz, aspa, desalineado, complejo, rotonda); sin vías con nombre se dicen los lados de `datos.rumbos`.
- Aceras con `datos.origen = "deducida"`: se dice al entrar por primera vez (`detalle` ≥ 2).
- Un espacio con `datos.terreno_base` no se anuncia ni cuenta como lugar descubierto.

## Pruebas

```
.venv\Scripts\python.exe -m pytest tests -q -k motor
```

`tests/test_motor_comun.py` tiene el `Robot` (da órdenes y guarda eventos) y una sala de pruebas; `Robot.recorrer(destino, evitar=...)` va a cualquier planta por la ruta del navegador con las órdenes del alumno (escaleras peldaño a peldaño; el ascensor llamándolo, entrando, eligiendo planta y saliendo) y `Robot.esperar_hasta(condicion, plazo)` espera con plazo. `tests/test_motor_integracion_*.py` juegan con él actividades entre plantas y un cruce con tráfico; `tests/test_motor_complementos.py` usa los complementos reales de `data/plugins`.
