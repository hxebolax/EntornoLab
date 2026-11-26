# Complementos de objetos

En esta carpeta están los complementos de EntornoLab: los objetos con los que el profesional amuebla los entornos que construye (viviendas, colegios, hospitales, tiendas, calles, parques, estaciones) para acercarlos al lugar real.

## Qué es un complemento

- Una carpeta con un fichero `complemento.json` y, si hacen falta, sonidos (`sonidos/`), imágenes (`imagenes/`) y traducciones (`locales/<idioma>.json`).
- Solo datos. No lleva código y el programa no ejecuta nada de él: instalar el de otra persona no supone un riesgo.
- Sus objetos no son dibujos. Cada uno es una forma (rectángulo, círculo, ele o polígono) con su huella en planta y sus medidas reales en metros, su altura, su material y su comportamiento. El alumno, al recorrer el entorno como un audiojuego, se los encuentra: chocan, hay que rodearlos, suenan al golpearlos según su material, algunos tienen sonido propio y otros se pueden abrir, encender, pulsar o esconder un premio.
- Cada objeto declara un tamaño mínimo, uno por defecto y uno máximo, y variantes con nombre (cama de 90, de 135, de 150). Con eso el programa ajusta el objeto al hueco y nunca lo deja más grande que la habitación.

- Cada objeto está clasificado: categoría y subcategoría dentro de su complemento, función (asiento, mesa, barrera…), lugares y estancias donde es habitual, clase de obstáculo (a ras de suelo, bajo, a media altura, alto, en voladizo, a la altura de la cabeza), riesgos (se mueve, es temporal, es un desnivel…) y frecuencia. Con eso se busca y se filtra en el catálogo del Estudio.

## Complementos de serie

| Complemento | Objetos | Sonidos propios | Contenido |
| --- | --- | --- | --- |
| [`hogar`](hogar/LEEME.md) · Hogar | 108 | 20 | Salón, cocina, dormitorio, baño, entrada y pasillo, trastos y obstáculos de casa, lavadero, plancha y costura, terraza, balcón y jardín, habitación infantil. |
| [`colegio`](colegio/LEEME.md) · Colegio | 73 | 9 | Aula, biblioteca e informática, comedor, gimnasio y patio, música, pasillos y zonas comunes, aula de plástica, aseos de alumnos, aula de apoyo y sala sensorial. |
| [`oficina_y_comercio`](oficina_y_comercio/LEEME.md) · Oficina y comercio | 66 | 12 | Oficina, recepción y sala de espera, máquinas, supermercado, tienda, accesos y elementos del edificio. |
| [`calle`](calle/LEEME.md) · Calle | 96 | 10 | Mobiliario urbano, semáforos y señales, contenedores y papeleras, árboles, jardineras y fuentes, vehículos aparcados, terrazas, quioscos y comercio, obras y obstáculos temporales, suelo, bordillos y servicios, plazas y monumentos. |
| [`transporte`](transporte/LEEME.md) · Transporte | 64 | 14 | Parada de autobús y de taxi, vestíbulo de estación, tornos y accesos, andén, información y ayuda, a bordo: autobús, tranvía, metro y tren. |
| [`juego`](juego/LEEME.md) · Juego | 95 | 35 | Escondites de premios, cosas que suenan, lugares de fantasía, metas y señales, juegos de adultos, llaves, puertas y acertijos, personajes y animales, obstáculos de aventura. |
| [`sanidad`](sanidad/LEEME.md) · Sanidad | 103 | 13 | Admisión y sala de espera, consulta, hospitalización, pasillos y equipos móviles, urgencias, radiología y extracciones, farmacia, dentista, rehabilitación y fisioterapia. |
| [`residencia_y_ayudas_tecnicas`](residencia_y_ayudas_tecnicas/LEEME.md) · Residencia y ayudas técnicas | 100 | 10 | Sala de estar y comedor de residencia, habitación de residencia y control, terapia ocupacional y gimnasia, aseo y baño adaptados, cocina y casa adaptadas, grúas, rampas y elevadores, señalización táctil y sonora, aparatos para ciegos y sordos y perro guía. |
| [`hosteleria`](hosteleria/LEEME.md) · Hostelería | 128 | 10 | Barra y cafetería, sala del bar y juegos, restaurante, terraza, vestíbulo y recepción de hotel, habitación de hotel, pasillos y desayunos de hotel, salón de eventos. |
| [`comunidad_y_edificio`](comunidad_y_edificio/LEEME.md) · Comunidad y edificio | 122 | 9 | Portal y conserjería, escalera, rellanos y ascensor, cuartos de instalaciones, basuras y bicicletas, garaje, trastero, azotea y patio de luces, piscina y zonas de recreo de la urbanización. |
| [`vehiculos_y_aparcamiento`](vehiculos_y_aparcamiento/LEEME.md) · Vehículos y aparcamiento | 92 | 11 | Coches, furgonetas y caravanas, camiones y autobuses, emergencias y limpieza, bicicletas, motos y triciclos, remolques y contenedores de obra, plazas, topes y suelo del aparcamiento, barreras, pago y control, gasolinera, lavado y aire. |
| [`cultura_y_ocio`](cultura_y_ocio/LEEME.md) · Cultura y ocio | 126 | 12 | Museo y exposiciones, cine, teatro y auditorio, biblioteca, sala de conciertos y discoteca, bolera y recreativos, centro cívico. |
| [`deporte`](deporte/LEEME.md) · Deporte | 143 | 10 | Pistas y polideportivo, atletismo, gimnasia y combate, sala de máquinas, piscina deportiva, vestuarios, gradas y accesos. |
| [`parque_y_naturaleza`](parque_y_naturaleza/LEEME.md) · Parque y naturaleza | 168 | 10 | Parque infantil, biosaludables y zona canina, merendero y mobiliario de parque, senderos, rocas y relieve, agua, árboles, setos y plantas, jardín y huerto, playa. |
| [`administracion_y_servicios`](administracion_y_servicios/LEEME.md) · Administración y servicios | 135 | 11 | Atención al ciudadano y edificios oficiales, banco y correos, juzgado y salón de plenos, lugares de culto, tanatorio y cementerio, peluquería y estética, lavandería y tintorería, otros servicios de barrio. |
| [`tiendas`](tiendas/LEEME.md) · Tiendas y centro comercial | 122 | 15 | Panadería y pastelería, frutería y mercado, carnicería, pescadería y charcutería, ferretería, ropa y zapatería, librería, estanco, óptica y joyería, floristería, electrónica, juguetería y bazar, centro comercial y puerta de la tienda. |
| [`trabajo_y_taller`](trabajo_y_taller/LEEME.md) · Trabajo y taller | 153 | 16 | Taller mecánico, carpintería y taller de metal, almacén y logística, fábrica, laboratorio, cocina profesional, obra por dentro. |
| [`educacion_superior_e_infantil`](educacion_superior_e_infantil/LEEME.md) · Guardería, universidad y residencia de estudiantes | 107 | 9 | Guardería y escuela infantil, ludoteca y rincones de juego, aulas de universidad, pasillos, estudio y secretaría de facultad, laboratorios y aulas de prácticas, residencia de estudiantes. |
| [`obstaculos_temporales`](obstaculos_temporales/LEEME.md) · Obstáculos temporales | 140 | 11 | Obras en la acera y la calzada, mudanzas y repartos, basura, limpieza y agua, comercio y hostelería que invaden el paso, mercadillo, fiestas y carreras, tormenta, poda y cosas caídas, personas, animales y carritos parados, dentro de un edificio. |
| [`estaciones_y_aeropuerto`](estaciones_y_aeropuerto/LEEME.md) · Estaciones, aeropuerto y puerto | 117 | 9 | Vestíbulo de gran estación, andenes de tren, metro, tranvía y estación de autobuses, aeropuerto: facturación y controles, aeropuerto: embarque y llegadas, puerto. |

En total, 2258 objetos. Cada carpeta tiene su `LEEME.md` con la lista completa y las medidas por defecto, y [`CATALOGO.md`](CATALOGO.md) es el índice de todos: complemento, categoría, subcategoría y cada objeto con sus medidas y una línea de descripción.

Además está [`comun`](comun/LEEME.md), un complemento sin objetos con los 33 sonidos que comparten varios complementos (así cada sonido ocupa una sola vez) y con los nombres visibles de la clasificación en español y en inglés. Los demás dependen de él.

Autor: Héctor J. Benítez Corredera. Licencia de los datos (fichas, traducciones, miniaturas y sonidos): CC BY 4.0, Creative Commons Atribución 4.0 Internacional (<https://creativecommons.org/licenses/by/4.0/deed.es>). Se pueden copiar, adaptar y redistribuir citando al autor.

Las miniaturas de `imagenes/` son la huella en planta de cada objeto, con sus proporciones reales, su color, su letra, un triángulo que marca el frente y una barra de escala. Un objeto traslúcido no corta el paso; uno con doble contorno está colgado.

Los complementos de serie se generan con `tools/generar_complementos.py` a partir de `tools/complementos_serie/`: no los edite aquí si quiere que el cambio dure. Para hacer el suyo, cree una carpeta nueva.

## Cómo añadir un complemento

Hay tres maneras:

1. **Copiar su carpeta aquí**, dentro de `data/plugins`, con el mismo nombre que su identificador, y reiniciar el Estudio.
2. **Instalar un fichero `.elabc`** (un ZIP con el complemento) desde el Estudio, en Herramientas, «Complementos instalados», con el botón «Añadir desde fichero».
3. **Desde el catálogo en línea**, en Herramientas, Catálogo en línea de complementos (ver `docs/catalogo-de-complementos.md`).

Un complemento se puede desactivar sin borrarlo: sus objetos dejan de salir en el catálogo, pero los ya colocados siguen funcionando. Si un entorno usa un complemento que no está instalado, se abre igual: sus objetos se conservan como cajas con sus medidas.

## Cómo crear uno

- Guía paso a paso, sin programar, con un ejemplo completo: `docs/crear-un-complemento.md`.
- Referencia del formato, clave por clave: `docs/formato-de-complementos.md`.
- Cómo publicarlo en el catálogo en línea: `docs/catalogo-de-complementos.md`.
