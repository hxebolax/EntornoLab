# Hostelería

Bar y cafetería, restaurante, terraza y hotel: barras con sus taburetes, mesas y sillas, juegos de bar, bufé, mobiliario de terraza, vestíbulo, habitación, pasillos y salón de eventos.

- Identificador: `hosteleria`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo hosteleria` a partir de `tools/complementos_serie/hosteleria.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (128)

Medidas por defecto: ancho × fondo × alto, en metros.

### Barra y cafetería (21)

#### Tramos de barra

- **Barra de bar recta** (`hosteleria/barra_recta`): 2,40 × 0,65 × 1,10 (4 variantes; puede esconder un premio).
- **Barra de bar en ele** (`hosteleria/barra_ele`): 3,00 × 2,20 × 1,10 (3 variantes; puede esconder un premio).
- **Barra de bar curva** (`hosteleria/barra_curva`): 3,20 × 1,40 × 1,10 (puede esconder un premio).
- **Tramo abatible de paso de la barra** (`hosteleria/barra_paso_abatible`): 0,70 × 0,65 × 1,10.
- **Tramo bajo accesible de la barra** (`hosteleria/barra_tramo_bajo`): 1,00 × 0,65 × 0,80.
- **Contrabarra** (`hosteleria/contrabarra`): 2,00 × 0,55 × 0,90 (puede esconder un premio).

#### Taburetes de barra

- **Taburete alto de barra fijo al suelo** (`hosteleria/taburete_barra_fijo`): 0,35 × 0,35 × 0,78.
- **Taburete alto de barra con respaldo** (`hosteleria/taburete_barra_respaldo`): 0,42 × 0,45 × 1,05.

#### Aparatos de la barra

- **Cafetera exprés de bar** (`hosteleria/cafetera_expres`): 0,75 × 0,55 × 0,50 (3 variantes; colgado a 0,90 m).
- **Molinillo de café** (`hosteleria/molinillo_cafe`): 0,22 × 0,35 × 0,60 (colgado a 0,90 m).
- **Columna de grifos de cerveza** (`hosteleria/grifo_cerveza`): 0,20 × 0,20 × 0,45 (3 variantes; colgado a 1,10 m).
- **Cámara botellero bajo la barra** (`hosteleria/camara_botellero`): 1,50 × 0,55 × 0,85 (3 variantes; puede esconder un premio).
- **Lavavasos de barra** (`hosteleria/lavavasos`): 0,45 × 0,50 × 0,70 (puede esconder un premio).
- **Caja registradora del bar** (`hosteleria/tpv_bar`): 0,38 × 0,40 × 0,38 (colgado a 1,10 m; puede esconder un premio).
- **Cubitera con pie** (`hosteleria/cubitera_pie`): 0,25 × 0,25 × 0,75 (puede esconder un premio).

#### Vitrinas y botelleros

- **Vitrina de tapas sobre la barra** (`hosteleria/vitrina_tapas`): 1,00 × 0,38 × 0,28 (3 variantes; colgado a 1,10 m; puede esconder un premio).
- **Expositor de bollería de mostrador** (`hosteleria/expositor_bolleria`): 0,50 × 0,40 × 0,45 (colgado a 1,10 m; puede esconder un premio).
- **Vitrina giratoria de tartas** (`hosteleria/vitrina_tartas`): 0,60 × 0,60 × 1,80 (puede esconder un premio).

#### Colgado sobre la barra

- **Botellero de pared tras la barra** (`hosteleria/botellero_pared`): 1,50 × 0,20 × 0,90 (colgado a 1,20 m; puede esconder un premio).
- **Colgador de copas sobre la barra** (`hosteleria/copas_colgadas`): 1,20 × 0,35 × 0,25 (colgado a 1,75 m).
- **Jamones colgados sobre la barra** (`hosteleria/jamones_colgados`): 1,50 × 0,30 × 0,70 (colgado a 1,65 m).

### Sala del bar y juegos (19)

#### Mesas de bar

- **Mesa alta de bar con reposapiés** (`hosteleria/mesa_alta_bar`): 0,70 × 0,60 × 1,10 (3 variantes).
- **Barril usado de mesa** (`hosteleria/barril_mesa`): 0,70 × 0,70 × 0,95 (puede esconder un premio).
- **Velador de mármol** (`hosteleria/velador_marmol`): 0,60 × 0,60 × 0,72 (3 variantes).
- **Mesa de bar de pie central** (`hosteleria/mesa_bar_pie_central`): 0,70 × 0,70 × 0,75 (4 variantes).

#### Sillas y bancos de bar

- **Silla apilable de hostelería** (`hosteleria/silla_apilable_bar`): 0,45 × 0,50 × 0,82.
- **Pila de sillas apiladas** (`hosteleria/sillas_apiladas`): 0,50 × 0,65 × 1,40.
- **Banco corrido de pared tapizado** (`hosteleria/banco_corrido_pared`): 2,40 × 0,55 × 0,95 (4 variantes; puede esconder un premio).
- **Banco corrido de rincón** (`hosteleria/banco_corrido_rincon`): 2,20 × 2,20 × 0,95 (puede esconder un premio).
- **Reservado de dos bancos y mesa** (`hosteleria/reservado_bar`): 1,60 × 1,20 × 1,10 (puede esconder un premio).

#### Juegos y máquinas de bar

- **Máquina tragaperras** (`hosteleria/tragaperras`): 0,55 × 0,55 × 1,75 (puede esconder un premio).
- **Máquina de tabaco** (`hosteleria/maquina_tabaco`): 0,65 × 0,45 × 1,80 (puede esconder un premio).
- **Máquina de bolas y frutos secos** (`hosteleria/maquina_bolas`): 0,30 × 0,30 × 1,10 (puede esconder un premio).
- **Futbolín** (`hosteleria/futbolin`): 1,50 × 1,15 × 0,92 (puede esconder un premio).
- **Mesa de billar** (`hosteleria/mesa_billar`): 2,54 × 1,42 × 0,80 (3 variantes; puede esconder un premio).
- **Taquera de pared** (`hosteleria/taquera_billar`): 0,60 × 0,12 × 1,50 (colgado a 0,50 m).
- **Diana de dardos electrónica de pared** (`hosteleria/diana_dardos`): 0,50 × 0,10 × 0,65 (2 variantes; colgado a 1,30 m).

#### Complementos de la sala

- **Televisor de bar colgado en un brazo** (`hosteleria/tv_brazo_bar`): 1,10 × 0,40 × 0,65 (colgado a 1,70 m).
- **Percha de pared con balda para sombreros** (`hosteleria/percha_pared_balda`): 1,00 × 0,30 × 0,30 (colgado a 1,55 m; puede esconder un premio).
- **Paragüero de rejilla de local** (`hosteleria/paraguero_rejilla`): 0,60 × 0,30 × 0,50 (puede esconder un premio).

### Restaurante (21)

#### Mesas de restaurante

- **Mesa redonda de banquete** (`hosteleria/mesa_banquete_redonda`): 1,60 × 1,60 × 0,75 (4 variantes; puede esconder un premio).
- **Mesa de restaurante con mantel** (`hosteleria/mesa_restaurante_vestida`): 1,20 × 0,80 × 0,75 (3 variantes; puede esconder un premio).
- **Mesa corrida de restaurante** (`hosteleria/mesa_corrida_restaurante`): 2,40 × 0,90 × 0,75 (3 variantes; puede esconder un premio).

#### Asientos de restaurante

- **Silla tapizada de restaurante** (`hosteleria/silla_restaurante_tapizada`): 0,48 × 0,55 × 0,92.
- **Trona de restaurante** (`hosteleria/trona_restaurante`): 0,55 × 0,55 × 0,75.

#### Servicio de sala

- **Aparador de camareros** (`hosteleria/aparador_camareros`): 1,20 × 0,50 × 1,00 (puede esconder un premio).
- **Mueble de cubiertos y servilletas** (`hosteleria/mueble_cubiertos`): 0,70 × 0,45 × 0,90 (puede esconder un premio).
- **Carro de servicio de camarero** (`hosteleria/carro_servicio_sala`): 0,50 × 0,85 × 0,95 (puede esconder un premio).
- **Carro de postres** (`hosteleria/carro_postres`): 0,50 × 0,90 × 1,00 (puede esconder un premio).
- **Mesa auxiliar de trinchar** (`hosteleria/gueridon`): 0,60 × 0,45 × 0,75.
- **Atril de reservas del maître** (`hosteleria/atril_reservas`): 0,55 × 0,45 × 1,15 (puede esconder un premio).
- **Mostrador de caja del restaurante** (`hosteleria/caja_restaurante`): 1,40 × 0,60 × 1,05 (puede esconder un premio).

#### Bufé

- **Bufé caliente con cubetas** (`hosteleria/bufe_caliente`): 1,80 × 0,75 × 0,90 (3 variantes; puede esconder un premio).
- **Isla de bufé frío** (`hosteleria/bufe_frio_isla`): 2,00 × 1,10 × 0,90 (puede esconder un premio).
- **Mesa de bufé con faldón** (`hosteleria/mesa_bufe`): 1,80 × 0,75 × 0,75 (3 variantes; puede esconder un premio).

#### Separadores y puertas

- **Separador de ambientes de media altura** (`hosteleria/separador_ambientes`): 1,20 × 0,35 × 1,20 (3 variantes; puede esconder un premio).
- **Biombo plegable de tres hojas** (`hosteleria/biombo_tres_hojas`): 1,40 × 0,40 × 1,75.
- **Puerta de vaivén de la cocina** (`hosteleria/puerta_vaiven_cocina`): 0,90 × 0,06 × 2,05.

#### Bodega y vivero

- **Vivero de marisco** (`hosteleria/vivero_marisco`): 1,20 × 0,60 × 1,30.
- **Bodega climatizada de vinos** (`hosteleria/bodega_climatizada`): 0,70 × 0,68 × 1,85 (3 variantes; puede esconder un premio).
- **Botellero de vinos de casillas** (`hosteleria/botellero_vinos`): 1,00 × 0,33 × 1,80 (puede esconder un premio).

### Terraza (18)

#### Mesas y asientos de terraza

- **Mesa de aluminio de terraza** (`hosteleria/mesa_aluminio_terraza`): 0,70 × 0,70 × 0,72 (3 variantes).
- **Silla de aluminio de terraza con brazos** (`hosteleria/silla_aluminio_terraza`): 0,56 × 0,58 × 0,75.
- **Terraza recogida y encadenada** (`hosteleria/terraza_recogida`): 1,50 × 1,00 × 1,50.
- **Sofá de palés de terraza** (`hosteleria/sofa_pales_terraza`): 1,80 × 0,80 × 0,70 (puede esconder un premio).
- **Barra exterior en U** (`hosteleria/barra_exterior_u`): 2,50 × 2,00 × 1,10 (puede esconder un premio).

#### Sombra, calor y fresco

- **Sombrilla de brazo lateral** (`hosteleria/sombrilla_brazo_lateral`): 1,00 × 1,00 × 2,60.
- **Base de sombrilla sin sombrilla** (`hosteleria/base_sombrilla_suelta`): 0,50 × 0,50 × 0,40.
- **Estufa de terraza de seta** (`hosteleria/estufa_seta`): 0,50 × 0,50 × 2,20 (2 variantes).
- **Calefactor de infrarrojos colgado** (`hosteleria/calefactor_colgado`): 0,80 × 0,15 × 0,15 (colgado a 1,90 m).
- **Línea de nebulizadores** (`hosteleria/nebulizadores_terraza`): 4,00 × 0,05 × 0,05 (no corta el paso; colgado a 2,10 m).

#### Cerramientos de terraza

- **Mampara cortavientos de cristal** (`hosteleria/mampara_cortavientos`): 1,50 × 0,40 × 1,50.
- **Valla de lona de terraza** (`hosteleria/valla_lona_terraza`): 1,50 × 0,40 × 0,90.
- **Jardinera separadora con celosía** (`hosteleria/jardinera_celosia`): 1,00 × 0,40 × 1,50 (puede esconder un premio).
- **Cortina transparente de terraza** (`hosteleria/cortina_terraza_transparente`): 2,50 × 0,05 × 2,10.

#### En la acera y la fachada

- **Tarima de terraza sobre la calzada** (`hosteleria/tarima_terraza`): 5,00 × 2,00 × 0,15 (no corta el paso).
- **Atril del menú en la acera** (`hosteleria/atril_menu_acera`): 0,50 × 0,45 × 1,40.
- **Repisa de barra en la ventana** (`hosteleria/repisa_barra_ventana`): 1,80 × 0,30 × 0,08 (colgado a 1,00 m).
- **Cenicero de pared exterior** (`hosteleria/cenicero_pared_exterior`): 0,12 × 0,10 × 0,40 (colgado a 1,00 m).

### Vestíbulo y recepción de hotel (14)

#### Recepción

- **Mostrador de recepción de hotel con tramo bajo** (`hosteleria/mostrador_recepcion_hotel`): 3,00 × 0,80 × 1,10 (3 variantes; puede esconder un premio).
- **Casillero de llaves y correo** (`hosteleria/casillero_llaves`): 1,20 × 0,15 × 0,80 (colgado a 1,10 m; puede esconder un premio).
- **Mostrador del conserje** (`hosteleria/mostrador_conserje`): 1,20 × 0,60 × 1,10 (puede esconder un premio).
- **Quiosco de registro automático de hotel** (`hosteleria/quiosco_registro_hotel`): 0,55 × 0,50 × 1,50.
- **Teléfono interior de cortesía** (`hosteleria/telefono_cortesia`): 0,22 × 0,10 × 0,25 (colgado a 1,20 m).
- **Expositor de folletos turísticos** (`hosteleria/expositor_folletos`): 0,50 × 0,35 × 1,60 (puede esconder un premio).

#### Zona de estar del vestíbulo

- **Sofá chéster de vestíbulo** (`hosteleria/sofa_chester_vestibulo`): 2,00 × 0,90 × 0,75 (2 variantes; puede esconder un premio).
- **Butaca de cubo de vestíbulo** (`hosteleria/butaca_cubo_vestibulo`): 0,75 × 0,75 × 0,75.
- **Mesa de centro de vestíbulo de cristal** (`hosteleria/mesa_centro_vestibulo`): 0,90 × 0,90 × 0,42.
- **Asiento circular de vestíbulo** (`hosteleria/borne_vestibulo`): 1,60 × 1,60 × 1,10.
- **Mesa redonda con centro de flores** (`hosteleria/mesa_floral_vestibulo`): 1,20 × 1,20 × 1,50.

#### Equipajes

- **Carro portamaletas del botones** (`hosteleria/carro_portamaletas_botones`): 0,65 × 1,10 × 1,85 (puede esconder un premio).
- **Banco de equipajes** (`hosteleria/banco_equipajes`): 1,50 × 0,50 × 0,45 (puede esconder un premio).
- **Maletas de un grupo en el vestíbulo** (`hosteleria/maletas_grupo`): 2,00 × 1,20 × 0,70 (puede esconder un premio).

### Habitación de hotel (15)

#### Camas de hotel

- **Cama de hotel con cabecero corrido** (`hosteleria/cama_hotel_cabecero_corrido`): 2,60 × 2,05 × 1,10 (3 variantes; puede esconder un premio).
- **Dos camas de hotel con cabecero común** (`hosteleria/camas_gemelas_hotel`): 2,40 × 2,05 × 1,10 (puede esconder un premio).
- **Cama supletoria plegable** (`hosteleria/cama_supletoria`): 0,90 × 1,95 × 0,40.
- **Cuna de viaje de hotel** (`hosteleria/cuna_viaje_hotel`): 0,70 × 1,25 × 0,75 (puede esconder un premio).

#### Muebles de la habitación

- **Portamaletas plegable de tijera** (`hosteleria/portamaletas_plegable`): 0,60 × 0,45 × 0,50 (puede esconder un premio).
- **Escritorio-tocador de hotel** (`hosteleria/escritorio_tocador_hotel`): 1,40 × 0,50 × 0,75 (3 variantes; puede esconder un premio).
- **Armario abierto de hotel con perchas** (`hosteleria/armario_abierto_hotel`): 0,90 × 0,58 × 2,10 (puede esconder un premio).
- **Galán de noche** (`hosteleria/galan_noche`): 0,45 × 0,35 × 1,10.
- **Butaca de lectura con reposapiés** (`hosteleria/butaca_lectura_reposapies`): 0,75 × 1,35 × 1,00.

#### Aparatos de la habitación

- **Minibar** (`hosteleria/minibar`): 0,45 × 0,45 × 0,55 (puede esconder un premio).
- **Caja fuerte de armario de hotel** (`hosteleria/caja_fuerte_armario`): 0,40 × 0,35 × 0,20 (colgado a 1,10 m; puede esconder un premio).
- **Televisor de habitación en la pared** (`hosteleria/tv_pared_habitacion`): 0,95 × 0,08 × 0,55 (colgado a 1,10 m).
- **Bandeja de cortesía con hervidor** (`hosteleria/bandeja_hervidor`): 0,40 × 0,30 × 0,25 (colgado a 0,75 m; puede esconder un premio).
- **Prensa de pantalones de pared** (`hosteleria/prensa_pantalones`): 0,45 × 0,12 × 1,05 (colgado a 0,10 m).
- **Secador de pelo de pared** (`hosteleria/secador_pared_hotel`): 0,20 × 0,12 × 0,25 (colgado a 1,30 m).

### Pasillos y desayunos de hotel (12)

#### Carros de servicio del hotel

- **Carro de camarera de pisos** (`hosteleria/carro_camarera_pisos`): 0,55 × 1,50 × 1,25 (puede esconder un premio).
- **Carro de lencería de hotel** (`hosteleria/carro_lenceria_hotel`): 0,70 × 0,90 × 1,60 (puede esconder un premio).
- **Carro de servicio de habitaciones** (`hosteleria/carro_servicio_habitaciones`): 1,00 × 0,60 × 0,76 (puede esconder un premio).

#### En el pasillo

- **Bandeja dejada en el suelo del pasillo** (`hosteleria/bandeja_pasillo`): 0,50 × 0,35 × 0,12.
- **Puerta de habitación con cerradura de tarjeta** (`hosteleria/puerta_habitacion_tarjeta`): 0,90 × 0,06 × 2,05.
- **Aplique de pasillo** (`hosteleria/aplique_pasillo`): 0,20 × 0,15 × 0,30 (colgado a 1,60 m).
- **Máquina de hielo de pasillo** (`hosteleria/maquina_hielo`): 0,60 × 0,70 × 1,80 (puede esconder un premio).
- **Máquina limpiazapatos** (`hosteleria/limpiazapatos`): 0,45 × 0,35 × 0,85.

#### Bufé de desayunos

- **Tostadora de cinta** (`hosteleria/tostadora_cinta`): 0,45 × 0,50 × 0,42 (colgado a 0,75 m).
- **Dispensador de zumos** (`hosteleria/dispensador_zumos`): 0,50 × 0,42 × 0,70 (2 variantes; colgado a 0,75 m).
- **Dispensador de cereales** (`hosteleria/dispensador_cereales`): 0,45 × 0,25 × 0,65 (3 variantes; colgado a 0,75 m).
- **Columna calientaplatos** (`hosteleria/calientaplatos`): 0,45 × 0,45 × 0,90 (puede esconder un premio).

### Salón de eventos (8)

#### Montaje del salón

- **Tabique móvil de salón** (`hosteleria/tabique_movil_salon`): 1,20 × 0,10 × 2,80.
- **Panel de photocall** (`hosteleria/photocall_eventos`): 2,50 × 0,60 × 2,20.
- **Carro de mesas de banquete plegadas** (`hosteleria/carro_mesas_plegadas`): 0,90 × 1,90 × 1,90.

#### Mobiliario de eventos

- **Mesa presidencial** (`hosteleria/mesa_presidencial`): 3,60 × 0,80 × 0,75 (3 variantes; puede esconder un premio).
- **Mesa alta de cóctel con funda** (`hosteleria/mesa_coctel_funda`): 0,80 × 0,80 × 1,10.
- **Fila de sillas de banquete enlazadas** (`hosteleria/sillas_banquete_enlazadas`): 2,50 × 0,55 × 0,90 (4 variantes).
- **Barra móvil de eventos** (`hosteleria/barra_movil_eventos`): 1,50 × 0,60 × 1,10 (puede esconder un premio).
- **Guardarropa con mostrador** (`hosteleria/guardarropa_mostrador`): 2,00 × 0,50 × 1,00 (puede esconder un premio).

## Sonidos propios (10)

`billar_bolas`, `cafetera_vapor`, `cerveza_tirar`, `dardo_diana`, `futbolin_golpe`, `maquina_hielo_hotel`, `molinillo_cafe`, `nebulizador_terraza`, `tragaperras_musica`, `vivero_burbujas`.

## Sonidos que toma del complemento `comun` (4)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`estufa_terraza_gas`, `hielo_cubitos`, `portamaletas_ruedas`, `vajilla_tintineo`.

## Sonidos que toma del complemento `hogar` (9)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `interruptor`, `lavavajillas`, `puerta_cristal`, `puerta_electrodomestico`, `puerta_mueble`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (1)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`teclado`.

## Sonidos que toma del complemento `oficina_y_comercio` (3)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_registradora`, `cortina`, `garrafa`.

## Sonidos que toma del complemento `calle` (2)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`papel`, `vidrio`.

## Sonidos que toma del complemento `transporte` (5)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `interfono`, `taquilla`, `teclas_cajero`.

## Sonidos que toma del complemento `juego` (5)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_fuerte`, `campana`, `cremallera`, `llaves`, `monedas`.
