# Calle

Lo que se encuentra en una acera: mobiliario urbano, semáforos, contenedores, árboles, vehículos aparcados, terrazas, obras y marcas del suelo.

- Identificador: `calle`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo calle` a partir de `tools/complementos_serie/calle.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (96)

Medidas por defecto: ancho × fondo × alto, en metros.

### Mobiliario urbano (20)

#### Farolas y postes

- **Farola** (`calle/farola`): 0,18 × 0,18 × 6,00 (3 variantes).
- **Poste de la luz** (`calle/poste_luz`): 0,30 × 0,30 × 9,00.

#### Bolardos y protecciones

- **Bolardo** (`calle/bolardo`): 0,15 × 0,15 × 0,80 (3 variantes).
- **Pilona escamoteable** (`calle/pilona`): 0,27 × 0,27 × 0,60.
- **Bloque de hormigón antivehículos** (`calle/bloque_antivehiculo`): 1,60 × 0,80 × 0,80 (2 variantes).
- **Guardacantón de esquina** (`calle/guardacanton`): 0,40 × 0,40 × 0,60.

#### Bancos y asientos

- **Banco** (`calle/banco`): 1,80 × 0,65 × 0,85 (3 variantes; puede esconder un premio).
- **Banco de piedra sin respaldo** (`calle/banco_piedra`): 2,00 × 0,50 × 0,45.
- **Bancos en rotonda** (`calle/bancos_rotonda`): 4,00 × 4,00 × 0,45 (puede esconder un premio).
- **Silla urbana individual** (`calle/silla_urbana`): 0,60 × 0,60 × 0,85.

#### Buzones, cabinas y aseos

- **Buzón de correos** (`calle/buzon`): 0,50 × 0,50 × 1,60 (puede esconder un premio).
- **Buzón de pared** (`calle/buzon_pared`): 0,40 × 0,20 × 0,50 (colgado a 1,00 m; puede esconder un premio).
- **Cabina de teléfono** (`calle/cabina`): 0,90 × 0,90 × 2,30 (puede esconder un premio).
- **Aseo público automático** (`calle/aseo_publico_automatico`): 2,60 × 1,80 × 2,60.

#### Información, publicidad y relojes

- **Tótem informativo** (`calle/totem`): 1,20 × 0,20 × 2,30.
- **Columna anunciadora** (`calle/columna_anunciadora`): 1,20 × 1,20 × 3,00.
- **Reloj de calle sobre columna** (`calle/reloj_calle`): 0,30 × 0,30 × 3,80.

#### Bicis, parquímetros y recarga

- **Aparcabicis con bicicletas** (`calle/aparcabicis`): 3,00 × 1,80 × 1,00 (3 variantes).
- **Parquímetro** (`calle/parquimetro`): 0,35 × 0,35 × 1,60.
- **Punto de recarga** (`calle/punto_recarga`): 0,40 × 0,30 × 1,50.

### Semáforos y señales (12)

#### Semáforos

- **Semáforo de peatones sonoro con pulsador** (`calle/semaforo_peatones`): 0,15 × 0,15 × 3,00.
- **Semáforo de peatones sonoro** (`calle/semaforo_peatones_sonoro`): 0,15 × 0,15 × 3,00.
- **Semáforo de peatones sin sonido** (`calle/semaforo_peatones_mudo`): 0,15 × 0,15 × 3,00.
- **Semáforo de vehículos** (`calle/semaforo_vehiculos`): 0,20 × 0,20 × 3,50.

#### Señales y placas

- **Señal de tráfico en poste** (`calle/senal`): 0,08 × 0,08 × 2,80.
- **Placa de señal a la altura de la cabeza** (`calle/senal_baja`): 0,60 × 0,05 × 0,60 (colgado a 1,50 m).
- **Placa de calle en relieve y braille** (`calle/placa_calle_braille`): 0,30 × 0,03 × 0,15 (no corta el paso; colgado a 1,20 m).

#### Pasos de peatones e isletas

- **Paso de peatones de cebra** (`calle/paso_cebra`): 4,00 × 7,00 × 0,00 (3 variantes; no corta el paso).
- **Isleta refugio en mitad del paso** (`calle/isleta_refugio`): 4,00 × 2,00 × 0,15 (no corta el paso).
- **Paso de peatones sobreelevado** (`calle/paso_elevado`): 4,00 × 7,00 × 0,10 (no corta el paso).

#### Carril bici y balizas

- **Carril bici por la acera** (`calle/carril_bici`): 2,00 × 10,00 × 0,00 (2 variantes; no corta el paso).
- **Baliza cilíndrica flexible** (`calle/baliza_flexible`): 0,10 × 0,10 × 0,75.

### Contenedores y papeleras (12)

#### Papeleras y bolsas para perros

- **Papelera** (`calle/papelera`): 0,40 × 0,40 × 0,90 (puede esconder un premio).
- **Dispensador de bolsas para perros** (`calle/dispensador_bolsas_perro`): 0,30 × 0,20 × 1,20.

#### Contenedores de basura

- **Contenedor de 240 litros** (`calle/contenedor_240`): 0,58 × 0,73 × 1,07 (2 variantes; puede esconder un premio).
- **Contenedor de resto de 1100 litros** (`calle/contenedor_resto`): 1,37 × 1,07 × 1,33 (2 variantes; puede esconder un premio).
- **Cercado de contenedores** (`calle/cercado_contenedores`): 4,00 × 1,80 × 1,50.
- **Buzón de contenedor soterrado** (`calle/contenedor_soterrado`): 0,80 × 0,70 × 1,15.

#### Reciclaje

- **Contenedor de envases** (`calle/contenedor_envases`): 1,88 × 1,45 × 1,65 (puede esconder un premio).
- **Contenedor de papel** (`calle/contenedor_papel`): 1,88 × 1,45 × 1,65 (puede esconder un premio).
- **Contenedor de vidrio tipo iglú** (`calle/contenedor_vidrio`): 1,60 × 1,60 × 1,70 (puede esconder un premio).
- **Contenedor de ropa usada** (`calle/contenedor_ropa`): 1,20 × 1,00 × 2,00 (puede esconder un premio).
- **Contenedor de aceite usado** (`calle/contenedor_aceite`): 0,70 × 0,60 × 1,40.
- **Contenedor de pilas en poste** (`calle/contenedor_pilas`): 0,25 × 0,20 × 0,50 (colgado a 0,80 m).

### Árboles, jardineras y fuentes (11)

#### Árboles y alcorques

- **Alcorque con árbol** (`calle/alcorque`): 0,35 × 0,35 × 6,00 (3 variantes; puede esconder un premio).
- **Alcorque sin árbol** (`calle/alcorque_hueco`): 1,00 × 1,00 × 0,08 (no corta el paso).
- **Rejilla de alcorque** (`calle/rejilla_alcorque`): 1,20 × 1,20 × 0,02 (no corta el paso).

#### Jardineras, setos y parterres

- **Jardinera** (`calle/jardinera`): 1,20 × 0,50 × 0,50 (puede esconder un premio).
- **Maceta grande** (`calle/maceta_grande`): 0,70 × 0,70 × 1,20 (puede esconder un premio).
- **Seto** (`calle/seto`): 3,00 × 0,60 × 1,00.
- **Parterre con bordillo bajo** (`calle/parterre_bordillo`): 3,00 × 1,50 × 0,10 (2 variantes; no corta el paso).
- **Valla baja de arquillos** (`calle/valla_arquillos`): 2,00 × 0,03 × 0,35.

#### Fuentes y agua

- **Fuente para beber** (`calle/fuente_beber`): 0,40 × 0,40 × 1,00.
- **Fuente ornamental** (`calle/fuente_ornamental`): 4,00 × 4,00 × 1,20 (3 variantes; puede esconder un premio).
- **Lavadero público** (`calle/lavadero_publico`): 4,00 × 1,50 × 0,80.

### Vehículos aparcados (5)

#### Coches y furgonetas

- **Coche aparcado** (`calle/coche`): 1,80 × 4,30 × 1,50 (3 variantes).
- **Furgoneta** (`calle/furgoneta`): 2,00 × 5,40 × 2,50 (puede esconder un premio).

#### Motos, bicis y patinetes

- **Moto aparcada en la acera** (`calle/moto`): 0,80 × 2,00 × 1,15.
- **Patinetes aparcados** (`calle/patinetes`): 1,20 × 1,15 × 1,10 (3 variantes).
- **Bicicleta atada a un poste** (`calle/bicicleta`): 0,60 × 1,75 × 1,05.

### Terrazas, quioscos y comercio (10)

#### Terrazas de bar

- **Mesa de terraza con sillas** (`calle/mesa_terraza`): 1,80 × 1,80 × 0,75 (puede esconder un premio).
- **Mesa alta de terraza** (`calle/mesa_alta`): 0,70 × 0,70 × 1,10.
- **Sombrilla** (`calle/sombrilla`): 0,50 × 0,50 × 2,50.

#### Quioscos y puestos

- **Quiosco** (`calle/quiosco`): 2,50 × 2,50 × 2,80 (puede esconder un premio).
- **Puesto de mercado** (`calle/puesto_mercado`): 3,00 × 2,00 × 2,30 (puede esconder un premio).
- **Quiosco de flores** (`calle/quiosco_flores`): 3,00 × 2,00 × 2,60 (puede esconder un premio).

#### Comercio en la acera

- **Cartel caballete** (`calle/cartel_caballete`): 0,60 × 0,60 × 1,00.
- **Toldo bajo** (`calle/toldo_bajo`): 3,00 × 1,20 × 0,25 (colgado a 1,65 m).
- **Cajas de fruta en la acera** (`calle/expositor_fruta`): 2,00 × 0,80 × 0,90 (puede esconder un premio).
- **Expositor giratorio de postales** (`calle/expositor_postales`): 0,50 × 0,50 × 1,70 (puede esconder un premio).

### Obras y obstáculos temporales (7)

#### Vallas y andamios

- **Valla de obra** (`calle/valla_obra`): 2,50 × 0,50 × 1,10 (2 variantes).
- **Pies de andamio** (`calle/andamio`): 5,00 × 0,15 × 2,50 (3 variantes).
- **Travesaño de andamio** (`calle/andamio_travesano`): 1,30 × 0,06 × 0,06 (colgado a 1,70 m).

#### Zanjas, conos y charcos

- **Zanja señalizada** (`calle/zanja`): 2,00 × 1,20 × 1,10.
- **Cono** (`calle/cono`): 0,30 × 0,30 × 0,50.
- **Saco de escombros** (`calle/saco_escombros`): 0,90 × 0,90 × 0,90 (puede esconder un premio).
- **Charco** (`calle/charco`): 1,20 × 0,80 × 0,02 (no corta el paso).

### Suelo, bordillos y servicios (14)

#### Tapas y rejillas

- **Boca de riego** (`calle/boca_riego`): 0,30 × 0,30 × 0,02 (no corta el paso).
- **Tapa de alcantarilla** (`calle/tapa_alcantarilla`): 0,70 × 0,70 × 0,02 (no corta el paso).
- **Rejilla de ventilación** (`calle/rejilla`): 1,50 × 1,00 × 0,02 (no corta el paso).

#### Armarios, hidrantes y fachada

- **Armario de servicios** (`calle/armario_servicios`): 1,00 × 0,40 × 1,30.
- **Hidrante de columna** (`calle/hidrante`): 0,30 × 0,30 × 0,75.
- **Reja de ventana saliente** (`calle/reja_ventana`): 1,20 × 0,25 × 1,40 (colgado a 0,80 m).

#### Bordillos, escalones y desniveles

- **Escalón o bordillo alto** (`calle/bordillo_alto`): 2,00 × 0,30 × 0,15 (no corta el paso).
- **Rampa de vado** (`calle/rampa_vado`): 3,00 × 1,50 × 0,10 (no corta el paso).
- **Escalinata de calle con pasamanos** (`calle/escaleras_calle`): 3,00 × 2,40 × 1,36 (3 variantes; no corta el paso).
- **Borde de acera elevada sin protección** (`calle/desnivel_lateral`): 6,00 × 0,20 × 0,01 (no corta el paso).

#### Pavimentos y guías del suelo

- **Pavimento táctil de botones** (`calle/pavimento_botones`): 4,00 × 0,60 × 0,01 (no corta el paso).
- **Pavimento táctil de rayas** (`calle/pavimento_rayas`): 0,80 × 4,00 × 0,01 (no corta el paso).
- **Rigola de calle de plataforma única** (`calle/rigola_plataforma_unica`): 0,40 × 10,00 × 0,01 (no corta el paso).
- **Tramo de adoquín irregular** (`calle/adoquinado`): 3,00 × 5,00 × 0,02 (no corta el paso).

### Plazas y monumentos (5)

#### Monumentos y soportales

- **Monumento sobre pedestal escalonado** (`calle/monumento_plaza`): 3,50 × 3,50 × 5,00.
- **Pilar de soportal** (`calle/pilar_soportal`): 0,50 × 0,50 × 3,50 (2 variantes).

#### Templetes, gradas y atracciones

- **Templete de música** (`calle/templete_musica`): 7,00 × 7,00 × 5,50 (puede esconder un premio).
- **Graderío de piedra** (`calle/graderio_plaza`): 6,00 × 2,50 × 0,90.
- **Tiovivo** (`calle/tiovivo`): 8,00 × 8,00 × 4,50 (puede esconder un premio).

## Sonidos propios (10)

`calle_expositor_giro`, `calle_reloj_campanadas`, `calle_soterrado_caida`, `chorro`, `hojas`, `papel`, `surtidor`, `trampilla_buzon`, `vidrio`, `zumbido_recarga`.

## Sonidos que toma del complemento `comun` (2)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`calle_tiovivo_organillo`, `carrusel_giro`.

## Sonidos que toma del complemento `hogar` (4)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cisterna`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `oficina_y_comercio` (1)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`garrafa`.

## Sonidos que toma del complemento `transporte` (4)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `interfono`, `megafonia`, `timbre_bici`.

## Sonidos que toma del complemento `juego` (1)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`monedas`.
