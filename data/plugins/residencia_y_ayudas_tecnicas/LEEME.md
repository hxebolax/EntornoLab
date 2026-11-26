# Residencia y ayudas técnicas

Residencia de mayores y centro de día, vivienda adaptada, grúas, barras, rampas y elevadores, y la señalización táctil y sonora y los aparatos de las personas ciegas y sordas.

- Identificador: `residencia_y_ayudas_tecnicas`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo residencia_y_ayudas_tecnicas` a partir de `tools/complementos_serie/residencia_y_ayudas_tecnicas.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (100)

Medidas por defecto: ancho × fondo × alto, en metros.

### Sala de estar y comedor de residencia (10)

#### Sillones y sillas de residencia

- **Sillón geriátrico de respaldo alto** (`residencia_y_ayudas_tecnicas/sillon_geriatrico`): 0,68 × 0,78 × 1,15.
- **Sillón geriátrico reclinable con ruedas** (`residencia_y_ayudas_tecnicas/sillon_geriatrico_ruedas`): 0,72 × 1,10 × 1,25 (2 variantes).
- **Sillón de relax con reposapiés** (`residencia_y_ayudas_tecnicas/sillon_relax_reposapies`): 0,85 × 1,55 × 1,05.
- **Hilera de sillones de sala común** (`residencia_y_ayudas_tecnicas/hilera_sillones`): 2,60 × 0,80 × 1,10 (4 variantes).
- **Silla de comedor con reposabrazos** (`residencia_y_ayudas_tecnicas/silla_comedor_brazos`): 0,58 × 0,60 × 0,90.

#### Mesas de comedor y de juegos

- **Mesa de comedor con escotaduras** (`residencia_y_ayudas_tecnicas/mesa_escotadura`): 1,20 × 0,90 × 0,77 (3 variantes; puede esconder un premio).
- **Mesa de cartas y dominó** (`residencia_y_ayudas_tecnicas/mesa_juegos_residencia`): 0,90 × 0,90 × 0,75 (puede esconder un premio).

#### Sonidos y referencias de la sala

- **Televisor de sala común colgado en alto** (`residencia_y_ayudas_tecnicas/televisor_sala_alto`): 1,20 × 0,10 × 0,70 (colgado a 1,60 m).
- **Jaula de pájaros en su pie** (`residencia_y_ayudas_tecnicas/jaula_pajaros_sala`): 0,50 × 0,50 × 1,65.
- **Panel de fecha y hora de la sala** (`residencia_y_ayudas_tecnicas/panel_orientacion_fecha`): 0,90 × 0,05 × 0,60 (colgado a 1,20 m).

### Habitación de residencia y control (11)

#### Cama articulada y su entorno

- **Cama articulada geriátrica con barandillas** (`residencia_y_ayudas_tecnicas/cama_geriatrica`): 1,00 × 2,10 × 0,75 (3 variantes; puede esconder un premio).
- **Colchoneta de caída junto a la cama** (`residencia_y_ayudas_tecnicas/colchoneta_anticaidas`): 0,70 × 1,90 × 0,04 (no corta el paso).
- **Mesilla con bandeja abatible** (`residencia_y_ayudas_tecnicas/mesilla_bandeja_abatible`): 0,48 × 0,45 × 0,85 (2 variantes; puede esconder un premio).
- **Cabecero con luz y pulsador de llamada** (`residencia_y_ayudas_tecnicas/cabecero_luz_llamada`): 1,00 × 0,10 × 0,20 (colgado a 1,30 m).
- **Incorporador de cama con triángulo** (`residencia_y_ayudas_tecnicas/incorporador_cama_colgante`): 0,30 × 0,70 × 0,50 (colgado a 1,30 m).
- **Alfombrilla sensora de levantarse** (`residencia_y_ayudas_tecnicas/alfombrilla_sensora_cama`): 0,90 × 0,60 × 0,01 (no corta el paso).

#### Mobiliario de la habitación

- **Armario con barra de colgar abatible** (`residencia_y_ayudas_tecnicas/armario_barra_abatible`): 0,90 × 0,60 × 2,00 (2 variantes; puede esconder un premio).
- **Silla con inodoro de habitación** (`residencia_y_ayudas_tecnicas/silla_wc_noche`): 0,60 × 0,60 × 0,95 (2 variantes).

#### Control de enfermería y planta

- **Mostrador del control de enfermería** (`residencia_y_ayudas_tecnicas/mostrador_control_enfermeria`): 2,40 × 1,80 × 1,10 (puede esconder un premio).
- **Panel de llamadas de habitaciones** (`residencia_y_ayudas_tecnicas/panel_llamadas_enfermeria`): 0,40 × 0,08 × 0,30 (colgado a 1,30 m).
- **Carro de lencería de planta** (`residencia_y_ayudas_tecnicas/carro_lenceria_planta`): 0,55 × 0,95 × 1,15 (puede esconder un premio).

### Terapia ocupacional y gimnasia (9)

#### Terapia ocupacional

- **Mesa de terapia en herradura** (`residencia_y_ayudas_tecnicas/mesa_terapia_herradura`): 1,80 × 1,10 × 0,74 (puede esconder un premio).
- **Tablero de cerrojos, grifos y cremalleras** (`residencia_y_ayudas_tecnicas/panel_actividades_diarias`): 1,00 × 0,10 × 0,70 (colgado a 0,75 m).
- **Mesa de cultivo elevada** (`residencia_y_ayudas_tecnicas/mesa_cultivo_adaptada`): 1,20 × 0,80 × 0,80 (puede esconder un premio).

#### Gimnasia de mantenimiento

- **Pedalier de suelo** (`residencia_y_ayudas_tecnicas/pedalier_sentado`): 0,42 × 0,50 × 0,30.
- **Corro de sillas de gimnasia de mantenimiento** (`residencia_y_ayudas_tecnicas/corro_sillas_gimnasia`): 3,80 × 3,80 × 0,85.
- **Circuito de aros y picas en el suelo** (`residencia_y_ayudas_tecnicas/circuito_aros_picas`): 3,00 × 1,20 × 0,25.
- **Cesto de pelotas blandas y cintas** (`residencia_y_ayudas_tecnicas/cesto_psicomotricidad`): 0,55 × 0,55 × 0,60 (puede esconder un premio).

#### Estimulación y juegos

- **Columna de burbujas** (`residencia_y_ayudas_tecnicas/columna_burbujas`): 0,40 × 0,40 × 1,80.
- **Bombo de bingo en su mesa** (`residencia_y_ayudas_tecnicas/bombo_bingo_mesa`): 0,80 × 0,60 × 1,10 (puede esconder un premio).

### Aseo y baño adaptados (17)

#### Sanitarios adaptados

- **Inodoro alto con barras a los lados** (`residencia_y_ayudas_tecnicas/inodoro_adaptado_barras`): 0,85 × 0,75 × 0,85.
- **Lavabo sin pedestal regulable** (`residencia_y_ayudas_tecnicas/lavabo_suspendido_regulable`): 0,65 × 0,55 × 0,18 (colgado a 0,68 m).
- **Alza de inodoro con marco de apoyo** (`residencia_y_ayudas_tecnicas/alza_inodoro_marco`): 0,60 × 0,52 × 0,75.

#### Barras de apoyo

- **Barra abatible de inodoro** (`residencia_y_ayudas_tecnicas/barra_abatible_inodoro`): 0,15 × 0,75 × 0,20 (colgado a 0,55 m).
- **Barra fija de pared** (`residencia_y_ayudas_tecnicas/barra_fija_pared`): 0,60 × 0,08 × 0,05 (4 variantes; colgado a 0,70 m).
- **Barra de apoyo de suelo a techo** (`residencia_y_ayudas_tecnicas/barra_suelo_techo`): 0,15 × 0,15 × 2,50.

#### Ducha y bañera adaptadas

- **Plato de ducha enrasado sin escalón** (`residencia_y_ayudas_tecnicas/plato_ducha_ras_suelo`): 1,20 × 0,90 × 0,02 (3 variantes; no corta el paso).
- **Asiento de ducha abatible de pared** (`residencia_y_ayudas_tecnicas/asiento_ducha_abatible`): 0,45 × 0,42 × 0,08 (colgado a 0,50 m).
- **Silla de ducha con ruedas** (`residencia_y_ayudas_tecnicas/silla_ducha_ruedas`): 0,56 × 0,90 × 1,00.
- **Banqueta de ducha de patas regulables** (`residencia_y_ayudas_tecnicas/banqueta_ducha_regulable`): 0,40 × 0,40 × 0,45.
- **Asiento giratorio de bañera** (`residencia_y_ayudas_tecnicas/asiento_giratorio_banera`): 0,72 × 0,55 × 0,40 (colgado a 0,55 m).
- **Bañera con puerta** (`residencia_y_ayudas_tecnicas/banera_con_puerta`): 1,40 × 0,72 × 0,95 (3 variantes; puede esconder un premio).
- **Media mampara abatible de ducha asistida** (`residencia_y_ayudas_tecnicas/mampara_baja_cuidador`): 0,90 × 0,04 × 0,90.
- **Peldaño de bañera antideslizante** (`residencia_y_ayudas_tecnicas/peldano_banera_asidero`): 0,45 × 0,38 × 0,15 (2 variantes).

#### Accesorios del aseo adaptado

- **Espejo basculante de aseo adaptado** (`residencia_y_ayudas_tecnicas/espejo_basculante_aseo`): 0,60 × 0,15 × 0,90 (colgado a 0,90 m).
- **Tirador de alarma con cordón** (`residencia_y_ayudas_tecnicas/tirador_alarma_aseo`): 0,08 × 0,08 × 2,00 (colgado a 0,10 m).
- **Cambiador de adultos abatible** (`residencia_y_ayudas_tecnicas/cambiador_adultos_abatible`): 1,80 × 0,75 × 0,15 (colgado a 0,60 m).

### Cocina y casa adaptadas (8)

#### Cocina adaptada

- **Encimera regulable con hueco inferior** (`residencia_y_ayudas_tecnicas/encimera_regulable_hueco`): 1,20 × 0,62 × 0,82 (3 variantes).
- **Fregadero poco profundo con hueco inferior** (`residencia_y_ayudas_tecnicas/fregadero_adaptado_hueco`): 0,90 × 0,60 × 0,80.
- **Placa de cocción con mandos frontales y hueco** (`residencia_y_ayudas_tecnicas/placa_coccion_adaptada`): 0,70 × 0,60 × 0,80.
- **Armarios altos descendentes** (`residencia_y_ayudas_tecnicas/armarios_altos_descendentes`): 0,90 × 0,35 × 0,70 (colgado a 1,40 m; puede esconder un premio).
- **Horno de puerta lateral con bandeja extraíble** (`residencia_y_ayudas_tecnicas/horno_lateral_bandeja`): 0,60 × 0,58 × 1,40 (puede esconder un premio).

#### Ayudas en casa

- **Carrito camarera con asa de apoyo** (`residencia_y_ayudas_tecnicas/carro_camarera_apoyo`): 0,48 × 0,68 × 0,92 (puede esconder un premio).
- **Sillón elevador** (`residencia_y_ayudas_tecnicas/sillon_elevador`): 0,82 × 0,95 × 1,08 (2 variantes).
- **Asidero de cama para incorporarse** (`residencia_y_ayudas_tecnicas/asidero_cama_incorporarse`): 0,50 × 0,08 × 0,90.

### Grúas, rampas y elevadores (12)

#### Grúas de traslado

- **Grúa de traslado con ruedas** (`residencia_y_ayudas_tecnicas/grua_traslado_ruedas`): 0,68 × 1,25 × 1,75 (3 variantes).
- **Grúa de techo con raíl** (`residencia_y_ayudas_tecnicas/grua_techo_rail`): 3,00 × 0,50 × 0,70 (3 variantes; colgado a 1,70 m).
- **Disco giratorio de transferencia** (`residencia_y_ayudas_tecnicas/disco_transferencia`): 0,40 × 0,40 × 0,03 (no corta el paso).

#### Salvaescaleras y plataformas

- **Silla salvaescaleras en su raíl** (`residencia_y_ayudas_tecnicas/silla_salvaescaleras`): 0,65 × 0,65 × 1,00 (2 variantes).
- **Plataforma elevadora vertical** (`residencia_y_ayudas_tecnicas/plataforma_elevadora_vertical`): 1,10 × 1,50 × 1,30 (2 variantes).
- **Plataforma salvaescaleras inclinada** (`residencia_y_ayudas_tecnicas/plataforma_salvaescaleras_plegable`): 1,00 × 0,30 × 1,10 (2 variantes).
- **Oruga salvaescaleras portátil** (`residencia_y_ayudas_tecnicas/oruga_salvaescaleras`): 0,65 × 1,10 × 1,00.

#### Rampas y pasamanos

- **Rampa portátil de umbral** (`residencia_y_ayudas_tecnicas/rampa_umbral_portatil`): 0,90 × 0,30 × 0,04 (no corta el paso).
- **Rampa modular con barandilla** (`residencia_y_ayudas_tecnicas/rampa_modular_barandilla`): 1,00 × 3,00 × 0,30 (3 variantes; no corta el paso).
- **Pasamanos doble a dos alturas** (`residencia_y_ayudas_tecnicas/pasamanos_doble_altura`): 2,00 × 0,08 × 0,25 (4 variantes; colgado a 0,65 m).

#### Scooter y evacuación

- **Scooter de movilidad aparcado y cargándose** (`residencia_y_ayudas_tecnicas/scooter_movilidad_cargando`): 0,60 × 1,20 × 1,00 (puede esconder un premio).
- **Silla de evacuación colgada en la escalera** (`residencia_y_ayudas_tecnicas/silla_evacuacion_colgada`): 0,55 × 0,25 × 1,00 (colgado a 0,80 m).

### Señalización táctil y sonora (18)

#### Planos y maquetas táctiles

- **Plano táctil del edificio en atril** (`residencia_y_ayudas_tecnicas/plano_tactil_atril`): 0,80 × 0,55 × 0,95.
- **Plano táctil de pared** (`residencia_y_ayudas_tecnicas/plano_tactil_pared`): 0,70 × 0,05 × 0,50 (colgado a 1,00 m).
- **Maqueta táctil del edificio** (`residencia_y_ayudas_tecnicas/maqueta_tactil_edificio`): 1,20 × 0,90 × 0,95.

#### Franjas y marcas del suelo

- **Franja guía interior adhesiva** (`residencia_y_ayudas_tecnicas/franja_guia_interior`): 0,30 × 4,00 × 0,01 (3 variantes; no corta el paso).
- **Loseta de cruce de franjas guía** (`residencia_y_ayudas_tecnicas/loseta_cruce_guia`): 0,90 × 0,90 × 0,01 (no corta el paso).
- **Franja de botones ante escalera interior** (`residencia_y_ayudas_tecnicas/franja_botones_escalera`): 1,20 × 0,80 × 0,01 (3 variantes; no corta el paso).
- **Bandas antideslizantes en el borde de los peldaños** (`residencia_y_ayudas_tecnicas/bandas_contraste_peldanos`): 1,20 × 0,05 × 0,00 (no corta el paso).
- **Felpudo encastrado de vestíbulo** (`residencia_y_ayudas_tecnicas/felpudo_encastrado_vestibulo`): 1,80 × 1,50 × 0,02 (no corta el paso).

#### Rótulos en braille

- **Placa braille junto a la puerta** (`residencia_y_ayudas_tecnicas/placa_braille_puerta`): 0,20 × 0,03 × 0,15 (colgado a 1,20 m).
- **Directorio con braille y voz** (`residencia_y_ayudas_tecnicas/directorio_braille_voz`): 0,80 × 0,30 × 1,60.
- **Pasamanos con indicación braille de planta** (`residencia_y_ayudas_tecnicas/pasamanos_braille`): 2,00 × 0,07 × 0,05 (colgado a 0,90 m).
- **Rótulo en banderola mal colocado** (`residencia_y_ayudas_tecnicas/rotulo_banderola_bajo`): 0,04 × 0,40 × 0,30 (colgado a 1,70 m).

#### Balizas, llamadas e intercomunicadores

- **Baliza sonora de orientación interior** (`residencia_y_ayudas_tecnicas/baliza_orientacion_interior`): 0,20 × 0,10 × 0,15 (colgado a 2,20 m).
- **Pulsador de llamada de asistencia** (`residencia_y_ayudas_tecnicas/pulsador_asistencia_pared`): 0,10 × 0,05 × 0,10 (colgado a 0,90 m).
- **Intercomunicador accesible de entrada** (`residencia_y_ayudas_tecnicas/intercomunicador_accesible`): 0,20 × 0,08 × 0,35 (colgado a 0,90 m).

#### Accesos y mostradores accesibles

- **Mostrador accesible con bucle magnético** (`residencia_y_ayudas_tecnicas/mostrador_accesible_bucle`): 2,00 × 0,80 × 1,10 (puede esconder un premio).
- **Puerta automática con detector y aviso** (`residencia_y_ayudas_tecnicas/puerta_automatica_detector`): 1,60 × 0,12 × 2,20 (3 variantes).
- **Poste con pulsador de apertura de puerta** (`residencia_y_ayudas_tecnicas/poste_pulsador_puerta`): 0,15 × 0,15 × 1,00.

### Aparatos para ciegos y sordos y perro guía (15)

#### Puestos de lectura y escritura adaptados

- **Lupa televisión en su mesa** (`residencia_y_ayudas_tecnicas/lupa_television_mesa`): 1,00 × 0,70 × 1,25 (puede esconder un premio).
- **Puesto de ordenador con línea braille** (`residencia_y_ayudas_tecnicas/puesto_linea_braille`): 1,20 × 0,70 × 0,76 (puede esconder un premio).
- **Mesa de ajedrez adaptado** (`residencia_y_ayudas_tecnicas/mesa_ajedrez_adaptado`): 0,70 × 0,70 × 0,75 (puede esconder un premio).

#### Braille y relieve

- **Máquina Perkins en su mesa** (`residencia_y_ayudas_tecnicas/maquina_perkins_mesa`): 0,80 × 0,60 × 0,90 (puede esconder un premio).
- **Impresora braille en su mueble** (`residencia_y_ayudas_tecnicas/impresora_braille_mueble`): 0,70 × 0,65 × 1,00 (puede esconder un premio).
- **Horno de láminas en relieve** (`residencia_y_ayudas_tecnicas/horno_relieves`): 0,75 × 0,70 × 1,05.
- **Estantería de libros en braille** (`residencia_y_ayudas_tecnicas/estanteria_libros_braille`): 1,00 × 0,42 × 2,00 (puede esconder un premio).

#### Avisos y aparatos de casa

- **Teléfono de teclas grandes en su mesita** (`residencia_y_ayudas_tecnicas/telefono_teclas_grandes_mesita`): 0,45 × 0,38 × 0,80 (puede esconder un premio).
- **Timbre luminoso** (`residencia_y_ayudas_tecnicas/timbre_luminoso`): 0,15 × 0,06 × 0,15 (colgado a 1,90 m).
- **Reloj parlante en su repisa** (`residencia_y_ayudas_tecnicas/reloj_parlante_repisa`): 0,40 × 0,18 × 0,18 (colgado a 1,10 m).
- **Punto de videointerpretación en lengua de signos** (`residencia_y_ayudas_tecnicas/punto_videointerpretacion`): 0,50 × 0,40 × 1,50.
- **Panel de pictogramas de comunicación** (`residencia_y_ayudas_tecnicas/panel_pictogramas`): 1,20 × 0,04 × 0,90 (colgado a 0,80 m).

#### Perro guía y bastones

- **Bastonero para bastones blancos** (`residencia_y_ayudas_tecnicas/bastonero_bastones_blancos`): 0,40 × 0,20 × 0,60 (puede esconder un premio).
- **Bebedero y comedero del perro guía** (`residencia_y_ayudas_tecnicas/bebedero_comedero_perro_guia`): 0,60 × 0,30 × 0,12 (2 variantes).
- **Cama del perro guía** (`residencia_y_ayudas_tecnicas/cama_perro_guia`): 0,90 × 0,70 × 0,18.

## Sonidos propios (10)

`baliza_orientacion_interior`, `bombo_bingo`, `impresora_braille_martilleo`, `llamada_asistencia`, `maquina_perkins`, `perro_guia_bebe`, `reloj_parlante_hora`, `salvaescaleras_motor`, `telefono_teclas_grandes_tonos`, `timbre_luminoso_dindon`.

## Sonidos que toma del complemento `comun` (3)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`actuador_ayuda_tecnica`, `barra_abatible_clac`, `ducha`.

## Sonidos que toma del complemento `hogar` (10)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `cisterna`, `interruptor`, `juguetes`, `puerta_cristal`, `puerta_electrodomestico`, `puerta_mueble`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (2)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`balon`, `teclado`.

## Sonidos que toma del complemento `oficina_y_comercio` (1)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`silla_ruedas`.

## Sonidos que toma del complemento `calle` (2)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`papel`, `zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (4)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `interfono`, `megafonia`.

## Sonidos que toma del complemento `juego` (3)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cremallera`, `llaves`, `xilofono`.
