# Hogar

Muebles y objetos de una vivienda: salón, cocina, dormitorio, baño, entrada y los trastos que suelen quedar por medio.

- Identificador: `hogar`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo hogar` a partir de `tools/complementos_serie/hogar.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (108)

Medidas por defecto: ancho × fondo × alto, en metros.

### Salón (26)

#### Sofás y sillones

- **Sofá** (`hogar/sofa`): 2,00 × 0,90 × 0,85 (3 variantes; puede esconder un premio).
- **Sofá en ele** (`hogar/sofa_ele`): 2,60 × 1,70 × 0,85 (2 variantes; puede esconder un premio).
- **Sillón** (`hogar/sillon`): 0,85 × 0,85 × 0,95.
- **Puf reposapiés** (`hogar/puf_reposapies`): 0,50 × 0,50 × 0,42 (3 variantes; puede esconder un premio).
- **Mecedora** (`hogar/mecedora`): 0,60 × 0,95 × 1,05.
- **Sofá cama** (`hogar/sofa_cama`): 1,90 × 0,95 × 0,85 (2 variantes; puede esconder un premio).

#### Mesas de salón y comedor

- **Mesa de centro** (`hogar/mesa_centro`): 1,10 × 0,60 × 0,42 (3 variantes).
- **Mesa redonda** (`hogar/mesa_redonda`): 1,10 × 1,10 × 0,75 (3 variantes).
- **Mesa de comedor** (`hogar/mesa_comedor`): 1,60 × 0,90 × 0,75 (3 variantes).
- **Mesa camilla con brasero** (`hogar/mesa_camilla_brasero`): 0,90 × 0,90 × 0,72 (3 variantes; puede esconder un premio).
- **Mesas nido** (`hogar/mesas_nido`): 0,50 × 0,40 × 0,50.

#### Muebles de almacenaje

- **Mueble de televisión con televisor** (`hogar/mueble_tv`): 1,60 × 0,42 × 1,20 (3 variantes; puede esconder un premio).
- **Estantería** (`hogar/estanteria`): 0,80 × 0,30 × 1,90 (3 variantes; puede esconder un premio).
- **Aparador** (`hogar/aparador`): 1,60 × 0,45 × 0,85 (3 variantes; puede esconder un premio).

#### Luz, calor y aire

- **Lámpara de pie** (`hogar/lampara_pie`): 0,35 × 0,35 × 1,60.
- **Chimenea de leña** (`hogar/chimenea`): 1,20 × 0,90 × 1,30 (3 variantes).
- **Lámpara colgante baja** (`hogar/lampara_colgante`): 0,45 × 0,45 × 0,30 (2 variantes; colgado a 1,50 m).
- **Ventilador de pie** (`hogar/ventilador_pie`): 0,45 × 0,45 × 1,30 (2 variantes).
- **Estufa portátil** (`hogar/estufa_portatil`): 0,45 × 0,35 × 0,70 (3 variantes).
- **Aire acondicionado portátil** (`hogar/aire_portatil`): 0,45 × 0,40 × 0,80.

#### Alfombras, plantas, relojes y mascotas

- **Alfombra** (`hogar/alfombra`): 2,00 × 1,40 × 0,02 (3 variantes; no corta el paso; puede esconder un premio).
- **Planta grande** (`hogar/planta_grande`): 0,50 × 0,50 × 1,40 (puede esconder un premio).
- **Reloj de pie** (`hogar/reloj_pie`): 0,50 × 0,30 × 2,00.
- **Rascador de gato** (`hogar/rascador_gato`): 0,60 × 0,50 × 1,30 (3 variantes; puede esconder un premio).

#### Pianos

- **Piano vertical** (`hogar/piano`): 1,50 × 0,60 × 1,20.
- **Piano de cola** (`hogar/piano_cola`): 1,50 × 1,80 × 1,00 (3 variantes).

### Cocina (18)

#### Muebles de cocina

- **Encimera** (`hogar/encimera`): 1,80 × 0,62 × 0,90 (4 variantes; puede esconder un premio).
- **Encimera en ele** (`hogar/encimera_ele`): 2,40 × 2,00 × 0,90 (puede esconder un premio).
- **Isla de cocina** (`hogar/isla`): 1,80 × 0,90 × 0,90 (puede esconder un premio).
- **Armarios altos de cocina** (`hogar/armarios_altos`): 1,20 × 0,35 × 0,70 (colgado a 1,45 m; puede esconder un premio).
- **Columna despensa** (`hogar/columna_despensa`): 0,60 × 0,60 × 2,10 (3 variantes; puede esconder un premio).

#### Electrodomésticos de cocina

- **Frigorífico** (`hogar/frigorifico`): 0,60 × 0,66 × 1,85 (3 variantes; puede esconder un premio).
- **Cocina** (`hogar/cocina`): 0,60 × 0,60 × 0,90.
- **Columna de horno** (`hogar/horno`): 0,60 × 0,58 × 2,00 (puede esconder un premio).
- **Lavavajillas** (`hogar/lavavajillas`): 0,60 × 0,60 × 0,85 (2 variantes; puede esconder un premio).
- **Microondas** (`hogar/microondas`): 0,48 × 0,38 × 0,30 (colgado a 0,90 m; puede esconder un premio).
- **Campana extractora** (`hogar/campana_extractora`): 0,90 × 0,50 × 0,60 (3 variantes; colgado a 1,50 m).

#### Fregadero y basura

- **Fregadero con grifo** (`hogar/fregadero`): 0,80 × 0,60 × 0,90 (3 variantes).
- **Cubo de basura** (`hogar/cubo_basura`): 0,30 × 0,30 × 0,60 (puede esconder un premio).

#### Mesa y asientos de cocina

- **Mesa de cocina** (`hogar/mesa_cocina`): 1,10 × 0,70 × 0,75 (3 variantes).
- **Silla** (`hogar/silla`): 0,45 × 0,48 × 0,90.
- **Taburete** (`hogar/taburete`): 0,35 × 0,35 × 0,65 (2 variantes).
- **Mesa abatible de pared** (`hogar/mesa_abatible_pared`): 0,80 × 0,50 × 0,75 (2 variantes).
- **Banco rinconera de cocina** (`hogar/banco_rinconera`): 1,60 × 1,20 × 0,90 (puede esconder un premio).

### Dormitorio (13)

#### Camas y cunas

- **Cama** (`hogar/cama`): 1,35 × 1,90 × 0,50 (6 variantes; puede esconder un premio).
- **Cama con cabecero** (`hogar/cama_cabecero`): 1,60 × 2,00 × 1,10 (3 variantes; puede esconder un premio).
- **Litera** (`hogar/litera`): 1,00 × 2,00 × 1,60 (puede esconder un premio).
- **Cuna** (`hogar/cuna`): 0,66 × 1,26 × 0,95 (2 variantes; puede esconder un premio).
- **Cama abatible** (`hogar/cama_abatible`): 1,45 × 0,45 × 2,10 (3 variantes).
- **Colchón hinchable** (`hogar/colchon_hinchable`): 1,40 × 1,95 × 0,30 (3 variantes; puede esconder un premio).

#### Armarios, cómodas y mesillas

- **Mesilla de noche** (`hogar/mesilla`): 0,45 × 0,40 × 0,55 (puede esconder un premio).
- **Armario** (`hogar/armario`): 1,50 × 0,60 × 2,10 (4 variantes; puede esconder un premio).
- **Cómoda** (`hogar/comoda`): 1,00 × 0,45 × 0,85 (puede esconder un premio).
- **Perchero de pie** (`hogar/perchero`): 0,45 × 0,45 × 1,75 (puede esconder un premio).
- **Baúl** (`hogar/baul`): 1,00 × 0,45 × 0,45 (puede esconder un premio).

#### Rincón de estudio

- **Escritorio** (`hogar/escritorio`): 1,20 × 0,60 × 0,75 (3 variantes; puede esconder un premio).
- **Silla de escritorio con ruedas** (`hogar/silla_escritorio`): 0,60 × 0,60 × 0,95.

### Baño (14)

#### Sanitarios, bañera y ducha

- **Inodoro** (`hogar/inodoro`): 0,38 × 0,68 × 0,78.
- **Lavabo** (`hogar/lavabo`): 0,60 × 0,46 × 0,85 (4 variantes).
- **Bidé** (`hogar/bide`): 0,37 × 0,56 × 0,40.
- **Bañera** (`hogar/banera`): 1,70 × 0,70 × 0,58 (4 variantes; puede esconder un premio).
- **Ducha con mampara** (`hogar/ducha`): 0,80 × 0,80 × 1,95 (3 variantes).
- **Plato de ducha de esquina** (`hogar/plato_ducha`): 0,80 × 0,80 × 0,04 (no corta el paso).

#### Muebles y accesorios de baño

- **Toallero de pared** (`hogar/toallero`): 0,50 × 0,10 × 0,90 (colgado a 0,60 m).
- **Columna de baño** (`hogar/columna_bano`): 0,35 × 0,30 × 1,60 (puede esconder un premio).
- **Armario con espejo sobre el lavabo** (`hogar/armario_espejo_bano`): 0,60 × 0,15 × 0,65 (colgado a 1,20 m; puede esconder un premio).
- **Alfombrilla de baño** (`hogar/alfombrilla_bano`): 0,50 × 0,60 × 0,01 (no corta el paso).
- **Báscula de baño** (`hogar/bascula_bano`): 0,32 × 0,32 × 0,03 (no corta el paso).
- **Portarrollos de pie con escobilla** (`hogar/portarrollos_pie`): 0,22 × 0,22 × 0,70.

#### Lavar, tender y planchar

- **Lavadora** (`hogar/lavadora`): 0,60 × 0,58 × 0,85 (puede esconder un premio).
- **Cesto de la ropa sucia** (`hogar/cesto_ropa`): 0,40 × 0,35 × 0,60 (puede esconder un premio).

### Entrada y pasillo (10)

#### Muebles de la entrada

- **Zapatero** (`hogar/zapatero`): 0,70 × 0,25 × 1,00 (puede esconder un premio).
- **Paragüero** (`hogar/paraguero`): 0,25 × 0,25 × 0,50 (puede esconder un premio).
- **Consola de media luna** (`hogar/consola`): 1,00 × 0,35 × 0,80 (puede esconder un premio).
- **Banco de entrada** (`hogar/banco`): 1,00 × 0,38 × 0,45 (puede esconder un premio).

#### Colgado en la pared

- **Espejo colgado** (`hogar/espejo`): 0,60 × 0,05 × 0,90 (colgado a 0,90 m).
- **Radiador** (`hogar/radiador`): 0,80 × 0,10 × 0,60 (colgado a 0,12 m).
- **Extintor colgado** (`hogar/extintor`): 0,15 × 0,15 × 0,50 (colgado a 1,00 m).

#### Suelo y escaleras

- **Felpudo** (`hogar/felpudo`): 0,60 × 0,40 × 0,02 (no corta el paso; puede esconder un premio).
- **Escalera de caracol** (`hogar/escalera_caracol`): 1,60 × 1,60 × 2,70 (3 variantes).
- **Escalera escamoteable de buhardilla** (`hogar/escalera_buhardilla`): 0,65 × 1,50 × 2,50.

### Trastos y obstáculos de casa (8)

#### Lavar, tender y planchar

- **Tendedero** (`hogar/tendedero`): 1,80 × 0,55 × 1,00.
- **Tabla de planchar** (`hogar/tabla_planchar`): 1,20 × 0,38 × 0,90.

#### Cosas que quedan por medio

- **Aspiradora en el suelo** (`hogar/aspiradora`): 0,30 × 0,40 × 0,30.
- **Juguetes por el suelo** (`hogar/juguetes`): 0,80 × 0,60 × 0,12 (puede esconder un premio).
- **Mesa plegable** (`hogar/mesa_plegable`): 0,80 × 0,60 × 0,72.
- **Escalera de mano abierta** (`hogar/escalera_mano`): 0,50 × 1,00 × 1,60.
- **Robot aspirador en marcha** (`hogar/robot_aspirador`): 0,35 × 0,35 × 0,10.

#### Puertas y cortinas de paso

- **Puerta de terraza** (`hogar/puerta_terraza`): 0,80 × 0,08 × 2,05.

### Lavadero, plancha y costura (5)

#### Lavar, tender y planchar

- **Tendedero de techo con poleas** (`hogar/tendedero_techo`): 1,20 × 0,50 × 0,50 (2 variantes; colgado a 1,50 m).

#### Armarios y congelador

- **Congelador arcón** (`hogar/congelador_arcon`): 1,00 × 0,65 × 0,85 (3 variantes; puede esconder un premio).
- **Armario escobero** (`hogar/armario_escobero`): 0,50 × 0,40 × 1,80 (puede esconder un premio).

#### Caldera y agua caliente

- **Caldera o termo colgado** (`hogar/caldera_mural`): 0,45 × 0,35 × 0,75 (3 variantes; colgado a 1,40 m).

#### Costura

- **Máquina de coser en su mueble** (`hogar/maquina_coser`): 0,90 × 0,45 × 0,78 (puede esconder un premio).

### Terraza, balcón y jardín (8)

#### Puertas y cortinas de paso

- **Cortina de tiras en la puerta** (`hogar/cortina_tiras`): 0,85 × 0,03 × 2,05 (no corta el paso).

#### Hamacas y sillones colgantes

- **Sillón colgante** (`hogar/sillon_colgante`): 1,05 × 1,10 × 2,00.
- **Hamaca con soporte** (`hogar/hamaca_soporte`): 3,00 × 1,10 × 1,10.

#### Barbacoa y leña

- **Barbacoa portátil de tapa** (`hogar/barbacoa_portatil`): 0,60 × 0,60 × 0,95 (2 variantes).
- **Leña apilada** (`hogar/lena_apilada`): 1,20 × 0,40 × 0,90 (3 variantes).

#### Jardín, piscina y almacenaje exterior

- **Cortacésped** (`hogar/cortacesped`): 0,50 × 1,50 × 1,00.
- **Armario de resina de terraza** (`hogar/armario_resina_terraza`): 0,70 × 0,45 × 1,70 (2 variantes; puede esconder un premio).
- **Piscina hinchable** (`hogar/piscina_hinchable`): 2,00 × 1,50 × 0,50 (3 variantes).

### Habitación infantil (6)

#### Camas de niños y cunas

- **Cama nido** (`hogar/cama_nido`): 1,00 × 2,00 × 0,50 (2 variantes; puede esconder un premio).
- **Cama casita Montessori** (`hogar/cama_montessori`): 1,00 × 2,00 × 1,60 (2 variantes; puede esconder un premio).
- **Cuna de colecho** (`hogar/cuna_colecho`): 0,60 × 0,95 × 0,80 (puede esconder un premio).

#### Baño y juego del bebé

- **Bañera de bebé con patas** (`hogar/banera_bebe_patas`): 0,55 × 0,90 × 0,95.
- **Gimnasio de bebé** (`hogar/gimnasio_bebe`): 0,85 × 0,85 × 0,45.
- **Taburete escalón infantil** (`hogar/taburete_escalon`): 0,40 × 0,30 × 0,22 (2 variantes).

## Sonidos propios (20)

`aspiradora`, `cajon`, `cisterna`, `hogar_cortacesped`, `hogar_cortina_tiras`, `hogar_maquina_coser`, `hogar_mecedora`, `interruptor`, `juguetes`, `lavadora`, `lavavajillas`, `microondas`, `microondas_fin`, `piano`, `puerta_cristal`, `puerta_electrodomestico`, `puerta_mueble`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `comun` (9)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`barbacoa_brasas`, `brasas_castanera`, `caldera_comunitaria`, `chapuzon`, `columpio_chirrido`, `compresor_azotea`, `estufa_terraza_gas`, `polea_tendedero`, `vajilla_tintineo`.

## Sonidos que toma del complemento `calle` (2)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`papel`, `zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (1)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`.

## Sonidos que toma del complemento `juego` (2)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cofre_abrir`, `cofre_cerrar`.
