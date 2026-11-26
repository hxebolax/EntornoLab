# Común

Complemento sin objetos. Lleva dos cosas que comparten los demás complementos de serie:

- Los **sonidos** que usan dos o más complementos. En lugar de copiar el mismo fichero en cada uno, lo citan como `comun:<nombre>.flac` y declaran `"depende_de": ["comun"]` en su ficha.
- Los **nombres visibles de la clasificación** de objetos (funciones, lugares, estancias, clases de obstáculo, riesgos y frecuencias), en español en `complemento.json` y en inglés en `locales/en.json`. Para traducirlos a otro idioma basta añadir `locales/<idioma>.json`.

- Identificador: `comun`
- Versión: 1.0.0
- Autor: Héctor J. Benítez Corredera
- Licencia: CC BY 4.0 (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)

No lo desinstale: los complementos que dependen de él seguirían funcionando, pero sin esos sonidos. Se genera con `tools/generar_complementos.py`; los sonidos están sintetizados por ordenador (`tools/complementos_serie/sonidos*.py`).

## Sonidos compartidos (33)

- `abejas_colmena`: juego, parque_y_naturaleza.
- `actuador_ayuda_tecnica`: colegio, oficina_y_comercio, residencia_y_ayudas_tecnicas.
- `amarras_crujido`: estaciones_y_aeropuerto, parque_y_naturaleza.
- `bandeja_seguridad`: estaciones_y_aeropuerto, trabajo_y_taller.
- `barbacoa_brasas`: comunidad_y_edificio, hogar.
- `barra_abatible_clac`: juego, residencia_y_ayudas_tecnicas.
- `bici_volante_giro`: deporte, juego.
- `brasas_castanera`: hogar, obstaculos_temporales.
- `caldera_comunitaria`: comunidad_y_edificio, hogar.
- `calle_tiovivo_organillo`: calle, juego.
- `carrusel_giro`: calle, parque_y_naturaleza.
- `chapuzon`: deporte, hogar.
- `columpio_chirrido`: colegio, hogar, parque_y_naturaleza.
- `compresor_azotea`: comunidad_y_edificio, hogar.
- `ducha`: administracion_y_servicios, comunidad_y_edificio, deporte, parque_y_naturaleza, residencia_y_ayudas_tecnicas, trabajo_y_taller, vehiculos_y_aparcamiento.
- `estufa_terraza_gas`: hogar, hosteleria.
- `goteo_pescaderia`: juego, tiendas.
- `hielo_cubitos`: hosteleria, parque_y_naturaleza.
- `plancha_vapor`: administracion_y_servicios, trabajo_y_taller.
- `playa_olas`: juego, parque_y_naturaleza.
- `polea_obra`: obstaculos_temporales, trabajo_y_taller.
- `polea_tendedero`: comunidad_y_edificio, hogar.
- `portamaletas_ruedas`: hosteleria, transporte.
- `prensa_industrial`: oficina_y_comercio, trabajo_y_taller.
- `puerta_pesada_muelle`: comunidad_y_edificio, trabajo_y_taller.
- `sanidad_oxigeno_burbujeo`: sanidad, trabajo_y_taller.
- `uni_asiento_abatible`: educacion_superior_e_infantil, transporte.
- `vajilla_tintineo`: hogar, hosteleria, trabajo_y_taller, transporte.
- `vapor_bano_turco`: deporte, trabajo_y_taller.
- `vehiculos_cadena`: juego, vehiculos_y_aparcamiento.
- `vehiculos_puerta_coche`: tiendas, vehiculos_y_aparcamiento.
- `vehiculos_ralenti_diesel`: transporte, vehiculos_y_aparcamiento.
- `zumbador_alarma`: trabajo_y_taller, transporte.
