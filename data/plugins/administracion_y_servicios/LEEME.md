# Administración y servicios

Donde se hacen gestiones: ayuntamiento y oficina de atención, comisaría, banco, correos, juzgado, iglesia y otros lugares de culto, tanatorio y cementerio, peluquería, lavandería y servicios de barrio.

- Identificador: `administracion_y_servicios`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.

## Licencia

Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia CC BY 4.0: se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor (Héctor J. Benítez Corredera). Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.

## Cómo se regenera

Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo administracion_y_servicios` a partir de `tools/complementos_serie/administracion_y_servicios.py`. Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.

## Objetos (135)

Medidas por defecto: ancho × fondo × alto, en metros.

### Atención al ciudadano y edificios oficiales (23)

#### Mostradores y ventanillas

- **Mostrador de atención con puestos** (`administracion_y_servicios/mostrador_atencion_puestos`): 3,60 × 1,00 × 1,10 (4 variantes).
- **Puesto de atención sentado con tramo accesible** (`administracion_y_servicios/puesto_atencion_sentado`): 1,80 × 1,60 × 0,80 (puede esconder un premio).
- **Ventanilla con cristal y pasadocumentos** (`administracion_y_servicios/ventanilla_cristal`): 1,20 × 0,45 × 2,10 (2 variantes; puede esconder un premio).
- **Mostrador de denuncias de comisaría** (`administracion_y_servicios/mostrador_denuncias`): 2,40 × 1,60 × 1,30.
- **Cabina de atención reservada** (`administracion_y_servicios/cabina_atencion`): 2,00 × 2,00 × 2,30 (puede esconder un premio).
- **Puesto de huellas y foto del DNI** (`administracion_y_servicios/puesto_huellas_dni`): 1,40 × 0,80 × 0,76.

#### Turnos y espera

- **Gestor de turnos con tique y voz** (`administracion_y_servicios/gestor_turnos`): 0,50 × 0,45 × 1,45.
- **Bancada de espera de chapa perforada** (`administracion_y_servicios/bancada_espera_chapa`): 2,40 × 0,68 × 0,82 (4 variantes).
- **Banco de espera anclado al suelo** (`administracion_y_servicios/banco_espera_anclado`): 1,80 × 0,45 × 0,45.
- **Línea de espere su turno en el suelo** (`administracion_y_servicios/linea_espera_suelo`): 1,20 × 0,10 × 0,01 (no corta el paso).

#### Impresos y máquinas de trámites

- **Mesa de rellenar impresos de pie** (`administracion_y_servicios/mesa_impresos`): 1,40 × 0,60 × 1,10 (puede esconder un premio).
- **Expositor de formularios de pared** (`administracion_y_servicios/expositor_formularios`): 0,80 × 0,15 × 0,90 (colgado a 0,90 m; puede esconder un premio).
- **Máquina de autoservicio de certificados** (`administracion_y_servicios/maquina_certificados`): 0,65 × 0,55 × 1,60.
- **Fotomatón con cortina** (`administracion_y_servicios/fotomaton`): 1,60 × 0,85 × 1,95 (puede esconder un premio).
- **Buzón de sugerencias sobre pedestal** (`administracion_y_servicios/buzon_sugerencias`): 0,35 × 0,30 × 1,15 (puede esconder un premio).

#### Vestíbulo oficial

- **Directorio de plantas en atril** (`administracion_y_servicios/directorio_plantas`): 0,90 × 0,45 × 1,05.
- **Mástiles con banderas del vestíbulo** (`administracion_y_servicios/mastiles_banderas`): 1,40 × 0,45 × 2,60 (3 variantes).
- **Tablón de edictos en vitrina** (`administracion_y_servicios/vitrina_edictos`): 1,20 × 0,10 × 1,00 (colgado a 1,00 m).
- **Mesa electoral con urna** (`administracion_y_servicios/mesa_electoral_urna`): 2,00 × 0,70 × 1,15 (puede esconder un premio).
- **Cabina de votación** (`administracion_y_servicios/cabina_votacion`): 0,90 × 0,90 × 2,00 (puede esconder un premio).

#### Control de entrada y seguridad

- **Escáner de bolsos con cinta** (`administracion_y_servicios/escaner_bolsos`): 2,60 × 0,90 × 1,30 (puede esconder un premio).
- **Mesa de bandejas del control** (`administracion_y_servicios/mesa_bandejas_control`): 1,20 × 0,60 × 0,85 (puede esconder un premio).
- **Garita de seguridad** (`administracion_y_servicios/garita_seguridad`): 1,50 × 1,50 × 2,40.

### Banco y correos (19)

#### Caja y atención del banco

- **Puesto de caja de banco con mampara** (`administracion_y_servicios/puesto_caja_banco`): 1,50 × 0,80 × 1,40 (2 variantes; puede esconder un premio).
- **Mesa de gestor con sillas de confidente** (`administracion_y_servicios/mesa_gestor_banco`): 1,60 × 1,60 × 0,76 (puede esconder un premio).
- **Mostrador de bienvenida de banco** (`administracion_y_servicios/atril_bienvenida_banco`): 0,90 × 0,55 × 1,10.

#### Cajeros y autoservicio del banco

- **Batería de cajeros de vestíbulo** (`administracion_y_servicios/bateria_cajeros`): 2,60 × 0,80 × 2,00 (3 variantes).
- **Cajero adaptado bajo con guía de voz** (`administracion_y_servicios/cajero_adaptado_voz`): 0,65 × 0,60 × 1,25.
- **Actualizador de libretas** (`administracion_y_servicios/actualizador_libretas`): 0,50 × 0,50 × 1,45.
- **Buzón de ingresos** (`administracion_y_servicios/buzon_ingresos`): 0,45 × 0,15 × 0,40 (colgado a 1,00 m; puede esconder un premio).
- **Máquina de ingreso de monedas** (`administracion_y_servicios/maquina_ingreso_monedas`): 0,60 × 0,65 × 1,35.

#### Seguridad y cajas fuertes

- **Puerta de esclusa de seguridad** (`administracion_y_servicios/esclusa_seguridad`): 1,20 × 1,30 × 2,30.
- **Caja fuerte grande de banco** (`administracion_y_servicios/caja_fuerte_banco`): 1,00 × 0,80 × 1,80 (puede esconder un premio).
- **Cajas de seguridad de alquiler** (`administracion_y_servicios/cajas_alquiler`): 2,00 × 0,55 × 2,00 (puede esconder un premio).

#### Oficina de correos

- **Mostrador de correos con báscula** (`administracion_y_servicios/mostrador_correos`): 2,00 × 0,80 × 1,00 (2 variantes; puede esconder un premio).
- **Casilleros de apartados de correos** (`administracion_y_servicios/apartados_correos`): 1,50 × 0,40 × 1,80 (puede esconder un premio).
- **Buzón interior de la oficina de correos** (`administracion_y_servicios/buzon_correos_interior`): 0,70 × 0,45 × 1,25 (puede esconder un premio).
- **Mesa de embalaje con cintas** (`administracion_y_servicios/mesa_embalaje`): 1,50 × 0,70 × 0,95 (puede esconder un premio).
- **Expositor de sobres y cajas** (`administracion_y_servicios/expositor_embalajes`): 1,00 × 0,45 × 1,70 (puede esconder un premio).

#### Paquetería y reparto

- **Taquilla inteligente de paquetería** (`administracion_y_servicios/taquilla_paqueteria`): 2,00 × 0,60 × 2,00 (3 variantes; puede esconder un premio).
- **Carro de reparto de cartero** (`administracion_y_servicios/carro_cartero`): 0,50 × 0,60 × 1,10 (puede esconder un premio).
- **Saca de correo** (`administracion_y_servicios/saca_correo`): 0,60 × 0,60 × 0,80 (puede esconder un premio).

### Juzgado y salón de plenos (13)

#### Estrado y partes

- **Estrado del juez** (`administracion_y_servicios/estrado_juez`): 4,00 × 1,80 × 1,30 (3 variantes; puede esconder un premio).
- **Mesa de letrados** (`administracion_y_servicios/mesa_letrados`): 2,40 × 0,70 × 0,78 (puede esconder un premio).
- **Mesa del secretario judicial** (`administracion_y_servicios/mesa_secretario_judicial`): 1,60 × 1,40 × 0,75 (puede esconder un premio).
- **Estrado del testigo con micrófono** (`administracion_y_servicios/estrado_testigo`): 0,90 × 0,80 × 1,05.
- **Banquillo de los acusados** (`administracion_y_servicios/banquillo_acusados`): 1,80 × 0,45 × 0,85.
- **Cabina blindada de acusados** (`administracion_y_servicios/cabina_acusados_blindada`): 3,00 × 1,50 × 2,40 (puede esconder un premio).

#### Público y sala

- **Barandilla del público con portezuela** (`administracion_y_servicios/barandilla_publico`): 4,00 × 0,10 × 0,95.
- **Banco del público de sala de vistas** (`administracion_y_servicios/banco_publico_sala`): 2,50 × 0,55 × 0,90 (3 variantes).
- **Cabina de intérprete** (`administracion_y_servicios/cabina_interprete`): 1,70 × 1,70 × 2,10 (puede esconder un premio).
- **Carro de expedientes** (`administracion_y_servicios/carro_expedientes`): 0,50 × 1,00 × 1,00 (puede esconder un premio).

#### Salón de plenos

- **Escaños curvos del salón de plenos** (`administracion_y_servicios/escanos_plenos`): 5,00 × 2,40 × 0,85 (3 variantes; puede esconder un premio).
- **Tribuna de oradores** (`administracion_y_servicios/tribuna_oradores`): 1,20 × 1,00 × 1,35.
- **Mesa de presidencia sobre estrado curvo** (`administracion_y_servicios/mesa_presidencia_pleno`): 4,00 × 2,20 × 1,00 (puede esconder un premio).

### Lugares de culto (31)

#### Bancos y asientos de culto

- **Banco de iglesia con reclinatorio** (`administracion_y_servicios/banco_iglesia`): 2,50 × 0,95 × 0,90 (4 variantes; puede esconder un premio).
- **Reclinatorio individual** (`administracion_y_servicios/reclinatorio_individual`): 0,60 × 0,60 × 0,90.
- **Filas de sillas unidas de templo** (`administracion_y_servicios/filas_sillas_unidas_templo`): 3,00 × 0,55 × 0,88 (3 variantes).

#### Altar y presbiterio

- **Gradas del presbiterio** (`administracion_y_servicios/gradas_presbiterio`): 5,00 × 0,90 × 0,30 (no corta el paso).
- **Altar de iglesia** (`administracion_y_servicios/altar_mayor`): 2,20 × 0,90 × 1,00 (puede esconder un premio).
- **Ambón** (`administracion_y_servicios/ambon`): 0,70 × 0,60 × 1,25.
- **Sede del celebrante** (`administracion_y_servicios/sede_celebrante`): 1,80 × 0,65 × 1,40.
- **Sagrario sobre columna** (`administracion_y_servicios/sagrario`): 0,50 × 0,50 × 1,60 (puede esconder un premio).
- **Cirio pascual en candelero** (`administracion_y_servicios/cirio_pascual`): 0,30 × 0,30 × 1,70.
- **Comulgatorio** (`administracion_y_servicios/comulgatorio`): 4,00 × 0,40 × 0,80.
- **Púlpito con escalera** (`administracion_y_servicios/pulpito_escalera`): 1,50 × 2,20 × 3,00.
- **Pila bautismal** (`administracion_y_servicios/pila_bautismal`): 1,00 × 1,00 × 1,00 (puede esconder un premio).

#### Capillas y devoción

- **Pila de agua bendita en voladizo** (`administracion_y_servicios/pila_agua_bendita`): 0,40 × 0,30 × 0,25 (colgado a 1,00 m).
- **Confesionario** (`administracion_y_servicios/confesionario`): 2,00 × 1,10 × 2,30 (puede esconder un premio).
- **Lampadario de velas votivas** (`administracion_y_servicios/lampadario_velas`): 0,80 × 0,50 × 1,00 (puede esconder un premio).
- **Cepillo de limosnas** (`administracion_y_servicios/cepillo_limosnas`): 0,25 × 0,25 × 1,00 (puede esconder un premio).
- **Imagen sobre peana** (`administracion_y_servicios/imagen_peana`): 0,70 × 0,60 × 2,10.
- **Verja de capilla** (`administracion_y_servicios/verja_capilla`): 3,00 × 0,08 × 2,80.
- **Lápida en el suelo de la iglesia** (`administracion_y_servicios/lapida_suelo`): 0,90 × 2,00 × 0,02 (no corta el paso).
- **Paso procesional sobre caballetes** (`administracion_y_servicios/paso_procesional`): 2,40 × 4,00 × 2,60 (3 variantes; puede esconder un premio).

#### Coro, órgano y campanas

- **Sillería del coro** (`administracion_y_servicios/silleria_coro`): 5,00 × 3,00 × 1,50 (puede esconder un premio).
- **Órgano de iglesia** (`administracion_y_servicios/organo_tubos`): 3,00 × 1,80 × 4,50.
- **Armonio** (`administracion_y_servicios/armonio`): 1,10 × 0,50 × 1,00 (puede esconder un premio).
- **Facistol** (`administracion_y_servicios/facistol`): 0,90 × 0,90 × 1,80.
- **Cuerda de la campana** (`administracion_y_servicios/cuerda_campana`): 0,08 × 0,08 × 3,00 (colgado a 1,10 m).

#### Mezquita, sinagoga y otros templos

- **Alfombras de oración de la mezquita** (`administracion_y_servicios/alfombras_oracion`): 4,00 × 3,00 × 0,02 (no corta el paso).
- **Mueble de calzado de la entrada** (`administracion_y_servicios/mueble_calzado_mezquita`): 1,50 × 0,35 × 1,20 (puede esconder un premio).
- **Fuente de abluciones** (`administracion_y_servicios/fuente_abluciones`): 2,40 × 0,90 × 0,90.
- **Mimbar** (`administracion_y_servicios/mimbar`): 0,90 × 3,00 × 3,00.
- **Bimá** (`administracion_y_servicios/bima`): 2,50 × 2,50 × 1,30 (puede esconder un premio).
- **Atril transparente de predicación** (`administracion_y_servicios/atril_metacrilato_templo`): 0,60 × 0,45 × 1,15.

### Tanatorio y cementerio (14)

#### Sala de velatorio

- **Sofás de sala de velatorio** (`administracion_y_servicios/sofas_velatorio`): 3,00 × 2,40 × 0,80 (puede esconder un premio).
- **Túmulo con féretro tras cristal** (`administracion_y_servicios/tumulo_cristal`): 2,60 × 0,15 × 2,30.
- **Libro de firmas en atril** (`administracion_y_servicios/libro_firmas_atril`): 0,50 × 0,45 × 1,10 (puede esconder un premio).
- **Corona de flores en caballete** (`administracion_y_servicios/corona_caballete`): 0,90 × 0,70 × 1,60 (puede esconder un premio).
- **Banco acolchado de pasillo de tanatorio** (`administracion_y_servicios/banco_tanatorio`): 1,60 × 0,50 × 0,45.
- **Carro de féretros** (`administracion_y_servicios/carro_feretros`): 0,65 × 2,00 × 0,70 (puede esconder un premio).

#### Sepulturas

- **Bloque de nichos** (`administracion_y_servicios/nichos_pared`): 8,00 × 2,60 × 3,20 (3 variantes).
- **Columbario** (`administracion_y_servicios/columbario`): 2,00 × 0,50 × 2,00 (puede esconder un premio).
- **Tumba con lápida de cabecera** (`administracion_y_servicios/tumba_tierra`): 1,00 × 2,20 × 0,90 (2 variantes; puede esconder un premio).
- **Panteón** (`administracion_y_servicios/panteon`): 3,00 × 3,50 × 4,00 (puede esconder un premio).
- **Cruz de piedra sobre gradas** (`administracion_y_servicios/cruz_piedra`): 1,60 × 1,60 × 4,00.

#### Servicios del cementerio

- **Escalera rodante de nichos** (`administracion_y_servicios/escalera_nichos`): 0,80 × 1,80 × 2,50.
- **Fuente de cementerio con regaderas** (`administracion_y_servicios/fuente_cementerio`): 0,90 × 0,60 × 1,20 (puede esconder un premio).
- **Jaula de flores secas** (`administracion_y_servicios/contenedor_flores_secas`): 1,50 × 1,00 × 1,10 (puede esconder un premio).

### Peluquería y estética (14)

#### Sillones de peluquería

- **Sillón de peluquería hidráulico** (`administracion_y_servicios/sillon_peluqueria`): 0,65 × 1,00 × 0,95.
- **Sillón de barbero** (`administracion_y_servicios/sillon_barbero`): 0,70 × 1,15 × 1,15.
- **Sillón infantil de peluquería con forma de coche** (`administracion_y_servicios/sillon_infantil_coche`): 0,60 × 1,00 × 0,95.

#### Lavado y secado del pelo

- **Lavacabezas con sillón** (`administracion_y_servicios/lavacabezas`): 0,65 × 1,25 × 1,00.
- **Secador de casco de pie** (`administracion_y_servicios/secador_casco`): 0,60 × 0,70 × 1,60.

#### Muebles de peluquería

- **Tocador de peluquería con repisa en voladizo** (`administracion_y_servicios/tocador_peluqueria`): 0,90 × 0,30 × 1,20 (colgado a 0,80 m; puede esconder un premio).
- **Carrito auxiliar de peluquería** (`administracion_y_servicios/carrito_peluqueria`): 0,40 × 0,45 × 0,90 (puede esconder un premio).
- **Recepción de peluquería** (`administracion_y_servicios/recepcion_peluqueria`): 1,20 × 1,20 × 1,10 (puede esconder un premio).
- **Expositor de productos de peluquería** (`administracion_y_servicios/expositor_productos_peluqueria`): 0,90 × 0,20 × 1,00 (colgado a 1,00 m; puede esconder un premio).
- **Poste de barbero giratorio** (`administracion_y_servicios/poste_barbero`): 0,22 × 0,30 × 0,70 (colgado a 1,50 m).

#### Estética

- **Camilla de cabina de estética** (`administracion_y_servicios/camilla_estetica`): 0,70 × 1,90 × 0,75 (puede esconder un premio).
- **Mesa de manicura** (`administracion_y_servicios/mesa_manicura`): 1,10 × 0,45 × 0,75 (puede esconder un premio).
- **Sillón de pedicura con pileta** (`administracion_y_servicios/sillon_pedicura`): 0,85 × 1,50 × 1,25.
- **Cabina vertical de rayos UVA** (`administracion_y_servicios/cabina_rayos_uva`): 1,10 × 1,10 × 2,25 (puede esconder un premio).

### Lavandería y tintorería (11)

#### Máquinas de lavandería

- **Lavadora industrial de carga frontal** (`administracion_y_servicios/lavadora_industrial`): 0,90 × 1,00 × 1,40 (3 variantes; puede esconder un premio).
- **Secadora industrial apilada** (`administracion_y_servicios/secadora_industrial_apilada`): 0,80 × 1,10 × 1,95 (puede esconder un premio).
- **Central de pago de lavandería** (`administracion_y_servicios/central_pago_lavanderia`): 0,45 × 0,25 × 0,70 (colgado a 0,90 m).
- **Dispensador de detergente** (`administracion_y_servicios/dispensador_detergente`): 0,45 × 0,40 × 1,50 (puede esconder un premio).
- **Calandra de planchar sábanas** (`administracion_y_servicios/calandra_planchado`): 2,20 × 0,80 × 1,10.

#### Muebles de lavandería

- **Mesa de doblar ropa** (`administracion_y_servicios/mesa_doblar_ropa`): 1,80 × 0,80 × 0,90 (puede esconder un premio).
- **Carro de ropa con ruedas** (`administracion_y_servicios/carro_ropa_lavanderia`): 0,55 × 0,80 × 0,85 (2 variantes; puede esconder un premio).
- **Banco de espera de lavandería** (`administracion_y_servicios/banco_lavanderia`): 2,00 × 0,40 × 0,45 (puede esconder un premio).

#### Tintorería

- **Mostrador de tintorería** (`administracion_y_servicios/mostrador_tintoreria`): 1,60 × 0,65 × 0,95 (puede esconder un premio).
- **Transportador aéreo de tintorería** (`administracion_y_servicios/transportador_tintoreria`): 1,50 × 4,00 × 1,20 (colgado a 1,00 m; puede esconder un premio).
- **Prensa de planchar de vapor** (`administracion_y_servicios/prensa_vapor`): 1,30 × 0,90 × 1,20.

### Otros servicios de barrio (10)

#### Locutorio y lotería

- **Cabina de locutorio** (`administracion_y_servicios/cabina_locutorio`): 0,90 × 1,00 × 2,10 (puede esconder un premio).
- **Puestos de internet con separadores** (`administracion_y_servicios/puestos_internet_locutorio`): 3,00 × 0,75 × 1,20 (3 variantes; puede esconder un premio).
- **Teléfono público de pared con orejeras** (`administracion_y_servicios/telefono_pared_orejeras`): 0,70 × 0,40 × 0,90 (colgado a 1,00 m).
- **Repisa de rellenar boletos** (`administracion_y_servicios/repisa_boletos`): 1,20 × 0,30 × 0,25 (colgado a 1,00 m; puede esconder un premio).
- **Mostrador de lotería con terminal** (`administracion_y_servicios/terminal_loteria`): 1,40 × 0,60 × 1,10 (puede esconder un premio).

#### Zapatero y copistería

- **Banco de finisaje de zapatero** (`administracion_y_servicios/maquina_zapatero`): 1,50 × 0,70 × 1,40.
- **Mostrador de zapatero con duplicadora de llaves** (`administracion_y_servicios/mostrador_zapatero_llaves`): 1,50 × 1,20 × 1,00 (puede esconder un premio).
- **Mostrador de copistería** (`administracion_y_servicios/mostrador_copisteria`): 2,20 × 0,70 × 1,00 (puede esconder un premio).
- **Guillotina de papel de pie** (`administracion_y_servicios/guillotina_copisteria`): 0,90 × 0,90 × 1,40.
- **Plóter de planos** (`administracion_y_servicios/plotter_planos`): 1,80 × 0,70 × 1,15 (puede esconder un premio).

## Sonidos propios (11)

`escaner_bolsos_cinta`, `esclusa_cerrojo`, `guillotina_papel`, `lavadora_industrial`, `lijadora_zapatero`, `organo_iglesia`, `secador_casco`, `secadora_industrial`, `sello_tampon`, `transportador_perchas`, `turno_voz_admin`.

## Sonidos que toma del complemento `comun` (2)

Este complemento depende de `comun`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`ducha`, `plancha_vapor`.

## Sonidos que toma del complemento `hogar` (7)

Este complemento depende de `hogar`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`cajon`, `interruptor`, `puerta_electrodomestico`, `puerta_mueble`, `sentarse`, `tapa_contenedor`, `valla_obra`.

## Sonidos que toma del complemento `colegio` (2)

Este complemento depende de `colegio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`impresora`, `teclado`.

## Sonidos que toma del complemento `oficina_y_comercio` (5)

Este complemento depende de `oficina_y_comercio`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_registradora`, `cortina`, `fotocopiadora`, `garrafa`, `silla_ruedas`.

## Sonidos que toma del complemento `calle` (4)

Este complemento depende de `calle`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`chorro`, `papel`, `trampilla_buzon`, `zumbido_recarga`.

## Sonidos que toma del complemento `transporte` (6)

Este complemento depende de `transporte`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`bip_validacion`, `carrito`, `interfono`, `taquilla`, `teclas_cajero`, `timbre_bici`.

## Sonidos que toma del complemento `juego` (6)

Este complemento depende de `juego`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.

`caja_fuerte`, `campana`, `cremallera`, `deseo`, `llaves`, `monedas`.
