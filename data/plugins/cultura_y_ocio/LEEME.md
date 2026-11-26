# Cultura y ocio

Museo y sala de exposiciones, cine, teatro y auditorio, biblioteca, sala de conciertos y discoteca, bolera y recreativos, y centro cívico.

- Identificador: `cultura_y_ocio`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo cultura_y_ocio` a partir de `tools/complementos_serie/cultura_y_ocio.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (126)

Medidas por defecto: ancho × fondo × alto, en metros.

### Museo y exposiciones (31)

#### Vitrinas y peanas

- **Vitrina de mesa** (`cultura_y_ocio/vitrina_mesa`): 1,20 × 0,60 × 0,95 (3 variantes).
- **Vitrina vertical de cristal** (`cultura_y_ocio/vitrina_vertical`): 0,60 × 0,60 × 2,00 (2 variantes).
- **Vitrina mural en voladizo** (`cultura_y_ocio/vitrina_mural_volada`): 1,20 × 0,30 × 0,80 (colgado a 0,90 m).
- **Peana con escultura** (`cultura_y_ocio/peana_escultura`): 0,50 × 0,50 × 1,60.
- **Peana con urna de cristal** (`cultura_y_ocio/peana_urna`): 0,50 × 0,50 × 1,50.
- **Tarima baja de exposición** (`cultura_y_ocio/tarima_obras`): 2,00 × 1,50 × 0,15.

#### Obras y montajes

- **Escultura grande exenta** (`cultura_y_ocio/escultura_exenta`): 2,00 × 1,50 × 2,50.
- **Esqueleto montado sobre tarima** (`cultura_y_ocio/esqueleto_montado`): 4,00 × 1,50 × 3,00.
- **Móvil colgante** (`cultura_y_ocio/movil_colgante`): 2,00 × 2,00 × 0,80 (colgado a 1,70 m).
- **Instalación de suelo** (`cultura_y_ocio/instalacion_suelo`): 2,50 × 2,00 × 0,08 (no corta el paso).
- **Maqueta sobre mesa** (`cultura_y_ocio/maqueta_mesa`): 1,50 × 1,20 × 1,10.

#### Barreras y distancias

- **Cuadro grande con barrera baja** (`cultura_y_ocio/cuadro_barrera`): 2,50 × 0,80 × 0,40.
- **Cordón separador bajo** (`cultura_y_ocio/cordon_bajo`): 2,00 × 0,10 × 0,40.
- **Catenaria de terciopelo** (`cultura_y_ocio/catenaria_terciopelo`): 1,50 × 0,32 × 0,95.
- **Cortina de sala oscura** (`cultura_y_ocio/cortina_sala_oscura`): 1,40 × 0,15 × 2,30.

#### Paneles e información

- **Panel expositor autoportante** (`cultura_y_ocio/panel_expositor`): 1,20 × 0,40 × 2,00 (3 variantes).
- **Panel en zigzag** (`cultura_y_ocio/panel_zigzag`): 3,00 × 0,80 × 2,00.
- **Atril informativo inclinado** (`cultura_y_ocio/atril_informativo`): 0,60 × 0,40 × 0,90.
- **Tótem interactivo de museo** (`cultura_y_ocio/totem_interactivo_museo`): 0,60 × 0,40 × 1,80.
- **Proyector en trípode** (`cultura_y_ocio/proyector_tripode`): 0,80 × 0,80 × 1,30.

#### Guías y estaciones táctiles

- **Maqueta táctil** (`cultura_y_ocio/maqueta_tactil`): 1,20 × 0,80 × 0,80.
- **Estación táctil con audio** (`cultura_y_ocio/estacion_tactil_audio`): 0,80 × 0,50 × 0,95.
- **Punto de recogida de audioguías** (`cultura_y_ocio/punto_audioguias`): 1,20 × 0,50 × 1,20 (puede esconder un premio).
- **Cargador mural de signoguías** (`cultura_y_ocio/cargador_signoguias`): 0,60 × 0,15 × 0,50 (colgado a 1,00 m).

#### Entrada, descanso y tienda

- **Banco de sala de museo** (`cultura_y_ocio/banco_museo`): 1,80 × 0,55 × 0,45 (3 variantes).
- **Banco circular con respaldo central** (`cultura_y_ocio/banco_circular_museo`): 1,60 × 1,60 × 0,90.
- **Carro de asientos plegables** (`cultura_y_ocio/carro_asientos_plegables`): 0,60 × 1,00 × 1,20.
- **Mostrador de entradas del museo** (`cultura_y_ocio/mostrador_entradas_museo`): 2,40 × 0,80 × 1,10 (3 variantes; puede esconder un premio).
- **Consigna de bolsos del museo** (`cultura_y_ocio/consigna_museo`): 1,20 × 0,45 × 1,80 (puede esconder un premio).
- **Arco detector de la entrada** (`cultura_y_ocio/arco_detector_museo`): 0,90 × 0,60 × 2,20 (no corta el paso).
- **Mesa isla de la tienda del museo** (`cultura_y_ocio/mesa_tienda_museo`): 1,40 × 1,00 × 0,90 (puede esconder un premio).

### Cine (14)

#### Vestíbulo y venta

- **Taquilla de cine** (`cultura_y_ocio/taquilla_cine`): 1,80 × 1,20 × 2,40.
- **Mostrador de palomitas** (`cultura_y_ocio/mostrador_palomitas`): 3,00 × 0,80 × 1,10.
- **Cartelera luminosa de pared** (`cultura_y_ocio/cartelera_luminosa`): 1,00 × 0,12 × 1,50 (colgado a 0,70 m).
- **Figura de cartón de estreno** (`cultura_y_ocio/figura_carton_estreno`): 1,50 × 0,50 × 1,90.
- **Atril de control de entradas** (`cultura_y_ocio/atril_control_entradas`): 0,50 × 0,40 × 1,10.
- **Contenedor de gafas 3D** (`cultura_y_ocio/contenedor_gafas_3d`): 0,50 × 0,50 × 1,00 (puede esconder un premio).

#### Butacas y pasillos

- **Fila de butacas de cine** (`cultura_y_ocio/fila_butacas_cine`): 3,40 × 0,75 × 1,05 (5 variantes).
- **Butaca de cine suelta** (`cultura_y_ocio/butaca_cine_suelta`): 0,60 × 0,75 × 1,05 (2 variantes).
- **Espacio reservado para silla de ruedas** (`cultura_y_ocio/espacio_silla_ruedas`): 0,90 × 1,30 × 0,01 (no corta el paso).
- **Escalón iluminado de pasillo** (`cultura_y_ocio/escalon_iluminado`): 1,20 × 0,30 × 0,15 (no corta el paso).
- **Alzadores para niños apilados** (`cultura_y_ocio/alzadores_apilados`): 0,50 × 0,45 × 0,90.

#### Pantalla, proyección y sonido

- **Pantalla de cine** (`cultura_y_ocio/pantalla_cine`): 5,00 × 0,30 × 2,80 (3 variantes; colgado a 1,00 m).
- **Proyector de cabina de cine** (`cultura_y_ocio/proyector_cabina`): 0,90 × 1,50 × 1,70.
- **Altavoz envolvente de pared** (`cultura_y_ocio/altavoz_envolvente`): 0,40 × 0,25 × 0,50 (colgado a 1,80 m).

### Teatro y auditorio (25)

#### Sala y palcos

- **Fila de butacas de patio** (`cultura_y_ocio/fila_butacas_patio`): 3,00 × 0,65 × 0,95 (4 variantes).
- **Palco de teatro** (`cultura_y_ocio/palco_teatro`): 2,00 × 2,00 × 1,10.

#### Escenario y telones

- **Borde de escenario** (`cultura_y_ocio/borde_escenario`): 5,00 × 0,40 × 0,01 (no corta el paso).
- **Foso de orquesta** (`cultura_y_ocio/foso_orquesta`): 5,00 × 2,50 × 0,10.
- **Telón de boca** (`cultura_y_ocio/telon_boca`): 5,00 × 0,30 × 5,00.
- **Pata lateral de bambalinas** (`cultura_y_ocio/pata_bambalinas`): 1,50 × 0,15 × 5,00.
- **Concha del apuntador** (`cultura_y_ocio/concha_apuntador`): 1,00 × 0,60 × 0,40.
- **Escalera de acceso al escenario** (`cultura_y_ocio/escalera_escenario`): 1,20 × 1,00 × 0,90.
- **Barra de tiros y contrapesos** (`cultura_y_ocio/barra_tiros`): 3,00 × 0,50 × 5,00.

#### Orquesta e instrumentos

- **Tarima de director con atril** (`cultura_y_ocio/tarima_director`): 1,10 × 1,10 × 1,10.
- **Semicírculo de sillas y atriles de orquesta** (`cultura_y_ocio/corro_atriles`): 4,00 × 1,80 × 1,20.
- **Arpa** (`cultura_y_ocio/arpa`): 0,55 × 1,00 × 1,85.
- **Timbales de orquesta** (`cultura_y_ocio/timbales_orquesta`): 2,50 × 1,20 × 0,85.
- **Contrabajo en su soporte** (`cultura_y_ocio/contrabajo_apoyado`): 0,70 × 0,55 × 1,90.
- **Batería** (`cultura_y_ocio/bateria`): 1,60 × 1,40 × 1,30.

#### Sonido, luces y cables

- **Baúl de gira con ruedas** (`cultura_y_ocio/baul_gira`): 1,20 × 0,60 × 0,70 (puede esconder un premio).
- **Amplificador de guitarra** (`cultura_y_ocio/amplificador_guitarra`): 0,60 × 0,30 × 0,60 (2 variantes).
- **Monitor de escenario en cuña** (`cultura_y_ocio/monitor_cuna`): 0,60 × 0,40 × 0,35.
- **Mesa de mezclas** (`cultura_y_ocio/mesa_mezclas`): 1,80 × 1,00 × 1,00.
- **Trípode de foco** (`cultura_y_ocio/tripode_foco`): 1,20 × 1,20 × 3,00.
- **Pie de micrófono** (`cultura_y_ocio/pie_microfono`): 0,30 × 0,30 × 1,50 (2 variantes).
- **Cables sueltos por el suelo** (`cultura_y_ocio/cables_sueltos`): 1,50 × 0,80 × 0,03 (no corta el paso).

#### Camerinos y guardarropa

- **Mostrador de guardarropa** (`cultura_y_ocio/mostrador_guardarropa`): 2,00 × 0,70 × 1,05 (puede esconder un premio).
- **Tocador de camerino** (`cultura_y_ocio/tocador_camerino`): 1,20 × 0,50 × 1,90 (puede esconder un premio).
- **Burro de vestuario de teatro** (`cultura_y_ocio/burro_vestuario`): 1,80 × 0,60 × 1,90 (puede esconder un premio).

### Biblioteca (20)

#### Estanterías y archivo

- **Estantería de doble cara** (`cultura_y_ocio/estanteria_doble_cara`): 2,70 × 0,60 × 2,00 (5 variantes; puede esconder un premio).
- **Armario compacto sobre raíles** (`cultura_y_ocio/armario_compacto`): 3,00 × 3,00 × 2,20 (puede esconder un premio).
- **Fichero de fichas de biblioteca** (`cultura_y_ocio/fichero_fichas`): 1,00 × 0,50 × 1,30 (puede esconder un premio).
- **Planero de mapas** (`cultura_y_ocio/planero`): 1,30 × 0,95 × 0,90 (puede esconder un premio).
- **Taburete rodante de biblioteca** (`cultura_y_ocio/taburete_rodante_biblioteca`): 0,44 × 0,44 × 0,43.
- **Escalera de biblioteca con ruedas** (`cultura_y_ocio/escalera_rodante_biblioteca`): 0,65 × 1,00 × 1,80.

#### Puestos de lectura y estudio

- **Mesa de lectura larga con lámparas** (`cultura_y_ocio/mesa_lectura_lamparas`): 3,60 × 1,20 × 0,76 (3 variantes; puede esconder un premio).
- **Puesto de estudio con separadores** (`cultura_y_ocio/puesto_estudio`): 0,90 × 0,70 × 1,20 (3 variantes; puede esconder un premio).
- **Puesto de consulta del catálogo** (`cultura_y_ocio/puesto_consulta_catalogo`): 0,70 × 0,55 × 1,30.
- **Globo terráqueo de pie** (`cultura_y_ocio/globo_terraqueo`): 0,60 × 0,60 × 1,20.

#### Préstamo y devolución

- **Mostrador de préstamo** (`cultura_y_ocio/mostrador_prestamo`): 3,00 × 1,60 × 1,05 (puede esconder un premio).
- **Buzón de devolución de libros** (`cultura_y_ocio/buzon_devolucion`): 0,60 × 0,60 × 1,20 (puede esconder un premio).
- **Máquina de autopréstamo** (`cultura_y_ocio/maquina_autoprestamo`): 0,70 × 0,60 × 1,40.

#### Prensa y novedades

- **Expositor de novedades** (`cultura_y_ocio/expositor_novedades`): 0,90 × 0,90 × 1,40 (puede esconder un premio).
- **Revistero inclinado de pared** (`cultura_y_ocio/revistero_inclinado`): 1,00 × 0,40 × 1,90 (puede esconder un premio).
- **Colgador de periódicos en barra** (`cultura_y_ocio/hemeroteca_barras`): 1,00 × 0,50 × 1,20.

#### Zona infantil y de descanso

- **Asiento curvo modular de lectura** (`cultura_y_ocio/asiento_curvo_lectura`): 2,40 × 1,20 × 0,80.
- **Cubeta de cuentos infantil** (`cultura_y_ocio/cubeta_cuentos`): 0,80 × 0,80 × 0,55 (puede esconder un premio).
- **Rincón infantil con cojines** (`cultura_y_ocio/rincon_cojines`): 2,50 × 2,50 × 0,30 (puede esconder un premio).
- **Grada de cuentacuentos** (`cultura_y_ocio/grada_cuentacuentos`): 2,40 × 1,20 × 0,60.

### Sala de conciertos y discoteca (8)

#### Cabina y pista

- **Cabina de DJ** (`cultura_y_ocio/cabina_dj`): 2,00 × 1,20 × 1,10.
- **Pista de baile** (`cultura_y_ocio/pista_baile`): 5,00 × 5,00 × 0,02 (no corta el paso).
- **Podio de baile** (`cultura_y_ocio/podio_baile`): 1,20 × 1,20 × 0,80.
- **Valla antiavalancha** (`cultura_y_ocio/valla_antiavalancha`): 1,20 × 1,20 × 1,20 (3 variantes).

#### Altavoces y luces

- **Torre de altavoces** (`cultura_y_ocio/torre_altavoces`): 0,80 × 0,70 × 2,00.
- **Bafle sobre trípode** (`cultura_y_ocio/bafle_tripode`): 0,90 × 0,90 × 2,00.
- **Torre de luces de celosía** (`cultura_y_ocio/torre_luces`): 1,50 × 1,50 × 4,00.
- **Bola de espejos** (`cultura_y_ocio/bola_espejos`): 0,50 × 0,50 × 0,50 (no corta el paso; colgado a 2,30 m).

### Bolera y recreativos (17)

#### Bolera

- **Pista de bolos** (`cultura_y_ocio/pista_bolos`): 1,70 × 18,30 × 0,02 (3 variantes; no corta el paso).
- **Línea de falta de la bolera** (`cultura_y_ocio/linea_falta_bolos`): 1,10 × 0,10 × 0,01 (no corta el paso).
- **Retorno de bolas** (`cultura_y_ocio/retorno_bolas`): 0,60 × 1,50 × 0,70 (puede esconder un premio).
- **Estante de bolas** (`cultura_y_ocio/estante_bolas`): 1,80 × 0,50 × 1,30 (puede esconder un premio).
- **Consola de puntuación** (`cultura_y_ocio/consola_puntuacion`): 0,50 × 0,45 × 1,10.
- **Banco curvo de bolera** (`cultura_y_ocio/banco_curvo_bolera`): 2,50 × 1,30 × 0,80.
- **Mostrador de alquiler de zapatos** (`cultura_y_ocio/mostrador_zapatos_bolera`): 2,50 × 0,70 × 1,05 (puede esconder un premio).

#### Máquinas recreativas

- **Máquina recreativa** (`cultura_y_ocio/maquina_recreativa`): 0,65 × 0,85 × 1,75.
- **Máquina de pinball** (`cultura_y_ocio/pinball`): 0,75 × 1,40 × 1,90.
- **Simulador de coche** (`cultura_y_ocio/simulador_coche`): 1,00 × 1,80 × 1,90.
- **Grúa de peluches** (`cultura_y_ocio/grua_peluches`): 0,80 × 0,85 × 1,90 (puede esconder un premio).
- **Canasta recreativa** (`cultura_y_ocio/canasta_recreativa`): 0,90 × 2,40 × 2,50.
- **Máquina de baile** (`cultura_y_ocio/maquina_baile`): 1,80 × 2,20 × 2,20.
- **Máquina de cambio de monedas** (`cultura_y_ocio/cambio_monedas`): 0,50 × 0,35 × 1,60.

#### Mesas de juego

- **Mesa de hockey de aire** (`cultura_y_ocio/hockey_aire`): 1,25 × 2,40 × 0,80.
- **Mesa de ajedrez** (`cultura_y_ocio/mesa_ajedrez`): 0,80 × 0,80 × 0,74 (puede esconder un premio).
- **Ajedrez gigante de suelo** (`cultura_y_ocio/ajedrez_gigante`): 3,00 × 3,00 × 0,60.

### Centro cívico (11)

#### Sala polivalente

- **Mesas plegables apiladas** (`cultura_y_ocio/mesas_plegables_apiladas`): 1,85 × 0,60 × 0,90.
- **Escenario modular de tarimas** (`cultura_y_ocio/escenario_modular`): 4,00 × 2,00 × 0,40 (4 variantes).
- **Atril de orador** (`cultura_y_ocio/atril_orador`): 0,60 × 0,50 × 1,20 (puede esconder un premio).
- **Pantalla de proyección con trípode** (`cultura_y_ocio/pantalla_portatil`): 1,80 × 0,80 × 2,20.

#### Talleres

- **Caballete de pintura** (`cultura_y_ocio/caballete_pintura`): 0,60 × 0,70 × 1,80.
- **Torno de alfarero** (`cultura_y_ocio/torno_alfarero`): 0,70 × 0,90 × 0,55.
- **Horno de cerámica** (`cultura_y_ocio/horno_ceramica`): 0,90 × 0,90 × 1,00 (puede esconder un premio).
- **Telar de bajo lizo** (`cultura_y_ocio/telar`): 1,50 × 1,30 × 1,50.

#### Participación y anuncios

- **Mesa con urna de votación** (`cultura_y_ocio/mesa_urna_votacion`): 1,60 × 0,70 × 1,10 (puede esconder un premio).
- **Expositor de folletos de asociaciones** (`cultura_y_ocio/expositor_folletos_asociaciones`): 0,30 × 0,35 × 1,60 (puede esconder un premio).
- **Cartel enrollable de pie** (`cultura_y_ocio/cartel_enrollable`): 0,85 × 0,40 × 2,00.

## Sonidos propios (12)

`arpa_glissando`, `audioguia_locucion`, `bateria_ritmo`, `bolera_retorno`, `bolos_derribo`, `contrabajo_pizzicato`, `hockey_aire`, `musica_discoteca`, `palomitera`, `pinball_campanas`, `proyector_cine`, `recreativa_melodia`.

## Sonidos que toma del complemento `hogar` (6)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `interruptor`, `juguetes`, `puerta_electrodomestico`, `sentarse`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (4)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`balon`, `colchoneta`, `pimpon`, `teclado`.

## Sonidos que toma del complemento `oficina_y_comercio` (2)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_registradora`, `cortina`.

## Sonidos que toma del complemento `calle` (3)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`papel`, `trampilla_buzon`, `zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (3)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `taquilla`.

## Sonidos que toma del complemento `juego` (6)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cofre_abrir`, `cofre_cerrar`, `llaves`, `monedas`, `muelle`, `tambor`.
