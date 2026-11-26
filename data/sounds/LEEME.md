# Sonidos de EntornoLab

En esta carpeta hay **paquetes de sonidos**: una carpeta por paquete. El paquete se elige en las preferencias de sonido y **se cambia al momento**, también en mitad de una partida.

| Carpeta | Paquete | Qué es |
|---|---|---|
| `por_defecto` | Sintético (por defecto) | Los sonidos de serie: limpios, cortos y muy distintos entre sí. Trae todos. |
| `natural` | Natural | Instrumentos acústicos (marimba, xilófono, glockenspiel, celesta, kalimba, trompeta) y objetos hechos con modelos físicos. |
| `grabado` | Grabado | Grabaciones reales de uso libre: pasos sobre doce suelos (acera, grava, arena, charcos, baldosa, madera, alfombra, hormigón, asfalto, tierra, hierba y metal), golpes, roces, puertas, ascensor, chasquido, agua, campanas, pájaros, tráfico, monedas, máquina expendedora y ambientes de calle, parque, casa, oficina, pasillo y cocina. Trae 113 sonidos; el resto suena con el de por defecto. |

Además está `catalogo.json`, que es **común a todos los paquetes**: dice cómo se llama cada sonido en voz alta, qué significa y a qué grupo pertenece (es lo que usa el menú «Aprender los sonidos»). No hay que tocarlo.

## Cómo es un paquete

Una carpeta con ficheros de audio que se llaman **igual que los sonidos del catálogo**, en las mismas subcarpetas:

```
mi_paquete/
    pack.json            (opcional) nombre, descripción, autor, licencia
    CREDITOS.txt         (recomendado) de dónde sale cada sonido
    puerta/abrir.ogg
    pasos/madera_izq_1.wav
    ...
```

- Formatos: `.ogg`, `.flac` o `.wav`. Cualquier frecuencia de muestreo (se convierte a 44,1 kHz al cargar).
- El nombre de la carpeta es el identificador del paquete: solo minúsculas, cifras, `_` y `-`.
- **No hace falta que traiga todos los sonidos.** Lo que un paquete no trae suena con el paquete por defecto.
- Los nombres de todos los sonidos están en `catalogo.json` (campo `fichero`) y en `por_defecto`.

`pack.json` (todo es opcional):

```json
{
	"id": "mi_paquete",
	"nombre": "Mi paquete",
	"descripcion": "Grabaciones de mi casa.",
	"autor": "Quien lo ha hecho",
	"licencia": "CC0",
	"version": "1.0",
	"generado": "Cómo se hizo (grabaciones, síntesis, qué herramienta).",
	"igualar": true,
	"volumenes": {"puerta/abrir": 0.8}
}
```

- `igualar` (de serie, `true`): cada sonido se lleva al volumen del sonido de serie del mismo nombre, para que al cambiar de paquete no suba ni baje el volumen general. Con `false` suenan como vienen.
- `volumenes`: retoque de sonidos concretos, de 0,3 a 2 (1 = sin cambio).

Si `pack.json` falta o está mal escrito, el paquete funciona igual y se llama como su carpeta.

## Instalar un paquete propio

Copie su carpeta **aquí**, junto a `por_defecto`, o en la carpeta `sounds` de los datos del usuario si el programa usa otra carpeta de datos. Aparecerá en la lista de paquetes sin reiniciar.

## Consejos para que un paquete sirva para orientarse

EntornoLab se juega sin ver. Un sonido bonito que no se puede situar no sirve.

- **Lo que se sitúa en el espacio debe ser mono** y tener contenido **por encima de 3 kHz** (un chasquido, un roce, aire): el oído distingue delante de detrás por los agudos. Un tono puro y grave suena igual delante que detrás.
- **Los bucles** (`fuente/…`, `ambiente/…`, `semaforo/…`, `premio/cerca`, `ascensor/viaje`) deben empalmar sin clic.
- **Los avisos que codifican algo** deben conservar su código: `sonda/cerca`, `media` y `lejos` son tres, dos y un pitido, cada vez más grave; la brújula cuenta notas (norte una aguda, este dos, sur una grave, oeste tres); `ascensor/planta_0` a `planta_9` suben de nota; `escalera/subir` sube y `escalera/bajar` baja. Si no puede garantizarlo, **no incluya esos sonidos**: sonarán los de serie.
- Duraciones parecidas a las de serie (un paso dura dos décimas, no dos segundos).
- Sin sustos: nada de picos a tope.

## Cómo se hicieron los que vienen

- **`por_defecto`**: síntesis con numpy (`app/audio/sintesis.py`). Se regenera con `entorno.bat sonidos` (o `tools\sintetizar_sonidos.py`), que también escribe `catalogo.json` y `por_defecto/niveles.json` (el volumen de referencia de cada sonido).
- **`natural`**: con el *Generador de sonidos* del autor, solo con su motor procedural (modelos físicos e instrumentos), **sin inteligencia artificial** y sin grabaciones. Lo hace `tools\generar_paquete_sonidos.py` a partir de `tools\receta_natural.py`; la receta exacta que se envió al generador está en `natural/receta.json` y lo que se midió de cada sonido, en `natural/medidas.json`. Detalles en `natural/CREDITOS.txt`.

- **`grabado`**: con grabaciones de terceros dedicadas al dominio público (licencia **CC0 1.0** todas), recortadas y niveladas con `tools\montar_paquete_grabado.py` a partir de la tabla de `tools\receta_grabado.py`. Los ficheros originales no viajan con el programa: solo los recortes. Parte de las grabaciones se descargó de Freesound para este paquete (la vista previa de alta calidad de cada una, con «Creative Commons 0» en su página); la página de cada una va en su línea de `CREDITOS.txt`. `grabado/CREDITOS.txt` dice, de cada sonido, el fichero original, la colección, el autor, la licencia y la página de origen; el tramo exacto está en `grabado/receta.json` y lo medido, en `grabado/medidas.json`. Es un paquete parcial a propósito: los avisos que codifican algo (balizas, bastón sonoro, brújula, plantas del ascensor, semáforos, peldaños, pavimento táctil) **no se han sustituido**, porque una grabación no conserva su código; y de lo demás solo entra lo que tiene una licencia que consta y pasa las medidas. `CREDITOS.txt` termina con la lista de lo que falta y la descripción de la grabación que habría que buscar para cada sonido.

Si quiere completar el paquete «Grabado» con grabaciones suyas, copie cada una en `grabado` con el nombre del sonido (por ejemplo `grabado/pasos/moqueta_izq_1.wav`), apunte de dónde sale en `CREDITOS.txt` y recuerde que un suelo necesita sus seis pasos (`_izq_1` a `_izq_3` y `_der_1` a `_der_3`).

Los sonidos propios de los complementos de objetos (`data/plugins/<complemento>/sonidos`) no forman parte de los paquetes.

Más detalles para quien programa: `docs/sonido.md`.
