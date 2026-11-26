# Estaciones, aeropuerto y puerto

Grandes estaciones de tren y de autobuses, andenes con el tren parado, metro, tranvía, aeropuerto (facturación, control, embarque y recogida de equipajes) y puerto, con sus referencias, sus sonidos y sus avisos.

- Identificador: `estaciones_y_aeropuerto`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo estaciones_y_aeropuerto` a partir de `tools/complementos_serie/estaciones_y_aeropuerto.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (117)

Medidas por defecto: ancho × fondo × alto, en metros.

### Vestíbulo de gran estación (18)

#### Información y asistencia

- **Mostrador de información de estación con tramo bajo** (`estaciones_y_aeropuerto/mostrador_info_estacion`): 3,60 × 0,90 × 1,10 (3 variantes; puede esconder un premio).
- **Punto de encuentro de asistencia al viajero** (`estaciones_y_aeropuerto/punto_asistencia_estacion`): 0,80 × 0,50 × 1,50.
- **Zona de espera de asistencia señalizada en el suelo** (`estaciones_y_aeropuerto/zona_espera_asistencia`): 2,50 × 2,00 × 0,01 (no corta el paso).
- **Interfono de asistencia de pared** (`estaciones_y_aeropuerto/interfono_asistencia_pared`): 0,25 × 0,10 × 0,40 (colgado a 0,90 m).
- **Tótem de información accesible con audio** (`estaciones_y_aeropuerto/totem_info_audio`): 0,60 × 0,40 × 1,90.
- **Panel de salidas y llegadas colgado** (`estaciones_y_aeropuerto/panel_salidas_colgado`): 5,00 × 0,30 × 1,50 (no corta el paso; colgado a 2,60 m).

#### Venta de billetes

- **Ventanillas de venta en batería con separadores** (`estaciones_y_aeropuerto/ventanillas_bateria`): 4,80 × 0,80 × 1,10 (3 variantes).
- **Máquinas de autoventa en batería con voz** (`estaciones_y_aeropuerto/autoventa_bateria`): 2,40 × 0,70 × 1,80 (3 variantes).

#### Espera y servicios

- **Consigna automática con terminal de pago** (`estaciones_y_aeropuerto/consigna_automatica`): 2,70 × 0,85 × 1,95 (puede esconder un premio).
- **Asiento reservado de estación** (`estaciones_y_aeropuerto/asiento_reservado_estacion`): 0,70 × 0,65 × 0,85.
- **Banco circular alrededor de una columna** (`estaciones_y_aeropuerto/banco_circular_columna`): 2,00 × 2,00 × 0,45 (puede esconder un premio).
- **Columna de carga de móviles** (`estaciones_y_aeropuerto/columna_carga_moviles`): 0,60 × 0,60 × 1,15.
- **Carros portaequipajes encajados con monedero** (`estaciones_y_aeropuerto/carros_encajados_monedero`): 0,70 × 3,50 × 1,05 (3 variantes).
- **Quiosco isla de vestíbulo** (`estaciones_y_aeropuerto/quiosco_isla_vestibulo`): 3,00 × 2,60 × 2,50 (puede esconder un premio).
- **Tienda de conveniencia abierta al vestíbulo** (`estaciones_y_aeropuerto/tienda_conveniencia_abierta`): 4,50 × 3,50 × 2,50 (puede esconder un premio).
- **Reloj monumental de estación** (`estaciones_y_aeropuerto/reloj_punto_encuentro`): 1,20 × 1,20 × 4,00.

#### Control de alta velocidad

- **Escáner de equipajes de acceso a alta velocidad** (`estaciones_y_aeropuerto/escaner_equipajes_estacion`): 1,00 × 3,20 × 1,40.
- **Atril de control de billetes de embarque** (`estaciones_y_aeropuerto/atril_control_billetes`): 0,60 × 0,50 × 1,10.

### Andenes de tren (21)

#### Bordes, huecos y marcas del andén

- **Borde de andén antiguo sin franja táctil** (`estaciones_y_aeropuerto/borde_anden_antiguo`): 10,00 × 0,40 × 0,01 (no corta el paso).
- **Hueco entre coche y andén** (`estaciones_y_aeropuerto/hueco_coche_anden`): 1,30 × 0,15 × 0,01 (no corta el paso).
- **Marca táctil de posición de puerta** (`estaciones_y_aeropuerto/marca_puerta_anden`): 1,50 × 1,20 × 0,01 (no corta el paso).
- **Manguera tendida en el andén** (`estaciones_y_aeropuerto/manguera_aguada_anden`): 0,08 × 4,00 × 0,06 (no corta el paso).

#### Mobiliario y cubiertas de andén

- **Refugio acristalado de andén** (`estaciones_y_aeropuerto/refugio_acristalado_anden`): 5,00 × 2,40 × 2,70 (puede esconder un premio).
- **Marquesina de andén sobre columnas** (`estaciones_y_aeropuerto/marquesina_anden_columnas`): 10,00 × 4,00 × 0,40 (no corta el paso; colgado a 3,50 m).
- **Vitrina de horarios de andén en voladizo** (`estaciones_y_aeropuerto/tablon_horario_voladizo`): 1,50 × 0,12 × 1,20 (colgado a 0,90 m).
- **Cartel del nombre de la estación sobre dos postes** (`estaciones_y_aeropuerto/cartel_nombre_estacion`): 2,50 × 0,10 × 0,60 (colgado a 1,50 m).

#### Tren parado

- **Coche de tren parado (tramo)** (`estaciones_y_aeropuerto/coche_tren_tramo`): 6,00 × 2,90 × 4,00 (3 variantes).
- **Cabeza de tren o locomotora parada** (`estaciones_y_aeropuerto/cabeza_tren`): 6,00 × 2,90 × 4,20.
- **Puerta de tren con escalón** (`estaciones_y_aeropuerto/puerta_tren_abierta`): 1,30 × 0,40 × 2,10 (3 variantes).
- **Fuelle entre dos coches** (`estaciones_y_aeropuerto/fuelle_tren`): 0,80 × 2,50 × 2,50.

#### Embarque asistido y carros de servicio

- **Rampa de embarque móvil** (`estaciones_y_aeropuerto/rampa_embarque_movil`): 0,90 × 1,80 × 0,20 (no corta el paso).
- **Plataforma elevadora de embarque para sillas de ruedas** (`estaciones_y_aeropuerto/plataforma_elevadora_embarque`): 1,00 × 1,60 × 1,20.
- **Carro de restauración en el andén** (`estaciones_y_aeropuerto/carro_restauracion_anden`): 0,70 × 1,10 × 1,50 (puede esconder un premio).
- **Carro de limpieza de trenes** (`estaciones_y_aeropuerto/carro_limpieza_trenes`): 0,60 × 1,10 × 1,05 (puede esconder un premio).

#### Vías y pasos entre andenes

- **Tope de vía** (`estaciones_y_aeropuerto/tope_via`): 2,50 × 1,50 × 1,20.
- **Vía del tren: zona prohibida** (`estaciones_y_aeropuerto/caja_via`): 10,00 × 2,80 × 0,02 (no corta el paso).
- **Paso a nivel entre andenes** (`estaciones_y_aeropuerto/paso_entre_andenes`): 2,50 × 5,00 × 0,03 (no corta el paso).
- **Barrera con señal sonora de paso entre andenes** (`estaciones_y_aeropuerto/barrera_paso_andenes`): 2,50 × 0,20 × 1,10.
- **Cancela de fin de andén** (`estaciones_y_aeropuerto/cancela_fin_anden`): 2,50 × 0,08 × 1,10.

### Metro (14)

#### Bocas y accesos de metro

- **Cancela de boca de metro** (`estaciones_y_aeropuerto/cancela_boca_metro`): 2,50 × 0,10 × 2,30.
- **Barandilla de boca de metro** (`estaciones_y_aeropuerto/barandilla_boca_metro`): 2,50 × 5,00 × 1,10.
- **Templete acristalado de boca de metro** (`estaciones_y_aeropuerto/templete_boca_metro`): 3,00 × 6,00 × 3,00.
- **Poste de boca de metro** (`estaciones_y_aeropuerto/poste_boca_metro`): 0,20 × 0,20 × 4,00.
- **Puertas batientes cortavientos de metro** (`estaciones_y_aeropuerto/puertas_cortavientos_metro`): 1,80 × 0,08 × 2,10.
- **Paso de validación de hojas de cristal** (`estaciones_y_aeropuerto/paso_hojas_cristal`): 0,85 × 1,80 × 1,10.
- **Torno de salida de cuerpo entero** (`estaciones_y_aeropuerto/torno_salida_jaula`): 1,50 × 1,50 × 2,30.
- **Cabina del agente de estación** (`estaciones_y_aeropuerto/cabina_agente_metro`): 2,00 × 2,00 × 2,40.

#### Andén de metro

- **Puertas de andén automáticas de cristal (tramo)** (`estaciones_y_aeropuerto/puertas_anden_cristal`): 4,00 × 0,25 × 2,30 (3 variantes).
- **Espejo de andén** (`estaciones_y_aeropuerto/espejo_anden`): 0,80 × 0,50 × 0,80 (colgado a 1,60 m).
- **Asiento abatible de pared de andén** (`estaciones_y_aeropuerto/asiento_abatible_anden`): 1,40 × 0,40 × 0,40 (colgado a 0,50 m).

#### Información y recarga

- **Panel de próximo tren con voz** (`estaciones_y_aeropuerto/panel_proximo_tren`): 1,40 × 0,20 × 0,40 (no corta el paso; colgado a 2,30 m).
- **Plano de la red en relieve** (`estaciones_y_aeropuerto/plano_red_relieve`): 1,50 × 0,06 × 1,00 (colgado a 0,90 m).
- **Máquina de recarga de tarjetas de pared** (`estaciones_y_aeropuerto/recarga_tarjetas_pared`): 0,50 × 0,30 × 0,70 (colgado a 0,80 m).

### Tranvía y estación de autobuses (7)

#### Parada y vía de tranvía

- **Andén bajo de parada de tranvía** (`estaciones_y_aeropuerto/anden_tranvia_bajo`): 20,00 × 3,00 × 0,28 (no corta el paso).
- **Raíl de tranvía embebido en el suelo** (`estaciones_y_aeropuerto/rail_tranvia_embebido`): 0,10 × 10,00 × 0,01 (no corta el paso).
- **Poste de catenaria** (`estaciones_y_aeropuerto/poste_catenaria`): 0,30 × 0,30 × 8,00.
- **Barandillas en zigzag de paso de tranvía** (`estaciones_y_aeropuerto/chicane_paso_tranvia`): 2,50 × 2,00 × 1,10.

#### Dársenas de autobuses

- **Dársena de estación de autobuses** (`estaciones_y_aeropuerto/darsena_autobuses`): 3,50 × 12,00 × 0,02 (no corta el paso).
- **Pilonas de dársena unidas por cadena** (`estaciones_y_aeropuerto/pilonas_cadena_darsena`): 3,00 × 0,20 × 0,80.
- **Poste de dársena con número en relieve y braille** (`estaciones_y_aeropuerto/poste_darsena_braille`): 0,12 × 0,12 × 2,20.

### Aeropuerto: facturación y controles (20)

#### Facturación

- **Mostrador de facturación** (`estaciones_y_aeropuerto/mostrador_facturacion`): 1,50 × 1,00 × 1,05 (puede esconder un premio).
- **Báscula con cinta de facturación** (`estaciones_y_aeropuerto/bascula_cinta_facturacion`): 0,80 × 1,80 × 0,35.
- **Quiosco de autofacturación** (`estaciones_y_aeropuerto/quiosco_autofacturacion`): 0,60 × 0,50 × 1,60.
- **Punto de entrega automática de equipaje** (`estaciones_y_aeropuerto/entrega_automatica_equipaje`): 1,50 × 2,20 × 1,60.
- **Medidor de equipaje de mano** (`estaciones_y_aeropuerto/medidor_equipaje_mano`): 0,50 × 0,40 × 1,10 (puede esconder un premio).
- **Máquina de embalar maletas** (`estaciones_y_aeropuerto/embaladora_maletas`): 1,50 × 1,50 × 1,50.

#### Colas y asistencia

- **Cola en zigzag de postes con cinta** (`estaciones_y_aeropuerto/cola_zigzag_cintas`): 4,00 × 3,60 × 0,95 (3 variantes).
- **Mostrador de asistencia a personas con movilidad reducida** (`estaciones_y_aeropuerto/mostrador_asistencia_pmr`): 2,00 × 1,10 × 0,82 (puede esconder un premio).

#### Control de seguridad

- **Contenedor de líquidos del control** (`estaciones_y_aeropuerto/contenedor_liquidos_control`): 0,60 × 0,60 × 1,00 (puede esconder un premio).
- **Pila de bandejas del control** (`estaciones_y_aeropuerto/pila_bandejas_control`): 0,50 × 0,65 × 0,90 (puede esconder un premio).
- **Cinta de rodillos del control de seguridad (tramo)** (`estaciones_y_aeropuerto/cinta_rodillos_control`): 0,70 × 3,00 × 0,80 (3 variantes).
- **Escáner de rayos X con cortinillas** (`estaciones_y_aeropuerto/tunel_rayos_x`): 1,00 × 2,20 × 1,45.
- **Arco detector de metales** (`estaciones_y_aeropuerto/arco_detector_metales`): 0,90 × 0,60 × 2,20 (no corta el paso).
- **Escáner corporal** (`estaciones_y_aeropuerto/escaner_corporal`): 1,70 × 1,70 × 2,50.
- **Mesa de recogida tras el control** (`estaciones_y_aeropuerto/mesa_recogida_control`): 2,00 × 0,80 × 0,85 (puede esconder un premio).
- **Banco para calzarse del control** (`estaciones_y_aeropuerto/banco_calzarse_control`): 1,50 × 0,40 × 0,45.
- **Cabina de registro con cortina** (`estaciones_y_aeropuerto/cabina_registro_control`): 1,50 × 1,50 × 2,10 (puede esconder un premio).

#### Pasaportes y aduana

- **Cabina de control de pasaportes** (`estaciones_y_aeropuerto/cabina_pasaportes`): 1,50 × 2,20 × 2,30.
- **Puerta automática de control de fronteras** (`estaciones_y_aeropuerto/puerta_fronteras_automatica`): 1,00 × 2,20 × 1,40.
- **Canal de aduana con mesa de inspección** (`estaciones_y_aeropuerto/canal_aduana`): 3,00 × 4,00 × 0,90 (puede esconder un premio).

### Aeropuerto: embarque y llegadas (20)

#### Sala de embarque

- **Bancada de puerta de embarque** (`estaciones_y_aeropuerto/bancada_embarque`): 3,00 × 0,70 × 0,85 (3 variantes; puede esconder un premio).
- **Tumbona de descanso de aeropuerto** (`estaciones_y_aeropuerto/tumbona_aeropuerto`): 0,70 × 1,70 × 0,90.
- **Barra de trabajo con enchufes** (`estaciones_y_aeropuerto/barra_trabajo_enchufes`): 2,40 × 0,50 × 1,05.
- **Zona de juegos infantil de aeropuerto** (`estaciones_y_aeropuerto/zona_juegos_aeropuerto`): 4,00 × 4,00 × 0,50 (puede esconder un premio).
- **Papelera de reciclaje de aeropuerto con tres bocas** (`estaciones_y_aeropuerto/papelera_reciclaje_aeropuerto`): 1,20 × 0,40 × 1,00 (puede esconder un premio).
- **Pasillo rodante (tramo)** (`estaciones_y_aeropuerto/pasillo_rodante`): 1,40 × 6,00 × 0,10 (no corta el paso).
- **Buggy eléctrico de asistencia** (`estaciones_y_aeropuerto/buggy_asistencia`): 1,30 × 3,00 × 1,90.

#### Puerta de embarque y pasarela

- **Mostrador de puerta de embarque** (`estaciones_y_aeropuerto/mostrador_puerta_embarque`): 1,60 × 0,70 × 1,10 (puede esconder un premio).
- **Puerta de la pasarela de embarque** (`estaciones_y_aeropuerto/puerta_pasarela_embarque`): 1,20 × 0,10 × 2,10.
- **Pasarela de embarque de avión (tramo)** (`estaciones_y_aeropuerto/pasarela_avion_tramo`): 2,00 × 6,00 × 0,05 (no corta el paso).
- **Escalerilla de avión** (`estaciones_y_aeropuerto/escalerilla_avion`): 2,00 × 6,00 × 3,50.

#### Recogida de equipajes

- **Cinta de recogida de equipajes ovalada** (`estaciones_y_aeropuerto/cinta_recogida_ovalada`): 6,00 × 2,50 × 0,45 (3 variantes; puede esconder un premio).
- **Cinta de recogida de equipajes (tramo recto)** (`estaciones_y_aeropuerto/cinta_recogida_tramo`): 4,00 × 1,20 × 0,45 (3 variantes; puede esconder un premio).
- **Cinta de recogida de equipajes (curva)** (`estaciones_y_aeropuerto/cinta_recogida_curva`): 3,20 × 2,00 × 0,45 (puede esconder un premio).
- **Mostrador de equipajes perdidos** (`estaciones_y_aeropuerto/mostrador_equipajes_perdidos`): 2,40 × 0,80 × 1,10 (puede esconder un premio).

#### Llegadas y exterior

- **Puertas antirretorno de salida de llegadas** (`estaciones_y_aeropuerto/puertas_antirretorno_llegadas`): 2,00 × 0,15 × 2,30.
- **Barandilla de espera de llegadas** (`estaciones_y_aeropuerto/barandilla_espera_llegadas`): 5,00 × 2,00 × 1,05.
- **Tótem de punto de encuentro con baliza sonora** (`estaciones_y_aeropuerto/totem_punto_encuentro`): 0,50 × 0,30 × 2,50.
- **Fila de espera de taxis entre barandillas** (`estaciones_y_aeropuerto/fila_taxis_barandillas`): 1,40 × 6,00 × 1,05.
- **Bordillo de la acera de llegadas** (`estaciones_y_aeropuerto/bordillo_llegadas`): 10,00 × 0,40 × 0,12 (no corta el paso).

### Puerto (17)

#### Muelle y amarres

- **Borde del muelle sin barandilla** (`estaciones_y_aeropuerto/borde_muelle`): 10,00 × 0,50 × 0,02 (no corta el paso).
- **Noray** (`estaciones_y_aeropuerto/noray`): 0,40 × 0,40 × 0,40.
- **Cabo de amarre tendido** (`estaciones_y_aeropuerto/cabo_amarre_tendido`): 0,08 × 3,00 × 0,40.
- **Argolla de amarre en el suelo** (`estaciones_y_aeropuerto/argolla_amarre`): 0,25 × 0,25 × 0,05 (no corta el paso).
- **Defensas amontonadas en el muelle** (`estaciones_y_aeropuerto/defensas_muelle`): 1,20 × 0,80 × 0,60 (puede esconder un premio).
- **Escala del muelle** (`estaciones_y_aeropuerto/escala_muelle`): 0,50 × 0,50 × 1,00.
- **Base de grúa de puerto** (`estaciones_y_aeropuerto/base_grua_puerto`): 3,00 × 3,00 × 8,00.

#### Embarque y pantalanes

- **Pasarela de embarque de barco** (`estaciones_y_aeropuerto/pasarela_embarque_barco`): 1,00 × 6,00 × 0,20 (no corta el paso).
- **Pantalán flotante (tramo)** (`estaciones_y_aeropuerto/pantalan_flotante`): 2,00 × 8,00 × 0,30 (no corta el paso).
- **Torreta de agua y luz de pantalán** (`estaciones_y_aeropuerto/torreta_pantalan`): 0,30 × 0,30 × 1,10.
- **Rampa de embarque de vehículos** (`estaciones_y_aeropuerto/rampa_embarque_vehiculos`): 6,00 × 10,00 × 0,20 (no corta el paso).

#### Estación marítima

- **Caseta de taquilla de ferris** (`estaciones_y_aeropuerto/taquilla_ferris`): 2,50 × 2,00 × 2,60 (puede esconder un premio).
- **Carro jaula de equipajes del ferri** (`estaciones_y_aeropuerto/carro_jaula_equipajes_ferri`): 1,50 × 1,00 × 1,80 (puede esconder un premio).

#### Pesca y lonja

- **Redes y nasas amontonadas** (`estaciones_y_aeropuerto/redes_nasas_amontonadas`): 2,50 × 1,50 × 0,80 (puede esconder un premio).
- **Cajas de pescado apiladas** (`estaciones_y_aeropuerto/cajas_pescado_lonja`): 0,80 × 0,60 × 0,90 (puede esconder un premio).
- **Báscula de la lonja** (`estaciones_y_aeropuerto/bascula_lonja`): 1,00 × 1,20 × 1,20.
- **Carretilla de mano de la lonja** (`estaciones_y_aeropuerto/carretilla_mano_lonja`): 0,60 × 0,60 × 1,20.

## Sonidos propios (9)

`arco_detector_pitido`, `buggy_aeropuerto`, `cinta_equipajes`, `cinta_facturacion`, `consigna_bip`, `paso_nivel_campana`, `puertas_anden_aviso`, `rayos_x_equipajes`, `tren_parado`.

## Sonidos que toma del complemento `comun` (2)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`amarras_crujido`, `bandeja_seguridad`.

## Sonidos que toma del complemento `hogar` (5)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`interruptor`, `puerta_cristal`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (1)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`teclado`.

## Sonidos que toma del complemento `oficina_y_comercio` (2)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_registradora`, `cortina`.

## Sonidos que toma del complemento `transporte` (7)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `interfono`, `megafonia`, `taquilla`, `teclas_cajero`, `torno`.

## Sonidos que toma del complemento `juego` (2)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`llaves`, `monedas`.
