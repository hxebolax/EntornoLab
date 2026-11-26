# Parque y naturaleza

Parque infantil con juegos que se mueven, circuito biosaludable, zona canina, merendero, senderos, agua, árboles y setos, jardín, huerto y playa.

- Identificador: `parque_y_naturaleza`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo parque_y_naturaleza` a partir de `tools/complementos_serie/parque_y_naturaleza.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (168)

Medidas por defecto: ancho × fondo × alto, en metros.

### Parque infantil (28)

#### Columpios

- **Columpio doble** (`parque_y_naturaleza/columpio_doble`): 3,20 × 1,90 × 2,30 (2 variantes).
- **Zona de vaivén del columpio** (`parque_y_naturaleza/zona_vaiven_columpio`): 3,50 × 7,00 × 0,03 (no corta el paso).
- **Columpio de cesta** (`parque_y_naturaleza/columpio_nido`): 3,00 × 2,20 × 2,50.
- **Columpio de bebé** (`parque_y_naturaleza/columpio_bebe`): 1,90 × 1,60 × 2,00.
- **Columpio adaptado para silla de ruedas** (`parque_y_naturaleza/columpio_adaptado`): 2,60 × 3,40 × 2,40.

#### Toboganes, torres y trepas

- **Tobogán de parque con escalera** (`parque_y_naturaleza/tobogan_parque`): 1,10 × 3,80 × 2,10 (3 variantes).
- **Tobogán de tubo** (`parque_y_naturaleza/tobogan_tubo`): 2,50 × 3,00 × 3,00.
- **Torre multijuego con puente** (`parque_y_naturaleza/torre_multijuego`): 5,50 × 3,00 × 3,20 (puede esconder un premio).
- **Red de trepar piramidal** (`parque_y_naturaleza/red_piramidal`): 4,50 × 4,50 × 3,50.
- **Rocódromo infantil** (`parque_y_naturaleza/rocodromo_infantil`): 3,00 × 0,50 × 2,20.
- **Barras de mono** (`parque_y_naturaleza/barras_mono`): 0,90 × 2,50 × 0,10 (colgado a 1,70 m).
- **Barra de equilibrio en zigzag** (`parque_y_naturaleza/barra_equilibrio_parque`): 3,00 × 0,80 × 0,30.
- **Casita de parque infantil** (`parque_y_naturaleza/casita_parque`): 1,50 × 1,50 × 1,70 (puede esconder un premio).

#### Balancines, giros y saltos

- **Cable de tirolina con asiento** (`parque_y_naturaleza/tirolina_cable`): 0,40 × 12,00 × 0,60 (colgado a 1,50 m).
- **Plataforma de salida de tirolina** (`parque_y_naturaleza/tirolina_plataforma`): 1,50 × 2,00 × 0,60.
- **Balancín de dos plazas** (`parque_y_naturaleza/balancin_doble`): 0,40 × 3,00 × 0,90.
- **Balancín de muelle con figura** (`parque_y_naturaleza/balancin_muelle`): 0,40 × 0,90 × 0,85 (3 variantes).
- **Carrusel giratorio de suelo** (`parque_y_naturaleza/carrusel_suelo`): 1,80 × 1,80 × 0,85.
- **Cama elástica enrasada** (`parque_y_naturaleza/cama_elastica_suelo`): 1,50 × 1,50 × 0,05 (no corta el paso).

#### Paneles sensoriales y de agua

- **Mesa de juegos de agua** (`parque_y_naturaleza/mesa_agua_infantil`): 1,50 × 0,80 × 0,60.
- **Panel de juegos sensorial** (`parque_y_naturaleza/panel_sensorial`): 1,20 × 0,15 × 1,30.
- **Panel musical de campanas tubulares** (`parque_y_naturaleza/panel_musical_tubos`): 1,50 × 0,30 × 1,60.
- **Tubo parlante** (`parque_y_naturaleza/tubos_parlantes`): 0,30 × 0,30 × 1,10.

#### Suelos, vallado y bancos del recinto

- **Arenero de parque con bordillo** (`parque_y_naturaleza/arenero_parque`): 4,00 × 4,00 × 0,25 (no corta el paso; puede esconder un premio).
- **Suelo de caucho amortiguador** (`parque_y_naturaleza/suelo_caucho`): 6,00 × 5,00 × 0,04 (no corta el paso).
- **Vallado bajo de parque infantil** (`parque_y_naturaleza/vallado_infantil`): 2,00 × 0,08 × 0,90 (3 variantes).
- **Puerta de muelle del parque infantil** (`parque_y_naturaleza/puerta_muelle_infantil`): 1,00 × 0,08 × 1,00.
- **Banco curvo de vigilancia del parque infantil** (`parque_y_naturaleza/banco_vigilancia`): 3,50 × 1,40 × 0,85 (puede esconder un premio).

### Biosaludables y zona canina (17)

#### Aparatos biosaludables

- **Rueda de hombros** (`parque_y_naturaleza/bio_rueda_hombros`): 1,20 × 0,50 × 1,90.
- **Pedales con banco** (`parque_y_naturaleza/bio_pedales`): 0,60 × 1,30 × 0,90.
- **Esquí de fondo** (`parque_y_naturaleza/bio_esqui`): 0,60 × 1,30 × 1,50.
- **Volante de giro** (`parque_y_naturaleza/bio_volante`): 1,00 × 1,00 × 1,60.
- **Giro de cintura de tres puestos** (`parque_y_naturaleza/bio_cintura`): 1,50 × 1,50 × 1,40.
- **Paralelas bajas** (`parque_y_naturaleza/bio_paralelas`): 0,65 × 2,50 × 0,80.
- **Escalera y rampa de ejercicio** (`parque_y_naturaleza/bio_escalera_rampa`): 0,90 × 2,80 × 1,10.

#### Circuito de agility

- **Rampa de agility en A** (`parque_y_naturaleza/agility_rampa`): 0,95 × 2,80 × 1,70.
- **Túnel de agility** (`parque_y_naturaleza/agility_tunel`): 3,50 × 1,80 × 0,60 (puede esconder un premio).
- **Slalom de postes de agility** (`parque_y_naturaleza/agility_slalom`): 0,06 × 6,60 × 1,00 (2 variantes).
- **Aro de salto de agility** (`parque_y_naturaleza/agility_aro`): 1,20 × 0,70 × 1,40.
- **Balancín de perros** (`parque_y_naturaleza/agility_balancin`): 0,35 × 3,60 × 0,60.
- **Valla de salto de agility** (`parque_y_naturaleza/agility_salto`): 1,40 × 0,50 × 0,60.
- **Mesa de pausa de agility** (`parque_y_naturaleza/agility_mesa`): 0,90 × 0,90 × 0,40.

#### Vallado y fuente de la zona canina

- **Vallado de zona canina** (`parque_y_naturaleza/vallado_canino`): 2,50 × 0,06 × 1,50 (2 variantes).
- **Doble puerta de zona canina** (`parque_y_naturaleza/esclusa_canina`): 1,50 × 2,00 × 1,50.
- **Fuente con bebedero para perros** (`parque_y_naturaleza/fuente_perros`): 0,40 × 0,65 × 1,00.

### Merendero y mobiliario de parque (11)

#### Mesas y bancos de merendero

- **Mesa de pícnic con bancos unidos** (`parque_y_naturaleza/mesa_picnic`): 1,80 × 1,50 × 0,75 (2 variantes; puede esconder un premio).
- **Mesa de pícnic adaptada con vuelo** (`parque_y_naturaleza/mesa_picnic_adaptada`): 2,40 × 1,50 × 0,80 (puede esconder un premio).
- **Mesa de pícnic redonda de piedra** (`parque_y_naturaleza/mesa_picnic_piedra`): 2,20 × 2,20 × 0,75 (puede esconder un premio).
- **Banco rústico de medio tronco** (`parque_y_naturaleza/banco_medio_tronco`): 2,00 × 0,45 × 0,45.

#### Barbacoas, fuentes y pilas

- **Depósito de cenizas de barbacoa** (`parque_y_naturaleza/deposito_cenizas`): 0,50 × 0,50 × 0,80.
- **Fuente de caño con pilón** (`parque_y_naturaleza/fuente_pilon`): 1,50 × 0,90 × 1,20.
- **Pila de fregar de merendero** (`parque_y_naturaleza/pila_merendero`): 1,20 × 0,60 × 0,85.

#### Refugios, paneles e hitos

- **Cenador refugio de merendero** (`parque_y_naturaleza/refugio_merendero`): 4,00 × 3,00 × 2,80 (puede esconder un premio).
- **Papelera de madera de parque** (`parque_y_naturaleza/papelera_madera_parque`): 0,50 × 0,50 × 0,90 (puede esconder un premio).
- **Panel informativo de ruta** (`parque_y_naturaleza/panel_ruta`): 1,50 × 0,40 × 2,20.
- **Hito kilométrico** (`parque_y_naturaleza/hito_km`): 0,30 × 0,20 × 0,60.

### Senderos, rocas y relieve (25)

#### Pasarelas, puentes y escalones

- **Pasarela de madera con barandilla** (`parque_y_naturaleza/pasarela_madera`): 1,50 × 6,00 × 0,15 (no corta el paso).
- **Puente de madera de sendero** (`parque_y_naturaleza/puente_madera_sendero`): 1,50 × 5,00 × 0,40 (no corta el paso).
- **Vado de piedras pasaderas** (`parque_y_naturaleza/vado_piedras`): 1,20 × 3,00 × 0,20 (no corta el paso).
- **Escalones de traviesas** (`parque_y_naturaleza/escalones_traviesas`): 1,50 × 3,00 × 0,20 (no corta el paso).
- **Tramo de grava del camino** (`parque_y_naturaleza/tramo_grava`): 2,00 × 4,00 × 0,03 (no corta el paso).

#### Portillas, barreras y postes

- **Portilla de paso de ganado** (`parque_y_naturaleza/portilla_ganado`): 1,20 × 0,10 × 1,20 (2 variantes).
- **Paso canadiense** (`parque_y_naturaleza/paso_canadiense`): 3,00 × 2,00 × 0,10 (no corta el paso).
- **Talanquera de madera** (`parque_y_naturaleza/talanquera`): 2,50 × 0,12 × 1,00.
- **Barrera forestal de un larguero** (`parque_y_naturaleza/barrera_forestal`): 4,00 × 0,10 × 0,10 (colgado a 0,85 m).
- **Muro de piedra seca** (`parque_y_naturaleza/muro_piedra_seca`): 4,00 × 0,60 × 1,00 (puede esconder un premio).
- **Mojón de piedras** (`parque_y_naturaleza/mojon_piedra`): 0,35 × 0,35 × 0,50.
- **Poste indicador de sendero con flechas** (`parque_y_naturaleza/flechas_sendero`): 0,90 × 0,15 × 0,40 (colgado a 1,50 m).

#### Tropiezos y ramas del camino

- **Raíz que cruza el camino** (`parque_y_naturaleza/raiz_camino`): 1,50 × 0,20 × 0,08 (no corta el paso).
- **Tronco caído atravesado en el sendero** (`parque_y_naturaleza/tronco_caido`): 3,00 × 0,40 × 0,40 (2 variantes; puede esconder un premio).
- **Rama baja sobre el sendero** (`parque_y_naturaleza/rama_baja`): 2,00 × 0,15 × 0,20 (colgado a 1,50 m).
- **Barrizal del sendero** (`parque_y_naturaleza/barrizal`): 2,00 × 1,50 × 0,03 (no corta el paso).
- **Zarzal al borde del camino** (`parque_y_naturaleza/zarzal`): 2,00 × 1,00 × 1,50.

#### Rocas, taludes y cunetas

- **Talud de tierra** (`parque_y_naturaleza/talud_tierra`): 4,00 × 1,50 × 1,50.
- **Cuneta del camino** (`parque_y_naturaleza/cuneta`): 0,60 × 5,00 × 0,30 (no corta el paso).
- **Roca grande redonda** (`parque_y_naturaleza/roca_redonda`): 1,50 × 1,50 × 1,20.
- **Grupo de rocas irregular** (`parque_y_naturaleza/grupo_rocas`): 3,00 × 2,00 × 1,00 (puede esconder un premio).
- **Piedra de sentarse** (`parque_y_naturaleza/piedra_sentarse`): 0,80 × 0,60 × 0,45.

#### Miradores y observatorios

- **Barandilla curva de mirador** (`parque_y_naturaleza/barandilla_mirador`): 5,00 × 2,50 × 1,10.
- **Mesa de orientación táctil** (`parque_y_naturaleza/mesa_orientacion`): 1,20 × 0,70 × 0,90.
- **Observatorio de aves** (`parque_y_naturaleza/observatorio_aves`): 3,00 × 2,00 × 2,30 (puede esconder un premio).

### Agua (10)

#### Estanques y albercas

- **Estanque de parque con borde bajo** (`parque_y_naturaleza/estanque_parque`): 6,00 × 4,00 × 0,30 (no corta el paso).
- **Alberca de riego** (`parque_y_naturaleza/alberca_riego`): 3,00 × 2,00 × 1,00.
- **Chorros de suelo transitables** (`parque_y_naturaleza/chorros_suelo`): 4,00 × 4,00 × 0,03 (no corta el paso).

#### Arroyos, cascadas y acequias

- **Arroyo** (`parque_y_naturaleza/arroyo`): 1,50 × 8,00 × 0,20 (no corta el paso).
- **Cascada pequeña** (`parque_y_naturaleza/cascada_pequena`): 2,00 × 1,50 × 2,00.
- **Acequia de riego** (`parque_y_naturaleza/acequia`): 0,60 × 6,00 × 0,30 (no corta el paso).

#### Pozos, embarcaderos y barcas

- **Abrevadero de piedra** (`parque_y_naturaleza/abrevadero`): 2,50 × 0,70 × 0,60.
- **Pozo con brocal** (`parque_y_naturaleza/pozo_brocal`): 1,20 × 1,20 × 0,90 (puede esconder un premio).
- **Embarcadero de madera** (`parque_y_naturaleza/embarcadero`): 1,50 × 6,00 × 0,40 (no corta el paso).
- **Barca de remos varada** (`parque_y_naturaleza/barca_varada`): 1,40 × 3,50 × 0,60 (puede esconder un premio).

### Árboles, setos y plantas (26)

#### Árboles

- **Plátano de sombra** (`parque_y_naturaleza/platano_sombra`): 0,70 × 0,70 × 18,00 (3 variantes).
- **Pino piñonero** (`parque_y_naturaleza/pino_pinonero`): 0,50 × 0,50 × 14,00.
- **Olivo** (`parque_y_naturaleza/olivo`): 0,80 × 0,80 × 5,00 (2 variantes; puede esconder un premio).
- **Palmera datilera** (`parque_y_naturaleza/palmera`): 0,60 × 0,60 × 12,00.
- **Cortina de sauce llorón** (`parque_y_naturaleza/sauce_lloron`): 8,00 × 8,00 × 7,00 (no corta el paso; colgado a 0,60 m).
- **Árbol frutal** (`parque_y_naturaleza/arbol_frutal`): 0,20 × 0,20 × 3,50 (3 variantes).
- **Encina** (`parque_y_naturaleza/encina`): 0,70 × 0,70 × 10,00.
- **Copa baja de árbol** (`parque_y_naturaleza/copa_baja`): 4,00 × 4,00 × 1,50 (colgado a 1,50 m).
- **Árbol joven con tutores** (`parque_y_naturaleza/arbol_joven_tutores`): 0,80 × 0,80 × 3,00.

#### Tocones y árboles caídos

- **Tocón** (`parque_y_naturaleza/tocon`): 0,60 × 0,60 × 0,45.
- **Tocones de equilibrio en fila** (`parque_y_naturaleza/tocones_equilibrio`): 1,50 × 3,00 × 0,35.
- **Pila de leña** (`parque_y_naturaleza/pila_lena`): 2,00 × 0,60 × 1,20 (puede esconder un premio).
- **Rama grande desgajada** (`parque_y_naturaleza/rama_desgajada`): 4,00 × 2,00 × 0,60.

#### Setos

- **Bordura de boj** (`parque_y_naturaleza/bordura_boj`): 3,00 × 0,30 × 0,40.
- **Tramo de laberinto de setos** (`parque_y_naturaleza/laberinto_setos`): 6,00 × 3,00 × 2,20 (puede esconder un premio).
- **Seto vivo de espino en la linde** (`parque_y_naturaleza/seto_espino`): 5,00 × 1,20 × 1,80.

#### Arbustos, flores y césped

- **Arbusto redondo** (`parque_y_naturaleza/arbusto_redondo`): 1,20 × 1,20 × 1,10 (3 variantes).
- **Macizo de rosales** (`parque_y_naturaleza/rosaleda`): 2,00 × 1,20 × 0,90.
- **Macizo de flores** (`parque_y_naturaleza/macizo_flores`): 2,50 × 1,50 × 0,30.
- **Fila de lavanda** (`parque_y_naturaleza/lavanda_fila`): 3,00 × 0,70 × 0,60.
- **Pradera de césped** (`parque_y_naturaleza/cesped_pradera`): 8,00 × 8,00 × 0,05 (no corta el paso).
- **Cañaveral** (`parque_y_naturaleza/canaveral`): 3,00 × 2,00 × 3,00.
- **Chumbera** (`parque_y_naturaleza/chumbera`): 2,00 × 1,50 × 1,50.

#### Pérgolas y emparrados

- **Emparrado** (`parque_y_naturaleza/emparrado`): 4,00 × 4,00 × 0,50 (colgado a 1,85 m).
- **Arco de rosales** (`parque_y_naturaleza/arco_rosales`): 1,50 × 0,60 × 0,50 (colgado a 1,75 m).
- **Celosía con enredadera** (`parque_y_naturaleza/celosia_enredadera`): 2,00 × 0,25 × 1,90.

### Jardín y huerto (25)

#### Bancales y cultivos

- **Surcos del huerto** (`parque_y_naturaleza/surcos_huerto`): 4,00 × 5,00 × 0,25 (no corta el paso; puede esconder un premio).
- **Bancal elevado de madera** (`parque_y_naturaleza/bancal_elevado`): 2,00 × 1,00 × 0,70 (2 variantes; puede esconder un premio).
- **Mesa de cultivo accesible** (`parque_y_naturaleza/mesa_cultivo`): 1,50 × 0,80 × 0,80 (puede esconder un premio).
- **Tomateras entutoradas** (`parque_y_naturaleza/tomateras_entutoradas`): 3,00 × 0,80 × 1,90.
- **Espantapájaros** (`parque_y_naturaleza/espantapajaros`): 1,20 × 0,30 × 1,80.

#### Casetas, invernadero y depósitos

- **Invernadero de túnel** (`parque_y_naturaleza/invernadero_tunel`): 4,00 × 8,00 × 2,40 (puede esconder un premio).
- **Compostador** (`parque_y_naturaleza/compostador`): 0,80 × 0,80 × 1,00.
- **Depósito de agua con jaula** (`parque_y_naturaleza/deposito_agua_huerto`): 1,20 × 1,00 × 1,15.
- **Cajonera de semillero** (`parque_y_naturaleza/cajonera_semillero`): 1,20 × 0,60 × 0,45 (puede esconder un premio).
- **Armarios de aperos de huerto urbano** (`parque_y_naturaleza/armarios_aperos`): 3,00 × 0,60 × 2,00 (puede esconder un premio).

#### Aperos y riego

- **Aspersor de riego en marcha** (`parque_y_naturaleza/aspersor`): 8,00 × 8,00 × 0,15 (no corta el paso).
- **Gomas de riego por goteo** (`parque_y_naturaleza/riego_goteo`): 2,00 × 5,00 × 0,02 (no corta el paso).
- **Aperos apoyados en la valla** (`parque_y_naturaleza/aperos_apoyados`): 1,00 × 0,30 × 1,50.
- **Rastrillo tumbado con las púas arriba** (`parque_y_naturaleza/rastrillo_tumbado`): 0,40 × 1,60 × 0,08 (no corta el paso).
- **Regaderas y cubos en el camino** (`parque_y_naturaleza/regaderas_suelo`): 0,80 × 0,40 × 0,40.

#### Colmenas y gallinero

- **Gallinero con corral** (`parque_y_naturaleza/gallinero`): 3,00 × 3,00 × 1,80 (puede esconder un premio).
- **Colmenas** (`parque_y_naturaleza/colmenas`): 2,50 × 0,60 × 0,80.
- **Conejera de patas** (`parque_y_naturaleza/conejera`): 1,50 × 0,70 × 1,20 (puede esconder un premio).
- **Cercado de ovejas** (`parque_y_naturaleza/cercado_ovejas`): 5,00 × 4,00 × 1,20 (puede esconder un premio).
- **Hotel de insectos** (`parque_y_naturaleza/hotel_insectos`): 0,60 × 0,25 × 1,60 (puede esconder un premio).

#### Descanso y adorno del jardín

- **Balancín de jardín con toldo** (`parque_y_naturaleza/balancin_jardin`): 2,10 × 1,40 × 1,80.
- **Banco de forja de jardín** (`parque_y_naturaleza/banco_forja_jardin`): 1,50 × 0,65 × 0,85.
- **Hamaca de red colgada entre árboles** (`parque_y_naturaleza/hamaca_cuerda`): 1,20 × 3,80 × 0,50 (colgado a 0,50 m).
- **Reloj de sol sobre pedestal** (`parque_y_naturaleza/reloj_sol`): 0,50 × 0,50 × 1,00.
- **Bebedero de pájaros** (`parque_y_naturaleza/bebedero_pajaros`): 0,60 × 0,60 × 0,80.

### Playa (26)

#### Tumbonas, sombrillas y toldos

- **Sombrilla de playa clavada** (`parque_y_naturaleza/sombrilla_playa`): 1,80 × 1,80 × 0,50 (colgado a 1,50 m).
- **Pareja de hamacas de alquiler con sombrilla** (`parque_y_naturaleza/hamacas_alquiler`): 2,20 × 2,00 × 0,40.
- **Paravientos de playa** (`parque_y_naturaleza/paravientos_playa`): 3,00 × 0,15 × 1,20.
- **Sombrajo fijo de troncos y cañizo** (`parque_y_naturaleza/sombrajo_fijo`): 4,00 × 4,00 × 2,50 (no corta el paso).
- **Tienda de playa plegable** (`parque_y_naturaleza/tienda_playa`): 1,50 × 1,20 × 1,00 (puede esconder un premio).

#### Servicios y accesos de la playa

- **Torre de socorrismo** (`parque_y_naturaleza/torre_socorrista_playa`): 2,00 × 2,60 × 3,80.
- **Mástil de la bandera del estado del mar** (`parque_y_naturaleza/mastil_bandera_playa`): 0,12 × 0,12 × 6,00.
- **Ducha y lavapiés de playa** (`parque_y_naturaleza/ducha_lavapies`): 1,20 × 1,20 × 2,20.
- **Pasarela de tablas sobre la arena** (`parque_y_naturaleza/pasarela_playa`): 1,20 × 15,00 × 0,05 (no corta el paso).
- **Silla anfibia de baño** (`parque_y_naturaleza/silla_anfibia`): 0,90 × 1,40 × 1,00.
- **Escalera de bajada a la playa** (`parque_y_naturaleza/escalera_bajada_playa`): 2,00 × 3,00 × 1,50 (no corta el paso).

#### Cosas sobre la arena

- **Castillo de arena** (`parque_y_naturaleza/castillo_arena`): 1,00 × 1,00 × 0,35 (puede esconder un premio).
- **Hoyo en la arena** (`parque_y_naturaleza/hoyo_arena`): 0,80 × 0,80 × 0,40 (no corta el paso; puede esconder un premio).
- **Toalla extendida con bolsa y chanclas** (`parque_y_naturaleza/toalla_bolsa`): 1,00 × 1,80 × 0,10 (no corta el paso; puede esconder un premio).
- **Nevera portátil** (`parque_y_naturaleza/nevera_playa`): 0,50 × 0,35 × 0,40 (puede esconder un premio).
- **Cubo, pala y rastrillo de playa** (`parque_y_naturaleza/juguetes_arena`): 0,80 × 0,80 × 0,15 (no corta el paso).

#### Embarcaciones varadas

- **Piragua varada** (`parque_y_naturaleza/piragua_varada`): 0,70 × 3,80 × 0,35 (2 variantes; puede esconder un premio).
- **Patín de pedales varado** (`parque_y_naturaleza/hidropedal`): 2,20 × 4,50 × 1,00.
- **Velero ligero sobre su carro** (`parque_y_naturaleza/velero_ligero`): 1,60 × 4,20 × 6,50 (puede esconder un premio).
- **Tabla de surf de remo tumbada** (`parque_y_naturaleza/tabla_paddle`): 0,80 × 3,20 × 0,15.

#### Orilla, dunas y rocas

- **Orilla del mar** (`parque_y_naturaleza/orilla_mar`): 15,00 × 5,00 × 0,10 (no corta el paso).
- **Duna** (`parque_y_naturaleza/duna`): 10,00 × 8,00 × 3,00 (no corta el paso).
- **Valla de captadores de arena** (`parque_y_naturaleza/captadores_dunas`): 6,00 × 0,15 × 0,70.
- **Escollera de rocas** (`parque_y_naturaleza/escollera`): 5,00 × 15,00 × 2,50.
- **Banco de algas secas en la orilla** (`parque_y_naturaleza/posidonia_acumulada`): 6,00 × 1,00 × 0,30 (no corta el paso).
- **Rocas planas con charcas** (`parque_y_naturaleza/charca_rocas`): 5,00 × 4,00 × 0,30 (no corta el paso; puede esconder un premio).

## Sonidos propios (10)

`aspersor_riego`, `balancin_golpe`, `biosaludable_giro`, `campanas_tubulares`, `canaveral_viento`, `cascada_parque`, `gallinas_corral`, `gaviotas_playa`, `ovejas_balido`, `tirolina_cable`.

## Sonidos que toma del complemento `comun` (7)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`abejas_colmena`, `amarras_crujido`, `carrusel_giro`, `columpio_chirrido`, `ducha`, `hielo_cubitos`, `playa_olas`.

## Sonidos que toma del complemento `hogar` (3)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`juguetes`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (1)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`colchoneta`.

## Sonidos que toma del complemento `oficina_y_comercio` (1)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`garrafa`.

## Sonidos que toma del complemento `calle` (3)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`chorro`, `hojas`, `surtidor`.

## Sonidos que toma del complemento `transporte` (1)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`megafonia`.

## Sonidos que toma del complemento `juego` (3)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bandera`, `cremallera`, `muelle`.
