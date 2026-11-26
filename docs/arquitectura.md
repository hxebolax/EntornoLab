# Arquitectura de EntornoLab

Este documento es el contrato entre los módulos. Quien programe una parte debe respetar las interfaces descritas aquí; si necesita cambiarlas, las cambia también en este documento.

## Qué es

EntornoLab es una aplicación de Windows, portable y sin conexión, para aprender lugares antes de visitarlos:

- **Estudio** (profesional de rehabilitación): crea entornos interiores y exteriores, los amuebla con objetos de complementos, define actividades, juegos y exámenes, lleva fichas de alumnos, supervisa en vivo y consulta informes. Interfaz wxPython con controles nativos (lector de pantalla, teclado, ratón y plano gráfico).
- **Jugar** (alumno): audiojuego en primera persona con sonido 3D, teclado o mando. Interfaz pygame-ce con menús hablados.
- **Modo recorrido** (profesional): el mismo reproductor, con un menú de edición para colocar cosas andando.

Los tres comparten un motor sin interfaz.

## Reglas generales de código

- Python 3.15, Windows de 64 bits.
- Todo en español de España: identificadores, comentarios, docstrings, mensajes y registros.
- Tabulaciones para indentar. Una instrucción por línea. Docstring en cada módulo, clase y función pública, explicando el porqué.
- Anotaciones de tipo en las firmas públicas. `from __future__ import annotations`.
- Textos para el usuario siempre con `_()` de `app.core.i18n` (también `_n` para plurales y `N_` para marcar sin traducir). El español es el idioma de origen. Nunca se comparan textos traducidos.
- Registro con `logging.getLogger(__name__)` y formato diferido `%s`. Ningún `except` silencioso.
- Portable: todo dato en `data/` mediante `app.core.paths`. Nunca rutas absolutas ni `os.getcwd()`.
- Los paquetes `app/dominio`, `app/motor` y `app/actividades` no importan `wx`, `pygame` ni bibliotecas de sonido. Se prueban sin ventana ni altavoces.
- Pruebas con pytest en `tests/`, nunca sobre el `data/` real (fixture `data_temporal` o `tmp_path`).
- No se ejecuta código procedente de entornos, actividades o complementos: son solo datos.

## Convenciones espaciales

- Unidades: metros y segundos.
- Eje X hacia el este, eje Y hacia el norte, eje Z hacia arriba.
- Rumbo en grados, 0 = norte, 90 = este, sentido del reloj. `rumbo = atan2(dx, dy)`.
- Cada planta tiene un `nivel` entero (0 = planta baja) y una `altura_m` (cota del suelo).
- Un punto es `(x, y)`; una posición completa es `(planta_id, x, y)`.

## Estructura de carpetas

```
main.py                    arranque del Estudio; con --jugar o --recorrido delega en el reproductor
jugar.py                   arranque directo del reproductor (segundo ejecutable)
app/core/                  rutas, versión, configuración, registro, instancia única, i18n
app/dominio/               modelo del entorno, geometría, formato de fichero, validación, catálogo de complementos
app/motor/                 simulación: mundo, colisiones, movimiento, percepción, acústica, navegación, eventos
app/audio/                 motores de sonido, voz, seguimiento de cabeza, síntesis de sonidos
app/entrada/               acciones con nombre, teclado, mando y vibración
app/actividades/           actividades, juegos, exámenes, puntuación y recompensas (declarativo)
app/seguimiento/           fichas de alumnos, sesiones, informes, cuaderno de evaluación real
app/supervision/           protocolo y conexión entre Estudio y Jugar
app/reproductor/           aplicación pygame: pantallas, menús hablados, tutorial, modo recorrido
app/ui/                    Estudio en wxPython
app/importar/              OpenStreetMap, DXF, SVG
app/exportar/              texto, SVG, GeoJSON
data/plugins/              complementos de objetos (se distribuyen)
data/sounds/               paquetes de sonidos (por_defecto, natural...) y catalogo.json (se distribuyen)
data/ejemplos/             entornos de ejemplo (se distribuyen)
data/locales/              traducciones (se distribuyen)
data/docs/                 manual, teclas, novedades (se distribuyen)
data/bin/                  bibliotecas nativas: OpenAL Soft y perfiles HRTF (se distribuyen)
data/entornos/             entornos del profesional (no se distribuyen)
data/db/, data/sessions/, data/config/, data/logs/   datos generados (no se distribuyen)
docs/                      documentación de desarrollo
tools/                     herramientas de desarrollo
tests/                     pruebas
```

## Modelo del entorno (`app/dominio/modelo.py`)

Dataclasses con `a_dict()` y `de_dict()`; `de_dict` tolera claves desconocidas y claves que faltan (valor de serie). Todos los elementos tienen `id` (cadena estable, única en el entorno), `nombre` y `descripcion`.

### Entorno

```
Entorno:
  formato: int = 1
  id, nombre, descripcion: str
  autor: str
  procedencia: dict          fuente, fecha, escala, licencia, notas
  georef: dict | None        {"lat0":..., "lon0":...} si viene de un mapa real
  inicio: Posicion           punto y rumbo de inicio por defecto
  plantas: list[Planta]
  conectores: list[Conector]
  complementos: list[str]    ids de complementos usados
```

`Posicion`: `planta: str`, `x: float`, `y: float`, `rumbo: float`.

### Planta

```
Planta:
  id, nombre: str
  nivel: int
  altura_m: float
  exterior: bool             True en plantas de calle
  espacios: list[Espacio]
  paredes: list[Pared]       tabiques, vallas y muros sueltos
  aberturas: list[Abertura]
  objetos: list[Objeto]
  fuentes: list[FuenteSonido]
  zonas: list[ZonaSuelo]
  referencias: list[Referencia]
  vias: list[Via]            solo exterior
```

### Espacio

Zona transitable con nombre: habitación, pasillo, acera, calzada, plaza…

```
Espacio:
  id, nombre, descripcion: str
  tipo: str      habitacion | pasillo | vestibulo | escalera | cabina | exterior |
                 acera | calzada | paso_peatones | plaza | parque | sendero | edificio
  contorno: list[(x, y)]     polígono simple, en sentido antihorario
  cerrado: bool              True: el contorno son paredes (interiores). False: es solo una zona (exteriores)
  lados_abiertos: list[int]  índices de lados del contorno sin pared cuando cerrado es True
  suelo: str                 material: ver lista de suelos
  acustica: str              preset de eco: ver lista
  pared_material: str
  macizo: bool               True: no se puede entrar (un edificio visto desde la calle)
  datos: dict                atributos propios del tipo (un paso de peatones: semaforo, sonoro, pulsador, isleta, ciclo...)
```

Suelos: `baldosa, madera, moqueta, alfombra, hormigon, asfalto, acera, adoquin, tierra, hierba, grava, metal, arena, agua, tactil_botones, tactil_rayas`.

Acústicas: `seca, habitacion, sala_grande, pasillo, bano, escalera, nave, exterior, calle, parque`.

### Pared, Abertura

```
Pared:
  id, nombre: str
  a, b: (x, y)
  grosor: float = 0.1
  material: str = "ladrillo"
  bloquea_paso: bool = True
  bloquea_sonido: bool = True      False en una valla o un cristal
  altura: float = 2.5

Abertura:
  id, nombre, descripcion: str
  tipo: str            puerta | hueco | ventana | portal
  a, b: (x, y)         tramo que ocupa sobre la pared
  estado: str          abierta | cerrada | con_llave
  hoja: str            batiente | corredera | automatica | ninguna
  material: str
  es_salida: bool      cuenta como salida del edificio en juegos y exámenes
```

Una abertura abierta, un hueco o un portal quitan pared en su tramo. Una puerta cerrada bloquea hasta que el alumno la abre. Una ventana no deja pasar a la persona pero sí parte del sonido.

### Conector

Une plantas.

```
Conector:
  id, nombre, descripcion: str
  tipo: str            escalera | rampa | ascensor | escalera_mecanica
  tramos: list[Tramo]  escalera, rampa, escalera mecánica
  paradas: list[Parada]  ascensor
  datos: dict          pasamanos ("izquierda", "derecha", "ambos", "ninguno"), anchura, aviso de planta hablado...

Tramo:
  desde: Posicion      boca inferior y rumbo de subida
  hasta: Posicion      boca superior y rumbo al salir arriba
  longitud_m: float
  peldanos: int        0 en una rampa

Parada:
  planta: str
  puerta: Posicion     punto delante de la puerta, y rumbo mirando a la cabina
```

### Objeto

Un objeto colocado, tomado de un complemento.

```
Objeto:
  id, nombre, descripcion: str
  tipo: str            "<complemento>/<objeto>", o "caja" si falta el complemento
  x, y: float          centro
  rumbo: float
  ancho, fondo, alto: float   medidas reales en metros
  variante: str
  estado: str          estado actual (abierto, cerrado, encendido...)
  datos: dict          sobrescrituras de lo que define el catálogo
```

### Otros

```
FuenteSonido: id, nombre, x, y, sonido, volumen=1.0, radio=12.0, bucle=True, intervalo=0.0, altura=1.0
ZonaSuelo:    id, nombre, contorno, suelo
Referencia:   id, nombre, descripcion, x, y, tipo, permanente=True
Via:          id, nombre, eje: list[(x, y)], ancho, carriles, sentido ("doble", "ida", "vuelta"), trafico (0 a 3), velocidad_kmh
```

## Geometría (`app/dominio/geometria.py`)

Funciones puras: distancia punto a segmento, corte de segmentos, punto en polígono, área, centroide, proyección sobre segmento, recorte de un segmento por intervalos, rumbo y diferencia de rumbos, punto a distancia y rumbo, rayo contra segmentos, rectángulo girado a polígono, intersección de polígonos (para saber si un objeto cabe).

## Formato de fichero (`app/dominio/formato.py`)

Paquete `.elab`: un ZIP con

```
manifiesto.json       {"formato": 1, "aplicacion": "EntornoLab", "version": "...", "id": "...", "nombre": "..."}
entorno.json          el Entorno
actividades/<id>.json actividades (ver más abajo)
sonidos/<nombre>      sonidos propios (wav, ogg, flac)
imagenes/<nombre>     imágenes propias
```

API:

```
guardar_paquete(ruta, entorno, actividades=(), recursos=None) -> None      atómico, con copia .bak
cargar_paquete(ruta) -> Paquete      Paquete.entorno, Paquete.actividades, Paquete.recurso(nombre) -> bytes
migrar(datos: dict) -> dict          convierte formatos antiguos
class ErrorFormato(Exception)
```

Al cargar se validan nombres (sin rutas absolutas ni `..`), tamaños máximos y tipos de fichero.

## Validación (`app/dominio/validacion.py`)

`validar(entorno, catalogo) -> list[Aviso]`, con `Aviso(gravedad: "error" | "aviso", codigo, mensaje, elemento_id, planta_id, sugerencia)`.

## Catálogo de complementos (`app/dominio/catalogo.py`)

Un complemento es una carpeta `data/plugins/<id>/` (o un ZIP `.elabc` que se instala allí) con `complemento.json` y, opcionalmente, `sonidos/` e `imagenes/`. Solo datos.

```
complemento.json:
  formato: 1
  id, nombre, version, autor, licencia, descripcion
  objetos: [
    {
      id, nombre, categoria, etiquetas: [..], descripcion
      ambito: ["interior", "exterior"]
      forma: {"tipo": "rectangulo" | "circulo" | "ele" | "poligono", "puntos": [[0..1, 0..1], ...]}
      medidas: {"ancho": [min, defecto, max], "fondo": [min, defecto, max], "alto": [min, defecto, max]}
      variantes: [{"id", "nombre", "ancho", "fondo", "alto"}]
      colocacion: ["suelo", "pared", "esquina", "acera", "calzada"]
      bloquea: true                 corta el paso
      altura_base: 0.0              mayor que 0: objeto colgante o en voladizo
      detectable_baston: true
      material: "madera"
      sonidos: {"golpe": "...", "uso": "...", "propio": {"sonido": "...", "volumen": 0.6, "radio": 8}}
      estados: ["cerrado", "abierto"]
      acciones: [{"id": "abrir", "nombre": "Abrir", "de": "cerrado", "a": "abierto", "sonido": "..."}]
      contenedor: true              puede esconder un premio dentro
      dinamica: {...}               comportamiento declarado (un semáforo: fases y tiempos)
      paso_libre: ["abierto"]       estados en los que deja pasar aunque bloquee (torno, puerta)
      suelo: "alfombra"             suelo que se pisa encima de un objeto que no bloquea
      aviso: "..."                  frase que se dice al pisarlo o al llegar a él
      simbolo: {"letra": "M", "color": "#8B5A2B"}
      imagen: {"fichero": "imagenes/x.png", "descripcion": "..."}
    }
  ]
```

API:

```
class Catalogo:
  cargar(carpetas) -> Catalogo
  complementos() -> list[Complemento]
  objeto(tipo) -> DefObjeto | None
  buscar(texto="", categoria=None, ambito=None) -> list[DefObjeto]
  crear_objeto(tipo, x, y, rumbo, variante=None) -> Objeto        con medidas por defecto
  ajustar_a_hueco(defn, ancho_libre, fondo_libre) -> (ancho, fondo) | None   elige variante o escala dentro del rango; None si no cabe
  huella(objeto) -> list[(x, y)]           polígono real en el mundo
instalar_complemento(ruta_zip) -> str
validar_complemento(carpeta) -> list[Aviso]
```

`colocar(entorno, planta, objeto, catalogo) -> list[Aviso]` comprueba que cabe en su espacio, que no se solapa, que no tapa una abertura y que deja el paso mínimo.

## Motor (`app/motor/`)

### Eventos (`eventos.py`)

El motor no suena ni habla: devuelve eventos.

```
EvSonido(nombre, pos=None, volumen=1.0, tono=1.0, bus="efectos", filtro=0.0, relativo=None)
    pos: (x, y, z) en el mundo; None = sin posición (interfaz)
    relativo: (angulo_grados, distancia) respecto al oyente, alternativa a pos
EvVoz(texto, interrumpir=False, canal="juego")       canales: juego, ayuda, aviso, profesional
EvVibrar(grave, agudo, ms)                           0 a 1
EvAcustica(preset)
EvRegistro(tipo, datos)                              para el seguimiento: choque, ayuda, objetivo, premio, entrada_espacio...
EvFin(resultado: dict)
```

### Sesión (`sesion.py`)

```
class Sesion:
  __init__(entorno, catalogo, ajustes: AjustesJuego, actividad=None, semilla=None, inicio: Posicion | None = None)
  orden(accion: str, valor: float = 1.0) -> None     acciones de app/entrada/acciones.py
  analogico(avance: float, lateral: float, giro: float, mirada: tuple[float, float] | None) -> None
  avanzar(dt: float) -> list[Evento]
  oyente() -> (x, y, z, rumbo)
  fuentes() -> list[FuenteActiva]      fuentes continuas audibles ahora
  estado() -> dict                     planta, x, y, rumbo, espacio, descripcion, tiempo_activo, pausado...
  pausar(si: bool)
  recolocar(pos: Posicion)
  terminado: bool
```

`FuenteActiva(id, sonido, pos, volumen, tono, filtro, bucle)`: el motor ya ha calculado oclusión y camino por puertas; la capa de sonido solo aplica.

`AjustesJuego`: `modo_movimiento` (pasos, continuo, brujula, salas), `paso_m`, `giro_grados`, `velocidad_ms`, `formato_direccion` (reloj, lados, cardinal, grados), `unidad` (metros, pasos), `detalle` (0 a 3), `ayudas` (diccionario ayuda → permitida y límite), `estilo` (infantil, juvenil, adulto).

### Otros módulos del motor

- `mundo.py`: índice del entorno para consultas rápidas: segmentos sólidos por planta, espacio en un punto, suelo en un punto, objetos cercanos, línea de visión.
- `movimiento.py`: pasos, giro, deslizamiento por paredes, puertas, escaleras (avance por peldaños con tono ascendente), rampas, ascensor (llamar, entrar, elegir planta, viajar, salir).
- `percepcion.py`: dónde estoy, qué hay delante, alrededor por cuadrantes, mirar en una dirección, sonda (bastón sonoro), lista de cercanos, descubiertos, brújula, eco.
- `acustica.py`: fuentes audibles, oclusión por paredes, sonido que llega por la puerta, preset de eco del espacio.
- `navegacion.py`: grafo de espacios y aberturas entre plantas, ruta más corta (A*), distancia de camino, salida más cercana.
- `lenguaje.py`: frases de orientación (reloj, lados, cardinales, metros o pasos, giros).
- `dinamica.py`: semáforos con fases, tráfico por las vías, puertas automáticas.

## Sonido (`app/audio/`)

```
class MotorAudio (interfaz, app/audio/base.py):
  nombre: str
  iniciar(dispositivo: str | None, opciones: dict) -> None
  cerrar() -> None
  dispositivos() -> list[str]
  cargar(nombre: str, ruta: Path | None = None, datos=None, frecuencia=44100) -> None
  oyente(x, y, z, rumbo) -> None
  reproducir(nombre, *, pos=None, relativo=None, volumen=1.0, tono=1.0, bus="efectos",
             bucle=False, filtro=0.0, eco=True) -> int
  actualizar(canal, *, pos=None, volumen=None, tono=None, filtro=None) -> None
  parar(canal, fundido=0.0) -> None
  parar_todo(bus=None) -> None
  suena(canal) -> bool
  acustica(preset: str) -> None
  volumen_bus(bus, valor) -> None        buses: maestro, efectos, pasos, ambiente, ayudas, interfaz, musica, voz
  atenuar_por_voz(segundos) -> None      baja ambiente y música mientras habla la voz
  pausar(si: bool) -> None
  tic(dt) -> None
```

Posiciones siempre en coordenadas del mundo; cada motor las convierte.

Motores, todos con la misma interfaz y elegibles en preferencias:

- `openal`: OpenAL Soft por ctypes. Binaural HRTF con perfiles de cabeza elegibles, reverberación EFX por preset, filtro paso bajo por fuente (oclusión y «detrás»), cambio de dispositivo en caliente.
- `clasico`: mezcla propia con numpy y salida por sounddevice. Paneo, diferencia de tiempo entre oídos, filtro para detrás. Admite segunda salida (para que el profesional oiga lo mismo).
- `estereo`: pygame.mixer, paneo simple. Para equipos modestos y altavoces.
- `bass`: BASS en 3D a través de `basskit`, que viene incluido (rueda de `__pip__`, con `bass.dll`). Panorama y distancia de BASS, sin HRTF; filtro con su ecualizador; cambio de salida en caliente. No está en la cadena de reserva. BASS es gratuita solo para uso no comercial: ver «Licencias» en [sonido.md](sonido.md).
- `nulo`: no suena; apunta las llamadas. Para pruebas.

`crear_motor(config) -> MotorAudio` elige el configurado y cae al siguiente si falla: openal → clasico → estereo → nulo.

Además:

- `cabeza.py`: seguimiento de cabeza por OpenTrack (UDP). El giro de la cabeza se suma al rumbo del oyente.
- `proteccion.py`: techo de volumen por fuente y de mezcla, subidas graduales.
- `sintesis.py` y `tools/sintetizar_sonidos.py`: generan el paquete de sonidos por defecto, `data/sounds/por_defecto` (pasos por suelo, golpes por material, puertas, escalera, ascensor, balizas, tonos de sonda, premios, interfaz, semáforo, tráfico, ambientes).
- `banco.py`: resuelve un nombre de sonido: paquete del entorno → complemento → paquete de sonidos elegido (`data/sounds/<paquete>`) → paquete por defecto; si no existe, un sonido sintetizado de reserva. `paquetes.py` lista y elige el paquete de sonidos en caliente, y `niveles.py` iguala su sonoridad.
- `voz.py`: `Voz.decir(texto, interrumpir=False, canal="juego")`, `callar()`, `repetir()`, historial con `anterior()` y `siguiente()`, braille. Salidas: lector de pantalla activo (accessible_output2) o SAPI. `VozFalsa` para pruebas (acumula en `registro`).
- `presentador.py`: `Presentador(motor, voz, haptica).aplicar(eventos, sesion)` traduce los eventos del motor a sonido, voz y vibración, y sincroniza las fuentes continuas.

## Entrada (`app/entrada/`)

`acciones.py` define las acciones con nombre, su texto y su ayuda:

```
avanzar retroceder girar_izquierda girar_derecha paso_izquierda paso_derecha media_vuelta
interactuar donde_estoy mirar_delante mirar_izquierda mirar_detras mirar_derecha alrededor
cercano_siguiente cercano_anterior descubiertos brujula sonda eco objetivo pista
repetir historial_anterior historial_siguiente callar volver_inicio ayuda pausa
menu_arriba menu_abajo menu_izquierda menu_derecha menu_aceptar menu_atras
```

- `teclado.py`: mapa tecla → acción por contexto (juego, menú), reasignable, guardado en configuración.
- `mando.py`: mandos por la interfaz normalizada de SDL (`pygame._sdl2.controller`), familia Xbox o PlayStation con nombres de botón correctos, zona muerta, ejes normalizados a ±1, conexión en caliente, reasignación y `vibrar(grave, agudo, ms)`.
- `entrada.py`: `Entrada.traducir(evento_pygame) -> list[(accion, pulsada)]` y `Entrada.ejes() -> (avance, lateral, giro, mirada)`.

## Actividades (`app/actividades/`)

Una actividad es un JSON declarativo dentro del paquete:

```
{
  "formato": 1, "id", "nombre", "descripcion",
  "tipo": "exploracion" | "busqueda" | "recadero" | "sacar_tesoros" | "escondite" | "sigue_guia" |
          "explorador" | "pistas" | "ruta" | "ruta_inversa" | "volver_origen" | "ruta_alternativa" |
          "localizar" | "perimetro" | "linea_guia" | "cruce" | "visita_guiada" |
          "examen_rutas" | "examen_salida" | "examen_senalar" | "examen_distancias" | "examen_reconstruccion",
  "modo": "juego" | "practica" | "examen",
  "estilo": "infantil" | "juvenil" | "adulto" | "del_alumno",
  "inicio": Posicion | null,
  "premios": [{"id", "nombre", "planta", "x", "y", "sonido", "visibilidad": "lejos" | "cerca" | "oculto",
               "dentro_de": id de objeto | null, "mensaje": "...", "audio": "sonidos/..." | null}],
  "objetivos": [{"id", "tipo": "ir_a" | "recoger" | "entregar" | "salir" | "senalar" | ..., "destino": ..., "texto": "..."}],
  "orden_obligatorio": false,
  "ayudas": {"donde_estoy": {"permitida": true, "limite": null}, "baliza": {...}, "sonda": {...}, ...},
  "niveles": [...],            retirada progresiva de ayudas
  "tiempo_limite_s": null,
  "regla_parada": {"de": 5, "minimo": 3} | null,
  "travieso": {"activo": false, ...},
  "mensajes": {"inicio": "...", "logro": "...", "final": "..."},
  "recompensas": {...}
}
```

El formato completo, con un ejemplo JSON de cada tipo, la API (`TIPOS`, `campos_de`, `nueva_actividad`, `validar_actividad`, `crear_actividad`, `repartir_premios`, `describir_actividad`), el resultado y cómo se puntúa cada examen están en [actividades.md](actividades.md).

`crear_actividad(datos, entorno, catalogo, estilo=None, semilla=None, nivel=None) -> Actividad`. La `Sesion` llama a los ganchos de la actividad (`al_empezar`, `tras_mover`, `al_interactuar`, `tic`, `al_pedir`, `al_registrar`, `resultado`), que devuelven eventos. `puntuacion.py` calcula estrellas, puntos de salida (3, 2, 1, 0), error angular al señalar y cociente camino real / camino óptimo.

## Seguimiento (`app/seguimiento/`)

- Base SQLite en `data/db/entornolab.db`: alumnos (alias, datos opcionales cifrados, perfil, estilo, ajustes), sesiones (alumno, entorno, actividad, fechas, resumen, traza comprimida), evaluaciones reales, recompensas.
- El reproductor escribe cada sesión en `data/sessions/<id>.json.gz`; el Estudio las incorpora a la base.
- Traza: muestras `(t, planta, x, y, rumbo)` cuatro veces por segundo, más los `EvRegistro`.
- `informes.py`: informe de sesión, comparación de sesiones y evolución, en texto, HTML y CSV.

## Supervisión (`app/supervision/`)

El Estudio abre una «sala» (servidor TCP, puerto 47900 por defecto); los reproductores se conectan como clientes con un código de emparejamiento. En el mismo ordenador, el Estudio lanza el reproductor ya conectado a `127.0.0.1`.

Mensajes: una línea JSON por mensaje, `{"v": 1, "tipo": ..., "seq": n, "t": segundos, "datos": {...}}`.

- Jugar → Estudio: `hola`, `estado` (5 por segundo), `evento`, `voz` (lo que oye el alumno), `fin`, `latido`, `peticion` (modo recorrido: «colocar aquí»).
- Estudio → Jugar: `bienvenida`, `pausa`, `reanudar`, `recolocar`, `mensaje`, `pista`, `ayudas`, `premio`, `reiniciar`, `terminar`, `latido`.

## Red, actualizaciones y catálogo en línea

La aplicación funciona sin conexión. Solo hay tres motivos para conectarse, siempre por acción explícita o con un permiso dado una vez, y nunca se envían datos de alumnos, entornos ni identificadores del equipo: buscar y descargar actualizaciones, el catálogo en línea de complementos e importar de OpenStreetMap.

- `app/core/red.py`: única puerta a Internet. `abrir(url)`, `leer_bytes(url, maximo)`, `leer_json(url, maximo)`, `comprobar_url(url)` (solo https), `clasificar_error(error)`, `ErrorRed`. Peticiones `GET` sin cuerpo ni galletas, `User-Agent` «EntornoLab/<versión>», certificados verificados siempre.
- `app/core/descargas.py`: `descargar(url, destino, sha256=None, tamano=None, ...) -> ResultadoDescarga`, reanudable, verificada, cancelable y atómica.
- `app/services/actualizador.py` (sin wx): `comprobar(config) -> InfoActualizacion | None`, `descargar_y_preparar(config, info, progreso, cancelacion) -> Path`, `lanzar_sustitucion(ruta_bat)`, `confirmar_arranque(config)`, `leer_resultado_anterior(config)`, `reproductores_abiertos(config)`. Lee `version.json` firmado (Ed25519) de las publicaciones de GitHub. Detalles en [actualizaciones.md](actualizaciones.md).
- `app/services/complementos_en_linea.py` (sin wx): `descargar_catalogo() -> Indice`, `comparar(indice) -> list[EstadoComplemento]`, `instalar(complemento, instalador=None, validador=None, ...)`, `instalar_varios(...)`, `desinstalar(id)`, `volver_a_anterior(id)`, `revisar_paquete(ruta_zip)`. Detalles en [catalogo-de-complementos.md](catalogo-de-complementos.md).
- `app/ui/dialogo_actualizacion.py`: `mostrar_dialogo_actualizacion(padre)` (menú Ayuda) y `al_arrancar(ventana)` (tras mostrar la ventana principal). `app/ui/dialogo_complementos_en_linea.py`: `mostrar_complementos_en_linea(padre, al_cambiar=None)` (menú Herramientas).

Ficheros que dejan en `data/`: `config/actualizaciones.json` (versión más alta que arrancó bien), `config/complementos.json` (complementos instalados desde el catálogo), `plugins/de_serie.json` (viaja con la aplicación: complementos de serie), `backups/complementos/<id>/` (versión anterior de un complemento), `temp/actualizacion/` y `temp/version_anterior/` (trabajo y copia de seguridad de una actualización) y `logs/actualizacion.log`.

## Arranque

- `main.py` sin argumentos: Estudio.
- `main.py --jugar [paquete] [--actividad id] [--alumno alias] [--sala host:puerto --codigo c] [--inicio planta,x,y,rumbo]`: reproductor.
- `main.py --recorrido paquete --sala host:puerto --codigo c`: modo recorrido.
- `jugar.py`: equivale a `main.py --jugar`; es el segundo ejecutable (EntornoLabJugar.exe).

El reproductor sale antes de la comprobación de instancia única del Estudio.

## Traducción

`app/core/i18n.py` expone `_`, `_n`, `N_`, `idioma_actual()`, `idiomas_disponibles()` y `cambiar_idioma()`. Catálogos gettext en `data/locales/<idioma>/LC_MESSAGES/entornolab.po` (leídos sin compilar o compilados). Los textos de los complementos y de los entornos de ejemplo se traducen con ficheros `locales/<idioma>.json` dentro del propio complemento.
