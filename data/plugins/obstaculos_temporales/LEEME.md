# Obstáculos temporales

Lo que cambia de un día a otro y no se puede aprender de memoria: obras, mudanzas y repartos, basura y baldeo, terrazas y comercios que invaden la acera, mercadillos y fiestas, lo que deja una tormenta, gente parada y los trastos de limpieza y mantenimiento de un edificio.

- Identificador: `obstaculos_temporales`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo obstaculos_temporales` a partir de `tools/complementos_serie/obstaculos_temporales.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (140)

Medidas por defecto: ancho × fondo × alto, en metros.

### Obras en la acera y la calzada (35)

#### Vallas, cintas y balizas

- **Barrera de plástico rellenable** (`obstaculos_temporales/barrera_new_jersey`): 1,20 × 0,50 × 0,80 (3 variantes).
- **Fila de vallas con pies que sobresalen** (`obstaculos_temporales/fila_vallas_pies`): 7,50 × 0,60 × 1,10 (3 variantes).
- **Cinta de balizar tendida a la cintura** (`obstaculos_temporales/cinta_balizamiento`): 3,00 × 0,05 × 0,08 (colgado a 0,90 m).
- **Malla naranja de obra** (`obstaculos_temporales/malla_naranja`): 5,00 × 0,10 × 1,00.
- **Zona acotada con conos y cinta** (`obstaculos_temporales/zona_acotada_fachada`): 4,00 × 2,50 × 0,90.
- **Señal de obras en trípode bajo** (`obstaculos_temporales/senal_obra_tripode`): 0,90 × 0,70 × 1,00.
- **Señal provisional con contrapeso** (`obstaculos_temporales/senal_contrapeso`): 0,40 × 0,80 × 2,20.
- **Baliza luminosa intermitente** (`obstaculos_temporales/baliza_luminosa`): 0,25 × 0,25 × 0,50.

#### Zanjas, huecos y pasarelas

- **Zanja abierta sin proteger** (`obstaculos_temporales/zanja_abierta`): 0,60 × 3,00 × 0,60 (no corta el paso).
- **Pasarela metálica sobre zanja** (`obstaculos_temporales/pasarela_zanja`): 1,00 × 2,50 × 0,15 (no corta el paso).
- **Plancha de acero sobre una zanja** (`obstaculos_temporales/plancha_acero`): 1,50 × 2,00 × 0,02 (no corta el paso).
- **Arqueta abierta sin tapa** (`obstaculos_temporales/arqueta_abierta`): 0,60 × 0,60 × 0,60 (3 variantes; no corta el paso).
- **Socavón en la acera** (`obstaculos_temporales/socavon`): 1,20 × 1,00 × 0,30 (no corta el paso).
- **Tramo de acera levantado** (`obstaculos_temporales/acera_levantada`): 2,00 × 1,50 × 0,08 (no corta el paso).

#### Materiales acopiados

- **Montón de arena de obra** (`obstaculos_temporales/monton_arena`): 1,80 × 1,50 × 0,60.
- **Montón de adoquines levantados** (`obstaculos_temporales/monton_adoquines`): 1,50 × 1,20 × 0,40.
- **Palé de baldosas en la acera** (`obstaculos_temporales/pale_baldosas`): 1,00 × 1,20 × 0,90 (3 variantes).
- **Sacos de escombro apilados** (`obstaculos_temporales/sacos_escombro`): 1,20 × 0,60 × 0,60.
- **Bordillos apilados** (`obstaculos_temporales/bordillos_apilados`): 1,00 × 0,60 × 0,50.
- **Tubos de obra en el suelo** (`obstaculos_temporales/tubos_acopiados`): 0,80 × 4,00 × 0,30.
- **Bobina de cable** (`obstaculos_temporales/bobina_cable`): 0,80 × 1,25 × 1,25 (3 variantes).

#### Máquinas, cables y herramientas

- **Pasacables de goma** (`obstaculos_temporales/pasacables`): 2,00 × 0,30 × 0,05 (no corta el paso).
- **Cables y mangueras de obra por el suelo** (`obstaculos_temporales/cables_mangueras_suelo`): 4,00 × 0,40 × 0,04 (no corta el paso).
- **Generador de obra** (`obstaculos_temporales/generador_obra`): 0,90 × 0,60 × 0,80.
- **Compresor con martillo neumático** (`obstaculos_temporales/compresor_martillo`): 1,50 × 2,20 × 1,20.
- **Foco de obra en trípode** (`obstaculos_temporales/foco_obra`): 1,00 × 1,00 × 2,00.
- **Carretilla de mano** (`obstaculos_temporales/carretilla_obra`): 0,60 × 1,40 × 0,60 (puede esconder un premio).
- **Plataforma elevadora de tijera** (`obstaculos_temporales/plataforma_tijera`): 1,80 × 2,80 × 2,30.

#### Andamios y trabajos en fachada

- **Túnel peatonal bajo andamio** (`obstaculos_temporales/tunel_andamio`): 1,20 × 6,00 × 2,20 (no corta el paso).
- **Andamio cerrado con red hasta el suelo** (`obstaculos_temporales/andamio_con_red`): 5,00 × 1,00 × 8,00.
- **Puntal inclinado de andamio** (`obstaculos_temporales/puntal_marquesina`): 0,10 × 1,20 × 2,50.
- **Bajante de escombros** (`obstaculos_temporales/bajante_escombros`): 0,50 × 0,50 × 6,00 (colgado a 1,50 m).
- **Polea con cubo que sube y baja** (`obstaculos_temporales/polea_cubo`): 0,40 × 0,40 × 0,40 (colgado a 1,00 m).
- **Cuerda colgando de la fachada** (`obstaculos_temporales/cuerda_colgando`): 0,05 × 0,05 × 3,00 (colgado a 1,00 m).
- **Escalera de mano apoyada en la fachada** (`obstaculos_temporales/escalera_fachada`): 0,45 × 1,20 × 3,50.

### Mudanzas y repartos (11)

#### Mudanzas

- **Muebles de mudanza en la acera** (`obstaculos_temporales/muebles_mudanza`): 2,50 × 1,20 × 1,50 (puede esconder un premio).
- **Cajas de mudanza apiladas** (`obstaculos_temporales/cajas_mudanza`): 1,00 × 0,50 × 1,20 (puede esconder un premio).

#### Mercancía en la acera

- **Barriles de cerveza en la acera** (`obstaculos_temporales/barriles_cerveza`): 0,80 × 0,40 × 0,60 (3 variantes).
- **Bombonas de butano en la acera** (`obstaculos_temporales/bombonas_butano`): 0,60 × 0,30 × 0,60.
- **Cajas de bebida apiladas** (`obstaculos_temporales/cajas_bebida`): 0,80 × 0,30 × 1,20 (puede esconder un premio).
- **Reparto dejado a la puerta de un local cerrado** (`obstaculos_temporales/reparto_puerta_cerrada`): 1,00 × 0,50 × 0,35 (puede esconder un premio).

#### Carros y rampas de reparto

- **Plataforma trasera de camión abierta** (`obstaculos_temporales/plataforma_camion`): 2,40 × 1,60 × 0,10 (colgado a 1,00 m).
- **Rampa de furgoneta apoyada en el bordillo** (`obstaculos_temporales/rampa_furgoneta`): 0,90 × 2,20 × 0,30 (no corta el paso).
- **Carretilla de reparto con cajas** (`obstaculos_temporales/carretilla_reparto`): 0,50 × 0,60 × 1,30 (puede esconder un premio).
- **Palé de reparto con transpaleta** (`obstaculos_temporales/transpaleta_pale`): 0,80 × 1,90 × 1,20.
- **Jaula de reparto con ruedas** (`obstaculos_temporales/jaula_reparto`): 0,72 × 0,80 × 1,70 (puede esconder un premio).

### Basura, limpieza y agua (14)

#### Basura suelta y cubos

- **Bolsas de basura amontonadas** (`obstaculos_temporales/bolsas_basura_monton`): 1,50 × 1,00 × 0,50 (puede esconder un premio).
- **Bolsa de basura suelta en la acera** (`obstaculos_temporales/bolsa_basura_suelta`): 0,45 × 0,45 × 0,40 (puede esconder un premio).
- **Cubo de basura volcado** (`obstaculos_temporales/contenedor_volcado`): 0,60 × 1,30 × 0,58.
- **Cubos de comunidad esperando la recogida** (`obstaculos_temporales/cubos_comunidad_fila`): 2,40 × 0,75 × 1,07 (3 variantes; puede esconder un premio).
- **Carrito de barrendero parado** (`obstaculos_temporales/carrito_barrendero`): 0,70 × 1,20 × 1,10 (puede esconder un premio).
- **Cristales rotos en el suelo** (`obstaculos_temporales/cristales_rotos`): 0,80 × 0,60 × 0,01 (no corta el paso).

#### Muebles y enseres viejos

- **Colchón viejo apoyado en la fachada** (`obstaculos_temporales/colchon_fachada`): 1,90 × 0,40 × 1,35.
- **Sofá viejo para recoger** (`obstaculos_temporales/sofa_viejo`): 1,90 × 0,90 × 0,85.
- **Frigorífico viejo tumbado** (`obstaculos_temporales/frigorifico_tumbado`): 0,60 × 1,80 × 0,65 (puede esconder un premio).
- **Trastos viejos amontonados para la recogida** (`obstaculos_temporales/trastos_viejos_monton`): 2,00 × 1,20 × 1,00 (puede esconder un premio).

#### Agua, hielo y suelo resbaladizo

- **Manguera de baldeo cruzando la acera** (`obstaculos_temporales/manguera_baldeo`): 4,00 × 0,20 × 0,06 (no corta el paso).
- **Balsa de agua tras la lluvia** (`obstaculos_temporales/balsa_agua`): 3,50 × 2,50 × 0,04 (no corta el paso).
- **Placa de hielo** (`obstaculos_temporales/placa_hielo`): 1,50 × 1,00 × 0,01 (no corta el paso).
- **Hojas mojadas en el suelo** (`obstaculos_temporales/hojas_mojadas`): 2,50 × 1,50 × 0,05 (no corta el paso).

### Comercio y hostelería que invaden el paso (13)

#### Terraza fuera de su sitio

- **Silla de terraza suelta en la acera** (`obstaculos_temporales/silla_terraza_suelta`): 0,55 × 0,55 × 0,80.
- **Sillas y mesas de terraza apiladas** (`obstaculos_temporales/terraza_apilada`): 1,20 × 0,70 × 1,50.
- **Sombrilla cerrada tumbada** (`obstaculos_temporales/sombrilla_tumbada`): 0,25 × 2,50 × 0,25.

#### Reclamos y género en la acera

- **Banderola publicitaria tipo vela** (`obstaculos_temporales/vela_publicitaria`): 0,60 × 0,60 × 3,00.
- **Atril con la carta del restaurante** (`obstaculos_temporales/atril_carta`): 0,45 × 0,40 × 1,30.
- **Figura publicitaria a la puerta** (`obstaculos_temporales/figura_publicitaria`): 0,60 × 0,60 × 1,60.
- **Cajas de fruta vacías apiladas** (`obstaculos_temporales/cajas_fruta_vacias`): 0,50 × 0,40 × 0,90.
- **Perchero de rebajas en la acera** (`obstaculos_temporales/perchero_rebajas`): 1,40 × 0,50 × 1,65.
- **Cajón de ofertas a la puerta de la tienda** (`obstaculos_temporales/cajon_ofertas`): 0,80 × 0,60 × 0,85 (puede esconder un premio).
- **Macetas sacadas a la puerta** (`obstaculos_temporales/macetas_puerta`): 1,20 × 0,30 × 0,40.

#### Puertas, persianas y alfombras

- **Alfombra de comercio arrugada** (`obstaculos_temporales/alfombra_arrugada`): 1,50 × 0,90 × 0,06 (no corta el paso).
- **Persiana metálica a medio abrir** (`obstaculos_temporales/persiana_medio_abrir`): 2,50 × 0,08 × 1,00 (colgado a 1,50 m).
- **Puerta de cristal abierta hacia la acera** (`obstaculos_temporales/puerta_cristal_acera`): 0,05 × 0,90 × 2,10.

### Mercadillo, fiestas y carreras (23)

#### Puestos y casetas

- **Viento de toldo atado a un peso** (`obstaculos_temporales/viento_puesto`): 0,30 × 1,20 × 1,90.
- **Mesa de puesto sobre caballetes** (`obstaculos_temporales/mesa_puesto`): 2,00 × 0,80 × 0,75 (puede esconder un premio).
- **Cajas y bolsas en el suelo del puesto** (`obstaculos_temporales/cajas_puesto`): 1,20 × 0,80 × 0,35 (puede esconder un premio).
- **Género colgado del toldo de un puesto** (`obstaculos_temporales/genero_colgado`): 2,00 × 0,40 × 0,60 (colgado a 1,50 m).
- **Carpa plegable con pesos** (`obstaculos_temporales/carpa_plegable`): 3,00 × 3,00 × 3,00 (3 variantes; puede esconder un premio).
- **Caseta de feria de madera** (`obstaculos_temporales/caseta_feria`): 3,00 × 2,00 × 2,60 (puede esconder un premio).
- **Puesto de castañas** (`obstaculos_temporales/puesto_castanas`): 1,00 × 0,80 × 1,20.
- **Churrería ambulante** (`obstaculos_temporales/churreria_ambulante`): 4,50 × 2,30 × 2,80.
- **Carrito ambulante de helados** (`obstaculos_temporales/carrito_helados`): 0,80 × 1,50 × 1,20 (puede esconder un premio).
- **Barra provisional de fiestas** (`obstaculos_temporales/barra_fiestas`): 4,00 × 0,60 × 1,10 (puede esconder un premio).

#### Escenarios, gradas y vallas

- **Cabina de aseo portátil** (`obstaculos_temporales/cabina_aseo_portatil`): 1,20 × 1,20 × 2,30 (2 variantes; puede esconder un premio).
- **Escenario provisional** (`obstaculos_temporales/escenario_provisional`): 8,00 × 6,00 × 1,50.
- **Torre de sonido con contrapesos** (`obstaculos_temporales/torre_sonido`): 1,50 × 1,50 × 5,00.
- **Sillas en fila para la procesión** (`obstaculos_temporales/sillas_procesion`): 5,00 × 0,55 × 0,85 (3 variantes).
- **Tribuna desmontable** (`obstaculos_temporales/tribuna_desmontable`): 8,00 × 5,00 × 3,00.

#### Carreras y mesas en la calle

- **Pata de arco hinchable con soplador** (`obstaculos_temporales/pata_arco_hinchable`): 1,20 × 1,20 × 4,00.
- **Alfombra de cronometraje de la meta** (`obstaculos_temporales/alfombra_cronometraje`): 4,00 × 1,00 × 0,02 (no corta el paso).
- **Mesa de avituallamiento** (`obstaculos_temporales/mesa_avituallamiento`): 3,60 × 0,75 × 0,74 (3 variantes; puede esconder un premio).
- **Mesa petitoria o de recogida de firmas** (`obstaculos_temporales/mesa_petitoria`): 1,20 × 1,20 × 0,75 (puede esconder un premio).

#### Adornos, luces y hogueras

- **Contenedor-jaula de vidrio de fiestas** (`obstaculos_temporales/jaula_vidrio_fiestas`): 1,20 × 1,00 × 1,20 (puede esconder un premio).
- **Guirnalda de luces colgada baja** (`obstaculos_temporales/guirnalda_baja`): 5,00 × 0,10 × 0,20 (colgado a 1,60 m).
- **Árbol de Navidad de plaza vallado** (`obstaculos_temporales/arbol_navidad_plaza`): 5,00 × 5,00 × 10,00.
- **Hoguera o falla vallada** (`obstaculos_temporales/hoguera_vallada`): 6,00 × 6,00 × 4,00.

### Tormenta, poda y cosas caídas (12)

#### Ramas y árboles caídos

- **Rama grande caída en la acera** (`obstaculos_temporales/rama_caida`): 3,00 × 2,00 × 0,80.
- **Árbol caído cruzado en la calle** (`obstaculos_temporales/arbol_caido`): 8,00 × 3,50 × 1,50.
- **Montón de ramas y hojas de poda** (`obstaculos_temporales/restos_poda`): 2,50 × 1,50 × 0,90.

#### Cables, toldos y cascotes

- **Toldo roto colgando** (`obstaculos_temporales/toldo_roto`): 2,00 × 0,60 × 1,00 (colgado a 1,20 m).
- **Cable caído del tendido** (`obstaculos_temporales/cable_caido`): 0,10 × 3,00 × 1,50.
- **Cascotes caídos con zona acotada** (`obstaculos_temporales/cascotes_acotados`): 2,50 × 2,00 × 1,00.
- **Macetero volcado** (`obstaculos_temporales/macetero_volcado`): 0,60 × 1,20 × 0,45.
- **Señal de tráfico derribada** (`obstaculos_temporales/senal_derribada`): 0,60 × 2,80 × 0,30.
- **Valla de obra tumbada por el viento** (`obstaculos_temporales/valla_tumbada`): 2,50 × 1,10 × 0,10.

#### Agua, barro y nieve

- **Alcorque inundado** (`obstaculos_temporales/alcorque_inundado`): 1,00 × 1,00 × 0,10 (no corta el paso).
- **Barro y grava arrastrados por la tormenta** (`obstaculos_temporales/arrastre_barro`): 3,00 × 1,50 × 0,05 (no corta el paso).
- **Nieve amontonada en el borde** (`obstaculos_temporales/nieve_amontonada`): 3,00 × 0,80 × 0,50.

### Personas, animales y carritos parados (11)

#### Personas y animales parados

- **Cola de gente a la puerta de un local** (`obstaculos_temporales/cola_de_gente`): 0,80 × 6,00 × 1,70.
- **Grupo de gente parada charlando** (`obstaculos_temporales/grupo_charlando`): 1,80 × 1,80 × 1,70.
- **Persona parada en mitad de la acera** (`obstaculos_temporales/persona_parada`): 0,60 × 0,50 × 1,70 (3 variantes).
- **Persona sentada en el suelo** (`obstaculos_temporales/persona_sentada_suelo`): 0,60 × 1,20 × 0,80.
- **Vecinos sentados al fresco** (`obstaculos_temporales/vecinos_al_fresco`): 2,50 × 1,20 × 1,20.
- **Perro atado con la correa tendida** (`obstaculos_temporales/perro_atado`): 0,50 × 1,50 × 0,50.

#### Artistas y venta en el suelo

- **Músico callejero con la funda abierta** (`obstaculos_temporales/musico_callejero`): 1,50 × 1,50 × 1,70 (puede esconder un premio).
- **Estatua humana sobre una peana** (`obstaculos_temporales/estatua_humana`): 0,60 × 0,80 × 2,00.
- **Manta de venta en el suelo** (`obstaculos_temporales/manta_venta`): 2,00 × 1,50 × 0,15 (no corta el paso).

#### Carritos dejados a la puerta

- **Cochecito de bebé parado a la puerta** (`obstaculos_temporales/cochecito_bebe`): 0,60 × 1,00 × 1,05.
- **Carro de la compra de tela a la puerta** (`obstaculos_temporales/carro_compra_puerta`): 0,40 × 0,35 × 1,00 (puede esconder un premio).

### Dentro de un edificio (21)

#### Limpieza

- **Tramo de suelo recién fregado** (`obstaculos_temporales/suelo_recien_fregado`): 2,00 × 2,00 × 0,01 (no corta el paso).
- **Carro de limpieza parado en el pasillo** (`obstaculos_temporales/carro_limpieza`): 0,60 × 1,20 × 1,10 (puede esconder un premio).
- **Máquina fregadora de suelos** (`obstaculos_temporales/fregadora_suelos`): 0,60 × 1,20 × 1,10.
- **Cubo bajo una gotera** (`obstaculos_temporales/cubo_gotera`): 0,30 × 0,30 × 0,30 (puede esconder un premio).

#### Mantenimiento y pintura

- **Andamio rodante de pintor** (`obstaculos_temporales/andamio_pintor`): 0,80 × 2,00 × 2,00.
- **Plástico de pintor en el suelo** (`obstaculos_temporales/plastico_pintor`): 3,00 × 2,00 × 0,01 (no corta el paso).
- **Cubos de pintura y rodillos** (`obstaculos_temporales/cubos_pintura`): 0,80 × 0,50 × 0,35.
- **Caja de herramientas abierta en el suelo** (`obstaculos_temporales/caja_herramientas_suelo`): 0,50 × 0,30 × 0,25 (puede esconder un premio).
- **Cable alargador cruzando el pasillo** (`obstaculos_temporales/alargador_cruzado`): 2,00 × 0,05 × 0,02 (no corta el paso).
- **Trampilla de registro abierta en el suelo** (`obstaculos_temporales/trampilla_registro_abierta`): 0,60 × 0,60 × 0,15 (no corta el paso).

#### Reposición y paquetes

- **Cajas de reposición en el pasillo de una tienda** (`obstaculos_temporales/cajas_reposicion`): 0,60 × 0,40 × 0,60 (puede esconder un premio).
- **Carro de reposición con cajas** (`obstaculos_temporales/carro_reposicion`): 0,60 × 1,00 × 1,00 (puede esconder un premio).
- **Paquetes de mensajería amontonados en la entrada** (`obstaculos_temporales/paquetes_entrada`): 1,00 × 0,60 × 0,60 (puede esconder un premio).

#### Muebles movidos y trastos

- **Mueble movido de su sitio** (`obstaculos_temporales/mueble_fuera_sitio`): 1,00 × 0,50 × 0,90 (3 variantes; puede esconder un premio).
- **Cinta de «no pasar» entre dos sillas** (`obstaculos_temporales/sillas_con_cinta`): 2,00 × 0,50 × 0,90.
- **Alfombra enrollada en el suelo** (`obstaculos_temporales/alfombra_enrollada`): 0,30 × 2,00 × 0,30.
- **Paraguas abierto secándose en el suelo** (`obstaculos_temporales/paraguas_abierto`): 1,00 × 1,00 × 0,60.
- **Árbol de Navidad en el vestíbulo** (`obstaculos_temporales/arbol_navidad_vestibulo`): 1,20 × 1,20 × 2,00 (puede esconder un premio).

#### Cosas abiertas o colgadas

- **Decoración colgada baja** (`obstaculos_temporales/decoracion_colgada_baja`): 1,50 × 0,30 × 0,30 (colgado a 1,60 m).
- **Puerta de armario alto abierta** (`obstaculos_temporales/puerta_alta_abierta`): 0,04 × 0,45 × 0,70 (colgado a 1,40 m).
- **Hoja de ventana abierta que invade el paso** (`obstaculos_temporales/ventana_abierta_paso`): 0,05 × 0,60 × 1,10 (colgado a 1,00 m).

## Sonidos propios (11)

`baliza_obra`, `chapa_zanja`, `cinta_baliza`, `cristales_rotos`, `fregadora_suelos`, `generador_obra`, `manguera_baldeo`, `martillo_neumatico`, `murmullo_cola`, `musico_callejero`, `perro_atado`.

## Sonidos que toma del complemento `comun` (2)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`brasas_castanera`, `polea_obra`.

## Sonidos que toma del complemento `hogar` (6)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`interruptor`, `puerta_cristal`, `puerta_electrodomestico`, `puerta_mueble`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `oficina_y_comercio` (1)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`garrafa`.

## Sonidos que toma del complemento `calle` (4)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`hojas`, `papel`, `vidrio`, `zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (2)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`.

## Sonidos que toma del complemento `juego` (4)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bandera`, `campana`, `llaves`, `monedas`.
