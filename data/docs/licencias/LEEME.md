# Licencias de EntornoLab y de lo que viaja con él

EntornoLab, Copyright © 2026 Héctor J. Benítez Corredera.

EntornoLab es software libre con la **Licencia Pública General de GNU, versión 3 o posterior** (GPL-3.0-or-later), con un **permiso adicional** (sección 7 de la GPL) para combinarlo con la biblioteca BASS. El texto completo y el permiso están en `LICENSE` (en la raíz del código fuente) o `LICENSE.txt` (junto a los ejecutables, en la versión compilada). Se distribuye **sin ninguna garantía**.

Las bibliotecas y los datos de terceros de esta lista conservan cada uno su propia licencia; la GPL de EntornoLab no los cubre. Sus textos están en esta misma carpeta.

## Aviso importante sobre BASS: solo uso no comercial

El motor de sonido «3D con BASS» usa `bass.dll`, de Un4seen Developments. **BASS no es software libre y es gratuita únicamente para uso no comercial.** Si alguien quisiera usar o distribuir EntornoLab con fines comerciales, tiene dos caminos:

1. comprar a Un4seen la licencia comercial de BASS (<https://www.un4seen.com>), o
2. **prescindir de BASS**: elegir cualquier otro motor de sonido en las preferencias y borrar `bass.dll`. El resto del programa funciona igual; el motor de serie es OpenAL Soft, que sí es libre.

Dónde está `bass.dll`:

- versión compilada: `lib\basskit\data\dlls\x64\bass.dll`;
- desde el código fuente: `.venv\Lib\site-packages\basskit\data\dlls\x64\bass.dll` (la instala la rueda de `__pip__`).

Sin ese fichero, el motor BASS aparece en las preferencias como no disponible y, si estaba elegido, el programa usa OpenAL.

## Lista de componentes

| Componente | Para qué se usa | Licencia | Texto |
|---|---|---|---|
| **BASS 2.4** (`bass.dll`), Un4seen Developments Ltd. | Motor de sonido «3D con BASS» (elegible, no es el de serie) | Propietaria: gratuita solo para uso no comercial | [BASS.txt](BASS.txt) (apartado «Licence») |
| **basskit** (recortado: solo la API nativa de BASS) | Acceso a `bass.dll` desde Python | MIT (solo el código Python) | [basskit.txt](basskit.txt) |
| **OpenAL Soft 1.25.2** (`data/bin/openal/soft_oal.dll`) | Motor de sonido binaural, el de serie | GNU LGPL 2 o posterior | [OpenAL-Soft-LGPL.txt](OpenAL-Soft-LGPL.txt) |
| **Perfiles HRTF** (`data/bin/openal/hrtf/*.mhr`) | «Cabezas» del sonido binaural | MIT KEMAR: uso libre citando a los autores. SADIE II: Apache 2.0 | [HRTF.txt](HRTF.txt) |
| **pygame-ce** (con SDL2, SDL_mixer, SDL_ttf, SDL_image, FreeType y otras) | Reproductor del alumno, mandos, motor de sonido «estéreo» | GNU LGPL 2.1 o posterior; sus bibliotecas, las suyas (zlib, FTL…) | [pygame-ce.txt](pygame-ce.txt), [LGPL-2.1.txt](LGPL-2.1.txt) |
| **wxPython** (con wxWidgets) | Estudio del profesional | LGPL 2 o posterior con la excepción de wxWindows 3.1 | [wxPython.txt](wxPython.txt) |
| **NumPy** | Mezcla y síntesis de sonido | BSD de 3 cláusulas (y componentes 0BSD, MIT, Zlib, CC0) | [numpy.txt](numpy.txt) |
| **sounddevice** y **PortAudio** | Salida de sonido del motor «clásico» | MIT las dos | [sounddevice-PortAudio.txt](sounddevice-PortAudio.txt) |
| **soundfile** y **libsndfile** | Leer y escribir ficheros de sonido | BSD de 3 cláusulas; libsndfile, GNU LGPL 2.1 o posterior | [soundfile-libsndfile.txt](soundfile-libsndfile.txt), [LGPL-2.1.txt](LGPL-2.1.txt) |
| **accessible_output2**, libloader y platform_utils | Voz y braille por el lector de pantalla | MIT; las bibliotecas cliente de cada lector, de su fabricante | [accessible_output2.txt](accessible_output2.txt) |
| **cryptography** (con OpenSSL) | Cifrado de las fichas de alumnos | Apache 2.0 o BSD de 3 cláusulas | [cryptography.txt](cryptography.txt) |
| **Python-Markdown** | Manual y ayuda en HTML | BSD de 3 cláusulas | [markdown.txt](markdown.txt) |
| **pywin32** | Acceso a Windows (SAPI, cifrado DPAPI) | PSF | [pywin32.txt](pywin32.txt) |
| **comtypes**, **cffi** y **pycparser** | Bibliotecas de apoyo de las anteriores | MIT, MIT-0 y BSD de 3 cláusulas | [comtypes-cffi-pycparser.txt](comtypes-cffi-pycparser.txt) |
| **Python** | Intérprete y biblioteca estándar (versión compilada) | PSF-2.0 | [Python.txt](Python.txt) |
| **Grabaciones del paquete de sonidos «Grabado»** (`data/sounds/grabado`): Fantozzi, Corsica_S, Kenney, rubberduck, BigSoundBank.com y Freesound | Pasos, golpes, puertas, agua, tráfico y ambientes del paquete de sonidos «Grabado» (elegible, no es el de serie) | CC0 1.0 (dominio público) todas | [sonidos-grabado.txt](sonidos-grabado.txt); sonido a sonido, en `data/sounds/grabado/CREDITOS.txt` |
| Bibliotecas de ejecución de **Microsoft Visual C++** (`vcruntime140*.dll`, `msvcp140*.dll`) | Las necesitan Python y las bibliotecas anteriores | Redistribuibles según los términos de Microsoft Visual Studio | — |

Los sonidos de los paquetes «por defecto» y «Natural» de `data/sounds` están generados por procedimiento para EntornoLab, sin grabaciones de terceros, y van con su misma licencia. El paquete «Grabado» está hecho con grabaciones de terceros dedicadas al dominio público (CC0 1.0): no hay ninguna con cláusula «no comercial» o «sin obra derivada», ni de procedencia desconocida. Cada paquete lleva su `CREDITOS.txt`, y el de «Grabado» dice de cada sonido el fichero original, la colección, el autor, la licencia y la página de origen.

## Bibliotecas con LGPL: se pueden sustituir

OpenAL Soft, libsndfile, SDL (dentro de pygame-ce) y wxWidgets van como **ficheros DLL sueltos**, nunca incrustados en los ejecutables. Quien lo desee puede sustituirlos por otra compilación compatible copiándola encima con el mismo nombre; es el derecho que da la LGPL. Dónde está el código fuente de cada una:

- OpenAL Soft: <https://github.com/kcat/openal-soft>
- libsndfile: <https://github.com/libsndfile/libsndfile>
- pygame-ce: <https://github.com/pygame-community/pygame-ce> · SDL: <https://github.com/libsdl-org/SDL>
- wxPython: <https://github.com/wxWidgets/Phoenix> · wxWidgets: <https://github.com/wxWidgets/wxWidgets>

## Código fuente de EntornoLab

La GPL da derecho a recibir el código fuente completo de EntornoLab. El de BASS no forma parte de él: lo permite el permiso adicional de `LICENSE`, y Un4seen no lo publica.

## De dónde salen estos textos

Cada fichero es el texto de licencia que trae el propio paquete instalado (su carpeta `licenses` o su fichero `LICENSE`), con una cabecera de tres o cuatro líneas que dice a qué versión corresponde. `BASS.txt` es, byte a byte, el `bass.txt` de la rueda de basskit. Al actualizar una dependencia hay que volver a copiar el suyo.
