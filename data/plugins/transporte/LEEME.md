# Transporte

Paradas de autobús y de taxi, vestíbulos de estación, tornos, máquinas de billetes y andenes, con sus referencias y sus avisos.

- Identificador: `transporte`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo transporte` a partir de `tools/complementos_serie/transporte.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (64)

Medidas por defecto: ancho × fondo × alto, en metros.

### Parada de autobús y de taxi (11)

#### Marquesinas

- **Marquesina de autobús con banco** (`transporte/marquesina`): 4,00 × 1,60 × 2,60 (3 variantes; puede esconder un premio).
- **Marquesina de autobús en ele** (`transporte/marquesina_ele`): 4,00 × 1,60 × 2,60 (puede esconder un premio).

#### Postes y paneles de parada

- **Poste de parada** (`transporte/poste_parada`): 0,10 × 0,10 × 2,70.
- **Panel informativo sonoro** (`transporte/panel_sonoro`): 0,30 × 0,20 × 2,60.
- **Poste de parada provisional sobre base** (`transporte/parada_provisional`): 0,50 × 0,50 × 2,50.

#### Apoyos, plataformas y aparcabicis

- **Apoyo isquiático** (`transporte/apoyo_isquiatico`): 1,20 × 0,35 × 0,80.
- **Aparcamiento de bicicletas** (`transporte/aparcabicis`): 3,00 × 1,80 × 1,00.
- **Plataforma elevada de embarque** (`transporte/plataforma_embarque`): 8,00 × 2,50 × 0,25 (no corta el paso).

#### Parada de taxi

- **Poste de parada de taxi** (`transporte/poste_taxi`): 0,10 × 0,10 × 2,70.
- **Poste llamador de taxi** (`transporte/llamador_taxi`): 0,25 × 0,20 × 1,50.
- **Taxi adaptado con la rampa trasera sacada** (`transporte/eurotaxi_rampa`): 1,90 × 6,50 × 1,90.

### Vestíbulo de estación (10)

#### Billetes e información

- **Máquina de billetes** (`transporte/maquina_billetes`): 0,80 × 0,70 × 1,80 (puede esconder un premio).
- **Mostrador de taquilla** (`transporte/mostrador_taquilla`): 2,00 × 0,80 × 1,10 (puede esconder un premio).
- **Quiosco de información** (`transporte/kiosco_informacion`): 2,40 × 2,40 × 1,10 (puede esconder un premio).

#### Asientos de espera

- **Fila de asientos de estación** (`transporte/asientos_estacion`): 2,40 × 0,65 × 0,80 (3 variantes).
- **Asientos de espalda con espalda** (`transporte/asientos_dobles`): 2,40 × 1,30 × 0,80.

#### Máquinas, papeleras y consigna

- **Máquina expendedora** (`transporte/vending`): 0,90 × 0,85 × 1,83 (puede esconder un premio).
- **Papelera de estación** (`transporte/papelera`): 0,40 × 0,40 × 0,90 (puede esconder un premio).
- **Consigna de equipajes** (`transporte/consigna`): 1,80 × 0,80 × 1,85 (puede esconder un premio).

#### Equipaje

- **Maleta en el suelo** (`transporte/maleta`): 0,45 × 0,30 × 0,70 (puede esconder un premio).
- **Carro portaequipajes** (`transporte/carro_equipaje`): 0,65 × 0,95 × 1,05 (puede esconder un premio).

### Tornos y accesos (7)

#### Validación y tornos

- **Canceladora** (`transporte/canceladora`): 0,25 × 0,25 × 1,10.
- **Torno de entrada** (`transporte/torno`): 0,80 × 1,20 × 1,00.
- **Tornos en fila** (`transporte/tornos_fila`): 3,20 × 1,50 × 1,00 (3 variantes).
- **Puerta de acceso ancha** (`transporte/puerta_acceso_ancha`): 1,40 × 1,50 × 1,00.

#### Barandillas, escaleras y ascensores

- **Barandilla** (`transporte/barandilla`): 2,00 × 0,06 × 1,00.
- **Ascensor de calle** (`transporte/ascensor_exterior`): 2,00 × 2,20 × 3,00.
- **Escalera mecánica (tramo)** (`transporte/escalera_mecanica`): 1,00 × 9,00 × 4,50 (3 variantes; no corta el paso).

### Andén (7)

#### Bancos, columnas y ceniceros

- **Banco de andén** (`transporte/banco_anden`): 1,80 × 0,60 × 0,80 (puede esconder un premio).
- **Columna de andén** (`transporte/columna_anden`): 0,40 × 0,40 × 4,00.
- **Cenicero de pie** (`transporte/cenicero`): 0,25 × 0,25 × 1,00.

#### Borde y franjas del andén

- **Borde de andén con franja táctil** (`transporte/borde_anden`): 10,00 × 0,60 × 0,01 (no corta el paso).
- **Franja guía de encaminamiento** (`transporte/franja_guia`): 0,40 × 5,00 × 0,01 (no corta el paso).

#### Carteles y relojes

- **Cartel colgante** (`transporte/cartel_colgante`): 1,50 × 0,15 × 0,40 (colgado a 1,85 m).
- **Reloj de estación** (`transporte/reloj_estacion`): 0,60 × 0,12 × 0,60 (colgado a 2,20 m).

### Información y ayuda (5)

#### Información accesible

- **Plano táctil** (`transporte/plano_tactil`): 0,80 × 0,50 × 1,00.
- **Baliza sonora de puerta** (`transporte/baliza_sonora`): 0,25 × 0,10 × 0,15 (no corta el paso; colgado a 2,30 m).
- **Altavoz de megafonía** (`transporte/megafono`): 0,30 × 0,25 × 0,30 (no corta el paso; colgado a 2,60 m).

#### Ayuda y emergencia

- **Interfono de ayuda** (`transporte/interfono`): 0,30 × 0,25 × 1,50.
- **Extintor colgado** (`transporte/extintor`): 0,15 × 0,15 × 0,50 (colgado a 1,00 m).

### A bordo: autobús, tranvía, metro y tren (24)

#### Puertas y puesto del conductor

- **Puerta doble de autobús** (`transporte/puerta_autobus`): 1,20 × 0,40 × 2,10 (2 variantes).
- **Puesto del conductor con validadora** (`transporte/puesto_conductor_bus`): 1,10 × 1,40 × 1,20.
- **Mampara de cristal junto a la puerta** (`transporte/mampara_puerta_bus`): 0,70 × 0,05 × 1,60 (colgado a 0,15 m).

#### Suelo, rampas y escalones

- **Rampa abatible de autobús** (`transporte/rampa_autobus`): 0,90 × 1,00 × 0,05 (no corta el paso).
- **Escalones interiores de la puerta** (`transporte/escalones_vehiculo`): 0,80 × 0,90 × 0,60 (3 variantes; no corta el paso).
- **Escalón de la tarima trasera** (`transporte/tarima_trasera_bus`): 2,30 × 0,30 × 0,20 (no corta el paso).
- **Cajón del paso de rueda** (`transporte/paso_rueda_bus`): 0,80 × 1,20 × 0,50.
- **Plataforma giratoria del fuelle** (`transporte/plataforma_fuelle_bus`): 1,20 × 1,40 × 0,02 (no corta el paso).
- **Escalera interior de vehículo de dos pisos** (`transporte/escalera_dos_pisos`): 0,60 × 1,80 × 1,80 (no corta el paso).

#### Barras y asideros

- **Barra vertical con pulsador de parada** (`transporte/barra_vertical_pulsador`): 0,04 × 0,04 × 2,10.
- **Barra de techo con asideros colgantes** (`transporte/barra_techo_asideros`): 2,00 × 0,10 × 0,25 (colgado a 1,65 m).
- **Barra central en árbol** (`transporte/barra_arbol_metro`): 0,50 × 0,50 × 2,10.

#### Asientos y espacios reservados

- **Pareja de asientos de autobús** (`transporte/asientos_bus_pareja`): 0,90 × 0,70 × 1,05 (2 variantes).
- **Asiento reservado abatible** (`transporte/asiento_reservado_bus`): 0,45 × 0,45 × 0,90.
- **Respaldo del espacio para silla de ruedas** (`transporte/zona_pmr_bus`): 0,80 × 0,20 × 0,80 (colgado a 0,50 m).
- **Bancada longitudinal de metro** (`transporte/banco_longitudinal_metro`): 2,50 × 0,50 × 0,90 (2 variantes).
- **Cuatro asientos enfrentados con mesa** (`transporte/cuarteto_asientos_tren`): 1,00 × 1,80 × 1,10 (puede esconder un premio).

#### Avisos y seguridad

- **Pantalla y altavoz de próxima parada** (`transporte/aviso_proxima_parada`): 0,80 × 0,10 × 0,25 (colgado a 1,95 m).
- **Martillo rompecristales** (`transporte/martillo_emergencia`): 0,08 × 0,05 × 0,20 (no corta el paso; colgado a 1,50 m).
- **Tirador de freno de emergencia** (`transporte/freno_emergencia`): 0,20 × 0,08 × 0,25 (no corta el paso; colgado a 1,60 m).

#### Equipaje, aseo y cafetería

- **Portaequipajes sobre los asientos** (`transporte/rejilla_equipaje`): 2,00 × 0,45 × 0,20 (colgado a 1,70 m; puede esconder un premio).
- **Maletero de pie del tren** (`transporte/maletero_tren`): 1,00 × 0,60 × 1,60 (puede esconder un premio).
- **Aseo adaptado de tren** (`transporte/aseo_tren`): 1,80 × 1,80 × 2,10.
- **Barra de la cafetería del tren** (`transporte/barra_cafeteria_tren`): 2,50 × 0,60 × 1,05.

## Sonidos propios (14)

`bip_validacion`, `carrito`, `interfono`, `megafonia`, `taquilla`, `teclas_cajero`, `timbre_bici`, `torno`, `transporte_aseo_vacio`, `transporte_escalera_mecanica`, `transporte_proxima_parada`, `transporte_puerta_bus`, `transporte_pulsador_parada`, `transporte_rampa_aviso`.

## Sonidos que toma del complemento `comun` (5)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`portamaletas_ruedas`, `uni_asiento_abatible`, `vajilla_tintineo`, `vehiculos_ralenti_diesel`, `zumbador_alarma`.

## Sonidos que toma del complemento `hogar` (2)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`puerta_cristal`, `sentarse`.

## Sonidos que toma del complemento `oficina_y_comercio` (1)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_registradora`.

## Sonidos que toma del complemento `juego` (1)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`monedas`.
