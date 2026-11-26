# Tiendas y centro comercial

El comercio pequeño tienda por tienda (panadería, frutería, carnicería, pescadería, ferretería, ropa, zapatería, librería, estanco, óptica, joyería, floristería, juguetería, bazar), el mercado municipal y la galería de un centro comercial.

- Identificador: `tiendas`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo tiendas` a partir de `tools/complementos_serie/tiendas.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (122)

Medidas por defecto: ancho × fondo × alto, en metros.

### Panadería y pastelería (9)

#### Mostradores y vitrinas de panadería

- **Mostrador-vitrina de panadería** (`tiendas/mostrador_panaderia`): 2,00 × 0,90 × 1,30 (3 variantes; puede esconder un premio).
- **Vitrina refrigerada de pasteles** (`tiendas/vitrina_pasteles`): 1,20 × 0,75 × 1,35 (2 variantes).
- **Barra de degustación de pared** (`tiendas/barra_degustacion_pared`): 1,80 × 0,35 × 0,30 (colgado a 0,75 m).

#### Pan a la vista

- **Estantes inclinados de pan** (`tiendas/estantes_pan_pared`): 1,50 × 0,45 × 2,00 (puede esconder un premio).
- **Cesto de barras de pie** (`tiendas/cesto_barras`): 0,45 × 0,45 × 0,90 (puede esconder un premio).
- **Mueble de bollería de autoservicio** (`tiendas/mueble_bolleria_autoservicio`): 1,20 × 0,60 × 1,60 (puede esconder un premio).

#### Horno y máquinas de panadería

- **Horno de panadería** (`tiendas/horno_panaderia`): 1,00 × 1,10 × 1,90 (2 variantes; puede esconder un premio).
- **Cortadora de pan** (`tiendas/cortadora_pan`): 0,60 × 0,70 × 1,15 (2 variantes).
- **Carro de latas de panadería** (`tiendas/carro_latas_panaderia`): 0,60 × 0,80 × 1,80 (puede esconder un premio).

### Frutería y mercado (14)

#### Fruta expuesta

- **Expositor inclinado de fruta en gradas** (`tiendas/expositor_fruta_gradas`): 2,00 × 1,00 × 1,20 (3 variantes; puede esconder un premio).
- **Isla central de fruta a dos caras** (`tiendas/isla_fruta`): 2,00 × 1,20 × 1,10 (puede esconder un premio).
- **Tolvas de frutos secos a granel** (`tiendas/tolvas_granel`): 1,20 × 0,40 × 1,80 (puede esconder un premio).
- **Racimos de plátanos y ristras colgados** (`tiendas/racimos_colgados`): 0,80 × 0,35 × 0,50 (colgado a 1,40 m).

#### Género en el suelo

- **Cajas de fruta apiladas en el suelo** (`tiendas/cajas_fruta_suelo`): 0,80 × 0,60 × 0,50 (3 variantes; puede esconder un premio).
- **Sacos de patatas en el suelo** (`tiendas/sacos_patatas`): 0,80 × 0,60 × 0,40 (puede esconder un premio).
- **Cajón de melones y sandías** (`tiendas/cajon_melones`): 1,20 × 1,00 × 0,90 (puede esconder un premio).

#### Básculas y bolsas

- **Báscula colgante de frutería** (`tiendas/bascula_colgante`): 0,35 × 0,35 × 0,60 (colgado a 1,20 m).
- **Mostrador de frutería con báscula** (`tiendas/mostrador_fruteria`): 1,50 × 0,70 × 0,90 (puede esconder un premio).
- **Báscula de autoservicio** (`tiendas/bascula_autoservicio`): 0,50 × 0,55 × 1,40.
- **Rollo de bolsas en soporte** (`tiendas/soporte_bolsas_fruta`): 0,30 × 0,30 × 1,30.

#### Mercado municipal

- **Puesto de mercado con mostrador en U** (`tiendas/puesto_mercado_u`): 3,50 × 2,50 × 1,10 (3 variantes; puede esconder un premio).
- **Persiana metálica de puesto** (`tiendas/persiana_puesto`): 3,00 × 0,10 × 2,50.
- **Báscula pública de monedas** (`tiendas/bascula_publica`): 0,45 × 0,70 × 1,40.

### Carnicería, pescadería y charcutería (11)

#### Mostradores de frío

- **Mostrador frigorífico de carnicería** (`tiendas/mostrador_carniceria`): 2,50 × 1,10 × 1,30 (3 variantes; puede esconder un premio).
- **Mostrador de hielo de pescadería** (`tiendas/mostrador_pescaderia`): 2,50 × 1,10 × 0,90.
- **Suelo mojado de pescadería** (`tiendas/suelo_mojado_pescaderia`): 2,50 × 1,00 × 0,02 (no corta el paso).
- **Pila de cajas de pescado** (`tiendas/cajas_poliespan`): 0,60 × 0,40 × 0,90 (puede esconder un premio).

#### Tajos y máquinas de corte

- **Tajo de carnicero** (`tiendas/tajo_carnicero`): 0,60 × 0,60 × 0,85 (2 variantes).
- **Cortadora de fiambre** (`tiendas/cortadora_fiambre`): 0,60 × 0,60 × 1,30.

#### Género colgado

- **Barra de ganchos de carnicería** (`tiendas/ganchos_carniceria`): 1,50 × 0,15 × 0,30 (colgado a 1,70 m).

#### Turno

- **Pantalla de turno colgada** (`tiendas/pantalla_turno`): 0,50 × 0,10 × 0,30 (no corta el paso; colgado a 2,10 m).
- **Dispensador de números de carrete en la pared** (`tiendas/dispensador_turno_pared`): 0,20 × 0,15 × 0,30 (colgado a 1,20 m).

#### Cámaras, viveros y asadores

- **Cámara frigorífica de carnicería** (`tiendas/camara_carniceria`): 2,00 × 2,00 × 2,30 (puede esconder un premio).
- **Asador de pollos** (`tiendas/asador_pollos`): 1,00 × 0,70 × 1,80.

### Ferretería (13)

#### Mostrador y cajones de ferretería

- **Mostrador de ferretería** (`tiendas/mostrador_ferreteria`): 2,50 × 0,70 × 0,95 (3 variantes; puede esconder un premio).
- **Mueble de cajoncitos de tornillería** (`tiendas/mueble_tornilleria`): 2,00 × 0,40 × 2,20 (puede esconder un premio).

#### Paneles y expositores de ferretería

- **Panel perforado de herramientas** (`tiendas/panel_herramientas`): 2,00 × 0,15 × 1,50 (colgado a 0,60 m).
- **Mueble de rollos de cadena y cuerda** (`tiendas/rollos_cadena`): 1,20 × 0,50 × 1,80.
- **Portarrollos de hule y plástico por metros** (`tiendas/portarrollos_hule`): 1,80 × 0,60 × 1,80.
- **Muestrario de hojas abatibles** (`tiendas/muestrario_hojas`): 0,80 × 0,50 × 1,80.

#### Género de ferretería en el suelo

- **Bidones y cubos apilados en el suelo** (`tiendas/cubos_apilados_ferreteria`): 0,80 × 0,60 × 0,90 (puede esconder un premio).
- **Escaleras de mano expuestas** (`tiendas/escaleras_expuestas`): 1,20 × 0,60 × 2,00.
- **Tubos y listones de pie en un bidón** (`tiendas/bidon_tubos_listones`): 0,50 × 0,50 × 2,50 (puede esconder un premio).
- **Carretillas de obra expuestas** (`tiendas/carretillas_expuestas`): 0,65 × 1,40 × 0,65 (3 variantes; puede esconder un premio).
- **Sacos de cemento apilados** (`tiendas/sacos_cemento`): 0,80 × 1,20 × 0,80.

#### Máquinas de ferretería

- **Máquina de duplicar llaves** (`tiendas/duplicadora_llaves`): 0,50 × 0,50 × 1,20.
- **Máquina de mezclar pintura** (`tiendas/mezcladora_pintura`): 0,80 × 0,70 × 1,50 (puede esconder un premio).

### Ropa y zapatería (18)

#### Percheros de tienda

- **Perchero de pared en voladizo** (`tiendas/perchero_pared_voladizo`): 1,20 × 0,50 × 0,90 (colgado a 0,80 m; puede esconder un premio).
- **Perchero de cuatro brazos** (`tiendas/perchero_cruz`): 1,00 × 1,00 × 1,50 (puede esconder un premio).
- **Burro de reposición cargado en el pasillo** (`tiendas/burro_reposicion`): 1,60 × 0,60 × 1,90 (puede esconder un premio).

#### Mesas y expositores de ropa

- **Mesa de ropa doblada** (`tiendas/mesa_ropa_doblada`): 1,40 × 0,80 × 0,80 (2 variantes; puede esconder un premio).
- **Mostrador de caja de tienda de ropa** (`tiendas/mostrador_caja_ropa`): 2,00 × 1,20 × 0,95 (puede esconder un premio).
- **Expositor de complementos** (`tiendas/expositor_complementos`): 0,80 × 0,80 × 1,60 (puede esconder un premio).
- **Cesta de ofertas** (`tiendas/cesta_ofertas`): 0,80 × 0,80 × 0,80 (puede esconder un premio).

#### Probadores y espejos

- **Fila de probadores con cortina** (`tiendas/fila_probadores`): 3,40 × 1,30 × 2,20 (3 variantes; puede esconder un premio).
- **Probador con puerta** (`tiendas/probador_puerta`): 1,60 × 1,80 × 2,20 (2 variantes; puede esconder un premio).
- **Puf redondo de espera de probadores** (`tiendas/puf_probadores`): 1,20 × 1,20 × 0,43 (puede esconder un premio).
- **Espejo de pie inclinado** (`tiendas/espejo_pie_inclinado`): 0,60 × 0,40 × 1,80.

#### Maniquíes y bustos

- **Busto de sastre sobre pie** (`tiendas/busto_sastre`): 0,45 × 0,35 × 1,50.
- **Tarima de maniquíes** (`tiendas/tarima_maniquies`): 2,00 × 1,00 × 2,00.

#### Zapatería

- **Estantes de pared con zapatos** (`tiendas/estantes_zapatos_pared`): 2,00 × 0,30 × 1,40 (colgado a 0,50 m).
- **Espejo bajo inclinado de zapatería** (`tiendas/espejo_bajo_zapateria`): 0,40 × 0,35 × 0,40.
- **Calzador con medidor de pies** (`tiendas/medidor_pies`): 0,15 × 0,35 × 0,05 (no corta el paso).
- **Expositor central de zapatos** (`tiendas/expositor_central_zapatos`): 1,40 × 1,20 × 1,20 (puede esconder un premio).
- **Pila de cajas de zapatos** (`tiendas/pila_cajas_zapatos`): 0,60 × 0,35 × 1,00 (puede esconder un premio).

### Librería, estanco, óptica y joyería (14)

#### Librería y papelería

- **Mesa de novedades de librería** (`tiendas/mesa_novedades`): 1,50 × 1,00 × 0,80 (puede esconder un premio).
- **Estantería de librería hasta el techo con escalera corredera** (`tiendas/estanteria_escalera_corredera`): 2,40 × 1,00 × 3,00 (puede esconder un premio).
- **Mostrador de papelería** (`tiendas/mostrador_papeleria`): 2,00 × 1,50 × 0,95 (puede esconder un premio).
- **Banqueta rodante de librería** (`tiendas/banqueta_rodante_libreria`): 0,44 × 0,44 × 0,43.

#### Estanco, prensa y lotería

- **Mostrador de estanco con vitrina** (`tiendas/mostrador_estanco`): 1,80 × 0,65 × 1,05 (puede esconder un premio).
- **Expositor de revistas y prensa de la puerta** (`tiendas/expositor_prensa_exterior`): 0,80 × 0,50 × 1,50 (puede esconder un premio).
- **Máquina de recargas** (`tiendas/maquina_recargas`): 0,50 × 0,40 × 1,50.

#### Óptica

- **Mesa de óptica con sillas** (`tiendas/mesa_optica`): 1,20 × 1,60 × 0,75 (puede esconder un premio).
- **Expositor de gafas de pared** (`tiendas/expositor_gafas_pared`): 1,20 × 0,15 × 1,20 (colgado a 0,80 m).
- **Columna de espejos de óptica** (`tiendas/columna_espejos_optica`): 0,50 × 0,50 × 2,00.
- **Sillón de gabinete con foróptero** (`tiendas/sillon_gabinete_optica`): 1,20 × 1,20 × 1,40.

#### Joyería

- **Vitrina de columna de joyería** (`tiendas/vitrina_columna_joyeria`): 0,50 × 0,50 × 1,80 (puede esconder un premio).
- **Mostrador de joyería en ele** (`tiendas/mostrador_joyeria`): 2,20 × 1,60 × 0,90 (puede esconder un premio).
- **Puerta de joyería con timbre de apertura** (`tiendas/puerta_joyeria`): 0,95 × 0,10 × 2,20.

### Floristería, electrónica, juguetería y bazar (18)

#### Floristería

- **Cubos de flores en gradas** (`tiendas/cubos_flores_gradas`): 1,50 × 1,00 × 1,10 (puede esconder un premio).
- **Mesa de montar ramos** (`tiendas/mesa_ramos`): 1,60 × 0,80 × 0,95 (puede esconder un premio).
- **Cámara de flores** (`tiendas/camara_flores`): 1,80 × 0,80 × 2,10 (puede esconder un premio).
- **Plantas colgantes del techo** (`tiendas/plantas_colgantes`): 0,40 × 0,40 × 0,70 (colgado a 1,40 m).

#### Telefonía y electrónica

- **Mesa de exposición con dispositivos anclados** (`tiendas/mesa_dispositivos`): 2,00 × 0,90 × 0,95.
- **Pared de televisores encendidos** (`tiendas/pared_televisores`): 3,00 × 0,40 × 2,00.
- **Puesto de prueba de videojuegos** (`tiendas/puesto_videojuegos`): 0,80 × 0,60 × 1,80.
- **Fila de electrodomésticos en exposición** (`tiendas/fila_electrodomesticos`): 3,00 × 0,70 × 1,00 (3 variantes; puede esconder un premio).

#### Juguetería

- **Góndola baja de juguetería** (`tiendas/gondola_baja_jugueteria`): 1,30 × 0,80 × 1,20 (2 variantes; puede esconder un premio).
- **Cesto de pelotas** (`tiendas/cesto_pelotas`): 0,80 × 0,80 × 1,20 (puede esconder un premio).
- **Mesa de juego de demostración** (`tiendas/mesa_juego_demostracion`): 1,20 × 0,80 × 0,50 (puede esconder un premio).
- **Peluche gigante de la entrada** (`tiendas/peluche_gigante`): 1,00 × 1,00 × 1,60 (puede esconder un premio).
- **Fila de bicicletas y triciclos expuestos** (`tiendas/fila_bicicletas_infantiles`): 2,50 × 1,20 × 0,80.

#### Bazar y mercería

- **Mercancía colgada en el pasillo del bazar** (`tiendas/mercancia_colgada_bazar`): 1,00 × 0,30 × 0,60 (colgado a 1,30 m).
- **Cestos en el suelo del bazar** (`tiendas/cestos_suelo_bazar`): 1,20 × 0,50 × 0,40 (puede esconder un premio).
- **Estantería de bazar hasta el techo** (`tiendas/estanteria_bazar`): 2,00 × 0,40 × 2,50 (puede esconder un premio).
- **Mostrador de corte de telas** (`tiendas/mostrador_telas`): 2,50 × 0,90 × 0,90 (puede esconder un premio).
- **Piezas de tela de pie** (`tiendas/rollos_tela_pie`): 1,50 × 0,40 × 1,50.

### Centro comercial y puerta de la tienda (25)

#### Bancos, fuentes, atrio y adornos de galería

- **Zona de descanso con sillones** (`tiendas/zona_descanso_sillones`): 2,60 × 2,60 × 0,80 (puede esconder un premio).
- **Banco alrededor de una jardinera** (`tiendas/banco_jardinera_galeria`): 2,40 × 2,40 × 0,50 (puede esconder un premio).
- **Fuente interior de galería** (`tiendas/fuente_galeria`): 3,50 × 3,50 × 0,45 (puede esconder un premio).
- **Barandilla de cristal del atrio** (`tiendas/barandilla_atrio`): 4,00 × 0,10 × 1,10 (2 variantes).
- **Macetero grande con palmera** (`tiendas/macetero_palmera_galeria`): 0,80 × 0,80 × 2,40 (puede esconder un premio).

#### Islas y puestos de galería

- **Isla de venta en el pasillo** (`tiendas/isla_venta_galeria`): 3,00 × 2,00 × 1,10 (puede esconder un premio).
- **Carro de venta decorativo** (`tiendas/carro_venta_galeria`): 1,80 × 1,00 × 2,20 (puede esconder un premio).
- **Isla de helados y gofres** (`tiendas/isla_helados_crepes`): 3,00 × 1,50 × 1,10 (puede esconder un premio).
- **Stand de promoción con azafata** (`tiendas/stand_promocion`): 1,50 × 0,80 × 1,10 (puede esconder un premio).

#### Zona infantil y máquinas de monedas

- **Atracción infantil de monedas** (`tiendas/maquina_balanceo_monedas`): 0,80 × 1,20 × 1,30 (3 variantes).
- **Sillón de masaje de monedas** (`tiendas/sillon_masaje_monedas`): 0,90 × 1,50 × 1,20.
- **Parque de bolas con redes** (`tiendas/parque_bolas_galeria`): 8,00 × 6,00 × 3,50 (puede esconder un premio).
- **Animal de peluche motorizado** (`tiendas/peluche_motorizado`): 0,60 × 1,20 × 1,10.

#### Información y servicios de galería

- **Enfundador de paraguas** (`tiendas/enfundador_paraguas`): 0,40 × 0,40 × 1,00.
- **Carros de la compra con cochecito** (`tiendas/carritos_coche_infantil`): 0,70 × 3,50 × 1,10 (2 variantes).
- **Entrada en recodo de los aseos** (`tiendas/entrada_aseos_recodo`): 2,40 × 2,40 × 2,60.

#### Puerta y entrada de la tienda

- **Puerta de tienda con campanilla** (`tiendas/puerta_campanilla_tienda`): 0,90 × 0,08 × 2,10.
- **Escalón de entrada a la tienda** (`tiendas/escalon_entrada_tienda`): 1,00 × 0,35 × 0,17 (no corta el paso).
- **Rampa portátil para el escalón** (`tiendas/rampa_portatil_tienda`): 0,80 × 0,90 × 0,17 (no corta el paso).
- **Escaparate de tienda** (`tiendas/escaparate_galeria`): 3,00 × 0,15 × 2,80 (puede esconder un premio).
- **Cierre de reja enrollable** (`tiendas/cierre_reja_galeria`): 4,00 × 0,10 × 2,80.

#### Carteles y reclamos

- **Pantalla publicitaria colgada en el atrio** (`tiendas/pantalla_atrio`): 5,00 × 0,50 × 3,00 (colgado a 4,00 m).
- **Coche en exposición en la galería** (`tiendas/coche_exposicion_galeria`): 3,00 × 5,50 × 1,50 (puede esconder un premio).
- **Columna de globos de inauguración** (`tiendas/columna_globos`): 0,60 × 0,60 × 2,20.
- **Photocall con tarima** (`tiendas/photocall_galeria`): 3,00 × 1,40 × 2,30.

## Sonidos propios (15)

`bolas_centro_comercial`, `caballito_monedas`, `campanilla_tienda`, `cortadora_fiambre`, `cortadora_pan`, `duplicadora_llaves`, `enfundador_paraguas`, `horno_panaderia`, `peluche_motorizado`, `perchas_barra`, `persiana_puesto`, `sillon_masaje_monedas`, `tajo_carnicero`, `turno_tienda`, `zumbador_joyeria`.

## Sonidos que toma del complemento `comun` (2)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`goteo_pescaderia`, `vehiculos_puerta_coche`.

## Sonidos que toma del complemento `hogar` (10)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `interruptor`, `juguetes`, `lavadora`, `puerta_cristal`, `puerta_electrodomestico`, `puerta_mueble`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (2)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`balon`, `teclado`.

## Sonidos que toma del complemento `oficina_y_comercio` (3)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_registradora`, `cortina`, `silla_ruedas`.

## Sonidos que toma del complemento `calle` (1)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`papel`.

## Sonidos que toma del complemento `transporte` (4)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `teclas_cajero`, `timbre_bici`.

## Sonidos que toma del complemento `juego` (4)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`globo`, `globo_explota`, `llaves`, `monedas`.
