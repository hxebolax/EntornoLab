# Juego

Objetos para los juegos: escondites de premios, cosas que suenan al tocarlas y metas. Unos fantásticos, para niños, y otros sobrios, para adultos.

- Identificador: `juego`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo juego` a partir de `tools/complementos_serie/juego.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (95)

Medidas por defecto: ancho × fondo × alto, en metros.

### Escondites de premios (18)

#### Cofres, cajas y vasijas

- **Cofre del tesoro** (`juego/cofre`): 0,80 × 0,50 × 0,50 (3 variantes; puede esconder un premio).
- **Caja sorpresa** (`juego/caja_sorpresa`): 0,40 × 0,40 × 0,40 (puede esconder un premio).
- **Caja de juguetes** (`juego/caja_juguetes`): 0,70 × 0,45 × 0,45 (puede esconder un premio).
- **Caja de música** (`juego/caja_musica`): 0,25 × 0,18 × 0,12 (puede esconder un premio).
- **Vasija antigua** (`juego/vasija`): 0,45 × 0,45 × 0,70 (puede esconder un premio).
- **Barril de pirata** (`juego/barril_pirata`): 0,60 × 0,60 × 0,90 (puede esconder un premio).

#### Huchas, sacos y piñatas

- **Hucha** (`juego/hucha`): 0,30 × 0,40 × 0,30 (puede esconder un premio).
- **Mochila** (`juego/mochila`): 0,35 × 0,25 × 0,45 (puede esconder un premio).
- **Saco de monedas** (`juego/saco_monedas`): 0,40 × 0,40 × 0,45 (puede esconder un premio).
- **Piñata colgada** (`juego/pinata`): 0,50 × 0,50 × 0,50 (colgado a 1,45 m; puede esconder un premio).

#### Joyas, reliquias y nidos

- **Nido gigante** (`juego/nido`): 1,00 × 1,00 × 0,40 (puede esconder un premio).
- **Olla del final del arcoíris** (`juego/olla_arcoiris`): 0,50 × 0,50 × 0,50 (puede esconder un premio).
- **Huevo de dragón** (`juego/huevo_dragon`): 0,40 × 0,40 × 0,60 (puede esconder un premio).
- **Corona sobre un cojín** (`juego/corona_cojin`): 0,50 × 0,50 × 1,00 (puede esconder un premio).
- **Gema sobre un pedestal** (`juego/gema_pedestal`): 0,40 × 0,40 × 1,10 (puede esconder un premio).

#### Mensajes y mapas

- **Buzón de mensajes** (`juego/buzon_mensajes`): 0,35 × 0,30 × 1,20 (puede esconder un premio).
- **Mapa del tesoro en un atril** (`juego/mapa_tesoro`): 0,50 × 0,40 × 1,10 (puede esconder un premio).
- **Botella con un mensaje** (`juego/botella_mensaje`): 0,10 × 0,30 × 0,10 (puede esconder un premio).

### Cosas que suenan (10)

#### Campanas, timbres y cuernos

- **Campana** (`juego/campana`): 0,50 × 0,50 × 0,50 (colgado a 1,00 m).
- **Carillón de viento** (`juego/carillon`): 0,30 × 0,30 × 0,60 (no corta el paso; colgado a 1,50 m).
- **Timbre de mostrador** (`juego/timbre`): 0,30 × 0,30 × 1,00.
- **Cuerno colgado de la pared** (`juego/cuerno_caza`): 0,50 × 0,20 × 0,25 (colgado a 1,30 m).

#### Instrumentos para tocar

- **Xilófono gigante** (`juego/xilofono`): 1,60 × 0,80 × 0,75.
- **Tambor** (`juego/tambor`): 0,60 × 0,60 × 0,80 (puede esconder un premio).
- **Litófono de piedras** (`juego/litofono`): 1,40 × 0,50 × 0,75.
- **Organillo de manivela** (`juego/organillo`): 0,70 × 0,50 × 1,00.

#### Balizas y pistas sonoras

- **Baliza musical** (`juego/baliza_musical`): 0,25 × 0,25 × 1,00.
- **Caracola que habla** (`juego/caracola`): 0,30 × 0,20 × 0,15.

### Lugares de fantasía (19)

#### Naturaleza mágica

- **Árbol mágico** (`juego/arbol_magico`): 1,00 × 1,00 × 5,00 (puede esconder un premio).
- **Fuente de los deseos** (`juego/fuente_deseos`): 1,40 × 1,40 × 0,90 (puede esconder un premio).
- **Seta gigante** (`juego/seta_gigante`): 0,90 × 0,90 × 0,90 (puede esconder un premio).
- **Charca de ranas** (`juego/charca`): 2,00 × 1,50 × 0,05 (no corta el paso; puede esconder un premio).

#### Refugios y caminos

- **Tienda de campaña** (`juego/tienda_campana`): 2,20 × 1,90 × 1,50 (puede esconder un premio).
- **Casita de juegos** (`juego/casita`): 1,60 × 1,60 × 1,60 (puede esconder un premio).
- **Alfombra voladora** (`juego/alfombra_voladora`): 1,80 × 1,20 × 0,02 (no corta el paso; puede esconder un premio).
- **Puentecillo** (`juego/puente`): 1,20 × 2,50 × 0,30 (no corta el paso).

#### Castillo y hechicería

- **Estatua** (`juego/estatua`): 0,80 × 0,80 × 2,20 (puede esconder un premio).
- **Trono** (`juego/trono`): 1,00 × 0,80 × 1,80 (puede esconder un premio).
- **Caldero de pociones al fuego** (`juego/caldero_pociones`): 0,80 × 0,80 × 0,70 (puede esconder un premio).
- **Libro de hechizos en un atril** (`juego/libro_hechizos`): 0,60 × 0,45 × 1,10 (puede esconder un premio).
- **Bola de cristal sobre una mesita** (`juego/bola_cristal`): 0,60 × 0,60 × 0,90 (puede esconder un premio).
- **Espada clavada en la roca** (`juego/espada_roca`): 1,00 × 1,00 × 1,30.

#### Barco pirata

- **Cañón pirata** (`juego/canon_pirata`): 0,80 × 1,80 × 0,90.
- **Timón de barco** (`juego/timon_barco`): 1,00 × 0,40 × 1,40.

#### Nave espacial

- **Consola de mandos de la nave** (`juego/consola_nave`): 1,60 × 0,80 × 1,10 (puede esconder un premio).
- **Escotilla de la nave** (`juego/escotilla_nave`): 1,20 × 0,40 × 2,10.
- **Meteorito humeante** (`juego/meteorito`): 0,90 × 0,90 × 0,60 (puede esconder un premio).

### Metas y señales (10)

#### Metas y podios

- **Bandera de meta** (`juego/bandera_meta`): 0,20 × 0,20 × 2,50.
- **Arco de meta** (`juego/arco_meta`): 3,50 × 0,80 × 3,00 (no corta el paso).
- **Podio** (`juego/podio`): 1,80 × 0,80 × 0,60 (puede esconder un premio).

#### Blancos y juegos de suelo

- **Globo** (`juego/globo`): 0,30 × 0,40 × 0,40 (no corta el paso; colgado a 1,40 m; puede esconder un premio).
- **Diana** (`juego/diana`): 0,80 × 0,60 × 1,50.
- **Dado gigante** (`juego/dado_gigante`): 0,50 × 0,50 × 0,50 (2 variantes).
- **Rayuela en relieve** (`juego/rayuela`): 1,20 × 3,50 × 0,01 (no corta el paso).

#### Marcas y pistas

- **Poste de flechas** (`juego/senal_flecha`): 0,12 × 0,12 × 2,20.
- **Estrella en el suelo** (`juego/estrella_suelo`): 0,80 × 0,80 × 0,01 (no corta el paso; puede esconder un premio).
- **Huellas en el suelo** (`juego/huellas_suelo`): 0,40 × 3,00 × 0,01 (no corta el paso).

### Juegos de adultos (9)

#### Taquillas, cajas y paquetes

- **Taquilla** (`juego/taquilla`): 0,40 × 0,50 × 1,80 (puede esconder un premio).
- **Caja fuerte** (`juego/caja_fuerte`): 0,50 × 0,45 × 0,60 (puede esconder un premio).
- **Buzón de portal** (`juego/buzon`): 0,90 × 0,15 × 0,60 (colgado a 1,00 m; puede esconder un premio).
- **Paquete** (`juego/paquete`): 0,40 × 0,30 × 0,25 (puede esconder un premio).
- **Maletín** (`juego/maletin`): 0,45 × 0,12 × 0,33 (puede esconder un premio).

#### Cosas que hay que recoger

- **Llavero en un cuenco** (`juego/cuenco_llaves`): 0,30 × 0,30 × 0,90 (puede esconder un premio).
- **Paraguas en el paragüero** (`juego/paraguero`): 0,25 × 0,25 × 0,90 (puede esconder un premio).
- **Abrigo en la percha** (`juego/percha_abrigo`): 0,50 × 0,20 × 1,10 (colgado a 0,60 m; puede esconder un premio).
- **Mesa de objetos** (`juego/mesa_objetos`): 0,80 × 0,50 × 0,75 (puede esconder un premio).

### Llaves, puertas y acertijos (10)

#### Llaves y puertas

- **Llave mágica en su gancho** (`juego/llave_magica`): 0,35 × 0,35 × 1,10 (puede esconder un premio).
- **Puerta mágica** (`juego/puerta_magica`): 1,20 × 0,30 × 2,30.
- **Estantería con puerta secreta** (`juego/puerta_secreta`): 1,20 × 0,40 × 2,20 (puede esconder un premio).
- **Reja levadiza del castillo** (`juego/rastrillo`): 3,00 × 0,15 × 3,00.
- **Puente levadizo** (`juego/puente_levadizo`): 2,50 × 4,00 × 0,15.

#### Mecanismos y acertijos

- **Palanca en la pared** (`juego/palanca`): 0,20 × 0,20 × 0,50 (colgado a 0,90 m).
- **Losa que se hunde** (`juego/placa_presion`): 0,60 × 0,60 × 0,02 (no corta el paso).
- **Panel de memoria de cuatro botones** (`juego/panel_simon`): 0,60 × 0,15 × 0,60 (colgado a 0,90 m).
- **Reloj de arena gigante** (`juego/reloj_arena`): 0,35 × 0,35 × 0,80.
- **Portal mágico de piedras** (`juego/portal_magico`): 2,00 × 0,50 × 2,50.

### Personajes y animales (9)

#### Animales y criaturas

- **Dragón dormido** (`juego/dragon_dormido`): 3,00 × 4,50 × 1,60 (puede esconder un premio).
- **Búho en su percha** (`juego/buho_percha`): 0,40 × 0,40 × 1,60.
- **Loro en su percha** (`juego/loro_percha`): 0,50 × 0,35 × 1,50.
- **Gato** (`juego/gato_negro`): 0,25 × 0,50 × 0,30.
- **Panal silvestre colgado de una rama** (`juego/panal_colgado`): 0,50 × 0,50 × 0,60 (colgado a 1,50 m; puede esconder un premio).

#### Figuras y seres

- **Armadura de caballero** (`juego/armadura`): 0,70 × 0,60 × 1,90 (puede esconder un premio).
- **Robot guía** (`juego/robot_guia`): 0,60 × 0,60 × 1,30 (puede esconder un premio).
- **Muñeco de nieve** (`juego/muneco_nieve`): 0,60 × 0,60 × 1,30.
- **Fantasma de sábana** (`juego/fantasma`): 0,60 × 0,60 × 1,30 (no corta el paso; colgado a 0,60 m).

### Obstáculos de aventura (10)

#### Trampas del suelo

- **Arenas movedizas** (`juego/arenas_movedizas`): 2,00 × 2,00 × 0,02 (no corta el paso).
- **Río de lava** (`juego/rio_lava`): 1,50 × 5,00 × 0,10.
- **Trampilla en el suelo** (`juego/trampilla_suelo`): 0,80 × 0,80 × 0,03 (puede esconder un premio).
- **Hilo con cascabeles** (`juego/hilo_cascabeles`): 2,00 × 0,03 × 0,03 (colgado a 0,15 m).

#### Cosas que cuelgan

- **Telaraña gigante** (`juego/telarana`): 1,50 × 0,10 × 1,40 (no corta el paso; colgado a 0,60 m).
- **Estalactita** (`juego/estalactita`): 0,30 × 0,30 × 0,60 (colgado a 1,50 m).
- **Liana colgante** (`juego/liana`): 0,15 × 0,15 × 2,00 (colgado a 0,40 m).
- **Escalera de cuerda** (`juego/escalera_cuerda`): 0,50 × 0,10 × 2,50.

#### Cuevas y murallas

- **Boca de cueva** (`juego/entrada_cueva`): 3,00 × 1,50 × 2,50 (puede esconder un premio).
- **Tramo de muralla con almenas** (`juego/muralla_almenas`): 4,00 × 0,80 × 3,50.

## Sonidos propios (35)

`arbol_magico`, `baliza_musical`, `bandera`, `caja_fuerte`, `campana`, `cofre_abrir`, `cofre_cerrar`, `cremallera`, `deseo`, `fuente_deseos`, `globo`, `globo_explota`, `juego_buho`, `juego_caldero`, `juego_canonazo`, `juego_cuerno`, `juego_dado`, `juego_dragon_ronquido`, `juego_escotilla`, `juego_fantasma`, `juego_litofono`, `juego_loro`, `juego_maullido`, `juego_portal`, `juego_reloj_arena`, `juego_robot`, `juego_rugido`, `juego_simon`, `llaves`, `magia`, `merendero_brasas`, `monedas`, `muelle`, `tambor`, `xilofono`.

## Sonidos que toma del complemento `comun` (7)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`abejas_colmena`, `barra_abatible_clac`, `bici_volante_giro`, `calle_tiovivo_organillo`, `goteo_pescaderia`, `playa_olas`, `vehiculos_cadena`.

## Sonidos que toma del complemento `hogar` (5)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `interruptor`, `juguetes`, `sentarse`, `tapa_contenedor`.

## Sonidos que toma del complemento `colegio` (1)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`pandereta`.

## Sonidos que toma del complemento `oficina_y_comercio` (1)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`puerta_giratoria`.

## Sonidos que toma del complemento `calle` (3)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`hojas`, `papel`, `trampilla_buzon`.

## Sonidos que toma del complemento `transporte` (4)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `taquilla`, `timbre_bici`.
