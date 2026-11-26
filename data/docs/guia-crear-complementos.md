# Guía para crear complementos de objetos

Un complemento es una carpeta con objetos para el catálogo del Estudio: muebles, aparatos, mobiliario urbano u obstáculos. No hace falta saber programar. Esta guía resume las dos formas de hacerlo. La guía paso a paso completa, con un ejemplo entero, está en el código fuente del proyecto: [docs/crear-un-complemento.md en GitHub](https://github.com/hxebolax/EntornoLab/blob/main/docs/crear-un-complemento.md), y la referencia de cada dato, en [docs/formato-de-complementos.md en GitHub](https://github.com/hxebolax/EntornoLab/blob/main/docs/formato-de-complementos.md).

## Qué es un objeto

Un objeto no es un dibujo: es una forma con medidas reales. Lo que importa es:

- cuánto mide de verdad, en metros, con un mínimo, un tamaño normal y un máximo;
- qué forma tiene vista desde arriba: rectángulo, círculo o elipse, ele o polígono;
- si corta el paso y a qué altura está su base. Lo que cuelga no lo detecta el bastón;
- cómo suena al golpearlo y si hace ruido él solo;
- qué se puede hacer con él: abrirlo, sentarse, pulsar un botón;
- si puede esconder un premio.

## Con el asistente del Estudio

1. Elija Herramientas, «Crear un complemento propio».
2. En la pestaña Ficha, escriba el «Nombre del complemento», el «Autor», la «Licencia» y la «Descripción». El «Identificador» se saca solo del nombre.
3. En la pestaña Objetos, pulse «Añadir» para cada objeto. Rellene los grupos «Qué es», «Forma y medidas», «Colocación», «Sonidos y acciones», «Clasificación» y «Símbolo». Ctrl+H explica cada campo y «Escuchar el sonido elegido» lo hace sonar.
4. En la pestaña Guardar, pulse «Comprobar» y corrija lo que diga.
5. Pulse «Guardar en este equipo». El complemento aparece en el catálogo sin reiniciar.
6. Para compartirlo, pulse «Exportar para compartir». Se crea un fichero `.elabc`.

Limitaciones del asistente en esta versión:

- solo ofrece los sonidos que trae el programa. Para un sonido grabado, copie el fichero en la carpeta `sonidos` del complemento (dentro de `data\plugins`) y escriba su nombre en la ficha a mano, como se explica abajo;
- siempre empieza vacío: no abre un complemento ya hecho para editarlo. Para cambiar uno, edite su `complemento.json`.

## A mano, con un editor de texto

1. Dentro de `data\plugins`, cree una carpeta. Su nombre es el identificador: minúsculas sin tildes, cifras, guion y guion bajo. Por ejemplo, `mi-centro`.
2. Dentro, cree el fichero `complemento.json`, guardado en UTF-8. Debe tener `formato`, `id` (igual que la carpeta), `nombre`, `version`, `autor`, `licencia`, `descripcion`, `categorias` y la lista `objetos`.
3. Escriba la ficha de cada objeto: `id`, `nombre`, `categoria`, `etiquetas`, `descripcion`, `forma`, `medidas` (tres números por medida: mínimo, normal y máximo), `colocacion`, `bloquea`, `material` y `sonidos`.
4. Para lo que cuelga, añada `altura_base` y `"detectable_baston": false`.
5. Si quiere sonidos propios, póngalos en la subcarpeta `sonidos` (OGG, WAV o FLAC, cortos y en mono) y nómbrelos como `sonidos/fichero.ogg`. Los del programa se nombran sin extensión, como `golpe/madera` o `fuente/frigorifico`.
6. Si quiere imágenes, póngalas en `imagenes`; y traducciones, en `locales`.
7. Cierre y vuelva a abrir el Estudio, o use Herramientas, «Complementos instalados», «Comprobar».

Errores frecuentes: comillas curvas en lugar de rectas, coma decimal en lugar de punto, una coma después del último elemento de una lista, o el fichero guardado como `complemento.json.txt`.

## Compartir e instalar

- Quien recibe un `.elabc` lo instala en Herramientas, «Complementos instalados», «Añadir desde fichero». No tiene que descomprimir nada.
- Al instalarlo, el programa comprueba que solo trae datos (fichas, imágenes, sonidos y textos) y nunca programas.
- Envíe el `.elabc` junto con los entornos que lo usan. Sin él, los objetos se ven como cajas con sus medidas.
- Para publicarlo en el catálogo en línea, propóngalo en el repositorio del proyecto con la plantilla «Complemento nuevo» de las incidencias.

## Buenas prácticas

- Mida objetos reales.
- Escriba la descripción para quien no ve: qué es y cómo se percibe con el tacto, el bastón o el oído. No dé un color como único dato.
- Use solo sonidos e imágenes que pueda compartir, y diga su licencia.
- No cambie el `id` de un objeto en versiones nuevas: los entornos lo buscan por ese nombre.
- Pruebe cada objeto recorriendo un entorno con auriculares.
