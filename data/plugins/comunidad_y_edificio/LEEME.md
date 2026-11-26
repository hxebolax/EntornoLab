# Comunidad y edificio

Las zonas comunes de un edificio de viviendas: portal, escalera y rellanos, cuartos de instalaciones y de basuras, garaje sin vehículos, trastero, azotea, patio de luces y las zonas de recreo de una urbanización.

- Identificador: `comunidad_y_edificio`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo comunidad_y_edificio` a partir de `tools/complementos_serie/comunidad_y_edificio.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (122)

Medidas por defecto: ancho × fondo × alto, en metros.

### Portal y conserjería (19)

#### Buzones y portero automático

- **Casillero de buzones de comunidad** (`comunidad_y_edificio/casillero_buzones`): 1,20 × 0,25 × 0,90 (4 variantes; colgado a 0,75 m; puede esconder un premio).
- **Batería de buzones sobre patas** (`comunidad_y_edificio/buzones_exentos`): 1,00 × 0,35 × 1,50 (2 variantes; puede esconder un premio).
- **Taquillas de paquetería del portal** (`comunidad_y_edificio/taquillas_paqueteria`): 0,90 × 0,50 × 1,90 (puede esconder un premio).
- **Portero automático de la calle** (`comunidad_y_edificio/portero_automatico`): 0,15 × 0,04 × 0,35 (2 variantes; colgado a 1,10 m).
- **Videoportero con teclado** (`comunidad_y_edificio/videoportero`): 0,18 × 0,05 × 0,32 (colgado a 1,15 m).

#### Mobiliario del portal

- **Tablón de anuncios de la comunidad con vitrina** (`comunidad_y_edificio/tablon_comunidad`): 0,80 × 0,08 × 0,70 (colgado a 1,10 m).
- **Alfombra pasillera del portal** (`comunidad_y_edificio/alfombra_pasillera`): 1,00 × 4,00 × 0,02 (no corta el paso).
- **Espejo de portal de cuerpo entero** (`comunidad_y_edificio/espejo_portal`): 1,50 × 0,04 × 1,80 (colgado a 0,20 m).
- **Banco de mármol del portal** (`comunidad_y_edificio/banco_portal`): 1,50 × 0,40 × 0,45.
- **Jardinera de obra del portal** (`comunidad_y_edificio/jardinera_portal`): 2,00 × 0,50 × 0,60 (puede esconder un premio).

#### Conserjería

- **Mostrador de conserjería** (`comunidad_y_edificio/mostrador_conserjeria`): 1,60 × 0,60 × 1,10 (puede esconder un premio).
- **Garita de conserje acristalada** (`comunidad_y_edificio/garita_conserje`): 1,50 × 1,50 × 2,20 (puede esconder un premio).

#### Lo que se deja aparcado en el portal

- **Carrito de la compra aparcado** (`comunidad_y_edificio/carrito_compra_tela`): 0,40 × 0,40 × 0,95 (puede esconder un premio).
- **Bicicleta apoyada en la pared del portal** (`comunidad_y_edificio/bici_pared_portal`): 1,75 × 0,55 × 1,05.

#### Puerta, peldaños y rampa

- **Felpudo encastrado del portal** (`comunidad_y_edificio/felpudo_encastrado`): 1,80 × 1,20 × 0,02 (no corta el paso).
- **Peldaños de entrada al portal** (`comunidad_y_edificio/peldanos_portal`): 1,50 × 0,60 × 0,34 (3 variantes; no corta el paso).
- **Rampa de portal con barandilla** (`comunidad_y_edificio/rampa_portal`): 1,20 × 3,00 × 0,25 (2 variantes; no corta el paso).
- **Puerta de portal pesada con muelle** (`comunidad_y_edificio/puerta_portal`): 0,95 × 0,08 × 2,10.
- **Pulsador abrepuertas del portal** (`comunidad_y_edificio/pulsador_abrepuertas`): 0,08 × 0,03 × 0,08 (colgado a 1,05 m).

### Escalera, rellanos y ascensor (14)

#### Escalera y barandilla

- **Arranque de barandilla de escalera** (`comunidad_y_edificio/arranque_barandilla`): 0,10 × 0,60 × 1,00.
- **Hueco bajo la escalera** (`comunidad_y_edificio/hueco_bajo_escalera`): 1,10 × 1,50 × 0,80 (colgado a 1,20 m).
- **Ventana del rellano abierta hacia dentro** (`comunidad_y_edificio/ventana_rellano_abierta`): 0,60 × 0,04 × 1,00 (colgado a 1,00 m).

#### Lo que dejan los vecinos en el rellano

- **Macetas del vecino en el rellano** (`comunidad_y_edificio/macetas_vecino`): 0,80 × 0,35 × 0,60 (puede esconder un premio).
- **Zapatos del vecino junto a la puerta** (`comunidad_y_edificio/zapatos_vecino`): 0,80 × 0,30 × 0,15.
- **Bolsa de basura en el rellano** (`comunidad_y_edificio/bolsa_basura_rellano`): 0,35 × 0,35 × 0,40.
- **Bombona de butano en el rellano** (`comunidad_y_edificio/bombona_rellano`): 0,30 × 0,30 × 0,60.
- **Triciclo y patinete de niño en el rellano** (`comunidad_y_edificio/triciclo_rellano`): 0,60 × 0,60 × 0,65.

#### Luz, registros y tuberías

- **Armario de contadores de rellano** (`comunidad_y_edificio/armario_contadores_rellano`): 0,80 × 0,15 × 2,00 (puede esconder un premio).
- **Pulsador de la luz de escalera con temporizador** (`comunidad_y_edificio/pulsador_luz_escalera`): 0,08 × 0,04 × 0,08 (colgado a 1,10 m).
- **Bajante vista** (`comunidad_y_edificio/bajante_vista`): 0,12 × 0,12 × 2,60.

#### Ascensor por fuera

- **Botonera de llamada del ascensor** (`comunidad_y_edificio/botonera_ascensor`): 0,10 × 0,03 × 0,20 (colgado a 0,95 m).
- **Puerta batiente de ascensor antiguo** (`comunidad_y_edificio/puerta_ascensor_batiente`): 0,75 × 0,05 × 2,00.
- **Banqueta de espera del ascensor** (`comunidad_y_edificio/banqueta_ascensor`): 0,90 × 0,32 × 0,45 (puede esconder un premio).

### Cuartos de instalaciones, basuras y bicicletas (16)

#### Electricidad y telecomunicaciones

- **Centralización de contadores de luz** (`comunidad_y_edificio/contadores_luz`): 2,00 × 0,25 × 2,00.
- **Cuadro eléctrico saliente** (`comunidad_y_edificio/cuadro_electrico_saliente`): 0,60 × 0,18 × 0,70 (colgado a 1,00 m; puede esconder un premio).
- **Armario de telecomunicaciones** (`comunidad_y_edificio/armario_telecomunicaciones`): 0,60 × 0,60 × 2,00.

#### Agua y calefacción

- **Batería de contadores de agua** (`comunidad_y_edificio/contadores_agua`): 1,50 × 0,35 × 1,30.
- **Grupo de presión de agua** (`comunidad_y_edificio/grupo_presion`): 1,20 × 0,70 × 1,20.
- **Caldera comunitaria** (`comunidad_y_edificio/caldera_comunitaria`): 1,40 × 1,20 × 1,80 (3 variantes).
- **Depósito de gasóleo de la calefacción** (`comunidad_y_edificio/deposito_gasoleo`): 2,00 × 0,90 × 1,50.
- **Depósito acumulador de agua caliente** (`comunidad_y_edificio/acumulador_agua_caliente`): 0,90 × 0,90 × 2,00.

#### Cuarto de basuras

- **Fila de cubos de basura de la comunidad** (`comunidad_y_edificio/fila_cubos_comunidad`): 2,40 × 0,75 × 1,07 (3 variantes; puede esconder un premio).
- **Cartones plegados apoyados en la pared** (`comunidad_y_edificio/cartones_plegados`): 1,00 × 0,40 × 0,90.

#### Cuarto de limpieza

- **Cubo de fregar con fregona** (`comunidad_y_edificio/cubo_fregona`): 0,38 × 0,30 × 1,30.
- **Vertedero del cuarto de limpieza** (`comunidad_y_edificio/vertedero_limpieza`): 0,50 × 0,45 × 0,50.
- **Escobas y recogedor apoyados en la pared** (`comunidad_y_edificio/escobas_apoyadas`): 0,50 × 0,20 × 1,40.

#### Cuarto de bicicletas

- **Ganchos de pared para bicicletas** (`comunidad_y_edificio/ganchos_bicis`): 1,50 × 0,25 × 0,15 (colgado a 1,70 m).
- **Bicicleta colgada de un gancho por la rueda** (`comunidad_y_edificio/bici_colgada_gancho`): 0,60 × 1,05 × 1,75 (colgado a 0,20 m).
- **Soporte de suelo para ruedas de bicicleta** (`comunidad_y_edificio/soporte_bicis_suelo`): 1,50 × 0,40 × 0,30 (3 variantes).

### Garaje (22)

#### Columnas, rampas y suelo

- **Columna de garaje con protector de esquinas** (`comunidad_y_edificio/columna_garaje_protegida`): 0,40 × 0,40 × 2,50 (2 variantes).
- **Columna redonda de garaje** (`comunidad_y_edificio/columna_garaje_redonda`): 0,45 × 0,45 × 2,50.
- **Rampa de garaje** (`comunidad_y_edificio/rampa_garaje`): 3,50 × 6,00 × 0,30 (no corta el paso).
- **Rejilla de desagüe de garaje** (`comunidad_y_edificio/rejilla_desague_garaje`): 3,00 × 0,20 × 0,02 (no corta el paso).
- **Badén de garaje** (`comunidad_y_edificio/baden_garaje`): 3,00 × 0,40 × 0,05 (no corta el paso).
- **Mancha de aceite en el suelo del garaje** (`comunidad_y_edificio/mancha_aceite`): 0,80 × 0,60 × 0,01 (no corta el paso).

#### Plazas de aparcamiento

- **Marca de plaza de garaje** (`comunidad_y_edificio/marca_plaza_garaje`): 2,40 × 5,00 × 0,01 (3 variantes; no corta el paso).
- **Tope de rueda de plaza de garaje** (`comunidad_y_edificio/tope_rueda_plaza`): 1,65 × 0,15 × 0,10 (2 variantes).
- **Punto de recarga de pared de garaje** (`comunidad_y_edificio/punto_recarga_pared`): 0,25 × 0,15 × 0,40 (colgado a 1,00 m).
- **Armario de plaza sobre el capó** (`comunidad_y_edificio/armario_sobre_capo`): 2,00 × 0,80 × 0,90 (colgado a 1,15 m; puede esconder un premio).
- **Trastero de jaula de malla en el garaje** (`comunidad_y_edificio/trastero_jaula`): 2,00 × 1,50 × 2,20 (puede esconder un premio).

#### Puertas y accesos del garaje

- **Puerta basculante de garaje** (`comunidad_y_edificio/puerta_basculante_garaje`): 2,80 × 0,10 × 2,20 (2 variantes).
- **Poste con pulsador de salida del garaje** (`comunidad_y_edificio/poste_pulsador_salida`): 0,15 × 0,15 × 1,20.
- **Luz y sirena de salida de vehículos** (`comunidad_y_edificio/aviso_salida_vehiculos`): 0,20 × 0,15 × 0,25 (no corta el paso; colgado a 2,30 m).
- **Puerta cortafuegos** (`comunidad_y_edificio/puerta_cortafuegos`): 0,90 × 0,06 × 2,10.
- **Vestíbulo de independencia** (`comunidad_y_edificio/vestibulo_independencia`): 1,50 × 1,50 × 0,01 (no corta el paso).

#### Techo, ventilación e incendios

- **Tuberías bajas colgadas del techo del garaje** (`comunidad_y_edificio/tuberias_bajas_garaje`): 3,00 × 0,30 × 0,20 (colgado a 1,75 m).
- **Conducto de ventilación de chapa bajo** (`comunidad_y_edificio/conducto_ventilacion_bajo`): 3,00 × 0,60 × 0,40 (colgado a 1,85 m).
- **Extractor de humos del garaje** (`comunidad_y_edificio/extractor_garaje`): 1,00 × 1,00 × 1,20.
- **Espejo convexo de garaje** (`comunidad_y_edificio/espejo_convexo_garaje`): 0,60 × 0,30 × 0,60 (colgado a 1,80 m).
- **Boca de incendio equipada** (`comunidad_y_edificio/boca_incendio_equipada`): 0,70 × 0,22 × 0,65 (colgado a 0,90 m).
- **Extintor de carro** (`comunidad_y_edificio/extintor_carro`): 0,45 × 0,50 × 1,00.

### Trastero (13)

#### Estanterías, cajas y bultos

- **Estantería metálica de trastero** (`comunidad_y_edificio/estanteria_metalica_trastero`): 0,90 × 0,40 × 2,00 (puede esconder un premio).
- **Cajas de cartón apiladas** (`comunidad_y_edificio/cajas_carton_apiladas`): 0,60 × 0,50 × 1,20 (2 variantes; puede esconder un premio).
- **Maletas apiladas** (`comunidad_y_edificio/maletas_apiladas`): 0,70 × 0,45 × 0,75 (puede esconder un premio).
- **Bolsas de ropa guardada** (`comunidad_y_edificio/bolsas_ropa_guardada`): 0,70 × 0,50 × 0,50 (puede esconder un premio).
- **Neumáticos apilados** (`comunidad_y_edificio/neumaticos_apilados`): 0,65 × 0,65 × 0,85 (puede esconder un premio).
- **Muebles viejos tapados con una sábana** (`comunidad_y_edificio/muebles_tapados_sabana`): 1,50 × 0,80 × 1,20 (puede esconder un premio).
- **Botes de pintura en el suelo** (`comunidad_y_edificio/botes_pintura_suelo`): 0,60 × 0,30 × 0,25 (puede esconder un premio).

#### Cosas apoyadas y colgadas

- **Árbol de Navidad en su caja** (`comunidad_y_edificio/arbol_navidad_caja`): 0,30 × 0,30 × 1,30 (puede esconder un premio).
- **Escalera de mano apoyada en la pared** (`comunidad_y_edificio/escalera_apoyada`): 0,45 × 0,80 × 2,50.
- **Colchón de pie apoyado en la pared** (`comunidad_y_edificio/colchon_de_pie`): 1,35 × 0,25 × 1,90.
- **Esquís y sombrilla apoyados en el rincón** (`comunidad_y_edificio/esquis_sombrilla_rincon`): 0,30 × 0,30 × 1,90.
- **Bicicleta colgada del techo** (`comunidad_y_edificio/bici_colgada_techo`): 1,75 × 0,60 × 0,70 (colgado a 1,50 m).
- **Tirador de la luz del trastero** (`comunidad_y_edificio/tirador_luz_trastero`): 0,04 × 0,04 × 0,50 (no corta el paso; colgado a 1,50 m).

### Azotea y patio de luces (20)

#### Tendederos

- **Cuerdas de tender de la azotea** (`comunidad_y_edificio/cuerdas_tender_azotea`): 4,00 × 1,20 × 0,10 (colgado a 1,50 m).
- **Poste de tendedero** (`comunidad_y_edificio/poste_tendedero`): 0,06 × 0,06 × 1,90.
- **Sábanas tendidas** (`comunidad_y_edificio/sabanas_tendidas`): 2,00 × 0,05 × 1,00 (no corta el paso; colgado a 0,60 m).
- **Tendedero de pie de aspa** (`comunidad_y_edificio/tendedero_aspa`): 1,80 × 1,80 × 0,40 (colgado a 1,40 m).

#### Elementos de la cubierta

- **Murete de azotea** (`comunidad_y_edificio/murete_azotea`): 3,00 × 0,25 × 1,00 (2 variantes).
- **Claraboya saliente en el suelo de la azotea** (`comunidad_y_edificio/claraboya_azotea`): 1,00 × 1,00 × 0,35.
- **Casetón de la escalera** (`comunidad_y_edificio/caseton_azotea`): 3,00 × 3,50 × 2,80 (puede esconder un premio).
- **Chimenea de ventilación** (`comunidad_y_edificio/chimenea_ventilacion`): 0,60 × 0,60 × 1,50.
- **Antena con vientos** (`comunidad_y_edificio/antena_con_vientos`): 3,00 × 3,00 × 5,00.
- **Escalera de gato** (`comunidad_y_edificio/escalera_gato`): 0,45 × 0,20 × 3,00.

#### Máquinas y depósitos

- **Unidad exterior de aire acondicionado en el suelo** (`comunidad_y_edificio/aire_acondicionado_suelo`): 0,85 × 0,35 × 0,65 (2 variantes).
- **Aire acondicionado sobre ménsulas a la altura de la cabeza** (`comunidad_y_edificio/aire_acondicionado_mensulas`): 0,80 × 0,32 × 0,55 (colgado a 1,50 m).
- **Depósito de agua de azotea** (`comunidad_y_edificio/deposito_agua_azotea`): 1,30 × 1,30 × 1,50.
- **Placas solares sobre soportes** (`comunidad_y_edificio/placas_solares_azotea`): 2,00 × 1,70 × 1,00.

#### Patio de luces

- **Tendedero de ventana de planta baja** (`comunidad_y_edificio/tendedero_ventana_bajo`): 1,50 × 0,60 × 0,05 (colgado a 1,20 m).
- **Cuerdas de tender con poleas entre ventanas** (`comunidad_y_edificio/cuerdas_poleas_patio`): 3,00 × 0,60 × 0,10 (no corta el paso; colgado a 2,30 m).
- **Sumidero de patio** (`comunidad_y_edificio/sumidero_patio`): 0,20 × 0,20 × 0,01 (no corta el paso).
- **Grifo de patio con manguera enrollada** (`comunidad_y_edificio/grifo_patio_manguera`): 0,50 × 0,40 × 0,80.
- **Manguera extendida por el suelo** (`comunidad_y_edificio/manguera_extendida`): 4,00 × 0,80 × 0,03 (no corta el paso).
- **Pila de lavar de patio** (`comunidad_y_edificio/pila_lavar_patio`): 0,70 × 0,55 × 0,85 (puede esconder un premio).

### Piscina y zonas de recreo de la urbanización (18)

#### Piscina comunitaria

- **Piscina de comunidad** (`comunidad_y_edificio/piscina_comunidad`): 8,00 × 5,00 × 0,10 (3 variantes; no corta el paso).
- **Valla de piscina** (`comunidad_y_edificio/valla_piscina`): 2,00 × 0,05 × 1,20.
- **Puerta de muelle de la valla de la piscina** (`comunidad_y_edificio/puerta_valla_piscina`): 0,90 × 0,05 × 1,25.
- **Lavapiés de la piscina** (`comunidad_y_edificio/lavapies_piscina`): 1,20 × 1,50 × 0,10 (no corta el paso).
- **Ducha de jardín de la piscina** (`comunidad_y_edificio/ducha_jardin_piscina`): 0,90 × 0,90 × 2,20.
- **Aro salvavidas en su poste** (`comunidad_y_edificio/aro_salvavidas_poste`): 0,70 × 0,20 × 1,60.
- **Tumbona de piscina de comunidad** (`comunidad_y_edificio/tumbona_comunidad`): 0,70 × 1,90 × 0,35.
- **Caseta de la depuradora** (`comunidad_y_edificio/caseta_depuradora`): 2,00 × 1,50 × 1,20 (puede esconder un premio).

#### Pérgola, barbacoa y bancos

- **Pérgola de madera** (`comunidad_y_edificio/pergola_urbanizacion`): 3,00 × 3,00 × 0,20 (no corta el paso; colgado a 2,20 m).
- **Poste de pérgola** (`comunidad_y_edificio/poste_pergola`): 0,12 × 0,12 × 2,40.
- **Barbacoa de obra** (`comunidad_y_edificio/barbacoa_obra`): 1,40 × 0,70 × 1,90 (puede esconder un premio).
- **Banco corrido de obra en ele** (`comunidad_y_edificio/banco_obra_ele`): 3,00 × 2,50 × 0,45.

#### Petanca y caminos

- **Pista de petanca con bordillo** (`comunidad_y_edificio/pista_petanca`): 3,00 × 12,00 × 0,15 (no corta el paso).
- **Camino de losas en el césped** (`comunidad_y_edificio/camino_losas_cesped`): 0,60 × 4,00 × 0,03 (no corta el paso).

#### Accesos y servicios de la urbanización

- **Caseta del jardinero** (`comunidad_y_edificio/caseta_jardinero`): 2,00 × 2,00 × 2,20 (puede esconder un premio).
- **Garita de vigilante de urbanización** (`comunidad_y_edificio/garita_vigilante`): 2,00 × 2,00 × 2,50 (puede esconder un premio).
- **Barrera levadiza de urbanización** (`comunidad_y_edificio/barrera_urbanizacion`): 3,00 × 0,35 × 0,15 (colgado a 0,90 m).
- **Cancela peatonal de la urbanización** (`comunidad_y_edificio/cancela_peatonal`): 1,00 × 0,06 × 2,00.

## Sonidos propios (9)

`abrepuertas_zumbido`, `aviso_garaje_pitido`, `bajante_desague`, `depuradora_piscina`, `extractor_garaje`, `grupo_presion`, `petanca_bolas`, `portero_automatico`, `puerta_garaje_basculante`.

## Sonidos que toma del complemento `comun` (6)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`barbacoa_brasas`, `caldera_comunitaria`, `compresor_azotea`, `ducha`, `polea_tendedero`, `puerta_pesada_muelle`.

## Sonidos que toma del complemento `hogar` (6)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`interruptor`, `juguetes`, `puerta_cristal`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (1)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`teclado`.

## Sonidos que toma del complemento `calle` (3)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`papel`, `trampilla_buzon`, `zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (4)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `taquilla`, `timbre_bici`.

## Sonidos que toma del complemento `juego` (3)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bandera`, `campana`, `llaves`.
