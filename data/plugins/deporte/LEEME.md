# Deporte

Polideportivo y pistas, atletismo, gimnasia y combate, sala de máquinas de gimnasio, piscina deportiva, vestuarios y gradas, con sus redes, aparatos colgados y bordes de agua.

- Identificador: `deporte`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo deporte` a partir de `tools/complementos_serie/deporte.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (143)

Medidas por defecto: ancho × fondo × alto, en metros.

### Pistas y polideportivo (28)

#### Porterías y canastas

- **Canasta de minibasket regulable** (`deporte/canasta_minibasket`): 1,20 × 1,60 × 3,20 (2 variantes).
- **Canasta colgada del techo, plegada** (`deporte/canasta_techo`): 1,80 × 2,50 × 1,20 (no corta el paso; colgado a 3,20 m).
- **Portería de fútbol de campo** (`deporte/porteria_futbol_grande`): 7,32 × 2,00 × 2,44 (2 variantes).
- **Portería de hockey** (`deporte/porteria_hockey`): 1,70 × 0,92 × 1,05 (2 variantes).

#### Redes y postes

- **Poste de voleibol** (`deporte/poste_voleibol`): 0,25 × 0,25 × 2,55.
- **Red de voleibol tendida** (`deporte/red_voleibol`): 9,50 × 0,05 × 1,00 (colgado a 1,40 m).
- **Poste de bádminton con base** (`deporte/poste_badminton`): 0,40 × 0,50 × 1,55.
- **Red de bádminton tendida** (`deporte/red_badminton`): 6,10 × 0,04 × 0,76 (2 variantes; colgado a 0,76 m).
- **Red de tenis con postes** (`deporte/red_tenis`): 12,80 × 0,10 × 1,07 (2 variantes).
- **Silla de juez de tenis** (`deporte/silla_juez_tenis`): 0,80 × 1,10 × 2,00.
- **Red de pádel con postes** (`deporte/red_padel`): 10,00 × 0,08 × 0,90.

#### Cerramientos de pista

- **Pared de cristal de pista de pádel** (`deporte/pared_cristal_padel`): 4,00 × 0,10 × 3,00 (3 variantes).
- **Valla metálica de pista** (`deporte/valla_pista`): 3,00 × 0,08 × 4,00 (2 variantes).
- **Puerta de malla de pista** (`deporte/puerta_pista`): 1,00 × 0,08 × 2,00.
- **Red parabalones** (`deporte/red_parabalones`): 10,00 × 0,10 × 6,00.
- **Cortina divisoria de pabellón** (`deporte/cortina_divisoria`): 6,00 × 0,05 × 7,00.
- **Valla publicitaria de pie de pista** (`deporte/valla_publicitaria`): 3,00 × 0,50 × 0,90.

#### Banquillos y anotación

- **Banquillo de suplentes con techo** (`deporte/banquillo_cubierto`): 4,00 × 1,30 × 2,00 (3 variantes; puede esconder un premio).
- **Banquillo de suplentes sin techo** (`deporte/banquillo_abierto`): 3,00 × 0,50 × 0,85 (puede esconder un premio).
- **Mesa de anotadores** (`deporte/mesa_anotadores`): 3,00 × 0,70 × 0,75 (puede esconder un premio).
- **Marcador electrónico con bocina** (`deporte/marcador_electronico`): 3,00 × 0,12 × 1,50 (no corta el paso; colgado a 3,00 m).

#### Material de entrenamiento

- **Carro de balones** (`deporte/carro_balones`): 0,90 × 0,60 × 0,95 (puede esconder un premio).
- **Fila de conos de entrenamiento** (`deporte/conos_fila`): 3,00 × 0,25 × 0,25 (2 variantes).
- **Pica con base** (`deporte/pica_base`): 0,25 × 0,25 × 1,60.
- **Escalera de agilidad en el suelo** (`deporte/escalera_agilidad`): 0,50 × 4,00 × 0,02 (no corta el paso).
- **Banderín de córner** (`deporte/banderin_corner`): 0,05 × 0,05 × 1,50.

#### Marcas de pista

- **Línea de pista** (`deporte/linea_pista`): 10,00 × 0,05 × 0,01 (no corta el paso).
- **Círculo central de pista** (`deporte/circulo_central`): 3,60 × 3,60 × 0,01 (3 variantes; no corta el paso).

### Atletismo (13)

#### Carreras

- **Valla de atletismo** (`deporte/valla_atletismo`): 1,20 × 0,70 × 0,91 (3 variantes).
- **Vallas pequeñas de entrenamiento** (`deporte/minivallas`): 0,60 × 4,00 × 0,30.
- **Taco de salida** (`deporte/taco_salida`): 0,40 × 0,85 × 0,20.
- **Ría de la carrera de obstáculos** (`deporte/ria_obstaculos`): 3,66 × 3,66 × 0,50 (no corta el paso).
- **Obstáculo fijo de la carrera de obstáculos** (`deporte/obstaculo_fijo`): 3,96 × 1,20 × 0,91.
- **Bordillo interior de la pista de atletismo** (`deporte/bordillo_pista_atletismo`): 5,00 × 0,05 × 0,05 (no corta el paso).

#### Saltos

- **Foso de salto de longitud** (`deporte/foso_longitud`): 2,75 × 9,00 × 0,10 (no corta el paso; puede esconder un premio).
- **Colchón de salto de altura** (`deporte/colchon_altura`): 5,00 × 3,00 × 0,70.
- **Saltómetro con listón** (`deporte/saltometro`): 4,20 × 0,50 × 2,30.
- **Cajetín de pértiga** (`deporte/cajetin_pertiga`): 0,60 × 1,00 × 0,20 (no corta el paso).

#### Lanzamientos

- **Jaula de lanzamientos** (`deporte/jaula_lanzamientos`): 7,00 × 8,00 × 7,00.
- **Círculo de lanzamiento** (`deporte/circulo_lanzamiento`): 2,13 × 2,13 × 0,02 (2 variantes; no corta el paso).
- **Contenedor de peso** (`deporte/contenedor_peso`): 1,21 × 0,30 × 0,10.

### Gimnasia y combate (21)

#### Aparatos de gimnasia

- **Caballo con arcos** (`deporte/caballo_arcos`): 1,60 × 0,60 × 1,15.
- **Barra de equilibrio** (`deporte/barra_equilibrio`): 5,00 × 0,60 × 0,30 (2 variantes).
- **Barras paralelas** (`deporte/paralelas`): 1,00 × 3,50 × 1,80.
- **Paralelas asimétricas con tensores** (`deporte/paralelas_asimetricas`): 4,00 × 5,50 × 2,50.
- **Barra fija con tensores** (`deporte/barra_fija`): 4,00 × 5,50 × 2,80.
- **Anillas colgadas** (`deporte/anillas`): 0,70 × 0,20 × 3,50 (colgado a 1,70 m).
- **Minitramp** (`deporte/minitramp`): 1,10 × 1,10 × 0,40.
- **Cama elástica de competición** (`deporte/cama_elastica`): 2,91 × 5,05 × 1,15.
- **Trampolín de batida** (`deporte/trampolin_batida`): 0,60 × 1,20 × 0,22.
- **Barra de ballet de pared** (`deporte/barra_ballet`): 3,00 × 0,20 × 0,25 (colgado a 0,85 m).

#### Tapices y colchonetas

- **Tapiz de gimnasia** (`deporte/tapiz_gimnasia`): 12,00 × 12,00 × 0,10 (2 variantes; no corta el paso).
- **Tatami** (`deporte/tatami`): 8,00 × 8,00 × 0,04 (3 variantes; no corta el paso).
- **Colchoneta quitamiedos gruesa** (`deporte/quitamiedos`): 3,00 × 2,00 × 0,40.
- **Carro de colchonetas apiladas** (`deporte/carro_colchonetas`): 1,10 × 2,10 × 1,00 (puede esconder un premio).

#### Deportes de combate

- **Ring de boxeo** (`deporte/ring_boxeo`): 6,00 × 6,00 × 2,20 (puede esconder un premio).
- **Saco de boxeo colgado** (`deporte/saco_boxeo`): 0,35 × 0,35 × 1,20 (colgado a 0,80 m).
- **Saco de boxeo de pie** (`deporte/saco_pie`): 0,60 × 0,60 × 1,75.
- **Pera de boxeo con plataforma** (`deporte/pera_boxeo`): 0,60 × 0,65 × 0,45 (colgado a 1,50 m).

#### Trepa y puntería

- **Cuerda de trepar** (`deporte/cuerda_trepar`): 0,05 × 0,05 × 5,00.
- **Rocódromo con colchoneta** (`deporte/rocodromo`): 4,00 × 2,50 × 4,00 (2 variantes).
- **Diana de tiro con arco sobre caballete** (`deporte/diana_arco`): 1,30 × 1,00 × 1,90.

### Sala de máquinas (36)

#### Máquinas de cardio

- **Cinta de correr** (`deporte/cinta_correr`): 0,85 × 2,00 × 1,50.
- **Elíptica** (`deporte/eliptica`): 0,70 × 1,80 × 1,70.
- **Bicicleta estática** (`deporte/bici_estatica`): 0,55 × 1,10 × 1,40 (2 variantes).
- **Bicicleta de ciclo indoor** (`deporte/bici_spinning`): 0,55 × 1,20 × 1,15.
- **Máquina de remo** (`deporte/remo`): 0,60 × 2,40 × 0,90.
- **Escaladora de peldaños** (`deporte/escaladora`): 0,85 × 1,40 × 2,10.

#### Máquinas de fuerza

- **Banco de press con soportes y barra** (`deporte/banco_press`): 2,20 × 1,70 × 1,25.
- **Rack de sentadillas** (`deporte/rack_sentadillas`): 2,20 × 1,50 × 2,30.
- **Máquina multipower** (`deporte/multipower`): 2,10 × 1,30 × 2,25.
- **Máquina de poleas con cables** (`deporte/cruce_poleas`): 3,60 × 0,90 × 2,30.
- **Máquina de jalón con barra colgante** (`deporte/jalon_dorsal`): 1,20 × 1,60 × 2,25.
- **Prensa de piernas** (`deporte/prensa_piernas`): 1,10 × 2,20 × 1,45.
- **Máquina de extensión de cuádriceps** (`deporte/extension_cuadriceps`): 1,10 × 1,30 × 1,50.
- **Máquina contractora de pecho** (`deporte/contractora`): 1,30 × 1,20 × 2,00.
- **Multiestación de musculación** (`deporte/multiestacion`): 1,90 × 2,00 × 2,10.
- **Estructura de entrenamiento funcional** (`deporte/jaula_funcional`): 4,50 × 1,80 × 2,70.

#### Peso libre

- **Banco plano de pesas** (`deporte/banco_plano`): 0,30 × 1,20 × 0,45.
- **Banco inclinado regulable** (`deporte/banco_inclinado`): 0,65 × 1,40 × 1,15.
- **Mancuernero** (`deporte/mancuernero`): 2,00 × 0,60 × 0,85 (2 variantes).
- **Soporte de discos** (`deporte/soporte_discos`): 0,60 × 0,60 × 1,00.
- **Barra olímpica cargada en el suelo** (`deporte/barra_olimpica`): 2,20 × 0,45 × 0,45.
- **Plataforma de halterofilia** (`deporte/plataforma_halterofilia`): 3,00 × 2,50 × 0,06 (no corta el paso).
- **Pesas rusas en fila** (`deporte/kettlebells`): 1,20 × 0,30 × 0,28.
- **Estante de balones medicinales** (`deporte/estante_balones_medicinales`): 0,60 × 0,40 × 1,40 (puede esconder un premio).
- **Cajón de salto pliométrico** (`deporte/cajon_pliometrico`): 0,50 × 0,60 × 0,60.

#### Suelo y entrenamiento funcional

- **Fitball** (`deporte/fitball`): 0,65 × 0,65 × 0,65.
- **Step** (`deporte/step`): 1,10 × 0,40 × 0,15.
- **Esterillas apiladas** (`deporte/esterillas_apiladas`): 1,80 × 0,60 × 0,40 (puede esconder un premio).
- **Esterilla extendida en el suelo** (`deporte/esterilla_extendida`): 0,60 × 1,80 × 0,01 (no corta el paso).
- **Cuerdas de batida en el suelo** (`deporte/cuerdas_batida`): 0,60 × 5,00 × 0,05 (no corta el paso).
- **Correas de suspensión colgadas** (`deporte/correas_suspension`): 0,30 × 0,30 × 1,60 (colgado a 0,80 m).

#### Servicios de la sala

- **Espejo de pared de sala de gimnasio** (`deporte/espejo_sala`): 2,00 × 0,04 × 2,00 (colgado a 0,15 m).
- **Dispensador de papel y desinfectante** (`deporte/dispensador_papel`): 0,30 × 0,25 × 0,60 (colgado a 1,00 m).
- **Báscula de columna** (`deporte/bascula_columna`): 0,35 × 0,55 × 1,35.
- **Fuente de pared para rellenar botellas** (`deporte/fuente_botellas`): 0,45 × 0,40 × 0,50 (colgado a 0,75 m).
- **Mostrador de recepción de gimnasio** (`deporte/mostrador_gimnasio`): 2,80 × 1,60 × 1,10 (puede esconder un premio).

### Piscina deportiva (23)

#### Vaso y bordes

- **Vaso de piscina** (`deporte/vaso_piscina`): 12,50 × 25,00 × 0,10 (4 variantes; no corta el paso).
- **Rebosadero con rejilla** (`deporte/rebosadero`): 5,00 × 0,30 × 0,02 (no corta el paso).
- **Murete de vaso elevado** (`deporte/murete_vaso`): 3,00 × 0,30 × 0,40.
- **Rampa de acceso al agua** (`deporte/rampa_piscina`): 1,50 × 7,50 × 0,10 (no corta el paso).

#### Salidas y saltos

- **Poyete de salida** (`deporte/poyete_salida`): 0,50 × 0,70 × 0,70.
- **Trampolín de piscina** (`deporte/trampolin_piscina`): 1,20 × 4,80 × 2,00 (2 variantes).
- **Torre de saltos** (`deporte/torre_saltos`): 4,00 × 5,00 × 6,50.

#### Calles y material

- **Corchera tendida** (`deporte/corchera_tendida`): 0,15 × 25,00 × 0,15 (no corta el paso).
- **Corchera enrollada en su carrete** (`deporte/corchera_carrete`): 1,80 × 1,30 × 1,60.
- **Jaula de tablas, churros y pull-buoys** (`deporte/jaula_material`): 1,20 × 0,70 × 1,10 (puede esconder un premio).
- **Chalecos y cinturones de flotación colgados** (`deporte/flotadores_colgados`): 1,50 × 0,30 × 0,90 (colgado a 0,80 m; puede esconder un premio).

#### Socorrismo y acceso al agua

- **Escalerilla de piscina** (`deporte/escalerilla_piscina`): 0,50 × 0,70 × 0,95.
- **Silla alta de socorrista** (`deporte/silla_socorrista`): 0,90 × 1,20 × 2,00.
- **Aro salvavidas en la pared** (`deporte/aro_salvavidas`): 0,75 × 0,12 × 0,75 (colgado a 1,00 m).
- **Pértiga de rescate en la pared** (`deporte/pertiga_rescate`): 3,50 × 0,08 × 0,30 (colgado a 1,60 m).
- **Silla hidráulica de acceso a la piscina** (`deporte/grua_piscina`): 0,70 × 1,30 × 1,80.

#### Playa de la piscina

- **Ducha de entrada a la piscina** (`deporte/ducha_piscina`): 0,30 × 0,30 × 2,20.
- **Pediluvio** (`deporte/pediluvio`): 1,50 × 2,00 × 0,10 (no corta el paso).
- **Banco de playa de piscina** (`deporte/banco_piscina`): 1,80 × 0,40 × 0,45 (puede esconder un premio).

#### Zona termal y de recreo

- **Tobogán acuático** (`deporte/tobogan_acuatico`): 1,50 × 4,50 × 3,00.
- **Bañera de hidromasaje** (`deporte/jacuzzi`): 2,50 × 2,50 × 0,30 (no corta el paso).
- **Cabina de sauna** (`deporte/sauna`): 2,00 × 2,00 × 2,10 (puede esconder un premio).
- **Baño turco** (`deporte/bano_turco`): 2,50 × 2,20 × 2,30 (puede esconder un premio).

### Vestuarios (15)

#### Bancos y perchas

- **Banco doble de vestuario con perchero central** (`deporte/banco_doble_vestuario`): 1,50 × 0,80 × 1,75 (puede esconder un premio).
- **Banco simple de vestuario** (`deporte/banco_simple_vestuario`): 1,50 × 0,35 × 0,45 (puede esconder un premio).
- **Percha alta de vestuario con balda** (`deporte/percha_alta_vestuario`): 1,50 × 0,30 × 0,30 (colgado a 1,60 m; puede esconder un premio).

#### Taquillas y cabinas

- **Bloque de taquillas de vestuario con banco** (`deporte/taquillas_con_banco`): 1,20 × 0,80 × 1,90 (3 variantes; puede esconder un premio).
- **Bloque de taquillas bajas de vestuario** (`deporte/taquillas_bajas`): 0,90 × 0,50 × 1,00 (puede esconder un premio).
- **Cabina de cambio de vestuario** (`deporte/cabina_cambio`): 1,10 × 1,40 × 2,00 (2 variantes; puede esconder un premio).

#### Duchas

- **Duchas colectivas en fila** (`deporte/duchas_colectivas`): 3,60 × 1,00 × 0,03 (3 variantes; no corta el paso).
- **Duchas de vestuario con separadores** (`deporte/duchas_separadores`): 2,70 × 1,10 × 1,90.
- **Ducha adaptada de vestuario con asiento abatible** (`deporte/ducha_adaptada`): 0,45 × 0,45 × 0,45 (colgado a 0,45 m).
- **Tarima de rejilla de vestuario** (`deporte/tarima_rejilla`): 1,00 × 0,50 × 0,03 (no corta el paso).

#### Secado y aseo

- **Secamanos de aire de vestuario** (`deporte/secamanos_vestuario`): 0,28 × 0,22 × 0,30 (colgado a 1,10 m).
- **Centrifugadora de bañadores** (`deporte/centrifugadora`): 0,30 × 0,35 × 0,50 (colgado a 0,90 m).
- **Encimera de tocador de vestuario con espejo** (`deporte/tocador_vestuario`): 1,50 × 0,40 × 1,10 (colgado a 0,80 m; puede esconder un premio).

#### Masaje y primeros auxilios

- **Camilla de masaje** (`deporte/camilla_masaje`): 0,70 × 1,90 × 0,70 (puede esconder un premio).
- **Botiquín de pared de instalación deportiva** (`deporte/botiquin_pared`): 0,45 × 0,18 × 0,45 (colgado a 1,30 m; puede esconder un premio).

### Gradas y accesos (7)

#### Graderíos

- **Tramo de grada de hormigón** (`deporte/grada_hormigon`): 4,00 × 2,40 × 1,20 (3 variantes).
- **Grada telescópica** (`deporte/grada_telescopica`): 6,00 × 4,00 × 2,50 (2 variantes).
- **Grada portátil metálica** (`deporte/grada_portatil`): 3,00 × 2,00 × 1,10 (puede esconder un premio).
- **Fila de asientos de grada** (`deporte/fila_asientos_grada`): 2,50 × 0,45 × 0,40 (2 variantes).

#### Accesos

- **Vomitorio** (`deporte/vomitorio`): 2,40 × 4,00 × 2,50 (no corta el paso).
- **Túnel de vestuarios** (`deporte/tunel_vestuarios`): 2,50 × 6,00 × 2,30 (no corta el paso).

#### Protecciones y marcas

- **Antepecho de cristal de grada** (`deporte/antepecho_cristal`): 2,00 × 0,05 × 1,10.

## Sonidos propios (10)

`bocina_marcador`, `centrifugadora_banador`, `cinta_correr_marcha`, `jacuzzi_burbujas`, `pesas_hierro`, `piscina_rebosadero`, `placas_pesas`, `remo_tiron`, `saco_golpe`, `secador_pared_aire`.

## Sonidos que toma del complemento `comun` (4)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bici_volante_giro`, `chapuzon`, `ducha`, `vapor_bano_turco`.

## Sonidos que toma del complemento `hogar` (4)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`interruptor`, `puerta_cristal`, `sentarse`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (2)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`balon`, `colchoneta`.

## Sonidos que toma del complemento `oficina_y_comercio` (1)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`garrafa`.

## Sonidos que toma del complemento `calle` (2)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`chorro`, `papel`.

## Sonidos que toma del complemento `transporte` (3)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `taquilla`.

## Sonidos que toma del complemento `juego` (4)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bandera`, `globo`, `monedas`, `muelle`.
