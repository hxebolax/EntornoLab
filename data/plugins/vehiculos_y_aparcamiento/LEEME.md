# Vehículos y aparcamiento

Vehículos parados como obstáculo (con sus puertas, portones, rampas y voladizos), remolques, contenedores y máquinas de obra, y lo que hay en un aparcamiento y en una gasolinera: plazas, topes, barreras, pago, lavado y aire.

- Identificador: `vehiculos_y_aparcamiento`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo vehiculos_y_aparcamiento` a partir de `tools/complementos_serie/vehiculos_y_aparcamiento.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (92)

Medidas por defecto: ancho × fondo × alto, en metros.

### Coches, furgonetas y caravanas (19)

#### Coches y todoterrenos

- **Todoterreno alto** (`vehiculos_y_aparcamiento/todoterreno_alto`): 1,98 × 4,90 × 1,90 (2 variantes).
- **Camioneta con caja abierta** (`vehiculos_y_aparcamiento/camioneta_caja_abierta`): 1,95 × 5,40 × 1,85 (puede esconder un premio).
- **Cuadriciclo sin carné** (`vehiculos_y_aparcamiento/cuadriciclo`): 1,50 × 3,00 × 1,50.
- **Taxi parado con el motor en marcha** (`vehiculos_y_aparcamiento/taxi_parado`): 1,82 × 4,65 × 1,50.
- **Coche eléctrico cargando** (`vehiculos_y_aparcamiento/coche_electrico_cargando`): 1,85 × 4,50 × 1,60.
- **Coche con remolque** (`vehiculos_y_aparcamiento/coche_con_remolque`): 1,80 × 7,00 × 1,60 (puede esconder un premio).

#### Puertas abiertas y salientes de coche

- **Cable de recarga por el suelo** (`vehiculos_y_aparcamiento/cable_recarga_suelo`): 2,50 × 0,05 × 0,03 (no corta el paso).
- **Portón trasero abierto** (`vehiculos_y_aparcamiento/porton_trasero_abierto`): 1,30 × 1,00 × 0,20 (colgado a 1,75 m).
- **Puerta de coche abierta hacia la acera** (`vehiculos_y_aparcamiento/puerta_coche_abierta`): 1,00 × 0,10 × 1,10 (colgado a 0,25 m).
- **Portabicicletas trasero con bicicletas** (`vehiculos_y_aparcamiento/portabicicletas_trasero`): 1,70 × 0,60 × 1,00 (colgado a 0,60 m).
- **Carga que sobresale de la baca** (`vehiculos_y_aparcamiento/carga_saliente_baca`): 0,45 × 1,20 × 0,15 (colgado a 1,60 m).
- **Bola de enganche de remolque** (`vehiculos_y_aparcamiento/bola_remolque`): 0,10 × 0,20 × 0,12 (colgado a 0,35 m).

#### Furgonetas y furgones

- **Furgoneta de reparto con las puertas traseras abiertas** (`vehiculos_y_aparcamiento/furgoneta_puertas_abiertas`): 2,05 × 6,30 × 2,50 (puede esconder un premio).
- **Furgón de caja con capitoné** (`vehiculos_y_aparcamiento/furgon_capitone`): 2,20 × 6,80 × 3,20 (puede esconder un premio).
- **Furgón de comida con el mostrador abierto** (`vehiculos_y_aparcamiento/puesto_rodante_comida`): 3,20 × 6,00 × 3,00.

#### Caravanas y autocaravanas

- **Caravana** (`vehiculos_y_aparcamiento/caravana`): 2,30 × 6,00 × 2,60 (puede esconder un premio).
- **Autocaravana con el toldo desplegado** (`vehiculos_y_aparcamiento/autocaravana_toldo`): 4,80 × 7,00 × 3,00 (puede esconder un premio).

#### Vehículos ligeros

- **Carrito de golf** (`vehiculos_y_aparcamiento/carrito_golf`): 1,20 × 2,40 × 1,80 (2 variantes).
- **Quad aparcado** (`vehiculos_y_aparcamiento/quad`): 1,15 × 2,00 × 1,15.

### Camiones y autobuses (13)

#### Camiones

- **Camión de reparto de caja cerrada** (`vehiculos_y_aparcamiento/camion_reparto`): 2,50 × 8,50 × 3,60 (2 variantes; puede esconder un premio).
- **Camión de mudanzas con rampa** (`vehiculos_y_aparcamiento/camion_mudanzas_rampa`): 2,50 × 11,00 × 3,60 (puede esconder un premio).
- **Camión hormigonera** (`vehiculos_y_aparcamiento/camion_hormigonera`): 2,50 × 9,00 × 3,90.
- **Camión grúa con los estabilizadores sacados** (`vehiculos_y_aparcamiento/camion_grua_estabilizadores`): 5,50 × 10,00 × 3,80.
- **Tractor** (`vehiculos_y_aparcamiento/tractor`): 2,40 × 4,50 × 2,90.

#### Autobuses y autocares

- **Autobús urbano parado** (`vehiculos_y_aparcamiento/autobus_urbano_parado`): 2,55 × 12,00 × 3,10 (2 variantes).
- **Autobús articulado: coche trasero con fuelle** (`vehiculos_y_aparcamiento/autobus_articulado_trasero`): 2,55 × 8,00 × 3,10.
- **Autocar** (`vehiculos_y_aparcamiento/autocar`): 2,55 × 13,00 × 3,70 (puede esconder un premio).
- **Microbús adaptado con la rampa sacada** (`vehiculos_y_aparcamiento/microbus_rampa_lateral`): 3,30 × 7,50 × 2,80.

#### Voladizos de camión y autobús

- **Plataforma elevadora de camión** (`vehiculos_y_aparcamiento/plataforma_elevadora_camion`): 2,40 × 1,80 × 0,10 (colgado a 1,00 m).
- **Retrovisor saliente de camión o autobús** (`vehiculos_y_aparcamiento/retrovisor_camion`): 0,30 × 0,20 × 0,45 (colgado a 1,50 m).
- **Trampilla de maletero de autocar abierta** (`vehiculos_y_aparcamiento/trampilla_maletero_autocar`): 2,00 × 0,90 × 0,10 (colgado a 1,50 m).
- **Carretilla de reparto de bebidas** (`vehiculos_y_aparcamiento/carretilla_bebidas`): 0,50 × 0,60 × 1,40 (puede esconder un premio).

### Emergencias y limpieza (7)

#### Vehículos de emergencias

- **Ambulancia con el portón abierto** (`vehiculos_y_aparcamiento/ambulancia_porton`): 2,10 × 7,20 × 2,70 (puede esconder un premio).
- **Coche de bomberos** (`vehiculos_y_aparcamiento/coche_bomberos`): 2,50 × 8,00 × 3,30 (puede esconder un premio).
- **Manguera de bomberos por el suelo** (`vehiculos_y_aparcamiento/manguera_bomberos`): 6,00 × 0,10 × 0,07 (no corta el paso).
- **Coche patrulla parado** (`vehiculos_y_aparcamiento/coche_patrulla`): 1,85 × 4,70 × 1,70.

#### Vehículos de limpieza

- **Barredora** (`vehiculos_y_aparcamiento/barredora`): 1,80 × 4,50 × 2,40 (2 variantes).
- **Camión de la basura** (`vehiculos_y_aparcamiento/camion_basura`): 2,50 × 9,50 × 3,70.
- **Carro de barrendero** (`vehiculos_y_aparcamiento/carro_barrendero`): 0,70 × 1,20 × 1,10 (puede esconder un premio).

### Bicicletas, motos y triciclos (7)

#### Bicicletas y triciclos

- **Bicicleta suelta sobre su pata de cabra** (`vehiculos_y_aparcamiento/bici_caballete`): 0,62 × 1,80 × 1,05.
- **Bicicleta de carga** (`vehiculos_y_aparcamiento/bici_carga`): 0,90 × 2,50 × 1,10 (puede esconder un premio).
- **Bicicleta con remolque infantil** (`vehiculos_y_aparcamiento/bici_remolque_infantil`): 0,80 × 3,30 × 1,05 (puede esconder un premio).
- **Triciclo adaptado de adulto** (`vehiculos_y_aparcamiento/triciclo_adaptado`): 0,80 × 1,80 × 1,10 (puede esconder un premio).
- **Bicicleta tirada en el suelo** (`vehiculos_y_aparcamiento/bicicleta_tumbada`): 1,75 × 1,00 × 0,35.

#### Motos y ciclomotores

- **Moto grande con maletas** (`vehiculos_y_aparcamiento/moto_grande_maletas`): 1,00 × 2,40 × 1,45 (puede esconder un premio).
- **Ciclomotor de reparto con cajón** (`vehiculos_y_aparcamiento/ciclomotor_reparto`): 0,70 × 1,95 × 1,50 (puede esconder un premio).

### Remolques y contenedores de obra (9)

#### Remolques

- **Remolque suelto con lanza** (`vehiculos_y_aparcamiento/remolque_suelto`): 1,50 × 3,30 × 0,90 (puede esconder un premio).
- **Montamuebles de mudanzas** (`vehiculos_y_aparcamiento/montamuebles`): 1,80 × 5,00 × 9,00.

#### Contenedores y casetas de obra

- **Cuba de escombros** (`vehiculos_y_aparcamiento/cuba_escombros`): 1,80 × 3,40 × 1,30 (3 variantes; puede esconder un premio).
- **Contenedor marítimo** (`vehiculos_y_aparcamiento/contenedor_maritimo`): 2,44 × 6,06 × 2,59 (2 variantes; puede esconder un premio).
- **Caseta de obra** (`vehiculos_y_aparcamiento/caseta_obra`): 2,40 × 6,00 × 2,60 (puede esconder un premio).
- **Depósito de gasoil de obra** (`vehiculos_y_aparcamiento/deposito_gasoil`): 1,30 × 2,20 × 1,50.
- **Silo de mortero** (`vehiculos_y_aparcamiento/silo_mortero`): 2,50 × 2,50 × 7,00.

#### Maquinaria de obra en la calle

- **Grupo electrógeno remolcable** (`vehiculos_y_aparcamiento/grupo_electrogeno`): 1,40 × 3,20 × 1,70.
- **Miniexcavadora parada** (`vehiculos_y_aparcamiento/miniexcavadora`): 1,50 × 4,50 × 2,50.

### Plazas, topes y suelo del aparcamiento (21)

#### Marcas de plaza

- **Plaza de aparcamiento en batería** (`vehiculos_y_aparcamiento/plaza_bateria`): 2,50 × 5,00 × 0,01 (3 variantes; no corta el paso).
- **Plaza de aparcamiento en línea** (`vehiculos_y_aparcamiento/plaza_linea`): 5,00 × 2,20 × 0,01 (no corta el paso).
- **Plaza de aparcamiento en espiga** (`vehiculos_y_aparcamiento/plaza_espiga`): 4,00 × 4,80 × 0,01 (no corta el paso).
- **Plaza reservada de movilidad reducida** (`vehiculos_y_aparcamiento/plaza_movilidad_reducida`): 3,70 × 5,00 × 0,01 (3 variantes; no corta el paso).

#### Topes, bordillos y cierres

- **Tope de rueda** (`vehiculos_y_aparcamiento/tope_rueda`): 1,80 × 0,15 × 0,10 (no corta el paso).
- **Isleta con bordillo del aparcamiento** (`vehiculos_y_aparcamiento/isleta_aparcamiento`): 5,00 × 1,50 × 0,15.
- **Bolardo abatible de plaza reservada** (`vehiculos_y_aparcamiento/bolardo_abatible_plaza`): 0,50 × 0,10 × 0,60.
- **Cepo en la rueda** (`vehiculos_y_aparcamiento/cepo_rueda`): 0,50 × 0,30 × 0,50.
- **Guardarraíl bajo** (`vehiculos_y_aparcamiento/guardarrail_bajo`): 4,00 × 0,30 × 0,70 (2 variantes).
- **Cadena entre postes** (`vehiculos_y_aparcamiento/cadena_entre_postes`): 2,50 × 0,08 × 0,08 (colgado a 0,50 m).

#### Aparcamiento de bicis, motos y patinetes

- **Aparcamiento de motos con anclajes** (`vehiculos_y_aparcamiento/anclajes_motos`): 4,00 × 0,70 × 0,40.
- **Taquilla individual de bicicleta** (`vehiculos_y_aparcamiento/taquilla_bicicleta`): 0,90 × 2,00 × 1,40 (puede esconder un premio).
- **Bancada de bicicletas de dos pisos** (`vehiculos_y_aparcamiento/bancada_bicis_dos_pisos`): 3,00 × 2,00 × 2,70 (3 variantes).
- **Estación de bicicleta pública** (`vehiculos_y_aparcamiento/estacion_bici_publica`): 7,50 × 1,90 × 1,10 (3 variantes).
- **Estación de patinetes compartidos** (`vehiculos_y_aparcamiento/estacion_patinetes`): 3,00 × 1,20 × 1,20.

#### Rampas y juntas del suelo

- **Rampa de entrada al aparcamiento** (`vehiculos_y_aparcamiento/rampa_aparcamiento`): 3,50 × 10,00 × 0,10 (no corta el paso).
- **Junta de dilatación metálica** (`vehiculos_y_aparcamiento/junta_dilatacion`): 5,00 × 0,20 × 0,01 (no corta el paso).
- **Canaleta de desagüe con rejilla** (`vehiculos_y_aparcamiento/canaleta_rejilla`): 3,50 × 0,20 × 0,02 (no corta el paso).
- **Banda reductora de goma** (`vehiculos_y_aparcamiento/banda_reductora_goma`): 3,00 × 0,40 × 0,05 (no corta el paso).

#### Marquesinas y recintos

- **Pilar de marquesina de aparcamiento** (`vehiculos_y_aparcamiento/pilar_marquesina_solar`): 0,60 × 0,60 × 2,70.
- **Recinto de carritos del aparcamiento** (`vehiculos_y_aparcamiento/recinto_carritos`): 2,50 × 5,00 × 2,30 (puede esconder un premio).

### Barreras, pago y control (9)

#### Barreras y cancelas

- **Barrera de aparcamiento** (`vehiculos_y_aparcamiento/barrera_aparcamiento`): 3,00 × 0,10 × 0,10 (3 variantes; colgado a 0,90 m).
- **Cancela corredera motorizada** (`vehiculos_y_aparcamiento/cancela_corredera`): 4,00 × 0,10 × 1,80.

#### Tiques y pago

- **Columna de tiques del aparcamiento** (`vehiculos_y_aparcamiento/columna_tiques`): 0,35 × 0,40 × 1,25 (2 variantes).
- **Cajero del aparcamiento** (`vehiculos_y_aparcamiento/cajero_aparcamiento`): 0,70 × 0,50 × 1,70 (puede esconder un premio).

#### Gálibo, espejos y avisos

- **Poste lector de matrículas** (`vehiculos_y_aparcamiento/lector_matricula`): 0,20 × 0,20 × 1,20.
- **Garita de control** (`vehiculos_y_aparcamiento/garita_control`): 1,50 × 2,00 × 2,50.
- **Arco de gálibo** (`vehiculos_y_aparcamiento/arco_galibo`): 3,00 × 0,10 × 0,15 (colgado a 2,00 m).
- **Espejo convexo de esquina** (`vehiculos_y_aparcamiento/espejo_convexo`): 0,60 × 0,25 × 0,60 (colgado a 1,70 m).
- **Avisador de salida de vehículos** (`vehiculos_y_aparcamiento/avisador_salida_vehiculos`): 0,25 × 0,15 × 0,30 (no corta el paso; colgado a 2,20 m).

### Gasolinera, lavado y aire (7)

#### Surtidores

- **Surtidor de combustible** (`vehiculos_y_aparcamiento/surtidor_combustible`): 1,20 × 0,60 × 2,10.
- **Arco protector de surtidor** (`vehiculos_y_aparcamiento/arco_protector_surtidor`): 0,80 × 0,09 × 0,60.
- **Jaula de bombonas de butano** (`vehiculos_y_aparcamiento/jaula_bombonas`): 1,50 × 0,80 × 1,80 (puede esconder un premio).

#### Lavado

- **Túnel de lavado** (`vehiculos_y_aparcamiento/tunel_lavado`): 4,50 × 10,00 × 3,50.
- **Box de lavado a presión** (`vehiculos_y_aparcamiento/box_lavado_manual`): 4,00 × 6,00 × 3,20.

#### Aire y aspirado

- **Aspirador de gasolinera** (`vehiculos_y_aparcamiento/aspirador_gasolinera`): 0,60 × 0,60 × 1,70.
- **Poste de aire y agua** (`vehiculos_y_aparcamiento/poste_aire_agua`): 0,40 × 0,35 × 1,40.

## Sonidos propios (11)

`aparcamiento_avisador_salida`, `aparcamiento_barrera`, `aparcamiento_tique`, `aparcamiento_tunel_lavado`, `vehiculos_barredora`, `vehiculos_camion_basura`, `vehiculos_compresor_aire`, `vehiculos_hormigonera`, `vehiculos_marcha_atras`, `vehiculos_plataforma_hidraulica`, `vehiculos_ralenti_gasolina`.

## Sonidos que toma del complemento `comun` (4)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`ducha`, `vehiculos_cadena`, `vehiculos_puerta_coche`, `vehiculos_ralenti_diesel`.

## Sonidos que toma del complemento `hogar` (3)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`puerta_cristal`, `sentarse`, `valla_obra`.

## Sonidos que toma del complemento `calle` (1)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (7)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `interfono`, `megafonia`, `taquilla`, `teclas_cajero`, `timbre_bici`.

## Sonidos que toma del complemento `juego` (2)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`llaves`, `monedas`.
