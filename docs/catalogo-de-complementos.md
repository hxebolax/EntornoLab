# Catálogo en línea de complementos

Cómo funciona el catálogo desde el que la aplicación descarga y actualiza complementos, cómo se publica uno propio y cómo se revisa uno de terceros. El formato de un complemento está en [formato-de-complementos.md](formato-de-complementos.md).

## Resumen

- Un complemento es una carpeta de solo datos: fichas JSON, textos, sonidos e imágenes. No lleva código.
- El catálogo es un índice firmado, `catalogo.json`, alojado en GitHub junto a los paquetes `.elabc`.
- Desde Herramientas, Catálogo en línea de complementos, el usuario instala, actualiza, quita o devuelve a la versión anterior cada complemento, uno a uno, sin descargar la aplicación.
- Publicar o corregir un complemento no exige sacar una versión de la aplicación.

Código: `app/services/complementos_en_linea.py` y `app/ui/dialogo_complementos_en_linea.py`. Herramienta: `tools/publicar_complemento.py`.

## Dónde se aloja

En un repositorio aparte: `https://github.com/hxebolax/EntornoLab-complementos`.

```
catalogo.json                 índice firmado
paquetes/<id>-<versión>.elabc paquetes que descarga la aplicación
fuentes/<id>/                 carpeta original de cada complemento, para revisarla
LEEME.md                      cómo proponer un complemento
```

La aplicación lee `https://raw.githubusercontent.com/hxebolax/EntornoLab-complementos/main/catalogo.json`. Las direcciones de los paquetes son relativas al índice.

Por qué un repositorio aparte y no una carpeta del principal ni los recursos de una publicación:

- Publicar un complemento es un «commit» en ese repositorio. No hay que compilar ni publicar la aplicación.
- Un tercero propone su complemento con una petición de cambios («pull request») que añade su carpeta a `fuentes/`. El contenido se revisa en la propia página, fichero a fichero.
- El historial de Git guarda todas las versiones de cada complemento.
- El repositorio de la aplicación no crece con sonidos e imágenes.

Límites: un paquete puede ocupar 200 MB como máximo para la aplicación, pero GitHub rechaza ficheros de más de 100 MB en un repositorio. GitHub tarda hasta cinco minutos en servir un índice recién subido.

La dirección se puede cambiar en `complementos.url_catalogo` de la configuración, para un espejo o para pruebas. El índice debe ir firmado igualmente con la clave de la aplicación.

## Formato de `catalogo.json`

```json
{
	"formato": 1,
	"tipo": "catalogo-complementos",
	"app": "EntornoLab",
	"serie": 12,
	"generado": "2026-11-26T10:00:00+00:00",
	"complementos": [
		{
			"id": "hogar",
			"nombre": "Hogar",
			"descripcion": "Muebles y objetos de una vivienda.",
			"autor": "Héctor J. Benítez Corredera",
			"licencia": "CC BY 4.0",
			"version": "1.2",
			"version_minima_app": "0.1.0",
			"categorias": ["Cocina", "Dormitorio", "Salón"],
			"objetos": 48,
			"tamano": 1843200,
			"url": "paquetes/hogar-1.2.elabc",
			"sha256": "64 caracteres hexadecimales",
			"fecha": "2026-11-20"
		}
	],
	"firma_ed25519": "firma en base64"
}
```

Campos del índice:

- `formato`: versión del formato. La aplicación solo acepta la que entiende.
- `tipo`: siempre `catalogo-complementos`. Impide que un `version.json` firmado se haga pasar por catálogo.
- `app`: `EntornoLab`.
- `serie`: número que sube en cada publicación. La aplicación rechaza un índice con una serie menor que la última que vio.
- `generado`: fecha y hora de la firma.
- `firma_ed25519`: firma de todo el índice, con la misma clave y el mismo método que `version.json`. Ver [actualizaciones.md](actualizaciones.md).

Campos de cada complemento:

- `id`: identificador, igual al de su `complemento.json` y al nombre de su carpeta. Minúsculas, cifras, guion y guion bajo.
- `nombre`, `descripcion`, `autor`, `licencia`: lo que se enseña en la lista y en los detalles.
- `version`: `1.0`, `1.2.3`. Se compara como números.
- `version_minima_app`: versión mínima de EntornoLab que lo entiende. Con una aplicación más antigua aparece como «Necesita una versión más nueva de la aplicación».
- `categorias`: nombres de las categorías de sus objetos; alimentan el filtro del diálogo.
- `objetos`: número de objetos que define.
- `tamano`: tamaño del paquete en bytes.
- `url`: dirección del `.elabc`, absoluta (`https`) o relativa al índice.
- `sha256`: huella del paquete.
- `fecha`: fecha de publicación de esa versión.

Una entrada mal formada se descarta sin invalidar el resto del catálogo.

## Estados en la aplicación

- Disponible: está en el catálogo y no está instalado.
- Hay actualización: el catálogo tiene una versión más nueva que la instalada.
- Al día: la instalada es igual o más nueva.
- Solo en este equipo: está instalado y no figura en el catálogo.
- Necesita una versión más nueva de la aplicación.

Sin conexión se sigue viendo lo instalado.

## De serie y del usuario

- De serie: los complementos que viajan con la aplicación. Los enumera `data\plugins\de_serie.json`, que escribe `tools\publicar_version.py` dentro del ZIP de cada versión. No se pueden desinstalar.
- Del usuario: los instalados desde el catálogo o a mano. Se pueden desinstalar.
- `data\config\complementos.json` apunta lo que se instaló o actualizó desde el catálogo.

Un complemento de serie puede actualizarse por el catálogo sin esperar a una versión de la aplicación. Con «Versión anterior» vuelve a como vino.

Al actualizar la aplicación no se pierden los complementos del usuario, y uno de serie que el catálogo dejó más nuevo no se pisa con el más antiguo del ZIP. La regla completa está en [actualizaciones.md](actualizaciones.md).

Ejecutando desde el código fuente no existe `de_serie.json`: se considera de serie todo lo que no instaló el usuario.

## Qué hace la aplicación al instalar o actualizar

1. Comprueba que el complemento sirve para esta versión de la aplicación.
2. Descarga el paquete a `data\temp\complementos`, comprobando el tamaño y el SHA-256 del índice firmado. Si se corta, continúa donde se quedó.
3. Revisa el paquete: ver «Revisión de seguridad».
4. Guarda la versión instalada en `data\backups\complementos\<id>`.
5. Instala con `app.dominio.catalogo.instalar_complemento`.
6. Valida con `app.dominio.catalogo.validar_complemento`. Si hay errores, vuelve a dejar la versión anterior y lo explica.
7. Apunta la instalación en `data\config\complementos.json` y borra el paquete descargado.

«Actualizar todos» repite estos pasos con cada complemento; el fallo de uno no detiene a los demás.

## Revisión de seguridad

Un complemento es solo datos. La aplicación nunca ejecuta nada de un complemento, y además rechaza el paquete entero si contiene:

- Programas o guiones: `.exe`, `.dll`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.js`, `.py`, `.msi`, `.lnk`, `.jar`, `.sh` y similares. También `.html` y `.svg`, que pueden llevar guiones.
- Programas disfrazados: un fichero que empieza como un ejecutable aunque se llame `.png` o `.wav`.
- Cualquier tipo que no sea `.json`, `.txt`, `.md`, `.wav`, `.ogg`, `.flac`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp` o `.webp`.
- Rutas absolutas, con `..`, con dos puntos o con nombres reservados de Windows.
- Enlaces simbólicos o ficheros cifrados.
- Más de 2000 ficheros, o más de 400 MB al descomprimir.
- Una ficha cuyo `id` no sea el que anuncia el índice. Así un paquete no puede sustituir a otro complemento.

La herramienta de publicación pasa cada paquete por esta misma revisión antes de añadirlo al índice.

## Publicar un complemento propio

Preparación, una sola vez:

1. Cree en GitHub el repositorio público `hxebolax/EntornoLab-complementos` y clónelo, por ejemplo en `D:\Repos\EntornoLab-complementos`.
2. Tenga la clave privada de firma en su sitio. Ver «Claves de firma» en [actualizaciones.md](actualizaciones.md).
3. Opcional: defina la variable de entorno `ENTORNOLAB_CATALOGO` con la carpeta del clon, para no escribir `--catalogo` cada vez.

Cada vez que publique o actualice un complemento:

1. Edite el complemento en `data\plugins\<id>` y suba `version` en su `complemento.json`.
2. Ensaye: `.venv\Scripts\python.exe tools\publicar_complemento.py <id> --catalogo D:\Repos\EntornoLab-complementos --simular`. Valida y empaqueta en una carpeta temporal; no escribe nada.
3. Publique: la misma orden sin `--simular`. Deja el paquete en `paquetes\`, actualiza `catalogo.json`, sube la serie, firma y verifica.
4. Copie la carpeta del complemento a `fuentes\<id>` del clon, para que se pueda revisar.
5. Confirme y suba, con las órdenes que imprime la herramienta: `git add`, `git commit` y `git push`.
6. Pasados unos minutos, abra en la aplicación Herramientas, Catálogo en línea de complementos, y pulse Refrescar.

Otras órdenes:

- Varios a la vez: `tools\publicar_complemento.py hogar ciudad --catalogo ...`.
- Exigir una versión de la aplicación: `--version-minima 0.2.0`.
- Publicar una carpeta que no está en `data\plugins`: escriba su ruta en lugar del identificador.
- Retirar un complemento: `--quitar <id>`. Las copias ya instaladas no se tocan.
- Ver lo publicado: `--listar`.

La herramienta se niega a publicar un complemento con errores de validación, con una versión que no sea mayor que la publicada (salvo `--forzar`), o firmado con una clave que la aplicación no lleva.

## Proponer un complemento de terceros

Para quien quiere aportar un complemento:

1. Cree el complemento siguiendo [formato-de-complementos.md](formato-de-complementos.md) y pruébelo en su EntornoLab: copie la carpeta a `data\plugins\<id>` y compruebe que sus objetos aparecen y suenan.
2. Indique en `complemento.json` el autor y una licencia que permita redistribuirlo. Los sonidos y las imágenes deben ser suyos o tener una licencia compatible; cite su procedencia en un `LEEME.md` dentro del complemento.
3. Abra una petición de cambios en `hxebolax/EntornoLab-complementos` que añada su carpeta en `fuentes\<id>`. No incluya `catalogo.json` ni paquetes: no puede firmarlos.
4. Si no usa Git, abra una incidencia y adjunte el `.elabc`.

Para el autor de EntornoLab, al recibir una propuesta:

1. Lea la ficha y la lista de ficheros en la propia petición. No debe haber nada que no sea JSON, texto, sonido o imagen.
2. Compruebe la licencia y la procedencia de los sonidos y las imágenes.
3. Compruebe que el `id` no coincide con el de un complemento existente de otro autor.
4. Descargue la carpeta y ensaye: `tools\publicar_complemento.py <carpeta> --catalogo ... --simular`. Falla si el complemento no es válido o trae algo que no son datos.
5. Pruébelo en la aplicación: escuche los sonidos, a volumen moderado, y lea las descripciones. Las medidas deben ser realistas y los textos, adecuados para alumnos menores.
6. Acepte la petición, publique con la herramienta y suba los cambios.

Solo el autor puede publicar: la firma del índice es lo que la aplicación acepta, y una petición de cambios no puede falsificarla.

## Privacidad

Abrir el catálogo descarga `catalogo.json`; instalar un complemento descarga su paquete. Son peticiones `GET` a GitHub sin ningún dato del equipo, del profesional ni de los alumnos. El detalle de lo que viaja está en [actualizaciones.md](actualizaciones.md).

El catálogo solo se consulta cuando el usuario abre el diálogo o, si dio permiso para comprobar al arrancar y `complementos.comprobar_actualizaciones` está activa, una vez al día junto a la comprobación de versión. En ese caso solo avisa de cuántos complementos tienen actualización; no instala nada por su cuenta.

## Lo que las pruebas no pueden comprobar

Las pruebas usan un servidor local. Queda por verificar con el repositorio real: la dirección de `raw.githubusercontent.com`, el retraso con que GitHub sirve un índice nuevo y el recorrido completo con un lector de pantalla.
