# Colegio

Mobiliario de un centro escolar: aula, biblioteca, comedor, gimnasio, patio, música, informática y pasillos.

- Identificador: `colegio`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo colegio` a partir de `tools/complementos_serie/colegio.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (73)

Medidas por defecto: ancho × fondo × alto, en metros.

### Aula (21)

#### Mesas y sillas de alumnos

- **Pupitre** (`colegio/pupitre`): 0,70 × 0,50 × 0,72 (3 variantes; puede esconder un premio).
- **Pupitre doble** (`colegio/pupitre_doble`): 1,20 × 0,50 × 0,72 (puede esconder un premio).
- **Silla de alumno** (`colegio/silla`): 0,42 × 0,42 × 0,78.
- **Mesa redonda de trabajo** (`colegio/mesa_redonda`): 1,20 × 1,20 × 0,72 (2 variantes; puede esconder un premio).
- **Mesa hexagonal de grupo** (`colegio/mesa_hexagonal`): 1,30 × 1,13 × 0,72.
- **Mesa trapezoidal** (`colegio/mesa_trapecio`): 1,20 × 0,60 × 0,64 (3 variantes; puede esconder un premio).

#### Puesto del profesor

- **Mesa del profesor** (`colegio/mesa_del_profesor`): 1,40 × 0,70 × 0,75 (puede esconder un premio).
- **Panel interactivo en soporte con ruedas** (`colegio/panel_interactivo_ruedas`): 1,95 × 0,80 × 1,80 (3 variantes).

#### Pizarras y lo que cuelga en el aula

- **Pizarra** (`colegio/pizarra`): 2,40 × 0,08 × 1,20 (3 variantes; colgado a 0,90 m).
- **Mapa mural enrollable** (`colegio/mapa_mural`): 1,40 × 0,05 × 1,20 (colgado a 1,00 m).
- **Reloj de pared del aula** (`colegio/reloj_aula`): 0,30 × 0,05 × 0,30 (colgado a 2,20 m).
- **Cordel de dibujos colgados** (`colegio/cordel_dibujos`): 4,00 × 0,10 × 0,30 (colgado a 1,60 m).

#### Ventilación y aire

- **Ventilador de techo** (`colegio/ventilador_techo`): 1,30 × 1,30 × 0,40 (colgado a 2,50 m).
- **Purificador de aire** (`colegio/purificador_aire`): 0,40 × 0,30 × 0,80.

#### Armarios y estanterías de aula

- **Armario de aula** (`colegio/armario`): 0,90 × 0,45 × 1,90 (puede esconder un premio).
- **Estantería baja de aula** (`colegio/estanteria_baja`): 1,00 × 0,40 × 0,80 (puede esconder un premio).

#### Papeleras y reciclaje

- **Papelera** (`colegio/papelera`): 0,30 × 0,30 × 0,35 (puede esconder un premio).
- **Contenedores de reciclaje de aula** (`colegio/reciclaje`): 0,90 × 0,35 × 0,70 (puede esconder un premio).

#### Rincones y cosas por el suelo

- **Alfombra de la asamblea** (`colegio/alfombra_asamblea`): 2,50 × 2,50 × 0,02 (no corta el paso; puede esconder un premio).
- **Mochilas en el suelo** (`colegio/mochilas`): 0,60 × 0,40 × 0,40 (puede esconder un premio).
- **Triángulo de Pikler** (`colegio/triangulo_pikler`): 0,80 × 0,75 × 0,75.

### Biblioteca e informática (5)

#### Libros y lectura

- **Estantería de biblioteca** (`colegio/estanteria_biblioteca`): 1,80 × 0,50 × 1,80 (3 variantes; puede esconder un premio).
- **Mesa de lectura** (`colegio/mesa_lectura`): 1,80 × 0,90 × 0,75.
- **Carrito de libros** (`colegio/carrito`): 0,50 × 0,90 × 1,00 (puede esconder un premio).

#### Ordenadores e impresora

- **Mesa con ordenador** (`colegio/mesa_ordenador`): 1,00 × 0,70 × 1,15.
- **Impresora** (`colegio/impresora`): 0,55 × 0,55 × 1,00 (puede esconder un premio).

### Comedor (5)

#### Mesas del comedor

- **Mesa de comedor con bancos** (`colegio/mesa_comedor`): 2,40 × 1,50 × 0,75 (3 variantes).
- **Mesa plegable con taburetes** (`colegio/mesa_plegable_taburetes`): 2,40 × 1,60 × 0,72 (2 variantes).

#### Servicio y agua

- **Línea de autoservicio** (`colegio/linea_bandejas`): 3,00 × 0,90 × 0,90.
- **Carro de bandejas** (`colegio/carro_bandejas`): 0,60 × 0,70 × 1,70 (puede esconder un premio).
- **Fuente de agua para beber** (`colegio/fuente_agua`): 0,35 × 0,35 × 0,95.

### Gimnasio y patio (18)

#### Aparatos de gimnasia

- **Colchoneta** (`colegio/colchoneta`): 2,00 × 1,00 × 0,08 (3 variantes; no corta el paso; puede esconder un premio).
- **Potro** (`colegio/potro`): 0,40 × 1,60 × 1,10.
- **Plinto** (`colegio/plinto`): 0,80 × 1,40 × 1,00 (puede esconder un premio).
- **Espalderas** (`colegio/espalderas`): 0,90 × 0,15 × 2,40 (3 variantes).
- **Banco sueco** (`colegio/banco_sueco`): 2,50 × 0,25 × 0,32.

#### Canastas, porterías y pelotas

- **Canasta de baloncesto** (`colegio/canasta`): 1,20 × 1,60 × 3,05 (2 variantes).
- **Portería** (`colegio/porteria`): 3,00 × 1,00 × 2,00 (2 variantes).
- **Mesa de pimpón** (`colegio/mesa_pimpon`): 1,52 × 2,74 × 0,76.
- **Balones sueltos por el suelo** (`colegio/balones_sueltos`): 1,00 × 1,00 × 0,22 (no corta el paso).

#### Vestuario

- **Banco de vestuario** (`colegio/banco_vestuario`): 1,50 × 0,40 × 1,70 (puede esconder un premio).

#### Juegos del patio

- **Tobogán** (`colegio/tobogan`): 0,60 × 3,00 × 1,80.
- **Arenero** (`colegio/arenero`): 3,00 × 3,00 × 0,20 (no corta el paso; puede esconder un premio).
- **Baúl de juegos del recreo** (`colegio/baul_recreo`): 1,20 × 0,60 × 0,60 (puede esconder un premio).

#### Huerto y naturaleza

- **Bancal del huerto escolar** (`colegio/bancal_huerto`): 2,00 × 1,00 × 0,40 (3 variantes).
- **Compostera** (`colegio/compostera`): 0,80 × 0,80 × 0,85.
- **Estación meteorológica escolar** (`colegio/estacion_meteorologica`): 0,80 × 0,80 × 2,20.
- **Depósito de agua de lluvia** (`colegio/deposito_lluvia`): 0,60 × 0,60 × 1,00 (2 variantes).
- **Comedero de pájaros colgado** (`colegio/comedero_pajaros`): 0,25 × 0,25 × 0,35 (colgado a 1,50 m).

### Música (6)

#### Instrumentos

- **Piano vertical** (`colegio/piano`): 1,50 × 0,60 × 1,20.
- **Mueble de instrumentos** (`colegio/instrumentos`): 1,20 × 0,45 × 1,00 (puede esconder un premio).
- **Teclado electrónico en soporte de tijera** (`colegio/teclado_soporte`): 1,20 × 0,40 × 0,85 (2 variantes).

#### Atriles, tarimas y gradas

- **Atril** (`colegio/atril`): 0,50 × 0,50 × 1,20.
- **Tarima** (`colegio/tarima`): 3,00 × 1,50 × 0,20 (no corta el paso).
- **Gradas de coro** (`colegio/gradas_coro`): 3,50 × 1,50 × 0,60 (2 variantes).

### Pasillos y zonas comunes (11)

#### Papeleras y reciclaje

- **Corazón de tapones solidarios** (`colegio/contenedor_tapones`): 0,90 × 0,40 × 1,20 (puede esconder un premio).

#### Taquillas, percheros y bancos

- **Taquillas** (`colegio/taquillas`): 0,90 × 0,50 × 1,80 (4 variantes; puede esconder un premio).
- **Percheros de pared** (`colegio/percheros`): 1,50 × 0,25 × 0,60 (colgado a 1,10 m; puede esconder un premio).
- **Banco de pasillo** (`colegio/banco_pasillo`): 1,50 × 0,40 × 0,45.
- **Cajón de objetos perdidos** (`colegio/cajon_objetos_perdidos`): 0,70 × 0,50 × 0,60 (2 variantes; puede esconder un premio).

#### Avisos, vitrinas y seguridad

- **Tablón de anuncios** (`colegio/tablon`): 1,20 × 0,04 × 0,90 (colgado a 1,00 m).
- **Extintor colgado** (`colegio/extintor`): 0,15 × 0,15 × 0,50 (colgado a 1,00 m).
- **Vitrina de trofeos** (`colegio/vitrina_trofeos`): 1,20 × 0,40 × 1,80 (puede esconder un premio).
- **Timbre del colegio** (`colegio/timbre_escolar`): 0,20 × 0,10 × 0,20 (colgado a 2,30 m).

#### Columnas y pilares

- **Columna** (`colegio/columna`): 0,40 × 0,40 × 3,00 (3 variantes).
- **Pilar cuadrado** (`colegio/pilar_cuadrado`): 0,40 × 0,40 × 3,00.

### Aula de plástica (2)

#### Aula de plástica

- **Secadero de dibujos** (`colegio/secadero_dibujos`): 0,70 × 0,55 × 1,15 (puede esconder un premio).
- **Pila honda del aula de plástica** (`colegio/pila_plastica`): 1,20 × 0,60 × 0,85 (2 variantes; puede esconder un premio).

### Aseos de alumnos (2)

#### Urinarios y cabinas

- **Fila de urinarios** (`colegio/urinarios_fila`): 2,00 × 0,45 × 1,20 (3 variantes).
- **Cabinas de inodoro** (`colegio/cabinas_inodoro`): 2,70 × 1,40 × 2,00 (3 variantes; puede esconder un premio).

### Aula de apoyo y sala sensorial (3)

#### Sala sensorial

- **Columpio sensorial de techo** (`colegio/columpio_sensorial`): 1,20 × 1,20 × 1,20 (2 variantes; colgado a 0,40 m).
- **Cortina de fibras ópticas** (`colegio/cortina_fibras_opticas`): 0,80 × 0,50 × 2,00 (no corta el paso).

#### Ayudas técnicas de aula

- **Bipedestador** (`colegio/bipedestador`): 0,65 × 0,85 × 1,20.

## Sonidos propios (9)

`balon`, `colchoneta`, `colegio_anemometro`, `colegio_timbre`, `impresora`, `pandereta`, `pimpon`, `teclado`, `tiza`.

## Sonidos que toma del complemento `comun` (2)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`actuador_ayuda_tecnica`, `columpio_chirrido`.

## Sonidos que toma del complemento `hogar` (8)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `cisterna`, `interruptor`, `juguetes`, `piano`, `puerta_mueble`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `oficina_y_comercio` (1)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cortina`.

## Sonidos que toma del complemento `calle` (3)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`chorro`, `hojas`, `papel`.

## Sonidos que toma del complemento `transporte` (2)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`carrito`, `taquilla`.

## Sonidos que toma del complemento `juego` (2)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cofre_abrir`, `cofre_cerrar`.
