# Oficina y comercio

Mobiliario de oficinas, recepciones y salas de espera, y de supermercados y tiendas, con sus máquinas y sus obstáculos típicos.

- Identificador: `oficina_y_comercio`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo oficina_y_comercio` a partir de `tools/complementos_serie/oficina_y_comercio.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (66)

Medidas por defecto: ancho × fondo × alto, en metros.

### Oficina (20)

#### Mesas y puestos de trabajo

- **Mesa de despacho** (`oficina_y_comercio/mesa_despacho`): 1,40 × 0,70 × 0,74 (4 variantes; puede esconder un premio).
- **Mesa en L** (`oficina_y_comercio/mesa_ele`): 1,60 × 1,60 × 0,74 (puede esconder un premio).
- **Bancada de puestos compartidos** (`oficina_y_comercio/mesa_bench`): 2,80 × 1,60 × 0,74 (2 variantes).
- **Mesa elevable** (`oficina_y_comercio/mesa_elevable`): 1,40 × 0,80 × 0,74 (2 variantes; puede esconder un premio).
- **Cubículo de oficina** (`oficina_y_comercio/cubiculo`): 1,60 × 1,60 × 1,40 (puede esconder un premio).

#### Sillas de oficina

- **Silla de oficina** (`oficina_y_comercio/silla_giratoria`): 0,64 × 0,64 × 1,00.
- **Silla de visita** (`oficina_y_comercio/silla_confidente`): 0,55 × 0,55 × 0,85.

#### Reuniones y formación

- **Mesa de reuniones** (`oficina_y_comercio/mesa_reuniones`): 2,40 × 1,20 × 0,74 (3 variantes).
- **Pizarra de caballete** (`oficina_y_comercio/pizarra_caballete`): 0,70 × 0,60 × 1,90.
- **Mesas abatibles de formación** (`oficina_y_comercio/mesa_abatible_formacion`): 1,40 × 0,60 × 0,74 (2 variantes).

#### Archivo y armarios

- **Archivador** (`oficina_y_comercio/archivador`): 0,47 × 0,62 × 1,32 (2 variantes; puede esconder un premio).
- **Armario de oficina** (`oficina_y_comercio/armario_oficina`): 0,90 × 0,45 × 1,95 (2 variantes; puede esconder un premio).
- **Estantería de oficina** (`oficina_y_comercio/estanteria_oficina`): 0,90 × 0,35 × 1,95 (puede esconder un premio).

#### Separadores, papeleras y percheros

- **Papelera** (`oficina_y_comercio/papelera`): 0,28 × 0,28 × 0,33 (puede esconder un premio).
- **Perchero de pie** (`oficina_y_comercio/perchero`): 0,40 × 0,40 × 1,75 (puede esconder un premio).
- **Mampara separadora** (`oficina_y_comercio/mampara`): 1,20 × 0,06 × 1,40.
- **Mampara de vidrio de despacho** (`oficina_y_comercio/mampara_vidrio`): 3,00 × 0,10 × 2,70 (3 variantes).

#### Instalaciones y control horario

- **Armario de servidores** (`oficina_y_comercio/rack_servidores`): 0,60 × 1,00 × 2,00 (3 variantes).
- **Aire acondicionado de pared** (`oficina_y_comercio/split_aire`): 0,90 × 0,25 × 0,30 (colgado a 2,20 m).

#### Office

- **Módulo de office** (`oficina_y_comercio/cocina_office`): 1,80 × 0,62 × 2,10 (3 variantes; puede esconder un premio).

### Recepción y sala de espera (7)

#### Mostradores de recepción

- **Mostrador de recepción** (`oficina_y_comercio/mostrador_recepcion`): 2,00 × 0,80 × 1,10 (3 variantes; puede esconder un premio).
- **Mostrador de recepción curvo** (`oficina_y_comercio/mostrador_curvo`): 2,80 × 1,40 × 1,10 (puede esconder un premio).

#### Asientos, mesitas y plantas

- **Sillas de sala de espera en fila** (`oficina_y_comercio/sillas_espera`): 1,70 × 0,60 × 0,80 (4 variantes).
- **Mesita de revistas** (`oficina_y_comercio/mesita`): 0,60 × 0,60 × 0,45 (puede esconder un premio).
- **Planta de interior** (`oficina_y_comercio/planta`): 0,45 × 0,45 × 1,50 (puede esconder un premio).

#### Colas y turnos

- **Dispensador de turno** (`oficina_y_comercio/dispensador_turno`): 0,35 × 0,35 × 1,30.
- **Postes con cinta** (`oficina_y_comercio/postes_cinta`): 2,00 × 0,35 × 0,95.

### Máquinas (6)

#### Copias y papel

- **Fotocopiadora** (`oficina_y_comercio/fotocopiadora`): 0,65 × 0,70 × 1,15 (puede esconder un premio).
- **Destructora de papel** (`oficina_y_comercio/destructora_papel`): 0,40 × 0,30 × 0,70.

#### Café, agua y máquinas de comida

- **Máquina de café** (`oficina_y_comercio/maquina_cafe`): 0,60 × 0,70 × 1,83.
- **Máquina expendedora** (`oficina_y_comercio/maquina_expendedora`): 0,90 × 0,85 × 1,83 (puede esconder un premio).
- **Dispensador de agua** (`oficina_y_comercio/dispensador_agua`): 0,33 × 0,35 × 1,30.

#### Cajero automático

- **Cajero automático** (`oficina_y_comercio/cajero`): 0,60 × 0,60 × 1,60.

### Supermercado (18)

#### Estanterías, murales y congelados

- **Góndola de supermercado** (`oficina_y_comercio/gondola`): 4,00 × 0,90 × 1,80 (3 variantes; puede esconder un premio).
- **Estantería mural de supermercado** (`oficina_y_comercio/gondola_pared`): 3,00 × 0,50 × 2,00 (puede esconder un premio).
- **Arcón de congelados** (`oficina_y_comercio/arcon_congelados`): 2,00 × 0,90 × 0,90 (puede esconder un premio).
- **Mural refrigerado abierto** (`oficina_y_comercio/mural_refrigerado`): 2,50 × 0,95 × 2,00 (3 variantes; puede esconder un premio).
- **Armario refrigerado con puertas de cristal** (`oficina_y_comercio/armario_refrigerado`): 1,30 × 0,70 × 2,00 (3 variantes; puede esconder un premio).

#### Cajas y precios

- **Caja con cinta** (`oficina_y_comercio/caja_registradora`): 1,20 × 3,00 × 0,90.
- **Caja de autopago** (`oficina_y_comercio/caja_autopago`): 1,10 × 0,70 × 1,50.
- **Lector de precios** (`oficina_y_comercio/verificador_precios`): 0,30 × 0,15 × 0,35 (colgado a 1,20 m).

#### Carros y cestas

- **Carritos apilados** (`oficina_y_comercio/carritos`): 0,60 × 3,00 × 1,05 (3 variantes).
- **Carrito suelto** (`oficina_y_comercio/carrito_suelto`): 0,60 × 1,00 × 1,05 (puede esconder un premio).
- **Cestas apiladas** (`oficina_y_comercio/cestas`): 0,45 × 0,32 × 0,70 (puede esconder un premio).

#### Reposición, limpieza y trastienda

- **Palé con mercancía** (`oficina_y_comercio/palet`): 0,80 × 1,20 × 1,20 (puede esconder un premio).
- **Señal de suelo mojado** (`oficina_y_comercio/senal_suelo_mojado`): 0,30 × 0,40 × 0,62.
- **Escalera de reposición con ruedas** (`oficina_y_comercio/escalera_reposicion`): 0,70 × 1,20 × 1,60 (2 variantes).
- **Prensa de cartón** (`oficina_y_comercio/prensa_carton`): 1,10 × 0,80 × 2,10.

#### Servicios y promociones

- **Mesa de degustación de promoción** (`oficina_y_comercio/mesa_degustacion`): 0,80 × 0,60 × 1,00.
- **Exprimidora de naranjas de autoservicio** (`oficina_y_comercio/exprimidora_naranjas`): 0,70 × 0,60 × 1,80.
- **Máquina de devolución de envases** (`oficina_y_comercio/maquina_reciclaje_envases`): 1,00 × 0,90 × 1,90 (2 variantes).

### Tienda (8)

#### Mostradores de tienda

- **Mostrador con vitrina** (`oficina_y_comercio/mostrador_vitrina`): 1,50 × 0,70 × 1,00 (puede esconder un premio).

#### Expositores, perchas y carteles

- **Expositor giratorio** (`oficina_y_comercio/expositor_giratorio`): 0,50 × 0,50 × 1,70 (puede esconder un premio).
- **Perchero de ropa** (`oficina_y_comercio/perchero_ropa`): 1,50 × 0,55 × 1,60 (puede esconder un premio).
- **Perchero circular de ropa** (`oficina_y_comercio/perchero_circular`): 1,00 × 1,00 × 1,40 (puede esconder un premio).
- **Maniquí** (`oficina_y_comercio/maniqui`): 0,45 × 0,40 × 1,80.
- **Cartel caballete** (`oficina_y_comercio/cartel_caballete`): 0,60 × 0,60 × 1,00.

#### Probadores y bancos

- **Probador** (`oficina_y_comercio/probador`): 1,10 × 1,20 × 2,10 (puede esconder un premio).
- **Banco** (`oficina_y_comercio/banco_tienda`): 1,20 × 0,45 × 0,45 (puede esconder un premio).

### Accesos y elementos del edificio (7)

#### Puertas, tornos y felpudos

- **Puerta giratoria** (`oficina_y_comercio/puerta_giratoria`): 2,00 × 2,00 × 2,30.
- **Torno de entrada** (`oficina_y_comercio/torno`): 0,80 × 1,10 × 1,00.
- **Arcos antihurto** (`oficina_y_comercio/arco_seguridad`): 1,20 × 0,40 × 1,60 (no corta el paso).
- **Felpudo de entrada** (`oficina_y_comercio/felpudo_entrada`): 1,80 × 1,00 × 0,02 (no corta el paso).
- **Reja de tijera** (`oficina_y_comercio/reja_tijera`): 2,00 × 0,12 × 2,30 (2 variantes).

#### Columnas y seguridad

- **Columna** (`oficina_y_comercio/columna`): 0,45 × 0,45 × 3,00.
- **Extintor colgado** (`oficina_y_comercio/extintor`): 0,15 × 0,15 × 0,50 (colgado a 1,00 m).

## Sonidos propios (12)

`caja_registradora`, `cinta_caja`, `cortina`, `fotocopiadora`, `garrafa`, `maquina_cafe`, `oficina_destructora`, `oficina_exprimidora`, `oficina_reciclaje_envases`, `oficina_servidores`, `puerta_giratoria`, `silla_ruedas`.

## Sonidos que toma del complemento `comun` (2)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`actuador_ayuda_tecnica`, `prensa_industrial`.

## Sonidos que toma del complemento `hogar` (5)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `interruptor`, `puerta_cristal`, `puerta_electrodomestico`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (1)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`teclado`.

## Sonidos que toma del complemento `calle` (1)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`papel`.

## Sonidos que toma del complemento `transporte` (6)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `megafonia`, `taquilla`, `teclas_cajero`, `torno`.
