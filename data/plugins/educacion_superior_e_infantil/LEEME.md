# Guardería, universidad y residencia de estudiantes

Guardería y escuela infantil, ludoteca, aulas en grada, pasillos, laboratorios de prácticas y aulas especiales de la universidad, y habitación, salas comunes y comedor de una residencia de estudiantes.

- Identificador: `educacion_superior_e_infantil`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo educacion_superior_e_infantil` a partir de `tools/complementos_serie/educacion_superior_e_infantil.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (107)

Medidas por defecto: ancho × fondo × alto, en metros.

### Guardería y escuela infantil (34)

#### Cunas y siesta

- **Cuna de guardería con ruedas** (`educacion_superior_e_infantil/cuna_guarderia`): 0,65 × 1,25 × 1,00 (puede esconder un premio).
- **Camita apilable de siesta** (`educacion_superior_e_infantil/camita_apilable`): 0,57 × 1,33 × 0,12 (2 variantes).
- **Pila de camitas de siesta** (`educacion_superior_e_infantil/camitas_apiladas`): 0,57 × 1,33 × 1,00.
- **Hamaca balancín de bebé** (`educacion_superior_e_infantil/hamaca_bebe`): 0,45 × 0,70 × 0,40.
- **Móvil colgante de la sala de cunas** (`educacion_superior_e_infantil/movil_cuna_colgante`): 0,50 × 0,50 × 0,35 (colgado a 1,45 m).

#### Cambiadores y aseo infantil

- **Cambiador abatible de pared** (`educacion_superior_e_infantil/cambiador_pared`): 0,87 × 0,50 × 0,50 (2 variantes; colgado a 0,80 m).
- **Mueble cambiador con escalerilla** (`educacion_superior_e_infantil/cambiador_mueble`): 1,20 × 1,00 × 0,95 (puede esconder un premio).
- **Contenedor de pañales con pedal** (`educacion_superior_e_infantil/contenedor_panales`): 0,30 × 0,40 × 0,75.
- **Lavamanos corrido infantil** (`educacion_superior_e_infantil/pila_lavamanos_infantil`): 1,20 × 0,40 × 0,55 (3 variantes).
- **Inodoro infantil** (`educacion_superior_e_infantil/inodoro_infantil`): 0,30 × 0,45 × 0,35.
- **Orinales en fila** (`educacion_superior_e_infantil/orinales_fila`): 1,20 × 0,32 × 0,20 (3 variantes).

#### Mesas, sillas y tronas bajas

- **Trona** (`educacion_superior_e_infantil/trona_guarderia`): 0,55 × 0,70 × 1,00.
- **Mesa de comer con asientos encajados** (`educacion_superior_e_infantil/mesa_tronas`): 1,90 × 1,00 × 0,55.
- **Mesa de infantil en forma de riñón** (`educacion_superior_e_infantil/mesa_rinon_infantil`): 1,50 × 0,80 × 0,46 (4 variantes; puede esconder un premio).
- **Mesa de infantil en forma de flor** (`educacion_superior_e_infantil/mesa_flor_infantil`): 1,20 × 1,20 × 0,46 (3 variantes; puede esconder un premio).
- **Sillita de infantil** (`educacion_superior_e_infantil/sillita_infantil`): 0,32 × 0,32 × 0,50 (3 variantes).

#### Perchas, casilleros y bandejas

- **Banco zapatero bajo** (`educacion_superior_e_infantil/banco_zapatero_infantil`): 1,00 × 0,35 × 0,30 (puede esconder un premio).
- **Perchas bajas con casilleros** (`educacion_superior_e_infantil/perchas_casilleros_infantil`): 1,20 × 0,25 × 0,45 (3 variantes; colgado a 0,70 m; puede esconder un premio).
- **Mueble de bandejas con ruedas** (`educacion_superior_e_infantil/mueble_bandejas_ruedas`): 1,05 × 0,45 × 0,75 (3 variantes; puede esconder un premio).

#### Psicomotricidad y suelo blando

- **Suelo de espuma en piezas** (`educacion_superior_e_infantil/suelo_espuma_puzle`): 1,80 × 1,80 × 0,02 (3 variantes; no corta el paso; puede esconder un premio).
- **Piscina de bolas** (`educacion_superior_e_infantil/piscina_bolas`): 1,50 × 1,50 × 0,40 (3 variantes; puede esconder un premio).
- **Rampa y escalones de espuma** (`educacion_superior_e_infantil/rampa_escalones_espuma`): 0,60 × 1,80 × 0,30.
- **Bloques de espuma sueltos** (`educacion_superior_e_infantil/bloques_espuma`): 1,20 × 1,00 × 0,40 (puede esconder un premio).
- **Túnel de gateo** (`educacion_superior_e_infantil/tunel_gateo`): 0,60 × 1,80 × 0,60 (puede esconder un premio).
- **Espejo de seguridad con barra** (`educacion_superior_e_infantil/espejo_barra_infantil`): 1,20 × 0,10 × 0,90.
- **Cojines en corro de la asamblea** (`educacion_superior_e_infantil/cojines_asamblea`): 2,50 × 2,50 × 0,12 (puede esconder un premio).
- **Panel sensorial de pared** (`educacion_superior_e_infantil/panel_sensorial_pared`): 0,90 × 0,10 × 0,60 (colgado a 0,30 m).
- **Caballete de pintura infantil doble** (`educacion_superior_e_infantil/caballete_pintura_doble`): 0,65 × 0,60 × 1,15 (2 variantes).

#### Entrada, vallas y carros

- **Parque de juegos vallado** (`educacion_superior_e_infantil/corralito`): 1,50 × 1,30 × 0,65 (puede esconder un premio).
- **Barrera de seguridad infantil de puerta** (`educacion_superior_e_infantil/valla_seguridad_puerta`): 0,80 × 0,05 × 0,76.
- **Cochecitos aparcados en la entrada** (`educacion_superior_e_infantil/cochecitos_aparcados`): 1,80 × 1,00 × 1,05 (3 variantes; puede esconder un premio).
- **Carro de paseo de seis plazas** (`educacion_superior_e_infantil/carro_paseo_multiple`): 0,78 × 1,90 × 1,05 (2 variantes).
- **Cuna de evacuación** (`educacion_superior_e_infantil/cuna_evacuacion`): 0,75 × 1,30 × 1,10 (puede esconder un premio).
- **Carro de comidas de guardería** (`educacion_superior_e_infantil/carro_comida_guarderia`): 0,55 × 0,95 × 0,92.

### Ludoteca y rincones de juego (18)

#### Juego simbólico y casitas

- **Burro de disfraces con espejo** (`educacion_superior_e_infantil/burro_disfraces`): 1,00 × 0,45 × 1,20 (puede esconder un premio).
- **Teatrillo de guiñol** (`educacion_superior_e_infantil/teatro_guinol`): 1,10 × 0,50 × 1,60 (puede esconder un premio).
- **Cocinita de juguete** (`educacion_superior_e_infantil/cocinita_juguete`): 0,90 × 0,35 × 0,95 (puede esconder un premio).
- **Casita de tela** (`educacion_superior_e_infantil/casita_tela`): 1,10 × 1,10 × 1,25 (puede esconder un premio).
- **Tipi de tela de interior** (`educacion_superior_e_infantil/tipi_interior`): 1,20 × 1,20 × 1,50 (puede esconder un premio).
- **Puf de bolitas en forma de pera** (`educacion_superior_e_infantil/puf_pera`): 0,80 × 0,90 × 0,70.

#### Mesas y estantes de juegos

- **Expositor frontal de cuentos** (`educacion_superior_e_infantil/estanteria_frontal_cuentos`): 0,90 × 0,35 × 0,80 (puede esconder un premio).
- **Isla baja de juegos de mesa** (`educacion_superior_e_infantil/isla_juegos_mesa`): 1,20 × 0,60 × 0,85 (puede esconder un premio).
- **Cubetero inclinado de juguetes** (`educacion_superior_e_infantil/cubetero_juguetes`): 0,85 × 0,40 × 0,65 (puede esconder un premio).
- **Mesa de construcciones** (`educacion_superior_e_infantil/mesa_construcciones`): 1,20 × 0,80 × 0,45 (puede esconder un premio).
- **Mesa de luz** (`educacion_superior_e_infantil/mesa_luz`): 0,80 × 0,60 × 0,50.
- **Mesa de agua y arena** (`educacion_superior_e_infantil/mesa_agua_arena`): 1,00 × 0,65 × 0,55 (puede esconder un premio).
- **Futbolín infantil de ludoteca** (`educacion_superior_e_infantil/futbolin_infantil`): 1,00 × 1,20 × 0,70 (2 variantes; puede esconder un premio).
- **Alfombra de carreteras** (`educacion_superior_e_infantil/alfombra_carreteras`): 1,50 × 1,00 × 0,03 (no corta el paso; puede esconder un premio).

#### Juguetes que se mueven

- **Tobogán pequeño de interior** (`educacion_superior_e_infantil/tobogan_interior`): 0,50 × 1,50 × 0,85.
- **Balancín de interior** (`educacion_superior_e_infantil/balancin_interior`): 0,40 × 0,90 × 0,50.
- **Andador de bebé por el suelo** (`educacion_superior_e_infantil/andador_bebe`): 0,65 × 0,70 × 0,50.
- **Correpasillos tirado por el suelo** (`educacion_superior_e_infantil/correpasillos`): 0,28 × 0,60 × 0,38.

### Aulas de universidad (13)

#### Bancadas, asientos y grada

- **Bancada corrida de aula con asientos abatibles** (`educacion_superior_e_infantil/bancada_grada`): 2,75 × 0,90 × 0,80 (7 variantes; puede esconder un premio).
- **Escalón de la grada** (`educacion_superior_e_infantil/escalon_grada`): 1,20 × 0,90 × 0,16 (no corta el paso).
- **Silla de pala abatible** (`educacion_superior_e_infantil/silla_pala`): 0,60 × 0,72 × 0,85.

#### Tarima, mesa y atril

- **Tarima corrida del aula universitaria** (`educacion_superior_e_infantil/tarima_docente`): 6,00 × 2,50 × 0,18 (3 variantes; no corta el paso).
- **Mesa de cátedra con frontal cerrado** (`educacion_superior_e_infantil/mesa_catedra`): 2,00 × 0,80 × 0,78 (puede esconder un premio).
- **Atril de conferenciante con micrófono** (`educacion_superior_e_infantil/atril_conferenciante`): 0,60 × 0,50 × 1,20 (puede esconder un premio).
- **Armario de equipos audiovisuales** (`educacion_superior_e_infantil/rack_audiovisuales`): 0,60 × 0,60 × 1,00.

#### Pizarras y proyección

- **Pizarra doble de guillotina** (`educacion_superior_e_infantil/pizarra_guillotina`): 3,00 × 0,20 × 2,80 (2 variantes).
- **Pizarra blanca volteable con ruedas** (`educacion_superior_e_infantil/pizarra_ruedas_volteable`): 1,80 × 0,60 × 1,90.
- **Pantalla de proyección bajada** (`educacion_superior_e_infantil/pantalla_proyeccion`): 2,40 × 0,05 × 1,80 (3 variantes; colgado a 1,00 m).
- **Proyector de techo** (`educacion_superior_e_infantil/proyector_techo`): 0,40 × 0,35 × 0,45 (no corta el paso; colgado a 2,20 m).

#### Salón de grados

- **Mesa de tribunal** (`educacion_superior_e_infantil/mesa_tribunal`): 3,00 × 0,80 × 0,76 (2 variantes; puede esconder un premio).
- **Estrado con escalinata** (`educacion_superior_e_infantil/estrado_escalinata`): 5,00 × 3,00 × 0,45.

### Pasillos, estudio y secretaría de facultad (13)

#### Tablones y paneles del pasillo

- **Vitrina de anuncios con puertas de cristal** (`educacion_superior_e_infantil/vitrina_anuncios`): 2,00 × 0,10 × 1,00 (3 variantes; colgado a 0,90 m).
- **Casilleros de correo del profesorado** (`educacion_superior_e_infantil/casilleros_profesorado`): 1,20 × 0,30 × 0,90 (colgado a 0,85 m; puede esconder un premio).
- **Monitor de horarios en brazo de pared** (`educacion_superior_e_infantil/monitor_horarios_brazo`): 0,10 × 1,00 × 0,60 (colgado a 1,75 m).
- **Paneles de pósteres en zigzag** (`educacion_superior_e_infantil/expositor_posteres`): 2,00 × 0,60 × 2,00 (3 variantes).

#### Zonas y cabinas de estudio

- **Mesa alta de trabajo con taburetes** (`educacion_superior_e_infantil/mesa_alta_taburetes`): 2,00 × 1,40 × 1,05.
- **Sofá modular curvo de zona de estudio** (`educacion_superior_e_infantil/sofa_modular_estudio`): 2,80 × 1,40 × 0,80 (puede esconder un premio).
- **Cabina de estudio insonorizada** (`educacion_superior_e_infantil/cabina_estudio_individual`): 1,10 × 1,10 × 2,20 (puede esconder un premio).
- **Box acristalado de estudio en grupo** (`educacion_superior_e_infantil/box_estudio_grupo`): 3,00 × 2,50 × 2,40 (3 variantes).

#### Reprografía, préstamo y secretaría

- **Armario de préstamo de portátiles** (`educacion_superior_e_infantil/armario_prestamo_portatiles`): 1,00 × 0,55 × 1,90 (puede esconder un premio).
- **Máquina de reprografía con tarjeta** (`educacion_superior_e_infantil/maquina_reprografia`): 1,15 × 0,70 × 1,20 (puede esconder un premio).
- **Torre de carga de móviles con casilleros** (`educacion_superior_e_infantil/torre_carga_moviles`): 0,40 × 0,35 × 1,60 (puede esconder un premio).
- **Ventanillas de secretaría** (`educacion_superior_e_infantil/ventanillas_secretaria`): 2,40 × 0,70 × 1,10 (3 variantes).
- **Estantería compacta móvil de depósito** (`educacion_superior_e_infantil/estanteria_compacta_movil`): 2,00 × 3,00 × 2,20 (puede esconder un premio).

### Laboratorios y aulas de prácticas (13)

#### Laboratorio de prácticas

- **Mesa de prácticas de laboratorio** (`educacion_superior_e_infantil/mesa_practicas_laboratorio`): 2,40 × 1,50 × 0,90 (3 variantes; puede esconder un premio).
- **Campana de gases de alumnos** (`educacion_superior_e_infantil/campana_gases_alumnos`): 1,50 × 0,90 × 2,40.
- **Lavaojos de pared** (`educacion_superior_e_infantil/lavaojos_pared`): 0,35 × 0,38 × 0,25 (colgado a 0,90 m).
- **Armario de batas y gafas** (`educacion_superior_e_infantil/armario_batas`): 1,00 × 0,50 × 1,80 (puede esconder un premio).

#### Anatomía y simulación

- **Mesa de disección** (`educacion_superior_e_infantil/mesa_diseccion`): 2,00 × 0,70 × 0,85.
- **Esqueleto de prácticas con ruedas** (`educacion_superior_e_infantil/esqueleto_practicas`): 0,50 × 0,50 × 1,80.
- **Maqueta del cuerpo humano sobre peana** (`educacion_superior_e_infantil/torso_anatomico`): 0,45 × 0,35 × 1,60 (puede esconder un premio).
- **Maniquí de reanimación en el suelo** (`educacion_superior_e_infantil/maniqui_reanimacion`): 0,50 × 1,70 × 0,25 (2 variantes).

#### Informática, dibujo y bellas artes

- **Fila de puestos del aula de informática** (`educacion_superior_e_infantil/fila_puestos_informatica`): 3,20 × 0,75 × 1,15 (3 variantes; puede esconder un premio).
- **Mesa de dibujo inclinada** (`educacion_superior_e_infantil/mesa_dibujo_inclinada`): 1,20 × 0,80 × 1,05 (puede esconder un premio).
- **Caballete de estudio de bellas artes** (`educacion_superior_e_infantil/caballete_bellas_artes`): 0,65 × 0,75 × 1,90.

#### Aulas de música

- **Sillas y atriles de orquesta en arco** (`educacion_superior_e_infantil/atriles_orquesta_arco`): 4,50 × 2,50 × 1,20.
- **Cabina de ensayo musical** (`educacion_superior_e_infantil/cabina_ensayo`): 2,00 × 2,00 × 2,30 (3 variantes; puede esconder un premio).

### Residencia de estudiantes (16)

#### Muebles de la habitación

- **Cama de residencia con cajones** (`educacion_superior_e_infantil/cama_residencia_cajones`): 0,95 × 2,00 × 0,55 (puede esconder un premio).
- **Estante sobre la cabecera** (`educacion_superior_e_infantil/estante_cabecera`): 0,95 × 0,25 × 0,30 (colgado a 1,10 m; puede esconder un premio).
- **Cama alta con escritorio debajo** (`educacion_superior_e_infantil/cama_alta_escritorio`): 1,15 × 2,05 × 1,85 (puede esconder un premio).
- **Mesa de estudio con balda y flexo** (`educacion_superior_e_infantil/mesa_estudio_balda`): 1,20 × 0,60 × 1,20 (puede esconder un premio).
- **Armario empotrado con lavabo** (`educacion_superior_e_infantil/armario_lavabo_residencia`): 1,50 × 0,60 × 2,20 (puede esconder un premio).
- **Minifrigorífico de habitación de estudiante** (`educacion_superior_e_infantil/minifrigorifico_habitacion`): 0,48 × 0,50 × 0,55 (2 variantes; puede esconder un premio).

#### Trastos de la habitación

- **Tendedero de torre en la habitación** (`educacion_superior_e_infantil/tendedero_torre`): 0,70 × 0,65 × 1,40.
- **Maleta abierta en el suelo** (`educacion_superior_e_infantil/maleta_abierta`): 0,50 × 1,30 × 0,25 (puede esconder un premio).
- **Guitarra en su soporte** (`educacion_superior_e_infantil/guitarra_soporte`): 0,42 × 0,35 × 1,05.

#### Cocina compartida y sala de estar

- **Encimera de microondas en fila** (`educacion_superior_e_infantil/microondas_fila`): 2,00 × 0,60 × 1,25 (3 variantes; puede esconder un premio).
- **Sofás en U de la sala de televisión** (`educacion_superior_e_infantil/sofas_u_television`): 3,00 × 2,40 × 0,80 (puede esconder un premio).
- **Televisor de sala común en brazo de pared** (`educacion_superior_e_infantil/televisor_brazo_pared`): 1,20 × 0,25 × 0,70 (colgado a 1,50 m).

#### Comedor de bandejas

- **Dispensador de bandejas y cubiertos** (`educacion_superior_e_infantil/dispensador_bandejas`): 0,80 × 0,65 × 1,30 (puede esconder un premio).
- **Vitrina caliente de autoservicio con pasabandejas** (`educacion_superior_e_infantil/vitrina_caliente_autoservicio`): 1,50 × 1,00 × 1,35 (3 variantes).
- **Caja del comedor universitario** (`educacion_superior_e_infantil/caja_comedor`): 1,00 × 0,70 × 1,00.
- **Cinta de devolución de bandejas** (`educacion_superior_e_infantil/cinta_devolucion_bandejas`): 2,00 × 0,60 × 0,90.

## Sonidos propios (9)

`guarderia_piscina_bolas`, `ludoteca_futbolin`, `residencia_cinta_bandejas`, `residencia_guitarra`, `uni_cabina_ensayo`, `uni_esqueleto_practicas`, `uni_micro_atril`, `uni_pantalla_motor`, `uni_pizarra_guillotina`.

## Sonidos que toma del complemento `comun` (1)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`uni_asiento_abatible`.

## Sonidos que toma del complemento `hogar` (12)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `cisterna`, `interruptor`, `juguetes`, `microondas`, `microondas_fin`, `puerta_cristal`, `puerta_electrodomestico`, `puerta_mueble`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (3)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`colchoneta`, `teclado`, `tiza`.

## Sonidos que toma del complemento `oficina_y_comercio` (2)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cortina`, `fotocopiadora`.

## Sonidos que toma del complemento `calle` (3)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`chorro`, `papel`, `zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (4)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `megafonia`, `taquilla`.

## Sonidos que toma del complemento `juego` (3)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`baliza_musical`, `cremallera`, `llaves`.
