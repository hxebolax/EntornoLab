# Importar y exportar entornos

Este documento describe los paquetes `app/importar` y `app/exportar`: qué se puede traer de fuera para empezar un entorno, cómo se interpreta, qué límites tiene y qué se puede sacar de un entorno ya hecho.

Dos ideas mandan sobre todo lo demás:

- **Lo importado es siempre un borrador.** El profesional lo revisa y lo completa. Cada importador devuelve el entorno y un **informe** en español con cuatro apartados: lo importado, lo deducido por el programa, lo que la fuente no dice y lo que conviene revisar in situ.
- **Nada inventado.** Si el mapa no dice algo, se dice «el mapa no lo dice»; no se supone que no existe ni que sí.

Ningún módulo de estos paquetes importa `wx` ni `pygame`, ni usa nada que no sea la biblioteca estándar.

## Privacidad

- Las únicas conexiones a Internet son a **Nominatim** (buscar un lugar por su nombre) y a **Overpass** (descargar el mapa de un recuadro), y solo cuando el profesional pulsa importar.
- Lo único que se envía es el texto buscado o las cuatro coordenadas del recuadro. No se envía ningún dato del alumno, del profesional ni del equipo. La aplicación se identifica solo con su nombre y su versión (`EntornoLab/x.y.z`).
- Un plano interior (DXF, SVG o imagen) se lee del disco y **nunca sale del equipo**.

## Piezas comunes (`app/importar/comun.py`)

```
class ErrorImportacion(Exception)            el mensaje se puede leer tal cual a la persona
class ImportacionCancelada(ErrorImportacion)
Informe:    titulo, importado, deducido, falta, revisar, avisos, cuentas;  a_texto(), a_dict(), secciones()
ResultadoImportacion: entorno, informe
progreso(fraccion: float, texto: str) -> None      función inyectable; fracción de 0 a 1
cancelado() -> bool                                función inyectable; se consulta entre fases
analizar_xml_seguro(datos, max_bytes, max_elementos) -> Element
```

`analizar_xml_seguro` se usa para todo XML que viene de fuera (`.osm`, SVG, GPX): rechaza cualquier `DOCTYPE` o declaración de entidad antes de expandir nada, no resuelve referencias externas y limita tamaño, número de elementos y profundidad.

Todos los importadores dejan el punto de inicio en un sitio válido (dentro de un espacio, lejos de muros y objetos), para que el borrador se pueda recorrer nada más crearlo.

## OpenStreetMap (`app/importar/osm.py`)

Se importa un **recuadro pequeño**, de unas pocas calles, directamente a un entorno editable. No hace falta ninguna dependencia: Overpass responde en JSON y se lee con la biblioteca estándar.

### Uso

```python
from app.importar import osm

candidatos = osm.buscar_lugar("Calle Mayor 12, Soria")                 # Nominatim
datos = osm.descargar_zona(candidatos[0].lat, candidatos[0].lon, 150)   # Overpass
resultado = osm.convertir(datos, osm.OpcionesOSM(nombre="Calle Mayor"), progreso, cancelado)
resultado.entorno      # Entorno con una planta exterior
resultado.informe      # Informe; informe.a_texto() para enseñarlo

datos = osm.importar_fichero_osm("zona.osm")    # sin conexión: un .osm (XML) o un JSON de Overpass
```

| Función | Qué hace |
| --- | --- |
| `buscar_lugar(texto, limite=8, *, descargar=None, cancelado=None, usar_cache=True) -> list[Candidato]` | Busca un lugar en Nominatim. `Candidato`: `nombre`, `descripcion`, `lat`, `lon`, `tipo`, `recuadro`, `osm`. |
| `recuadro_de(lat, lon, radio_m) -> (sur, oeste, norte, este)` | Recuadro alrededor de un punto; falla con un mensaje claro si el radio pasa del máximo. |
| `descargar_zona(lat, lon, radio_m=150, **opciones) -> dict` | Descarga la zona alrededor de un punto. El punto será el (0, 0) del entorno. |
| `descargar_recuadro(sur, oeste, norte, este, *, servidores=None, descargar=None, usar_cache=True, progreso=None, cancelado=None) -> dict` | Lo mismo por recuadro. |
| `importar_fichero_osm(ruta) -> dict` | Lee un `.osm` o un JSON de Overpass ya descargado. |
| `convertir(datos_osm, opciones=None, progreso=None, cancelado=None) -> ResultadoImportacion` | Convierte los datos en un entorno. |
| `consulta_overpass(recuadro) -> str` | La consulta Overpass QL que se envía (para revisarla o usarla a mano). |

`descargar` es una función inyectable `descargar(url, datos=None) -> bytes` (`datos` son los parámetros ya codificados como formulario). Por defecto usa `app.core.red` (HTTPS con verificación de certificado y reintentos). Las pruebas la sustituyen por una falsa; nunca salen a la red.

### Límites

| Límite | Valor | Motivo |
| --- | --- | --- |
| Radio máximo de la zona | 400 m (`RADIO_MAXIMO_M`) | Más allá el borrador no se puede revisar ni recorrer. Si se pide más, el mensaje lo explica y propone importar por partes. |
| Radio mínimo | 20 m | |
| Lado máximo que se convierte | 1000 m | Para ficheros `.osm` grandes: indicar `centro` y `radio_m` en las opciones para importar un trozo. |
| Respuesta de Overpass | 32 MB | |
| Fichero `.osm` | 64 MB y 600 000 elementos | |
| Tiempo de la consulta | 60 s en el servidor | |

### Opciones (`OpcionesOSM`)

| Opción | Por defecto | Efecto |
| --- | --- | --- |
| `nombre`, `descripcion`, `autor` | | Datos del entorno. |
| `centro` | centro del recuadro | (latitud, longitud) del punto (0, 0). |
| `radio_m` | sin recorte | Recorta a ese radio alrededor del centro. |
| `aceras` | sí | Crear aceras. |
| `deducir_aceras` | sí | Deducir aceras donde el mapa solo da el eje. |
| `ancho_acera` | 2,0 m | Anchura de una acera cuando no hay fachada que la limite. |
| `edificios`, `lugares`, `obstaculos` | sí | Importar esas clases de elementos. |
| `vias_de_servicio` | sí | Importar `highway=service`. |
| `terreno_base` | sí | Poner debajo de todo un «Terreno sin detallar» para que la zona se pueda recorrer entera. |
| `interiores` | no | Importar interiores con Simple Indoor Tagging como plantas. |
| `catalogo` | ninguno | Catálogo de complementos: con él los obstáculos usan los objetos del complemento `calle`. |

### Cómo se interpreta cada etiqueta

Todo va a una planta exterior de nivel 0 llamada «Calle». Las coordenadas son metros locales (x al este, y al norte) alrededor del centro.

| En OpenStreetMap | En EntornoLab | Notas |
| --- | --- | --- |
| `highway=motorway, trunk, primary, secondary, tertiary, unclassified, residential, living_street, service, road, busway` (y sus `_link`) | Una `Via` y un espacio `calzada` por calle | Las vías del mapa con el mismo nombre y las mismas etiquetas que se tocan por un extremo se unen en una sola calle. |
| `name` | Nombre de la vía, de su calzada y de sus aceras | Sin nombre: «Calle residencial sin nombre», y se anota. |
| `lanes` | `Via.carriles` | Si falta: 1 en sentido único, o los habituales del tipo; se anota como estimado. |
| `oneway=yes`, `-1`; `junction=roundabout` | `Via.sentido`: `ida`, `vuelta`; si no, `doble` | |
| `maxspeed` | `Via.velocidad_kmh` | Si falta: la habitual del tipo de vía, y se dice. |
| tipo de vía | `Via.trafico` (0 a 3) | **Siempre estimado**: primaria 3, secundaria y terciaria 2, residencial 1; 0 si `access` o `motor_vehicle` es `no` o `private`. |
| `width`, `est_width` | `Via.ancho` | Si falta: carriles × 3,2 m, o el habitual del tipo; se estrecha si las fachadas no dejan sitio. |
| `surface` | `suelo` del espacio | Ver la tabla de superficies. |
| `sidewalk=both, left, right, no, separate`; `sidewalk:left`, `sidewalk:right` | Espacios `acera` a cada lado, con `datos.origen = "mapa"` | Ver «Aceras». |
| `highway=footway` + `footway=sidewalk` | Espacio `acera` con `datos.origen = "mapa"` | Toma el nombre de la calle más cercana. |
| nodo donde se juntan tres ramas o más | Espacio `calzada` con `datos.cruce = true` y `datos.forma` | Formas: `t`, `y`, `cruz`, `aspa`, `desalineado`, `complejo`. La descripción dice qué calle sale hacia cada punto cardinal. |
| `junction=roundabout` (vía cerrada) | Espacio `calzada` «Rotonda de …» con `datos.forma = "rotonda"` | Se importa el círculo entero; la isleta central no. |
| `highway=crossing`, o `crossing=*` en un nodo de la calzada; vía `footway=crossing` | Espacio `paso_peatones` con su ficha | Ver «Pasos de peatones». |
| `building=*` (vía cerrada o multipolígono) | Espacio `edificio` macizo | Los patios interiores no se recortan. `building=roof`, `carport`, `canopy` o `building:walls=no`: zona cubierta no maciza. Los subterráneos no se importan. |
| `entrance=*` o `addr:housenumber` en un nodo del contorno de un edificio | `Abertura` de tipo `portal` sobre esa fachada | Nombre «Portal número N de …». Si no cabe, queda como referencia de tipo `portal`. |
| `building:levels`, `addr:street` | Descripción del edificio | |
| `place=square`; `highway=pedestrian` o `footway` con `area=yes` | Espacio `plaza` | |
| `leisure=park, garden, playground, dog_park`; `landuse=grass, village_green, flowerbed, meadow, forest`; `natural=wood, scrub` | Espacio `parque` | |
| `natural=water`; `amenity=fountain` (área); `leisure=swimming_pool` | Espacio `exterior` con suelo `agua` | No se crea ninguna fuente de sonido. |
| `amenity=parking`; `leisure=pitch`; andenes (`public_transport=platform`, `railway=platform`) como área | Espacio `exterior` | |
| `highway=footway, path, track, bridleway, cycleway` | Espacio `sendero` | `cycleway`: `datos.bicis = true`. |
| `highway=pedestrian` (línea) | Espacio `plaza` «Calle peatonal» | |
| `highway=steps` | Espacio `escalera` (zona, no conector) con `datos.peldanos`, `pasamanos`, `sube_hacia` | `step_count`, `handrail`, `handrail:left/right`, `incline`. Lo que falta: «el mapa no lo dice». |
| `ramp=yes`, `ramp:wheelchair=yes`, `incline` con pendiente | Espacio `sendero` «Rampa» con `datos.rampa = true` y `pendiente_pct` | |
| `highway=bus_stop`; `public_transport=platform, station`; `railway=tram_stop, station, halt, subway_entrance`; `amenity=taxi, bus_station` | `Referencia` de tipo `parada` | Descripción con `ref`, `route_ref`, `shelter`, `bench`, `tactile_paving`, cada uno con sus tres estados. |
| `amenity`, `shop`, `tourism`, `leisure`, `healthcare`, `office`, `craft`, `historic`, `emergency` con nombre | `Referencia` de tipo `comercio` o `punto`, con su tipo en español | Sin nombre solo las que sirven por sí mismas (farmacia, cajero, aseos, fuente…). |
| `barrier=wall, city_wall, retaining_wall, fence, railing, handrail, guard_rail, hedge, jersey_barrier, chain` (línea) | `Pared` suelta por cada tramo | Material y altura típicos; `height` si la da. Una valla no tapa el sonido. |
| `barrier=gate, lift_gate, swing_gate, wicket_gate, kissing_gate, turnstile, sliding_gate, entrance` en un nodo de una barrera | `Abertura` (`puerta` o `hueco`) sobre esa pared | `locked=yes`: con llave. |
| `barrier=bollard, block, planter, cycle_barrier, stile, log, debris`; `highway=street_lamp`; `man_made=utility_pole, flagpole, street_cabinet`; `power=pole`; `natural=tree`; `amenity=bench, waste_basket, post_box, telephone, vending_machine, recycling, waste_disposal, bicycle_parking, parking_meter, drinking_water`; `advertising=column`; `emergency=fire_hydrant`; `tourism=information` | `Objeto` con medidas típicas | Con el complemento `calle` instalado y su catálogo en las opciones, usa su objeto (`calle/bolardo`, `calle/farola`, `calle/banco`…). Sin él, una caja con nombre que recuerda en `datos.tipo_previsto` qué objeto sería. Si no cabe en su punto (cae dentro de un edificio), queda como referencia. |
| `barrier=bollard` (línea) | Un bolardo en cada vértice | Se anota como deducido. |
| `indoor=room, corridor, area` + `level`; `door=*`; `highway=elevator` | Habitaciones, puertas y ascensor (solo con la opción `interiores`) | Ver «Interiores». |

No se importan: vías en proyecto u obras (`proposed`, `construction`, `abandoned`…), túneles y lo subterráneo, líneas de transporte, límites administrativos ni usos del suelo que no se pisan (`landuse=residential`…).

**Fuentes de sonido: nunca.** OpenStreetMap no describe sonidos, así que no se crea ninguna `FuenteSonido`, ni siquiera para una fuente de agua. El informe lo recuerda para que el profesional añada las que sirvan de referencia.

#### Superficies

| `surface` | Suelo |
| --- | --- |
| `asphalt`, `chipseal` | `asfalto` |
| `concrete`, `concrete:lanes`, `paved` | `hormigon` |
| `paving_stones`, `concrete:plates`, `tiles`, `marble`, `brick` | `baldosa` |
| `sett`, `cobblestone`, `unhewn_cobblestone`, `stone`, `rock` | `adoquin` |
| `gravel`, `fine_gravel`, `pebblestone` | `grava` |
| `ground`, `dirt`, `earth`, `compacted`, `unpaved`, `clay`, `mud` | `tierra` |
| `sand` | `arena` |
| `grass`, `grass_paver`, `artificial_turf` | `hierba` |
| `wood` | `madera` |
| `metal`, `metal_grid` | `metal` |
| `rubber`, `tartan`, `carpet` | `moqueta` |

Si falta `surface` se pone el suelo habitual del tipo de espacio y la descripción lo dice.

### Aceras

OpenStreetMap suele dar solo el eje de la calle. Las aceras se materializan como espacios editables así, por cada lado:

1. Si el mapa dice que la hay (`sidewalk=both`, `left`, `right`, `sidewalk:left=yes`…): se crea, con `datos.origen = "mapa"`.
2. Si dice que no (`no`, `none`): no se crea, y el informe lo apunta.
3. Si dice `separate`, o hay cerca una vía `footway=sidewalk`: no se calcula; se usa la acera dibujada.
4. Si no dice nada: se **deduce** en calles principales, de barrio y residenciales (no en vías de servicio ni en caminos sin nombre), con `datos.origen = "deducida"`. El informe lista las calles con aceras deducidas y la descripción de cada una pide comprobarla in situ.

Anchura: la de `sidewalk:width` (o `sidewalk:left:width`…) si existe. Si no, se mide la distancia del eje a la línea de fachadas: hasta 4 metros la acera llega a la fachada; con más sitio, o sin fachadas, se usa `ancho_acera`; con menos de 60 centímetros no se crea y se avisa. Si las fachadas no dejan sitio para la calzada estimada, la calzada se estrecha.

En cada bocacalle la acera se corta del lado por el que sale la otra calle; cada tramo es un espacio aparte («Acera norte de Calle Mayor, tramo 2»). `datos` de una acera: `via`, `lado` (`izquierda` o `derecha` según el sentido del eje), `ancho`, `tramo`, `origen`, `ancho_segun_mapa`.

### Pasos de peatones: «no tiene» no es «el mapa no lo dice»

Cada paso guarda cada atributo dos veces:

- `datos["segun_mapa"]`: un diccionario con **tres estados** por atributo, `"si"`, `"no"` o `"desconocido"`. Claves: `semaforo`, `sonoro`, `vibracion`, `pulsador`, `isleta`, `tactil`, `bordillo`.
- Los valores verdadero o falso de siempre (`semaforo`, `sonoro`, `pulsador`, `isleta`, y además `vibracion` y `tactil`), que son los que usa el motor. Un «desconocido» se guarda ahí como falso, porque el motor no puede simular lo que no se sabe.

| Etiqueta | Atributo |
| --- | --- |
| `crossing=traffic_signals`, `crossing:signals=yes` | `semaforo`: sí |
| `crossing=uncontrolled, unmarked, marked, zebra`, `crossing:signals=no` | `semaforo`: no (y con él `sonoro`, `vibracion` y `pulsador`: no) |
| `traffic_signals:sound=yes, walk, locate` / `no` | `sonoro` |
| `traffic_signals:vibration=yes` / `no` | `vibracion` |
| `button_operated=yes` / `no` | `pulsador` |
| `crossing:island=yes` / `no` (o `traffic_island`) | `isleta` |
| `tactile_paving=yes, contrasted, partial, incorrect` / `no` | `tactil` |
| `kerb=lowered, flush, raised, rolled, no` | `datos.bordillo` |
| `crossing:markings` | `datos.marcas` |

La descripción del paso es su ficha en frases («Con semáforo. Con señal sonora. … Bordillo: el mapa no lo dice.»). La genera `app.exportar.fichas.ficha_paso`, que también usa la exportación en texto. El informe lista, paso por paso, lo que el mapa no dice.

Solo se crean bandas de pavimento táctil cuando el mapa dice que las hay. En un paso con semáforo, los tiempos (`datos.ciclo`) son los de serie del programa y van marcados con `datos.ciclo_estimado = true`.

### Interiores (Simple Indoor Tagging)

Con `OpcionesOSM(interiores=True)`, las áreas con `indoor=room`, `corridor` o `area` se importan como habitaciones, pasillos y vestíbulos:

- Las de `level=0` van en la propia planta de calle; el edificio que las contiene deja de ser un bloque macizo.
- Las de otros niveles van cada una en su planta, que se crea si hace falta (`level=1;2` o `0-2` repiten la sala en cada planta).
- Los nodos con `door=*` o `entrance=*` en el contorno de una sala abren la puerta en esa pared (`door=no`: hueco; `entrance`: portal y salida).
- `highway=elevator` con varias plantas en `level` pasa a ser un ascensor si cae dentro de una sala en cada planta; si no, queda como referencia.
- Las escaleras interiores no se conectan solas: el informe pide conectarlas a mano.

### Georreferencia y procedencia

```json
"georef": {"lat0": 40.0, "lon0": -3.7, "proyeccion": "local_plana", "recuadro": [sur, oeste, norte, este]},
"procedencia": {
	"fuente": "OpenStreetMap",
	"fecha": "2026-11-26",
	"fecha_datos": "2026-11-01T00:00:00Z",
	"escala": "1:1",
	"licencia": "ODbL 1.0",
	"atribucion": "© colaboradores de OpenStreetMap",
	"url_licencia": "https://www.openstreetmap.org/copyright",
	"recuadro": [sur, oeste, norte, este],
	"servidor": "overpass-api.de",
	"notas": "…"
}
```

`app.importar.georef.Proyeccion(lat0, lon0)` pasa de latitud y longitud a metros locales (`a_xy`) y al revés (`a_latlon`). Es una proyección plana local: en menos de un kilómetro el error es de centímetros.

Cada espacio importado guarda en `datos.osm` de qué elemento del mapa sale (`way/123`, `node/45`).

### Prueba con datos reales: Plaza Mayor de Valladolid

El 26 de noviembre de 2026 se hizo una importación real con el cliente de la aplicación (`User-Agent: EntornoLab/0.1.0`): **una** búsqueda en Nominatim («Plaza Mayor, Valladolid», primer resultado `way/24432960`, 41,6520609 N 4,7285484 O) y **una** descarga de Overpass de 150 m de radio alrededor de ese punto (recuadro de 300 × 300 m). Las respuestas se guardaron tal cual como muestra para las pruebas sin red:

| Fichero | Contenido |
| --- | --- |
| `tests/datos/osm_real_valladolid_nominatim.json` | Respuesta de Nominatim (2,3 kB, 5 resultados). |
| `tests/datos/osm_real_valladolid_overpass.json` | Respuesta de Overpass (369 kB, 2488 elementos, datos de 2026-11-26T16:43:51Z). |
| `tests/datos/osm_real_valladolid_ATRIBUCION.txt` | Atribución («© colaboradores de OpenStreetMap», ODbL), fecha, consultas exactas y radio. Quien reparta la muestra tiene que conservarlo. |

Resultado de la conversión: 16 calles (con sus nombres reales), 5 cruces, 7 pasos de peatones (5 con semáforo), 27 tramos de acera (19 del mapa, 4 dibujados aparte y los deducidos de 2 calles), 51 caminos y calles peatonales, 133 edificios con 156 portales, 3 escaleras, 48 obstáculos y 188 lugares. La validación no da errores; quedan 8 avisos razonables (contenedores y aparcabicicletas que sobresalen de su acera, un panel a 10 cm de una pared). El motor recorre el resultado: el alumno anda por la acera, llega por el camino del navegador a un paso, cruza (también esperando el verde del semáforo), y «dónde estoy» dice la calle real («Acera oeste de Calle de Quiñones»).

Lo que falló con datos reales y se corrigió en `osm_conversion.py` y `formas.py`:

- **Plaza duplicada.** La Plaza Mayor es una vía `highway=pedestrian` cerrada con `place=square` (sin `area=yes`). Salía como zona y además como franja peatonal de borde con el mismo nombre. Ahora una vía peatonal cerrada que ya es una zona no se convierte también en línea.
- **Medianeras que se pisan.** Los edificios pegados casi nunca comparten exactamente la medianera: salían 17 avisos «se pisan» por solapes de 0,01 a 0,09 m². `formas.ajustar_medianeras` lleva al borde del vecino cada vértice metido en él a menos de 0,5 m (si el contorno sigue siendo válido). Un solape mayor no se toca: sigue avisando.
- **Bordes de zonas de fuera.** De la Plaza de la Fuente Dorada, que queda fuera del recuadro, entraba una tira de 3,7 m² con su nombre. Una zona que entra menos de 10 m² y menos del 10 % de su superficie ya no se importa.
- **Paneles con el nombre de lo que explican.** Dos paneles `tourism=information` se llaman en el mapa «Iglesia de Santiago» e «Iglesia de la Pasión»: el alumno habría oído que tocaba una iglesia. Un obstáculo con nombre se llama ahora «Panel de información «Iglesia de Santiago»», salvo que el nombre ya diga la clase (`nombre_de_obstaculo`).
- **Rumbo de inicio.** En una acera, el inicio miraba al lado largo de su caja (este u oeste): con calles en diagonal, el alumno empezaba de cara a la calzada. Ahora mira a lo largo de su calle, en el sentido que deja más acera por delante.

La prueba es `tests/test_importar_osm_real.py`; las dos que recorren con el motor van marcadas `lento`.

## Política de uso de Nominatim y Overpass

Son servicios públicos y gratuitos que mantienen voluntarios. El código cumple sus condiciones:

**Nominatim** (<https://operations.osmfoundation.org/policies/nominatim/>):

- Una petición por segundo como máximo (`LimitadorRitmo`, compartido por toda la aplicación).
- Identificación de la aplicación en el `User-Agent`: `EntornoLab/versión`, sin datos personales.
- Resultados guardados en caché 30 días; la misma búsqueda no se repite.
- Solo búsquedas que lanza una persona: nada de autocompletar tecla a tecla ni de búsquedas en lote.

**Overpass** (<https://dev.overpass-api.de/overpass-doc/en/preface/commons.html>):

- Una sola consulta por importación, acotada a 60 segundos y a un recuadro pequeño.
- Caché en `data/cache/osm` durante 30 días: volver a importar la misma zona no vuelve a pedir nada.
- Si un servidor está ocupado se prueba el siguiente de la lista, una vez cada uno; no se insiste.

**Servidor propio.** Quien tenga su propia instancia puede indicarla en la configuración con las claves `importar.overpass_url` e `importar.nominatim_url`; se usa antes que los servidores públicos. Solo se admiten direcciones `https`.

La caché está en `data/cache/osm` y se puede borrar sin perder nada.

## Licencia ODbL y atribución obligatoria

Los datos de OpenStreetMap se publican con la licencia **Open Database License (ODbL) 1.0**. Un entorno importado es una obra derivada, y eso obliga a:

1. **Citar la fuente**: «© colaboradores de OpenStreetMap», con la licencia.
2. **Conservar esa atribución** en todo lo que se saque del entorno.

El programa lo hace solo. La atribución queda en `entorno.procedencia` y aparece en todo lo exportado:

| Exportación | Dónde aparece |
| --- | --- |
| Texto, Markdown y HTML | Apartado «Procedencia» y apartado final «Datos del mapa». |
| Plano SVG visual | Texto abajo a la derecha, y en la leyenda. |
| Plano SVG táctil | En la leyenda en texto y en BRF, y en el grupo `tinta` del SVG. |
| GeoJSON | Claves `attribution` y `license` del documento. |
| DXF | Comentario 999 al principio del fichero. |
| Indicaciones de ruta | Nota final. |

Quien reparta un entorno importado o algo exportado de él tiene que dejar esa atribución donde está. `app.importar.georef.texto_atribucion(procedencia)` devuelve la frase que hay que mostrar (o cadena vacía si el entorno no viene de un mapa).

## Planos DXF (`app/importar/dxf.py`)

Lector propio, sin dependencias, de DXF de texto. Entiende las entidades `LINE`, `LWPOLYLINE`, `POLYLINE` (con sus `VERTEX`), `CIRCLE`, `ARC`, `TEXT`, `MTEXT` e `INSERT` (bloques con posición, escala y giro, hasta cuatro niveles), cada una en su capa. Los tramos curvos de una polilínea («bulge») se convierten en tramos rectos cortos. Lo demás (`HATCH`, cotas, mallas 3D…) se cuenta y se dice en el informe.

```python
from app.importar import dxf
from app.importar.plano import OpcionesPlano

plano = dxf.leer_dxf("planta.dxf")
for capa in plano.capas():                 # CapaPlano: nombre, abiertos, cerrados, rotulos, arcos, sugerencia
	print(capa.descripcion())
escala, explicacion = plano.sugerir_escala()    # (metros por unidad | None, frase)
resultado = dxf.convertir_dxf(plano, OpcionesPlano(metros_por_unidad=0.001, capas_paredes=["MUROS"]))
```

`dxf.importar_dxf(ruta, opciones)` hace las dos cosas de una vez.

### Qué se convierte

| En el plano | En EntornoLab |
| --- | --- |
| Polilínea cerrada (o círculo) en una capa de espacios o de paredes | Espacio cerrado (habitación). |
| Contorno cerrado muy fino (menos de 45 cm de grosor) | Pared: es el cuerpo de un muro dibujado con doble línea. |
| Contorno cerrado que envuelve a varias salas | Perímetro del edificio: sus lados, como paredes. |
| Línea, polilínea abierta o arco en una capa de paredes | Paredes sueltas. Las que coinciden con el lado de un espacio no se repiten. |
| Texto dentro de un espacio | Nombre del espacio (el de letra más grande); los demás, a su descripción. Del nombre se deducen el tipo (`pasillo`, `vestibulo`, `escalera`, `cabina`) y el uso (`cocina`, `bano`, `aula`…). |
| Texto fuera de todo espacio | Referencia. |
| Arco de 45 a 135 grados y de 0,55 a 1,40 m de radio pegado a una pared | Puerta: el centro es la bisagra y el radio, el ancho de la hoja. Se anota como deducida. |

### Unidades, escala y origen

- **Escala**: `OpcionesPlano.metros_por_unidad` (1 unidad del plano = X metros). Si no se indica, se usa la que declara el fichero (`$INSUNITS`: milímetros, centímetros, metros, pulgadas…) y se anota para comprobarla. Si el fichero no dice nada y el dibujo mide varios miles de unidades, se suponen milímetros. Si no se puede saber, `convertir_dxf` lanza `ErrorImportacion` con las medidas del dibujo para que la interfaz **pregunte** («el dibujo mide 12 por 8 unidades: ¿cuántos metros es una unidad?»).
- **Origen**: `OpcionesPlano.origen` es el punto del dibujo (en sus unidades) que será el (0, 0). Por defecto, la esquina inferior izquierda.
- **Capas**: `capas_paredes`, `capas_espacios`, `capas_puertas` y `capas_textos`. A `None` se usan las sugerencias, que salen del nombre de la capa (`MUROS`, `A-WALL`, `PUERTAS`, `TEXTOS`, `MOBILIARIO`, `COTAS`…) y de su contenido.
- **Planta nueva en un entorno que ya existe**: `OpcionesPlano(entorno=…, nivel=1, nombre_planta="Primera")`.

### Cómo preparar un DXF

1. Guardarlo como **DXF de texto (ASCII)**, no binario. Cualquier versión sirve (R12 a 2018).
2. Dejar solo las capas del plano: muros, puertas y rótulos. Quitar o apagar cotas, sombreados, mobiliario e instalaciones (o no elegirlas al importar).
3. Mejor si cada sala es una **polilínea cerrada**: sale como un espacio con sus medidas. Si los muros son líneas sueltas, se importan como paredes y las salas se dibujan encima en el Estudio.
4. Escribir el nombre de cada sala con un texto **dentro** de ella.
5. Comprobar las unidades del dibujo; si no se sabe, medir una puerta: unas 0,8 unidades son metros; 80, centímetros; 800, milímetros.
6. El dibujo tiene que estar en el espacio modelo (lo del espacio papel se ignora) y en planta, sin 3D.

Límites: 60 MB, 300 000 entidades, 20 000 tramos de pared, 3000 espacios.

## Planos SVG (`app/importar/svg.py`)

Para un plano dibujado en un programa de dibujo vectorial (Inkscape u otro). Entiende `rect`, `polygon`, `polyline`, `line`, `circle`, `ellipse`, `text` y `path` con las órdenes `M`, `L`, `H`, `V` y `Z` (en mayúsculas o minúsculas). Las curvas de un `path` se sustituyen por la recta a su punto final y se avisa. Aplica los `transform` (`translate`, `scale`, `rotate`, `matrix`) de los grupos.

```python
from app.importar import svg
plano = svg.leer_svg("planta.svg")
resultado = svg.convertir_svg(plano, OpcionesPlano(metros_por_unidad=0.1))
resultado = svg.importar_svg("planta.svg", metros_por_unidad=0.1)
```

- **La escala es obligatoria**: un SVG no tiene unidades reales. Sin ella, `convertir_svg` lanza `ErrorImportacion` con las medidas del dibujo.
- **Capas**: la capa de cada figura es la del grupo que la contiene (el nombre de capa de Inkscape, o el `id` del grupo), o su `class`.
- La y de un SVG crece hacia abajo; al importar se invierte para que el norte quede arriba.
- La conversión es la misma que la del DXF (figuras cerradas → espacios, líneas → paredes, textos → nombres), salvo las puertas, que un SVG no tiene cómo indicar.

### Seguridad

Un SVG puede traer código y referencias a otros ficheros. Al importarlo:

- No se ejecuta nada: `script`, `foreignObject` y las hojas de estilo se ignoran.
- No se sigue ninguna referencia: `image`, `use` y los enlaces se ignoran, y se dice en el informe.
- Un SVG con `DOCTYPE` o con entidades (el truco para leer ficheros del equipo o para agotar la memoria) se **rechaza entero**.
- Límites: 8 MB, 60 000 elementos, 400 000 puntos y 200 niveles de anidamiento.

### Cómo preparar un SVG

1. Dibujar cada sala como un rectángulo o un polígono cerrado, y las paredes sueltas como líneas.
2. Poner las salas y las paredes en capas (grupos) con nombre: `salas`, `muros`, `rotulos`.
3. Escribir el nombre de cada sala dentro de ella.
4. Convertir a trazados rectos lo que sea curvo, si importa su forma.
5. Guardar como «SVG plano» (sin las extensiones del programa) y anotar la escala: cuántos metros mide una unidad del dibujo.

## Imagen de fondo (`app/importar/imagen.py`)

Un plano escaneado o una foto **no se vectorizan**. Se guarda una referencia a la imagen, con dos puntos de calibración, para que el plano gráfico del Estudio la pinte debajo y el profesional dibuje encima.

Como el formato 1 no tiene un campo propio, va en `entorno.procedencia["fondos"]` (una clave más en un diccionario que ya admite claves libres, así que es compatible con cualquier versión):

```json
"fondos": [
	{
		"planta": "pla-1",
		"imagen": "imagenes/plano.png",
		"puntos": [
			{"imagen": [120, 860], "mundo": [0.0, 0.0]},
			{"imagen": [1480, 96], "mundo": [13.6, 7.64]}
		],
		"opacidad": 0.5,
		"visible": true
	}
]
```

- `imagen` es el nombre del recurso dentro del paquete `.elab` (carpeta `imagenes/`).
- Cada punto empareja un píxel de la imagen (desde su esquina superior izquierda, con la y hacia abajo) con su posición en el entorno, en metros. Dos puntos fijan escala, giro y desplazamiento.
- Hay un fondo por planta como mucho.

```
preparar_recurso(ruta) -> (nombre_interno, bytes)        para guardar_paquete(..., recursos={nombre: bytes})
definir_fondo(entorno, planta, imagen, punto_imagen_1, punto_mundo_1, punto_imagen_2, punto_mundo_2, opacidad=0.5) -> dict
fondos_de(entorno, planta_id=None) -> list[dict]
quitar_fondo(entorno, planta_id) -> bool
transformacion(fondo) -> (metros_por_pixel, giro_grados, x, y)      (x, y): dónde cae el píxel (0, 0)
imagen_a_mundo(fondo, px, py) -> (x, y)
mundo_a_imagen(fondo, x, y) -> (px, py)
```

## Rutas y puntos reales (`app/importar/gpx.py`)

Para marcar una ruta real sobre un exterior georreferenciado: un GPX grabado con el móvil o un GeoJSON dibujado en un mapa.

```
leer_gpx(origen) -> Trazado            wpt → puntos; rte y trk → rutas
leer_geojson(origen) -> Trazado        Point → puntos; LineString y el borde de Polygon → rutas
anadir_trazado(entorno, planta, trazado, referencias_de_ruta=True) -> Informe
importar_gpx(entorno, planta, origen) -> Informe
importar_geojson(entorno, planta, origen) -> Informe
rutas_de(entorno, planta_id=None) -> list[dict]
```

- Los puntos pasan a ser referencias permanentes de tipo `punto`.
- Cada ruta se guarda entera en `entorno.procedencia["rutas"]` como `{"nombre", "descripcion", "planta", "puntos": [[x, y], …], "longitud_m", "origen"}`, y además deja referencias no permanentes en sus vértices principales («Ruta al parque: salida», «…: punto 2 de 5», «…: llegada»).
- Hace falta `entorno.georef`. Lo que cae a más de 50 metros de la planta se deja fuera y se anota.

## Exportar

### Descripción en texto, Markdown y HTML (`app/exportar/texto.py`)

```
a_texto(entorno, catalogo=None) -> str
a_markdown(entorno, catalogo=None) -> str
a_html(entorno, catalogo=None) -> str
describir(entorno, formato="txt", catalogo=None) -> str          formato: txt, md o html
guardar_descripcion(entorno, ruta, formato=None, catalogo=None) -> Path
estructura(entorno, catalogo=None) -> list[Bloque]                Bloque: titulo, nivel, parrafos, lista
```

Amplía `edicion.describir_entorno`. Es un documento para leer con lector de pantalla saltando de encabezado en encabezado, o para imprimir en braille:

- Portada: nombre, descripción, autor, resumen e inicio. Procedencia completa.
- **Interiores**: un apartado por espacio, con sus medidas, vecinos, puertas, objetos, sonidos y referencias.
- **Exteriores**: calles con sus aceras (y si son deducidas), cruces con su forma, pasos de peatones con su ficha, paradas, edificios y portales, plazas y caminos, escaleras con su ficha, obstáculos, referencias y muros.
- Conectores entre plantas y, si procede, la atribución de los datos del mapa.

Cada línea es una frase completa. El HTML declara el idioma, usa encabezados en orden y listas de verdad, y no lleva estilos ni código.

`app/exportar/fichas.py` da las fichas en frases: `ficha_paso(espacio)` y `ficha_escalera(espacio)`.

### Plano SVG a escala (`app/exportar/svg.py`)

```
plano_svg(entorno, planta, variante="visual", pagina="A4", apaisado=None, escala=None, catalogo=None) -> PlanoSVG
guardar_planos(entorno, carpeta, variante="visual", pagina="A4", catalogo=None) -> list[Path]
PlanoSVG: svg, leyenda, escala, pagina, apaisado, variante, claves;  leyenda_brf()
```

Las medidas del SVG son milímetros de la hoja (A4 o A3). Sin `escala` se elige la mayor escala normalizada (1:50, 1:75, 1:100, 1:200…) con la que la planta cabe; sin `apaisado`, la orientación que da el plano más grande. **Hay que imprimir al 100 %**, sin «ajustar a la página», para que la escala sea cierta.

| | Visual | Táctil |
| --- | --- | --- |
| Para | Tinta, pantalla, resto visual | Lámina en relieve: papel de microcápsulas y horno «fuser», o impresora de relieve |
| Superficies | Color por tipo de espacio | Sin color: tramas distintas por tipo (calzada, edificio, parque, plaza, agua, paso de peatones, escalera, pavimento táctil) |
| Paredes | Línea negra de 0,7 mm | Línea negra de 1,4 mm |
| Puertas | Tramo marrón (portal: naranja; ventana: azul) | Hueco en el muro con un tope a cada lado; con una línea fina si está cerrada |
| Nombres | Escritos donde caben; si no, un número y su nombre en la leyenda | Claves numéricas en braille; los nombres, en la leyenda |
| Objetos | Su forma real, con la letra y el color de su ficha | Su forma real, en negro macizo |
| Referencias | Rombo verde con letra | Círculo negro macizo |
| Además | Norte, barra de escala, título, inicio, atribución | Marco, esquina superior izquierda rellena para orientar la hoja, título, norte y escala en braille |

La **leyenda** va aparte, en texto (`PlanoSVG.leyenda`): escala, orientación, qué es cada trazo y cada trama, y la lista de claves con sus nombres. `guardar_planos` la escribe junto a cada SVG como `…_leyenda.txt` y, en la variante táctil, también en BRF (`…_leyenda.brf`) para imprimirla en braille. El braille es español de grado 1 (`app/exportar/braille.py`).

En el papel de microcápsulas todo lo negro sube. Lo que en la variante táctil es solo para quien acompaña (los números en tinta) va en un grupo aparte, `<g id="tinta">`, en azul claro: se puede borrar antes de imprimir.

### GeoJSON (`app/exportar/geojson.py`)

```
a_geojson(entorno, planta=None, catalogo=None) -> dict        todas las plantas si planta es None
texto_geojson(entorno, planta=None, catalogo=None) -> str
guardar_geojson(entorno, carpeta, catalogo=None) -> list[Path]     un fichero por planta
```

- **Coordenadas**: longitud y latitud reales (WGS84) si el entorno tiene `georef`. Si no, metros locales, y el documento lleva la clave `crs_local` que lo avisa.
- Cada elemento es una «feature» con sus propiedades de EntornoLab (prefijo `elab:`), las etiquetas equivalentes de **Simple Indoor Tagging** y las de **IMDF** cuando hay equivalencia. Todas llevan `level` (número de planta) y `level_id`.

| Elemento | Geometría | Simple Indoor Tagging / OSM | IMDF |
| --- | --- | --- | --- |
| Habitación, cabina | Polígono | `indoor=room` | `feature_type=unit`, `category=room` / `elevator` |
| Pasillo | Polígono | `indoor=corridor` | `unit`, `walkway` |
| Vestíbulo | Polígono | `indoor=area` | `unit`, `lobby` |
| Hueco de escalera | Polígono | `indoor=room`, `stairs=yes` | `unit`, `stairs` |
| Edificio macizo | Polígono | `building=yes` | `footprint`, `ground` |
| Acera | Polígono | `highway=footway`, `footway=sidewalk`, `area=yes` | |
| Paso de peatones | Polígono | `footway=crossing` y, **solo si se sabe**, `crossing`, `traffic_signals:sound`, `button_operated`, `crossing:island`, `tactile_paving`, `kerb` | |
| Plaza, parque, sendero, escalera exterior | Polígono | `highway=pedestrian`, `leisure=park`, `highway=path`, `highway=steps` | |
| Puerta, portal, hueco | Línea | `door=*`, `entrance=*`, `width` | `opening`, `pedestrian` o `pedestrian.principal` |
| Ventana | Línea | `window=yes` | |
| Pared suelta | Línea | `barrier=wall`, `fence` o `hedge`; `indoor=wall` | |
| Objeto | Polígono (su huella) | | `fixture`, `furniture` |
| Referencia | Punto | `public_transport=platform`, `highway=traffic_signals`, `entrance=yes`… según su tipo | `amenity` |
| Fuente de sonido | Punto | | |
| Vía | Línea | `highway`, `lanes`, `oneway`, `maxspeed`, `width` | |
| Boca de conector | Punto | `highway=elevator` o `steps`, `level=0;1` | |

Lo que el mapa no decía de un paso no se exporta como si se supiera: en OpenStreetMap, no poner una etiqueta es la manera de decir «no lo sé». Los tres estados van además en `elab:segun_mapa`.

### DXF (`app/exportar/dxf.py`)

```
a_dxf(entorno, planta, catalogo=None) -> str
guardar_dxf(entorno, carpeta, catalogo=None) -> list[Path]      un fichero por planta, en Windows-1252
```

DXF de texto en su variante más compatible (R12), en **metros**, por capas:

| Capa | Contenido |
| --- | --- |
| `ESPACIOS` | Contorno cerrado de cada espacio. |
| `EDIFICIOS` | Contorno de los edificios macizos. |
| `MUROS` | Tramos de pared: los de las salas (ya sin los huecos de las puertas) y las paredes sueltas. |
| `PUERTAS` | Puertas, portales y huecos, con el arco de barrido de las puertas. |
| `VENTANAS` | Ventanas. |
| `MOBILIARIO` | Huella y nombre de cada objeto. |
| `TEXTOS` | Nombre de cada espacio. |
| `REFERENCIAS` | Referencias y fuentes de sonido, con su nombre. |
| `EJES_VIAS` | Eje de cada calle. |

El fichero empieza con un comentario que el importador reconoce (`EntornoLab: unidades en metros`): un DXF exportado se puede volver a importar sin preguntar la escala. En esa ida y vuelta se recuperan los espacios con su nombre y las puertas (por su arco); los huecos, las ventanas, los objetos y los suelos, no.

### Indicaciones de ruta (`app/exportar/indicaciones.py`)

```
redactar(entorno, ruta, opciones=None) -> Indicaciones
OpcionesIndicaciones: unidad ("metros" | "pasos"), paso_m=0.65, giros ("lados" | "reloj"), referencias=True, radio_referencia=3.0
Indicaciones: resumen, pasos: list[Indicacion], total_m, nota;  lineas(), a_texto(), a_markdown()
Indicacion: texto, planta, x, y, distancia_m, tipo (salida, avance, giro, entrada, cruce, escaleras, planta, llegada)
normalizar_ruta(ruta) -> list[(planta_id, x, y)]
```

La ruta **se recibe como dato** (la calcula el motor de navegación). Se admite en cualquiera de estas formas:

- una lista de puntos `(planta_id, x, y)`, de objetos con `planta`, `x` e `y` (como `Posicion`) o de diccionarios con esas claves;
- una lista de tramos `(planta_id, [(x, y), …])` o de diccionarios `{"planta": id, "puntos": [[x, y], …]}`.

Qué se redacta: el punto de salida y hacia dónde ponerse, los avances (en metros o en pasos), los giros (a la derecha o a la izquierda, o por horas del reloj) con el punto cardinal en que se queda mirando, los cambios de espacio y las puertas que se cruzan, los pasos de peatones con lo esencial de su ficha, las calzadas que se pisan sin paso («Atención: bajas a la calzada…»), las escaleras exteriores, los cambios de planta por su escalera, rampa o ascensor, y la llegada. En los giros y en la llegada se nombra la referencia que haya a menos de `radio_referencia`.

```
Ruta de 65 metros, 3 giros, 2 cruces de calzada.

1. Empiezas en Acera norte de Calle Mayor, tramo 1, planta Calle. Ponte mirando al este.
2. Avanza 10 metros. Gira a la derecha, a la altura de «Semáforo norte de Paso con semáforo de Calle Mayor»: quedas mirando al sur.
3. Avanza 1 metro. Cruza por «Paso con semáforo de Calle Mayor», de 6,5 metros: tiene semáforo con señal sonora, con pulsador.
…
```

## Claves nuevas en `datos` y en `procedencia`

Todas caben en el formato 1 (diccionarios de claves libres); quien no las conozca las ignora.

| Dónde | Clave | Significado |
| --- | --- | --- |
| `Espacio.datos` | `osm` | Elemento del mapa del que sale (`way/123`, `node/45`, o una lista). |
| `Espacio.datos` | `segun_mapa` | Atributos con tres estados (`si`, `no`, `desconocido`): pasos de peatones y escaleras. |
| `Espacio.datos` | `descripcion_automatica` | La descripción la redactó el importador a partir de `datos`. |
| Pasos | `vibracion`, `tactil`, `bordillo`, `marcas`, `ciclo_estimado` | Atributos que añade la importación. |
| Aceras | `origen` (`mapa` o `deducida`), `ancho_segun_mapa` | De dónde sale la acera y su anchura. |
| Cruces | `forma`, `ramas`, `rumbos`, `semaforo_vehiculos` | Forma del cruce y rumbo de cada rama. |
| Escaleras y rampas exteriores | `peldanos`, `pasamanos`, `pasamanos_lado_desconocido`, `sube_hacia`, `rampa`, `pendiente_pct` | |
| Zonas | `terreno_base`, `cubierta`, `bicis` | Terreno sin detallar; zona con techo y sin paredes; pasan bicicletas. |
| Edificios | `numero`, `calle` | Dirección según el mapa. |
| `Objeto.datos` | `tipo_previsto`, `osm` | Objeto del complemento `calle` que sería si estuviera instalado. |
| `Entorno.georef` | `proyeccion`, `recuadro` | Además de `lat0` y `lon0`. |
| `Entorno.procedencia` | `atribucion`, `url_licencia`, `fecha_datos`, `recuadro`, `servidor` | Procedencia completa de un mapa. |
| `Entorno.procedencia` | `fondos` | Imágenes de fondo con sus puntos de calibración. |
| `Entorno.procedencia` | `rutas` | Rutas reales importadas de GPX o GeoJSON. |

## Pruebas

`tests/test_importar_*.py` y `tests/test_exportar_*.py`, con datos ficticios en `tests/datos/`, salvo la muestra real de OpenStreetMap `tests/datos/osm_real_valladolid_*` (ver «Prueba con datos reales»). No salen a la red: las descargas se sustituyen por funciones falsas que devuelven ficheros guardados.

```
.venv\Scripts\python.exe -m pytest tests -q -k "importar or exportar"
.venv\Scripts\python.exe -m ruff check app/importar app/exportar
```
