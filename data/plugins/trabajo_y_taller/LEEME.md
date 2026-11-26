# Trabajo y taller

Lugares de trabajo y de prácticas con sus riesgos reales: taller mecánico, carpintería y taller de metal, almacén y logística, fábrica, laboratorio, cocina profesional y obra por dentro del recinto.

- Identificador: `trabajo_y_taller`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo trabajo_y_taller` a partir de `tools/complementos_serie/trabajo_y_taller.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (153)

Medidas por defecto: ancho × fondo × alto, en metros.

### Taller mecánico (19)

#### Bancos y herramienta

- **Banco de trabajo con tornillo de banco** (`trabajo_y_taller/banco_trabajo_tornillo`): 1,80 × 0,85 × 0,90 (3 variantes; puede esconder un premio).
- **Carro de herramientas con cajones** (`trabajo_y_taller/carro_herramientas`): 0,75 × 0,46 × 0,95 (puede esconder un premio).
- **Panel de herramientas de pared** (`trabajo_y_taller/panel_herramientas`): 1,20 × 0,10 × 1,00 (colgado a 0,95 m; puede esconder un premio).
- **Camilla de mecánico con ruedas** (`trabajo_y_taller/camilla_mecanico`): 0,45 × 1,00 × 0,12.

#### Elevación del vehículo

- **Elevador de coches de dos columnas** (`trabajo_y_taller/elevador_dos_columnas`): 3,40 × 2,40 × 2,85.
- **Coche subido en el elevador** (`trabajo_y_taller/coche_en_elevador`): 1,80 × 4,30 × 1,50 (colgado a 1,60 m).
- **Foso de taller** (`trabajo_y_taller/foso_taller`): 0,90 × 5,00 × 0,05 (2 variantes; no corta el paso).
- **Gato hidráulico de carretilla** (`trabajo_y_taller/gato_carretilla`): 0,35 × 1,30 × 0,95.
- **Caballete de apoyo de coche** (`trabajo_y_taller/caballete_coche`): 0,25 × 0,25 × 0,40.
- **Grúa pluma de motores** (`trabajo_y_taller/grua_pluma_motores`): 1,00 × 1,60 × 1,80.

#### Neumáticos y ruedas

- **Desmontadora de neumáticos** (`trabajo_y_taller/desmontadora_neumaticos`): 1,00 × 1,50 × 1,90.
- **Equilibradora de ruedas** (`trabajo_y_taller/equilibradora_ruedas`): 1,10 × 0,75 × 1,30.
- **Pila de neumáticos** (`trabajo_y_taller/pila_neumaticos`): 0,65 × 0,65 × 1,00 (3 variantes; puede esconder un premio).
- **Estantería de neumáticos** (`trabajo_y_taller/estante_neumaticos`): 2,00 × 0,50 × 2,20 (puede esconder un premio).

#### Aire, aceite y baterías

- **Compresor de aire de taller** (`trabajo_y_taller/compresor_aire`): 0,50 × 1,20 × 1,00 (3 variantes).
- **Enrollador de manguera de aire colgado** (`trabajo_y_taller/enrollador_manguera_aire`): 0,40 × 0,25 × 0,80 (colgado a 1,20 m).
- **Bidón de aceite de 200 litros** (`trabajo_y_taller/bidon_aceite`): 0,58 × 0,58 × 0,88 (puede esconder un premio).
- **Recogedor de aceite usado con embudo** (`trabajo_y_taller/recogedor_aceite`): 0,50 × 0,50 × 1,50.
- **Cargador de baterías con carro** (`trabajo_y_taller/cargador_baterias`): 0,40 × 0,35 × 0,80.

### Carpintería y taller de metal (26)

#### Máquinas de madera

- **Sierra circular de mesa** (`trabajo_y_taller/sierra_mesa`): 0,90 × 1,00 × 0,90 (3 variantes).
- **Sierra de cinta** (`trabajo_y_taller/sierra_cinta`): 0,75 × 0,60 × 1,90.
- **Cepilladora de carpintería** (`trabajo_y_taller/cepilladora`): 0,60 × 2,20 × 0,85.
- **Torno de madera** (`trabajo_y_taller/torno_madera`): 1,50 × 0,50 × 1,20.
- **Lijadora de banda de pie** (`trabajo_y_taller/lijadora_banda`): 0,60 × 1,30 × 1,00.
- **Aspirador de virutas con saco y tubo** (`trabajo_y_taller/aspirador_virutas`): 0,60 × 1,20 × 2,00.

#### Bancos y material de carpintería

- **Banco de carpintero con prensas** (`trabajo_y_taller/banco_carpintero`): 2,00 × 0,70 × 0,88 (puede esconder un premio).
- **Tablero sobre caballetes** (`trabajo_y_taller/tablero_caballetes`): 2,44 × 1,22 × 0,80 (2 variantes).
- **Tablones apoyados en la pared** (`trabajo_y_taller/tablones_pared`): 0,60 × 0,50 × 2,50.
- **Carro de tableros** (`trabajo_y_taller/carro_tableros`): 0,80 × 2,00 × 1,70.
- **Montón de serrín y virutas** (`trabajo_y_taller/monton_serrin`): 1,20 × 1,00 × 0,08 (no corta el paso).
- **Sargentos colgados de una barra** (`trabajo_y_taller/sargentos_colgados`): 1,00 × 0,20 × 0,60 (colgado a 1,10 m).

#### Máquinas de metal

- **Taladro de columna** (`trabajo_y_taller/taladro_columna`): 0,45 × 0,70 × 1,70.
- **Esmeril de banco sobre pedestal** (`trabajo_y_taller/esmeril_banco`): 0,50 × 0,40 × 1,10.
- **Torno de metal** (`trabajo_y_taller/torno_metal`): 2,20 × 0,90 × 1,30.
- **Fresadora de columna** (`trabajo_y_taller/fresadora_columna`): 1,50 × 1,50 × 2,00.
- **Plegadora de chapa** (`trabajo_y_taller/plegadora_chapa`): 2,50 × 1,00 × 1,50.
- **Cizalla guillotina de chapa** (`trabajo_y_taller/cizalla_chapa`): 2,60 × 1,80 × 1,40.

#### Forja y soldadura

- **Equipo de soldadura con carro** (`trabajo_y_taller/equipo_soldadura`): 0,50 × 0,90 × 1,00.
- **Pantalla de soldadura** (`trabajo_y_taller/pantalla_soldadura`): 2,00 × 0,50 × 1,90.
- **Mesa de soldadura** (`trabajo_y_taller/mesa_soldadura`): 1,20 × 0,80 × 0,85.
- **Yunque sobre tocón** (`trabajo_y_taller/yunque_tocon`): 0,70 × 0,45 × 0,80.
- **Fragua de forja** (`trabajo_y_taller/fragua_forja`): 1,00 × 1,00 × 0,85.

#### Perfiles y chapa

- **Estantería de brazos para perfiles** (`trabajo_y_taller/estante_perfiles`): 4,00 × 1,20 × 2,50 (3 variantes; puede esconder un premio).
- **Perfiles que sobresalen del estante** (`trabajo_y_taller/perfiles_sobresalen`): 0,60 × 0,80 × 0,20 (colgado a 1,50 m).
- **Chapas apoyadas en un caballete** (`trabajo_y_taller/chapas_apoyadas`): 1,00 × 2,50 × 1,60.

### Almacén y logística (27)

#### Estanterías de palés

- **Estantería de palés** (`trabajo_y_taller/estanteria_pales`): 2,70 × 1,10 × 6,00 (3 variantes; puede esconder un premio).
- **Estantería de media carga con cubetas** (`trabajo_y_taller/estanteria_picking`): 2,00 × 0,60 × 2,50 (puede esconder un premio).
- **Estantería dinámica de rodillos** (`trabajo_y_taller/estanteria_dinamica`): 1,80 × 2,00 × 2,00 (puede esconder un premio).
- **Palé que sobresale de la estantería** (`trabajo_y_taller/pale_sobresale_estante`): 1,00 × 0,40 × 1,00 (colgado a 1,60 m).

#### Palés y mercancía

- **Palés vacíos** (`trabajo_y_taller/pales_vacios`): 0,80 × 1,20 × 0,15 (4 variantes).
- **Contenedor de rejilla metálica** (`trabajo_y_taller/jaula_rejilla`): 0,84 × 1,24 × 0,97 (puede esconder un premio).
- **Depósito IBC de 1000 litros** (`trabajo_y_taller/contenedor_ibc`): 1,00 × 1,20 × 1,16 (2 variantes).
- **Bobina de chapa sobre cuna** (`trabajo_y_taller/bobina_chapa`): 1,20 × 1,00 × 1,20.

#### Transpaletas, carretillas y carros

- **Transpaleta manual** (`trabajo_y_taller/transpaleta_manual`): 0,54 × 1,55 × 1,20.
- **Transpaleta eléctrica con plataforma** (`trabajo_y_taller/transpaleta_electrica`): 0,80 × 2,00 × 1,40.
- **Carretilla elevadora con las horquillas abajo** (`trabajo_y_taller/carretilla_elevadora`): 1,15 × 3,40 × 2,15 (2 variantes).
- **Horquillas de carretilla en alto** (`trabajo_y_taller/horquillas_en_alto`): 0,90 × 1,20 × 0,15 (colgado a 1,50 m).
- **Carro de plataforma con asa** (`trabajo_y_taller/carro_plataforma`): 0,60 × 0,90 × 0,90 (puede esconder un premio).
- **Carro de preparación de pedidos** (`trabajo_y_taller/carro_preparacion_pedidos`): 0,70 × 1,20 × 1,60 (puede esconder un premio).
- **Escalera de almacén con plataforma** (`trabajo_y_taller/escalera_almacen_plataforma`): 0,80 × 1,50 × 2,30 (3 variantes).

#### Cintas, embalaje y pesaje

- **Cinta transportadora de banda** (`trabajo_y_taller/cinta_transportadora`): 0,60 × 5,00 × 0,80 (2 variantes).
- **Curva de cinta transportadora** (`trabajo_y_taller/curva_transportadora`): 1,60 × 1,60 × 0,80.
- **Enfardadora de palés** (`trabajo_y_taller/enfardadora_pales`): 1,65 × 1,90 × 2,50.
- **Báscula de plataforma para palés** (`trabajo_y_taller/bascula_plataforma`): 1,20 × 2,00 × 0,09 (no corta el paso).

#### Muelle de carga y puertas

- **Borde del muelle de carga** (`trabajo_y_taller/borde_muelle_carga`): 3,00 × 0,30 × 0,05 (no corta el paso).
- **Rampa niveladora de muelle** (`trabajo_y_taller/rampa_niveladora`): 2,00 × 3,00 × 0,05 (no corta el paso).
- **Puerta seccional de muelle con abrigo** (`trabajo_y_taller/puerta_seccional`): 3,00 × 0,50 × 3,20.
- **Escalera de bajada del muelle** (`trabajo_y_taller/escalera_muelle_carga`): 1,00 × 1,50 × 1,20 (no corta el paso).

#### Protecciones y pasos

- **Protector de puntal de estantería** (`trabajo_y_taller/protector_puntal`): 0,20 × 0,20 × 0,40.
- **Barrera de pasillo peatonal** (`trabajo_y_taller/barrera_peatonal_almacen`): 3,00 × 0,20 × 1,10.
- **Baliza de aviso de carretillas** (`trabajo_y_taller/baliza_cruce_carretillas`): 0,15 × 0,15 × 2,20.
- **Cortina de lamas de plástico** (`trabajo_y_taller/cortina_lamas`): 1,50 × 0,05 × 2,20 (no corta el paso).

### Fábrica (20)

#### Máquinas de producción

- **Prensa hidráulica de producción** (`trabajo_y_taller/prensa_hidraulica`): 1,80 × 1,60 × 3,00.
- **Inyectora de plástico** (`trabajo_y_taller/inyectora_plastico`): 1,50 × 6,00 × 2,10.
- **Telar industrial** (`trabajo_y_taller/telar_industrial`): 3,00 × 1,80 × 1,50.
- **Célula de robot vallada** (`trabajo_y_taller/celda_robot`): 4,00 × 4,00 × 2,20.
- **Centro de mecanizado CNC** (`trabajo_y_taller/centro_mecanizado`): 2,60 × 2,40 × 2,60.
- **Horno industrial de secado** (`trabajo_y_taller/horno_industrial`): 2,00 × 1,50 × 2,30.

#### Línea y puestos de trabajo

- **Mesa de costura industrial** (`trabajo_y_taller/maquina_coser_industrial`): 1,20 × 0,60 × 1,10.
- **Línea de montaje con puestos** (`trabajo_y_taller/linea_montaje`): 8,00 × 2,00 × 0,95.
- **Puesto de montaje con estante de cubetas** (`trabajo_y_taller/puesto_montaje`): 1,50 × 0,90 × 2,00 (puede esconder un premio).
- **Taburete alto de puesto de trabajo** (`trabajo_y_taller/taburete_puesto`): 0,50 × 0,50 × 1,00.
- **Contenedor basculante de virutas** (`trabajo_y_taller/contenedor_virutas`): 1,00 × 1,20 × 0,90.

#### Instalaciones de la nave

- **Tubería que cruza a poca altura** (`trabajo_y_taller/tuberia_aerea`): 3,00 × 0,20 × 0,20 (3 variantes; colgado a 1,80 m).
- **Gancho del puente grúa** (`trabajo_y_taller/puente_grua_gancho`): 0,30 × 0,30 × 0,50 (colgado a 1,60 m).
- **Brazo de aspiración de humos** (`trabajo_y_taller/brazo_aspiracion_humos`): 0,40 × 2,00 × 0,40 (colgado a 1,50 m).
- **Armario eléctrico de control** (`trabajo_y_taller/armario_electrico_fabrica`): 0,80 × 0,40 × 2,00.
- **Ventilador industrial de pie** (`trabajo_y_taller/ventilador_industrial`): 0,90 × 0,80 × 1,90.
- **Puerta rápida de lona** (`trabajo_y_taller/puerta_rapida`): 3,00 × 0,30 × 3,50.

#### Seguridad y personal

- **Reloj de fichar** (`trabajo_y_taller/reloj_fichar`): 0,25 × 0,10 × 0,30 (colgado a 1,20 m).
- **Seta de parada de emergencia en poste** (`trabajo_y_taller/pulsador_seta_emergencia`): 0,12 × 0,12 × 1,10.
- **Armario de equipos de protección** (`trabajo_y_taller/armario_epis`): 1,00 × 0,50 × 1,95 (puede esconder un premio).

### Laboratorio (15)

#### Mesas y asientos de laboratorio

- **Poyata mural de laboratorio** (`trabajo_y_taller/poyata_mural`): 3,00 × 0,75 × 0,90 (puede esconder un premio).
- **Mesa antivibratoria de balanzas** (`trabajo_y_taller/mesa_antivibratoria`): 1,00 × 0,70 × 0,80.
- **Fregadero de laboratorio con escurridor de clavijas** (`trabajo_y_taller/fregadero_laboratorio`): 1,00 × 0,70 × 0,90.

#### Equipos de laboratorio

- **Cabina de seguridad biológica** (`trabajo_y_taller/cabina_seguridad_biologica`): 1,50 × 0,80 × 2,20.
- **Centrífuga de laboratorio** (`trabajo_y_taller/centrifuga_laboratorio`): 0,70 × 0,80 × 0,90 (2 variantes).
- **Autoclave de laboratorio** (`trabajo_y_taller/autoclave_laboratorio`): 0,70 × 0,70 × 1,10 (2 variantes).
- **Congelador de 80 grados bajo cero** (`trabajo_y_taller/congelador_ultra`): 0,90 × 0,90 × 2,00.
- **Tanque de nitrógeno líquido con ruedas** (`trabajo_y_taller/tanque_nitrogeno`): 0,60 × 0,60 × 1,20.
- **Estufa de cultivo** (`trabajo_y_taller/estufa_cultivo`): 0,70 × 0,70 × 1,00 (2 variantes).
- **Destilador de agua de pared** (`trabajo_y_taller/destilador_pared`): 0,50 × 0,25 × 0,70 (colgado a 1,20 m).
- **Lavadora de material de laboratorio** (`trabajo_y_taller/lavadora_material_vidrio`): 0,65 × 0,65 × 0,90.

#### Almacenaje y emergencia

- **Armario de seguridad para productos químicos** (`trabajo_y_taller/armario_seguridad_quimicos`): 1,20 × 0,60 × 1,95 (3 variantes; puede esconder un premio).
- **Ducha de emergencia con lavaojos** (`trabajo_y_taller/ducha_emergencia`): 0,70 × 0,60 × 2,30.
- **Botellas de gas sujetas con cadena** (`trabajo_y_taller/botellas_gas_cadena`): 0,90 × 0,30 × 1,60 (2 variantes).
- **Bidones de residuos químicos en cubeto** (`trabajo_y_taller/residuos_quimicos_cubeto`): 1,20 × 0,80 × 0,70.

### Cocina profesional (24)

#### Cocción

- **Cocina industrial de fuegos con horno** (`trabajo_y_taller/cocina_fogones_industrial`): 1,20 × 0,90 × 0,90 (2 variantes).
- **Freidora industrial** (`trabajo_y_taller/freidora_industrial`): 0,60 × 0,90 × 0,90.
- **Plancha de cocina industrial** (`trabajo_y_taller/plancha_cocina`): 0,80 × 0,90 × 0,90.
- **Marmita industrial** (`trabajo_y_taller/marmita_industrial`): 1,00 × 1,00 × 1,00 (2 variantes).
- **Horno mixto de convección** (`trabajo_y_taller/horno_mixto`): 0,90 × 0,85 × 1,70.
- **Campana extractora de cocina industrial** (`trabajo_y_taller/campana_extractora_cocina`): 3,00 × 1,10 × 0,50 (colgado a 1,95 m).
- **Fogón bajo para ollas grandes** (`trabajo_y_taller/fogon_bajo`): 0,60 × 0,60 × 0,50.
- **Salamandra gratinadora de pared** (`trabajo_y_taller/salamandra_gratinador`): 0,80 × 0,50 × 0,45 (colgado a 1,40 m).

#### Frío

- **Mesa refrigerada bajo encimera** (`trabajo_y_taller/mesa_refrigerada`): 1,50 × 0,70 × 0,90 (2 variantes; puede esconder un premio).
- **Armario frigorífico industrial** (`trabajo_y_taller/armario_refrigerado`): 1,40 × 0,85 × 2,05 (2 variantes; puede esconder un premio).
- **Abatidor de temperatura** (`trabajo_y_taller/abatidor_temperatura`): 0,80 × 0,80 × 1,80 (2 variantes).

#### Lavado

- **Lavavajillas de capota con mesas** (`trabajo_y_taller/lavavajillas_capota`): 2,80 × 2,00 × 1,50.
- **Tren de lavado de vajilla** (`trabajo_y_taller/tren_lavado`): 5,00 × 0,90 × 1,80.
- **Fregadero industrial con ducha de prelavado** (`trabajo_y_taller/fregadero_industrial`): 1,60 × 0,70 × 0,90.

#### Mesas y preparación

- **Mesa de trabajo de acero inoxidable** (`trabajo_y_taller/mesa_trabajo_inox`): 1,60 × 0,70 × 0,90 (2 variantes).
- **Estante de pared sobre la mesa** (`trabajo_y_taller/estante_mural_inox`): 1,60 × 0,35 × 0,30 (colgado a 1,45 m; puede esconder un premio).
- **Amasadora de espiral** (`trabajo_y_taller/amasadora_espiral`): 0,60 × 0,90 × 1,30.
- **Barra de utensilios colgados** (`trabajo_y_taller/barra_utensilios_colgados`): 1,20 × 0,15 × 0,45 (colgado a 1,40 m).

#### Carros y estantes

- **Cubeta de ingredientes con ruedas** (`trabajo_y_taller/cubeta_ingredientes`): 0,40 × 0,65 × 0,70 (puede esconder un premio).
- **Carro de cestas de lavavajillas** (`trabajo_y_taller/carro_cestas_lavavajillas`): 0,55 × 0,55 × 0,15 (2 variantes).
- **Estantería de cocina de baldas ranuradas** (`trabajo_y_taller/estanteria_cocina_ranurada`): 1,50 × 0,50 × 1,80 (puede esconder un premio).

#### Suelo y residuos

- **Canal de desagüe con rejilla** (`trabajo_y_taller/canal_desague_cocina`): 3,00 × 0,20 × 0,01 (no corta el paso).
- **Alfombra de goma con agujeros** (`trabajo_y_taller/alfombra_goma_drenante`): 0,90 × 1,50 × 0,02 (no corta el paso).
- **Cubo de basura de pedal con ruedas** (`trabajo_y_taller/cubo_pedal_industrial`): 0,55 × 0,60 × 0,90.

### Obra por dentro (22)

#### Acopios de material

- **Acopio de ferralla** (`trabajo_y_taller/acopio_ferralla`): 2,00 × 6,00 × 0,40.
- **Esperas de ferralla** (`trabajo_y_taller/esperas_ferralla`): 0,40 × 0,40 × 0,80 (2 variantes).
- **Paneles de mallazo apilados** (`trabajo_y_taller/mallazo_paneles`): 2,15 × 6,00 × 0,20.
- **Pila de tableros y vigas de encofrado** (`trabajo_y_taller/tableros_encofrado`): 1,20 × 2,50 × 0,80.
- **Artesa de mortero** (`trabajo_y_taller/artesa_mortero`): 0,90 × 0,60 × 0,25.

#### Máquinas de obra

- **Hormigonera eléctrica de obra** (`trabajo_y_taller/hormigonera_electrica`): 0,80 × 1,40 × 1,40 (2 variantes).
- **Cortadora de material de mesa** (`trabajo_y_taller/cortadora_material_agua`): 0,70 × 1,30 × 1,30.
- **Montacargas de obra** (`trabajo_y_taller/montacargas_obra`): 1,60 × 2,00 × 3,00.
- **Base de grúa torre** (`trabajo_y_taller/base_grua_torre`): 5,00 × 5,00 × 30,00.
- **Carga suspendida de la grúa** (`trabajo_y_taller/carga_suspendida`): 1,20 × 1,20 × 1,20 (colgado a 2,50 m).

#### Medios auxiliares

- **Puntal metálico** (`trabajo_y_taller/puntal_forjado`): 0,15 × 0,15 × 3,00.
- **Andamio de borriquetas** (`trabajo_y_taller/andamio_borriquetas`): 2,50 × 0,80 × 1,20.
- **Barandilla provisional de borde** (`trabajo_y_taller/barandilla_sargento`): 2,50 × 0,15 × 1,00.
- **Rampa de tablones** (`trabajo_y_taller/rampa_tablones`): 0,80 × 3,00 × 0,60 (no corta el paso).

#### Casetas e instalaciones

- **Cuadro eléctrico de obra** (`trabajo_y_taller/cuadro_electrico_obra`): 0,50 × 0,40 × 1,50.
- **Manguera eléctrica colgada** (`trabajo_y_taller/cable_colgado_obra`): 5,00 × 0,03 × 0,03 (colgado a 1,60 m).
- **Cofre de herramientas de obra** (`trabajo_y_taller/cofre_herramientas_obra`): 1,20 × 0,60 × 0,70 (puede esconder un premio).

#### Huecos, zanjas y redes

- **Hueco en el forjado** (`trabajo_y_taller/hueco_forjado`): 1,50 × 1,50 × 0,05 (3 variantes; no corta el paso).
- **Borde de forjado sin cerrar** (`trabajo_y_taller/borde_forjado`): 5,00 × 0,50 × 0,05 (no corta el paso).
- **Hueco del ascensor en obra** (`trabajo_y_taller/hueco_ascensor_obra`): 1,80 × 1,80 × 0,05 (no corta el paso).
- **Escalera de obra sin barandilla** (`trabajo_y_taller/escalera_obra_sin_barandilla`): 1,20 × 3,50 × 1,50 (no corta el paso).
- **Borde de vaciado** (`trabajo_y_taller/borde_vaciado`): 10,00 × 1,00 × 0,05 (no corta el paso).

## Sonidos propios (16)

`amasadora_espiral`, `centrifuga_laboratorio`, `cinta_banda_almacen`, `compresor_aire`, `enfardadora_film`, `esmeril_chispas`, `freidora_aceite`, `fuegos_gas_cocina`, `hormigonera_obra`, `marmita_borboteo`, `martillo_yunque`, `pitido_carretilla`, `puerta_seccional_muelle`, `sierra_circular`, `soldadura_arco`, `telar_industrial`.

## Sonidos que toma del complemento `comun` (10)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bandeja_seguridad`, `ducha`, `plancha_vapor`, `polea_obra`, `prensa_industrial`, `puerta_pesada_muelle`, `sanidad_oxigeno_burbujeo`, `vajilla_tintineo`, `vapor_bano_turco`, `zumbador_alarma`.

## Sonidos que toma del complemento `hogar` (9)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `interruptor`, `lavavajillas`, `microondas_fin`, `puerta_electrodomestico`, `puerta_mueble`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `oficina_y_comercio` (3)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cortina`, `garrafa`, `silla_ruedas`.

## Sonidos que toma del complemento `calle` (1)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (3)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `taquilla`.

## Sonidos que toma del complemento `juego` (6)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`campana`, `cofre_abrir`, `cofre_cerrar`, `llaves`, `tambor`, `xilofono`.
