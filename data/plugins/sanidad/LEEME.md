# Sanidad

Centro de salud, hospital, urgencias, farmacia, dentista y rehabilitación: salas de espera, consultas, habitaciones, pasillos con camillas, carros y sillas de ruedas, y los aparatos que suenan.

- Identificador: `sanidad`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo sanidad` a partir de `tools/complementos_serie/sanidad.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (103)

Medidas por defecto: ancho × fondo × alto, en metros.

### Admisión y sala de espera (11)

#### Asientos de espera

- **Bancada de espera de centro de salud** (`sanidad/bancada_espera`): 1,70 × 0,65 × 0,80 (4 variantes; puede esconder un premio).
- **Silla alta de cadera** (`sanidad/silla_alta_cadera`): 0,60 × 0,60 × 1,05.

#### Mostradores de admisión

- **Mostrador de admisión** (`sanidad/mostrador_admision`): 2,40 × 0,80 × 1,10 (2 variantes; puede esconder un premio).
- **Línea de espera de confidencialidad** (`sanidad/linea_confidencialidad`): 1,20 × 0,10 × 0,00 (no corta el paso).

#### Turnos y avisos

- **Quiosco de citas con tarjeta sanitaria** (`sanidad/quiosco_citas`): 0,55 × 0,50 × 1,50.
- **Pantalla de llamada de turnos** (`sanidad/pantalla_turnos`): 1,00 × 0,12 × 0,60 (colgado a 1,90 m).

#### Higiene de manos

- **Dispensador de gel en la pared** (`sanidad/gel_pared`): 0,12 × 0,12 × 0,25 (colgado a 1,00 m).
- **Dispensador de gel de pie con pedal** (`sanidad/gel_pie`): 0,35 × 0,35 × 1,10.

#### Para pasar la espera

- **Revistero de pared de sala de espera** (`sanidad/revistero_pared`): 0,50 × 0,12 × 0,60 (colgado a 0,90 m; puede esconder un premio).
- **Rincón infantil de sala de espera** (`sanidad/rincon_infantil`): 1,20 × 1,20 × 0,55 (puede esconder un premio).
- **Tensiómetro de autoservicio con asiento** (`sanidad/tensiometro_espera`): 0,70 × 1,00 × 1,40.

### Consulta (18)

#### Mesa y asientos de consulta

- **Mesa de consulta médica** (`sanidad/mesa_consulta`): 1,40 × 0,80 × 0,75 (3 variantes; puede esconder un premio).
- **Sillas del paciente y el acompañante** (`sanidad/sillas_paciente`): 1,15 × 0,55 × 0,85.
- **Taburete de médico con ruedas** (`sanidad/taburete_medico`): 0,40 × 0,40 × 0,50.

#### Camillas de exploración

- **Camilla de exploración** (`sanidad/camilla_exploracion`): 0,65 × 1,90 × 0,75 (3 variantes; puede esconder un premio).
- **Sillón ginecológico** (`sanidad/camilla_ginecologica`): 0,90 × 1,70 × 0,90.
- **Escalerilla de dos peldaños** (`sanidad/escalerilla_camilla`): 0,45 × 0,50 × 0,38.
- **Biombo clínico con ruedas** (`sanidad/biombo_clinico`): 1,60 × 0,40 × 1,70 (3 variantes).

#### Aparatos de medida y diagnóstico

- **Báscula con tallímetro** (`sanidad/bascula_tallimetro`): 0,35 × 0,55 × 2,10.
- **Pesabebés sobre su mueble** (`sanidad/pesabebes`): 0,90 × 0,60 × 1,00 (puede esconder un premio).
- **Negatoscopio de pared** (`sanidad/negatoscopio`): 0,80 × 0,10 × 0,50 (3 variantes; colgado a 1,30 m).
- **Estación de diagnóstico de pared** (`sanidad/estacion_diagnostico`): 0,70 × 0,12 × 0,40 (colgado a 1,20 m).
- **Ecógrafo con ruedas** (`sanidad/ecografo`): 0,60 × 0,90 × 1,50.
- **Lámpara de exploración con brazo** (`sanidad/lampara_exploracion`): 0,60 × 0,90 × 1,80.
- **Cabina de audiometría** (`sanidad/cabina_audiometria`): 1,20 × 1,20 × 2,20 (puede esconder un premio).

#### Material y lavado

- **Lavamanos clínico de pared** (`sanidad/lavamanos_clinico`): 0,50 × 0,42 × 0,25 (colgado a 0,65 m).
- **Vitrina de material clínico** (`sanidad/vitrina_material`): 0,80 × 0,40 × 1,70 (2 variantes; puede esconder un premio).
- **Carro de curas** (`sanidad/carro_curas`): 0,60 × 0,45 × 0,90 (puede esconder un premio).
- **Frigorífico de vacunas** (`sanidad/frigorifico_vacunas`): 0,60 × 0,60 × 0,85 (2 variantes; puede esconder un premio).

### Hospitalización (14)

#### Camas y cunas

- **Cama de hospital articulada** (`sanidad/cama_hospital`): 1,00 × 2,20 × 1,00 (2 variantes; puede esconder un premio).
- **Cuna hospitalaria** (`sanidad/cuna_hospital`): 0,75 × 1,50 × 1,45 (puede esconder un premio).
- **Incubadora** (`sanidad/incubadora`): 0,65 × 1,10 × 1,40.

#### Muebles de la habitación

- **Mesilla hospitalaria con ruedas** (`sanidad/mesilla_hospitalaria`): 0,45 × 0,45 × 0,85 (puede esconder un premio).
- **Mesa de cama con ruedas** (`sanidad/mesa_cama`): 0,80 × 0,42 × 0,90.
- **Sillón de acompañante reclinable** (`sanidad/sillon_acompanante`): 0,75 × 0,85 × 1,10 (2 variantes).
- **Armario de habitación de hospital** (`sanidad/armario_habitacion`): 0,50 × 0,55 × 1,95 (2 variantes; puede esconder un premio).
- **Cortina separadora entre camas** (`sanidad/cortina_cama`): 2,00 × 0,08 × 2,00.
- **Televisor de habitación en brazo de pared** (`sanidad/tv_hospital`): 0,60 × 0,40 × 0,40 (colgado a 1,70 m).

#### Aparatos de cabecera

- **Gotero con ruedas** (`sanidad/portasueros`): 0,55 × 0,55 × 2,00.
- **Columna de bombas de infusión** (`sanidad/bomba_infusion`): 0,60 × 0,60 × 1,80.
- **Monitor de constantes en su pie** (`sanidad/monitor_constantes`): 0,50 × 0,50 × 1,35.
- **Cabecero técnico de pared** (`sanidad/cabecero_tecnico`): 1,80 × 0,12 × 0,30 (colgado a 1,45 m).

#### Control de planta

- **Control de enfermería** (`sanidad/control_enfermeria`): 3,50 × 2,00 × 1,10 (puede esconder un premio).

### Pasillos y equipos móviles (18)

#### Sillas de ruedas, andadores y muletas

- **Silla de ruedas aparcada** (`sanidad/silla_ruedas_abierta`): 0,65 × 1,05 × 0,95.
- **Silla de ruedas plegada** (`sanidad/silla_ruedas_plegada`): 0,30 × 1,05 × 0,95.
- **Sillas de ruedas de préstamo en fila** (`sanidad/sillas_ruedas_prestamo`): 0,70 × 2,50 × 1,00 (3 variantes).
- **Andador** (`sanidad/andador`): 0,60 × 0,60 × 0,90 (2 variantes).
- **Muletas apoyadas en la pared** (`sanidad/muletas_pared`): 0,30 × 0,25 × 1,20.

#### Camillas y carros

- **Camilla de traslado en el pasillo** (`sanidad/camilla_traslado`): 0,70 × 2,10 × 0,90.
- **Carro de medicación** (`sanidad/carro_medicacion`): 0,75 × 0,55 × 1,10 (puede esconder un premio).
- **Carro de lencería** (`sanidad/carro_lenceria`): 1,20 × 0,60 × 1,70 (puede esconder un premio).
- **Carro de comidas de planta** (`sanidad/carro_comidas`): 0,80 × 0,75 × 1,50 (2 variantes; puede esconder un premio).
- **Carro de paradas** (`sanidad/carro_paradas`): 0,70 × 0,60 × 1,20 (puede esconder un premio).
- **Bombona de oxígeno en su carro** (`sanidad/bombona_oxigeno`): 0,30 × 0,30 × 1,40.

#### Paredes y puertas del pasillo

- **Desfibrilador en vitrina de pared** (`sanidad/desfibrilador_pared`): 0,40 × 0,20 × 0,40 (colgado a 1,10 m; puede esconder un premio).
- **Pasamanos de pasillo de hospital** (`sanidad/pasamanos_pasillo`): 3,00 × 0,10 × 0,15 (3 variantes; colgado a 0,80 m).
- **Puerta de vaivén de hospital** (`sanidad/puerta_vaiven`): 1,60 × 0,08 × 2,10.

#### Limpieza y residuos

- **Carro de ropa sucia con saco** (`sanidad/carro_ropa_sucia`): 0,50 × 0,50 × 0,90 (puede esconder un premio).
- **Carro de limpieza hospitalario** (`sanidad/carro_limpieza_hospital`): 0,60 × 1,20 × 1,10 (puede esconder un premio).
- **Contenedor de residuos sanitarios** (`sanidad/contenedor_sanitario`): 0,40 × 0,40 × 0,65 (3 variantes).
- **Lavamanos quirúrgico de acero** (`sanidad/lavamanos_quirurgico`): 1,60 × 0,55 × 1,10.

### Urgencias, radiología y extracciones (12)

#### Triaje y boxes

- **Mostrador de triaje** (`sanidad/mostrador_triaje`): 1,60 × 0,70 × 0,85 (puede esconder un premio).
- **Sillón de triaje** (`sanidad/silla_triaje`): 0,65 × 0,70 × 1,10.
- **Box de urgencias con cortina** (`sanidad/box_cortina`): 2,50 × 2,80 × 2,00 (puede esconder un premio).
- **Camilla de observación** (`sanidad/camilla_observacion`): 0,80 × 2,10 × 1,00 (puede esconder un premio).

#### Radiología

- **Mesa de rayos X** (`sanidad/mesa_rayos`): 0,80 × 2,20 × 0,80.
- **Tubo de rayos colgado del techo** (`sanidad/tubo_rayos_techo`): 0,50 × 0,60 × 0,50 (colgado a 1,50 m).
- **Soporte mural de rayos** (`sanidad/bucky_mural`): 0,65 × 0,40 × 2,10.
- **Mampara plomada de rayos** (`sanidad/mampara_plomada`): 1,20 × 0,30 × 2,00.
- **Tubo de resonancia magnética** (`sanidad/resonancia`): 2,30 × 3,80 × 2,20 (2 variantes).
- **Mamógrafo** (`sanidad/mamografo`): 0,70 × 1,20 × 2,00.

#### Extracciones y tratamientos

- **Sillón de extracciones** (`sanidad/sillon_extracciones`): 0,90 × 0,80 × 1,10.
- **Puesto de hemodiálisis** (`sanidad/puesto_dialisis`): 1,50 × 1,90 × 1,40.

### Farmacia (8)

#### Mostradores de farmacia

- **Mostrador de farmacia** (`sanidad/mostrador_farmacia`): 2,00 × 0,60 × 0,95 (3 variantes; puede esconder un premio).
- **Puesto de atención de farmacia en isla** (`sanidad/puesto_farmacia_isla`): 0,70 × 0,60 × 0,95 (puede esconder un premio).

#### Expositores y rebotica

- **Cajoneras de medicamentos** (`sanidad/cajoneras_medicamentos`): 1,20 × 1,00 × 2,00 (3 variantes; puede esconder un premio).
- **Góndola de parafarmacia** (`sanidad/gondola_parafarmacia`): 1,20 × 0,60 × 1,40 (puede esconder un premio).

#### Servicios al cliente

- **Báscula de farmacia con voz** (`sanidad/bascula_farmacia`): 0,50 × 0,60 × 2,20.
- **Punto de recogida de medicamentos caducados** (`sanidad/punto_sigre`): 0,45 × 0,45 × 1,20 (puede esconder un premio).

#### Fachada

- **Cruz de farmacia en la fachada** (`sanidad/cruz_farmacia`): 0,15 × 0,90 × 0,90 (3 variantes; colgado a 2,30 m).
- **Ventanilla de guardia de farmacia** (`sanidad/dispensador_guardia`): 0,50 × 0,25 × 0,40 (colgado a 0,90 m; puede esconder un premio).

### Dentista (5)

#### Sillón y muebles

- **Sillón dental** (`sanidad/sillon_dental`): 1,50 × 2,00 × 1,40.
- **Escupidera del dentista** (`sanidad/escupidera_dental`): 0,35 × 0,35 × 0,90.
- **Mueble clínico de dentista** (`sanidad/mueble_clinico_dental`): 2,00 × 0,50 × 0,90 (3 variantes; puede esconder un premio).

#### Rayos del dentista

- **Aparato de rayos de pared del dentista** (`sanidad/rayos_pared_dental`): 0,30 × 0,50 × 0,40 (2 variantes; colgado a 1,20 m).
- **Ortopantomógrafo** (`sanidad/ortopantomografo`): 1,00 × 1,20 × 2,20.

### Rehabilitación y fisioterapia (17)

#### Marcha y equilibrio

- **Paralelas de marcha** (`sanidad/paralelas_marcha`): 0,80 × 3,00 × 0,90 (3 variantes).
- **Escalera y rampa de ejercicios** (`sanidad/escalera_rampa`): 0,90 × 3,20 × 1,40.
- **Plato de equilibrio en el suelo** (`sanidad/platos_equilibrio`): 0,40 × 0,40 × 0,08 (no corta el paso).
- **Pista de marcha con vallas bajas** (`sanidad/pista_obstaculos_marcha`): 0,80 × 3,00 × 0,15.

#### Camillas de tratamiento

- **Camilla de fisioterapia** (`sanidad/camilla_fisioterapia`): 0,70 × 1,95 × 0,70 (puede esconder un premio).
- **Camilla ancha de tratamiento neurológico** (`sanidad/camilla_bobath`): 2,00 × 2,00 × 0,50 (2 variantes).
- **Jaula de poleoterapia** (`sanidad/jaula_poleoterapia`): 2,00 × 2,00 × 2,00 (puede esconder un premio).

#### Aparatos de ejercicio

- **Bicicleta estática clínica** (`sanidad/bicicleta_clinica`): 0,60 × 1,10 × 1,30.
- **Pedalier de rehabilitación** (`sanidad/pedalier`): 0,45 × 0,50 × 0,30.
- **Rueda de hombro en la pared** (`sanidad/rueda_hombro`): 0,90 × 0,30 × 0,90 (colgado a 0,90 m).
- **Banco de cuádriceps** (`sanidad/banco_cuadriceps`): 1,00 × 1,20 × 1,20.
- **Mesa de manos** (`sanidad/mesa_manos`): 1,20 × 0,70 × 0,75 (puede esconder un premio).

#### Material y aparatos sueltos

- **Espejo de postura con ruedas** (`sanidad/espejo_postura`): 0,70 × 0,50 × 1,80.
- **Cuñas y rulos de fisioterapia** (`sanidad/cunas_rulos`): 0,60 × 0,60 × 0,30 (puede esconder un premio).
- **Pelota grande de fisioterapia** (`sanidad/pelota_fisioterapia`): 0,65 × 0,65 × 0,65 (3 variantes).
- **Baño de parafina** (`sanidad/bano_parafina`): 0,50 × 0,35 × 0,90.
- **Carro de electroterapia** (`sanidad/carro_electroterapia`): 0,50 × 0,50 × 1,00.

## Sonidos propios (13)

`sanidad_bascula_farmacia`, `sanidad_bomba_infusion`, `sanidad_cama_motor`, `sanidad_carro_clinico`, `sanidad_desfibrilador_alarma`, `sanidad_gel`, `sanidad_llamada_turno`, `sanidad_monitor_cardiaco`, `sanidad_rayos_disparo`, `sanidad_resonancia`, `sanidad_tensiometro`, `sanidad_timbre_enfermera`, `sanidad_turbina_dental`.

## Sonidos que toma del complemento `comun` (1)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`sanidad_oxigeno_burbujeo`.

## Sonidos que toma del complemento `hogar` (9)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `interruptor`, `juguetes`, `microondas_fin`, `puerta_electrodomestico`, `puerta_mueble`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (3)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`balon`, `colchoneta`, `teclado`.

## Sonidos que toma del complemento `oficina_y_comercio` (3)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_registradora`, `cortina`, `silla_ruedas`.

## Sonidos que toma del complemento `calle` (4)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`chorro`, `papel`, `trampilla_buzon`, `zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (3)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `interfono`, `megafonia`.

## Sonidos que toma del complemento `juego` (2)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`llaves`, `monedas`.
