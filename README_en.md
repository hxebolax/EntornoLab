# EntornoLab

[Leer en español](README.md)

**Learn places before you visit them.** EntornoLab is a portable, offline Windows application that lets blind and low-vision people get to know a building or a street before they go there. The instructor builds the place in the **Studio** and the student walks through it in **Play**, a first-person audio game with 3D sound, using the keyboard or a game controller.

- Version: 0.1.0 (first public release).
- Author: Héctor J. Benítez Corredera.
- License: GPL 3 or later, with an additional permission for the BASS library.
- Languages: Spanish and English.

EntornoLab is an educational and training tool. It is not a medical device, it does not diagnose or treat anything, and it does not replace learning in the real place with an instructor.

## Contents

- [For users](#for-users)
  - [What it is and who it is for](#what-it-is-and-who-it-is-for)
  - [What you will find](#what-you-will-find)
  - [Add-ons and online catalog](#add-ons-and-online-catalog)
  - [Sound packs](#sound-packs)
  - [Requirements](#requirements)
  - [Download and installation](#download-and-installation)
  - [Getting started](#getting-started)
  - [Updates](#updates)
  - [Privacy](#privacy)
  - [Accessibility](#accessibility)
  - [Scientific basis, with its limits](#scientific-basis-with-its-limits)
  - [Important notice](#important-notice)
  - [Project status](#project-status)
  - [Help and bug reports](#help-and-bug-reports)
  - [Buy me a coffee](#buy-me-a-coffee)
  - [Languages](#languages)
- [For developers](#for-developers)
  - [The project in numbers](#the-project-in-numbers)
  - [Project tree](#project-tree)
  - [Architecture in brief](#architecture-in-brief)
  - [Development requirements](#development-requirements)
  - [Setting up the environment](#setting-up-the-environment)
  - [Running from source](#running-from-source)
  - [Tests and style](#tests-and-style)
  - [Building with cx_Freeze](#building-with-cx_freeze)
  - [Verifying and packaging](#verifying-and-packaging)
  - [Publishing a signed release and the catalog](#publishing-a-signed-release-and-the-catalog)
  - [Creating add-ons and sound packs](#creating-add-ons-and-sound-packs)
  - [Translating into another language](#translating-into-another-language)
  - [Code conventions](#code-conventions)
  - [Map of the technical documentation](#map-of-the-technical-documentation)
- [License](#license)
- [Credits and acknowledgments](#credits-and-acknowledgments)
- [How to cite](#how-to-cite)

## For users

### What it is and who it is for

EntornoLab has two programs that share the same engine:

- **The Studio** (`EntornoLab.exe`), for the instructor. It can be used entirely with the keyboard and a screen reader, and it also has a visual map for those who work with a mouse.
- **Play** (`EntornoLabJugar.exe`), for the student. Everything is spoken aloud and everything is done with the keyboard or with an Xbox or PlayStation controller.

It is designed for:

- **rehabilitation and orientation and mobility (O&M) instructors**, blind or sighted, who prepare the learning of a specific place: a home, a school, a workplace, a station or the route to a stop;
- **blind and low-vision students of any age**, with messages in a child, teen or adult style;
- **families**, who support at home the work the instructor prepares;
- **centers**, which can use the same folder on several computers and supervise several students over the local network.

### What you will find

#### In the Studio

- **Build indoor areas**: levels, rooms by measurements or attached to another room, spaces of any shape, doors, doorways, windows and entrances, freestanding walls, stairs, ramps and elevators, sound sources, landmarks and surface zones (rugs, tactile paving).
- **Build outdoor areas**: streets with roadway and sidewalks, intersections, crosswalks with or without an accessible pedestrian signal, push button and refuge island, buildings, blocks and stops.
- **Three ways to place things**: by measurements, relative to what is already there (attached, against a wall, in a corner, next to another item) or by walking through the environment with Play and placing things where you are.
- **Add-on objects**, with search, sorting, automatic scaling, a warning for overhanging obstacles and a furniture suggestion to furnish a space.
- **Check** the environment, **measure** between items, a **visual map** with a grid and the **complete description** of the place in text.
- **Import** from OpenStreetMap (without inventing anything the map does not say), from DXF and SVG plans, a background image to trace, and GPX routes.
- **Export** the package for the student, the description as text, Markdown or accessible HTML, the visual map, the **tactile map with a braille legend**, GeoJSON and DXF.
- **Student records**, password-protected and encrypted, with step length calculation, work list, rewards, export and complete deletion.
- **Live supervision**, on the same computer or over the local network, encrypted: position, what the student hears, events, messages, hints, live rewards, repositioning, pausing and marking moments.
- **Sessions, reports and log**: step-by-step replay of the route, session reports, comparison, progress, exam and real-world assessment, and a log to record the tests in the physical place.

#### In Play

- First-person walkthrough with **3D sound**: footsteps that depend on the floor, bumps and scrapes that depend on the material, the echo of each place, doors, stairs, elevators, traffic lights and cars.
- **Fourteen help features** the student can ask for: where am I, look in four directions, around, list of what is nearby, discovered places, compass, sound cane, echo, goal and hint, among others.
- **Tutorial**, «Learn the sounds» and «Practice the controls».
- **Remappable** keys and buttons, several ways to move, adjustable turning and step length, distances in meters or in steps.
- For low vision: level map, high contrast, large text and black screen.

#### Activities and exams

- **22 activity types**: games (treasure hunt, the errand runner, bring out the treasures, hide and seek, follow the guide, the explorer, chained hints, cross with the beep), practice (free exploration, guided tour, routes, reverse route, return to the origin, alternative route, locate a space, room familiarization, follow a shoreline) and exams (routes, shortest way out, pointing, distances and reconstruction).
- **Hidden rewards** placed by hand, inside objects, spread out automatically or placed while walking through, with a message and recorded audio.
- Goals, allowed help features with a usage limit, help fading levels, styles, time trial and «the prankster», which moves rewards around.
- Exams without hints, with a stopping rule and a seed to repeat them exactly. The student is never told whether an answer is right.

### Add-ons and online catalog

Objects (furniture, appliances, street furniture, obstacles) come in **add-ons**. EntornoLab includes several by default (home, school, office and shop, street, transport and play), and the complete list of their objects is in `data/plugins/CATALOGO.md` when the release includes it. From the Studio you can:

- enable, disable, add and remove add-ons;
- install and update add-ons from the **online catalog**, which is signed and verified: only data is accepted, never programs;
- create your own add-ons with a wizard and share them in an `.elabc` file.

### Sound packs

Play includes three sound packs that can be switched instantly: **Synthetic** (the default one, clean and very easy to tell apart), **Natural** (acoustic instruments and physical models) and **Recorded** (real public-domain recordings, partial). You can create your own packs by copying files into a folder; the details are in the manual.

### Requirements

- 64-bit Windows 10 or 11.
- Stereo headphones (it also works with speakers, with less precision).
- Recommended screen reader: NVDA, JAWS or another compatible one. Without one, Play speaks with the Windows voice, unless another speech output, or none, is chosen.
- Xbox or PlayStation controller, optional.
- It does not need the Internet or administrator permissions.

### Download and installation

1. Go to the [releases page](https://github.com/hxebolax/EntornoLab/releases) and download the ZIP of the latest version (`EntornoLab_v` followed by the number).
2. Unzip it into a folder you have write permission for, for example in Documents or on a USB drive. Do not put it in «Program Files».
3. Inside are `EntornoLab.exe` (Studio), `EntornoLabJugar.exe` (Play) and the `data` folder, where everything is saved.

To uninstall it, delete the folder. To make a backup, copy the whole folder.

### Getting started

- **Instructor**: open `EntornoLab.exe`, press F1 for the manual and follow the [quick guide for instructors](data/docs/en/guia-rapida-profesional.md): from zero to the first session in ten steps.
- **Student**: open `EntornoLabJugar.exe`, choose your alias and start with the «Tutorial». There is a [quick guide to Play](data/docs/en/guia-rapida-alumno.md), with a version for children.
- All the user documentation: [manual](data/docs/en/manual.md), [keyboard shortcuts](data/docs/en/teclas.md), [frequently asked questions](data/docs/en/preguntas-frecuentes.md) and [what's new](data/docs/en/novedades.md).

### Updates

The Studio can check for new versions in Help, «Check for updates». By default it does not connect on its own: the first time, it asks whether it may check at startup, at most once a day. Releases are signed and verified before they are installed; if the new version does not start, it automatically goes back to the previous one. Your environments, records, sessions and preferences are never touched.

### Privacy

- No accounts, no cloud and no telemetry. Everything is saved in the program's `data` folder.
- The personal data in the records (real name, notes and observations) is encrypted with AES-256-GCM and an instructor password that is not stored anywhere.
- There are Internet connections only if you ask for them: updates and add-ons (GitHub) and OpenStreetMap import. Supervision uses the computer itself or the local network, encrypted.
- The logs do not store students' names, aliases, notes or texts.
- Each student has «Export data» and «Delete completely».

### Accessibility

- The Studio uses standard Windows controls with labels, access keys, help for each control (Ctrl+H), column-by-column reading of lists and progress announcements for long tasks.
- Nothing depends only on color or on the mouse: the visual map is an extra.
- Play says everything it shows, can be used entirely with the keyboard or a controller, sends messages to the braille display and has high contrast, large text and black screen.
- The manual (F1) can be navigated by headings, and the list of keyboard shortcuts (Ctrl+F1) is ordered by window.

### Scientific basis, with its limits

EntornoLab is inspired by studies on learning places with virtual sound environments, above all those on the game AbES (Connors, Chrastil, Sánchez and Merabet, 2014): blind adults who trained on a real building with an audio video game did as well as with directed instruction on routes from one point to another, and did clearly better at finding the shortest way out. Other studies point in the same direction with teenagers, children, street crossing and maps with sound.

The limits, just as clearly: these are small studies (from 4 to 17 participants) on a single building; what is learned is the trained place, not a general skill; it has not been shown to work for whole neighborhoods, to last for months, or that the controller is equivalent to the keyboard. EntornoLab gathers what those studies point to as most useful, but it does not promise results. The section «Scientific basis and its limits» of the [manual](data/docs/en/manual.md) summarizes it with figures.

### Important notice

- EntornoLab **is not a medical device**. It does not diagnose or treat anything.
- It **does not replace** learning in the real place with an orientation and mobility instructor.
- **It is not for deciding whether a real crossing is safe.** On the street, what you hear and the instructor have the final say.
- Scores and reports describe what happened in the simulator, not competence in the real place.

### Project status

Version 0.1.0, the first public release.

- **Checked automatically**: more than a hundred test files cover the environment model, the engine, activities, tracking, supervision, import and export, updates, add-ons, configuration, documentation and parts of the interface. There are checks for style, keyboard shortcuts and startup of both programs.
- **Still to be tested with people**: it has not yet been tested with students or in a rehabilitation program, nor by hand with each screen reader, nor with physical controllers, nor head tracking with a real sensor. Your feedback is very welcome.

### Help and bug reports

- Complete manual in the Studio with F1.
- [Frequently asked questions](data/docs/en/preguntas-frecuentes.md).
- Bug reports and suggestions in the [project issues](https://github.com/hxebolax/EntornoLab/issues), also from Help, «Report a bug». Never publish student data.
- Security or privacy problems: privately, as explained in [SECURITY.md](SECURITY.md).

### Buy me a coffee

EntornoLab is free. If you find it useful and want to support its development, you can [buy the author a coffee](https://www.paypal.com/paypalme/hjbcdonaciones). It is also in the Studio, in Help, «Buy me a coffee if you like my work».

### Languages

The application is written in Spanish from Spain and fully translated into English (interface, manual, keyboard shortcuts, release notes and quick guides in `data/docs/en`). You choose the language in Preferences or with the `APP_IDIOMA` variable; by default, the Windows language is used. Translations into other languages are welcome: see «Translating into another language» and the [English translation glossary](docs/glosario-traduccion.md) (in Spanish).

## For developers

### The project in numbers

These figures are calculated by `tools/cifras_proyecto.py` from the real data. To update them: `.venv\Scripts\python.exe tools\cifras_proyecto.py --escribir README.md`.

<!-- cifras:inicio -->

| What | How many |
|---|---|
| Built-in object add-ons | 21 |
| Objects in those add-ons | 2,258 |
| Distinct sounds in the sound catalog | 198 |
| Sound packs | 3 (grabado, natural, por_defecto) |
| Activity types | 22 |
| Example environments | 3 |
| Interface languages (with a catalog, even if incomplete) | 2 |
| Automated test files | 120 |
| Test functions (not counting parametrized ones) | 1,819 |

<!-- cifras:fin -->

### Project tree

In the root:

- `main.py`: starts the Studio (and Play with `--jugar`).
- `jugar.py`: starts Play.
- `entorno.bat`: project administration: virtual environment, tests, languages and building.
- `setup_cx.py`: builds the two executables with cx_Freeze.
- `pyproject.toml`: metadata and configuration for ruff and pytest.
- `requirements.txt` and `requirements-dev.txt`: application and development dependencies.
- `__pip__/`: our own wheels that travel with the code, such as basskit with BASS.

In `app/`, the application code:

- `core/`: paths, configuration, logging, encryption, network, tasks, processes, languages and version.
- `dominio/`: environment model, geometry, editing, object catalog and validation.
- `motor/`: world, movement, perception, acoustics, street dynamics and game session.
- `actividades/`: activity types, games, practice, exams and scoring.
- `audio/`: sound engines, speech, braille, vibration and sound packs.
- `entrada/`: named actions, keyboard and controller.
- `reproductor/`: Play, with pygame: screens, menus, map and connection to the room.
- `ui/`: the Studio, with wxPython: main window, dialogs, map and tracking windows.
- `seguimiento/`: students, sessions, measurements, reports and log.
- `supervision/`: room, client, protocol and security of live supervision.
- `importar/` and `exportar/`: OpenStreetMap, DXF, SVG, image and GPX; text, visual and tactile maps, braille, GeoJSON and DXF.
- `services/`: updater and online add-on catalog.

In `data/`, what travels with the application:

- `bin/openal/`: OpenAL Soft and the HRTF profiles.
- `sounds/`: sound packs and sound catalog.
- `plugins/`: built-in object add-ons.
- `ejemplos/`: example environments.
- `docs/`: user documentation and third-party licenses.
- `locales/`: translations.
- `icons/`: icons.

And also:

- `docs/`: technical documentation, which does not travel with the application.
- `tests/`: tests with pytest.
- `tools/`: tools to generate sounds, examples and add-ons, translate, build, package and publish.

When it is used, the program also creates in `data` the folders `config`, `logs`, `db`, `sessions`, `entornos`, `cache`, `temp` and `backups`, which are neither versioned nor distributed.

### Architecture in brief

- Two processes with the same engine: the Studio (wxPython) and Play (pygame-ce). The Studio launches Play as a child process to test, walk through or supervise, and they communicate through the supervision room.
- `app/dominio`, `app/motor` and `app/actividades` do not import wx, pygame or sound libraries: they receive data and return data or events, and they are tested without a window or speakers.
- The engine does not play sounds or speak: it produces events that the sound layer and the speech layer apply.
- Input is translated into named actions, so keys and buttons can be remapped without touching the engine.
- Everything the program generates lives in `data`, next to the executable: it is portable.

The contract between modules is in [docs/arquitectura.md](docs/arquitectura.md).

### Development requirements

- 64-bit Windows.
- 64-bit Python 3.15, with the `py` launcher.
- Git.

Everything else is installed in the project's virtual environment.

### Setting up the environment

1. Clone the repository:

   ```
   git clone https://github.com/hxebolax/EntornoLab.git
   cd EntornoLab
   ```

2. Create the virtual environment and install the dependencies:

   ```
   entorno.bat crear
   ```

   It creates `.venv` with Python 3.15 and installs `requirements.txt` and `requirements-dev.txt`. Our own wheels in the `__pip__` folder, such as **basskit** with the BASS library, are installed automatically from the repository itself: `requirements.txt` names them by their path. When it finishes, `entorno.bat` checks that basskit loads `bass.dll`.

3. Check the result:

   ```
   entorno.bat diagnostico
   ```

   It shows the versions of Python, wxPython, pygame-ce, numpy, sounddevice, cryptography, basskit and cx_Freeze, and whether OpenAL Soft and the screen reader are present.

**OpenAL Soft** is not installed with pip: its `soft_oal.dll` library and the HRTF profiles go in `data/bin/openal`, inside the repository. Without it, the binaural engine is not available and the next one is used.

`entorno.bat` without arguments opens a numbered menu. With a command, it runs it and returns an exit code: `crear`, `instalar`, `actualizar`, `ejecutar`, `depurar`, `jugar`, `pruebas`, `comprobar`, `sonidos`, `ejemplos`, `idiomas`, `compilar`, `compilar-debug`, `empaquetar`, `limpiar`, `datos`, `registros`, `diagnostico` and `congelar`.

### Running from source

- Studio: `entorno.bat ejecutar`, or `.venv\Scripts\python.exe main.py`.
- Studio with a console and detailed logging: `entorno.bat depurar`.
- Play: `entorno.bat jugar`, or `.venv\Scripts\python.exe jugar.py`. It accepts arguments, for example:

  ```
  entorno.bat jugar data\ejemplos\vivienda-de-ejemplo.elab --alumno ana
  ```

- Check without windows: `main.py --comprobar-arranque` and `jugar.py --comprobar-arranque` exit with 0 if everything is fine.

Useful environment variables: `APP_DATA_DIR` (another `data` folder), `APP_IDIOMA` (force a language) and `APP_DEPURACION=1` (DEBUG logging). More details in [docs/desarrollo.md](docs/desarrollo.md).

### Tests and style

```
entorno.bat pruebas
.venv\Scripts\python.exe -m pytest tests -q -m "not red and not interfaz and not lento"
.venv\Scripts\python.exe -m ruff check app main.py jugar.py tools setup_cx.py tests
entorno.bat comprobar
```

- The markers are `lento` (more than one second), `red` (needs the Internet) and `interfaz` (shows windows or sends real keystrokes). By default, `red` and `interfaz` are not run.
- Tests never touch the real `data` folder or go out to the Internet: `tests/conftest.py` guarantees it.
- `entorno.bat comprobar` runs ruff, compares the shortcuts in the code with the list of keyboard shortcuts (`tools/comprobar_teclas.py`), checks the release notes and the languages, and starts the Studio and Play.

### Building with cx_Freeze

1. Make sure the tests and the check pass: `entorno.bat pruebas` and `entorno.bat comprobar`.
2. Build:

   ```
   entorno.bat compilar
   ```

What `compilar` does, in order:

1. `tools/antes_de_compilar.py`: compiles the translations and checks that the version has notes in `data/docs/novedades.md`.
2. `setup_cx.py build`: generates in `build/entornolab` the two executables, `EntornoLab.exe` (Studio) and `EntornoLabJugar.exe` (Play), with the Visual C++ runtimes.
3. `tools/verificar_build.py`: checks the executables, the required DLLs, OpenAL Soft, the documentation and the licenses, and that `data` travels clean.
4. Starts both executables with `--comprobar-arranque`, with a separate `data` folder.
5. `tools/empaquetar.py`: creates `build/EntornoLab_v<version>.zip` and `build/version.json`.

The result is the distributable folder `build/entornolab`, with the two executables and the `data` folder, and its ZIP. Only `bin`, `sounds`, `locales`, `docs`, `icons`, `plugins` and `ejemplos` travel in `data`. `entorno.bat compilar-debug` builds with a console, to see startup errors; do not distribute it.

### Verifying and packaging

- `entorno.bat comprobar` also starts the built version if it exists.
- `entorno.bat empaquetar` recreates the ZIP and `version.json` from the existing build.
- Before publishing, test the built version by hand with a screen reader, if possible on a Windows computer without Python: startup, F1, a game with headphones and closing.

### Publishing a signed release and the catalog

Summary; the details are in [docs/actualizaciones.md](docs/actualizaciones.md) and [docs/catalogo-de-complementos.md](docs/catalogo-de-complementos.md).

1. Bump `APP_VERSION` in `app/core/version.py` and `version` in `pyproject.toml` (a test checks that they match).
2. Add the entry `## Versión X.Y.Z - AAAA-MM-DD` in `data/docs/novedades.md`, in user-facing language.
3. Run `entorno.bat idiomas`, `entorno.bat pruebas`, `entorno.bat comprobar` and `entorno.bat compilar`.
4. Rehearse with `tools/publicar_version.py --simular` and prepare with `tools/publicar_version.py`: it leaves in `build/publicar` the ZIP, the `version.json` signed with Ed25519 and the release notes. With `--subir` and GitHub CLI, it publishes them.
5. Add-ons for the online catalog are published with `tools/publicar_complemento.py` in the catalog repository, also signed.

**The private signing key never goes into the repository.** It is generated only once with `tools/generar_claves.py`, it is stored outside the project (in the folder set by the `ENTORNOLAB_CLAVES` variable or in the user profile), and the tool refuses to write it inside the project. The public key goes in `app/services/actualizador.py`.

### Creating add-ons and sound packs

- Add-ons: [docs/crear-un-complemento.md](docs/crear-un-complemento.md) (step by step) and [docs/formato-de-complementos.md](docs/formato-de-complementos.md) (reference). The built-in ones are generated with `tools/generar_complementos.py`.
- Sound packs: [docs/sonido.md](docs/sonido.md) and `data/sounds/LEEME.md`. The default pack is generated with `entorno.bat sonidos` and the «Natural» one with `tools/generar_paquete_sonidos.py`.
- Example environments: `entorno.bat ejemplos`. The environment format is in [docs/formato-de-entornos.md](docs/formato-de-entornos.md).

### Translating into another language

The code is written in Spanish and each language is a gettext catalog in `data/locales/<language>/LC_MESSAGES/entornolab.po`.

1. `.venv\Scripts\python.exe tools\extraer_cadenas.py`: generates the `entornolab.pot` template.
2. `.venv\Scripts\python.exe tools\actualizar_po.py --nuevo fr`: creates the catalog for the language.
3. Translate the `.po` with Poedit or a text editor, without touching the `{nombre}` placeholders or the shortcut that follows the tab.
4. `.venv\Scripts\python.exe tools\compilar_traducciones.py`: generates the `.mo`.
5. `.venv\Scripts\python.exe tools\informe_traducciones.py --detalle`: what is still pending.
6. Test with `set APP_IDIOMA=fr` and `entorno.bat ejecutar`.

`entorno.bat idiomas` runs the whole cycle. Add-ons and examples carry their translations in `locales/<language>.json`. Translated user documentation goes in `data/docs/<language>/` with the same file names; F1 opens the one for the interface language and, if it is missing, the Spanish one.

### Code conventions

Python 3.15, everything in Spanish from Spain, tabs, 140-character lines, `ruff check` with no warnings, texts with `_()`, logging without personal data and accessibility as a requirement. The complete guide is in [CONTRIBUTING.md](CONTRIBUTING.md) and the community rules, in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

### Map of the technical documentation

The index, with one line per document, is in [docs/LEEME.md](docs/LEEME.md). The main ones:

- [docs/arquitectura.md](docs/arquitectura.md): the contract between modules.
- [docs/desarrollo.md](docs/desarrollo.md): environment, tests, translation and building.
- [docs/estudio.md](docs/estudio.md) and [docs/reproductor.md](docs/reproductor.md): the two applications.
- [docs/motor.md](docs/motor.md), [docs/sonido.md](docs/sonido.md), [docs/voz.md](docs/voz.md) and [docs/entrada.md](docs/entrada.md): engine, sound, speech and input.
- [docs/actividades.md](docs/actividades.md), [docs/seguimiento.md](docs/seguimiento.md), [docs/estudio-seguimiento.md](docs/estudio-seguimiento.md) and [docs/supervision.md](docs/supervision.md).
- [docs/formato-de-entornos.md](docs/formato-de-entornos.md), [docs/formato-de-complementos.md](docs/formato-de-complementos.md) and [docs/importar-y-exportar.md](docs/importar-y-exportar.md).
- [docs/actualizaciones.md](docs/actualizaciones.md) and [docs/catalogo-de-complementos.md](docs/catalogo-de-complementos.md).

## License

EntornoLab, Copyright 2026 Héctor J. Benítez Corredera, is free software: you can redistribute it and modify it under the terms of the [GNU General Public License](LICENSE), version 3 or (at your option) any later version. It is distributed without any warranty.

- **Additional permission for BASS.** The license includes an additional permission (section 7 of the GPL) to combine EntornoLab with the BASS library. **BASS is not free software and is free of charge only for non-commercial use.** For commercial use you need to buy its license from Un4seen Developments, or choose another sound engine and delete `bass.dll`: the rest of the program works the same.
- **OpenAL Soft**, the default binaural engine, is licensed under the GNU LGPL.
- **Sounds**: the «Synthetic» and «Natural» packs have the EntornoLab license; the recordings in the «Recorded» pack are CC0, with their credits in `data/sounds/grabado/CREDITOS.txt`.
- **Add-ons**: each one declares its license in its information sheet; the built-in ones in this version use CC BY 4.0.
- **OpenStreetMap data**: © OpenStreetMap contributors, licensed under the ODbL.
- The complete list of third-party components and their texts is in [data/docs/licencias](data/docs/licencias/LEEME.md).

## Credits and acknowledgments

- Author: Héctor J. Benítez Corredera.
- EntornoLab relies on free projects: wxPython, pygame-ce, OpenAL Soft, NumPy, sounddevice, soundfile, accessible_output2, cryptography, Python-Markdown, pywin32 and cx_Freeze. It also uses the BASS library from Un4seen Developments, HRTF profiles from MIT KEMAR and SADIE II, and OpenStreetMap data and services.
- It is inspired by research on learning places with audio games and virtual environments, especially the work of Jaime Sánchez, Lotfi Merabet, Erin Connors and colleagues (AbES, AudioDoom, AudioChile), of Orly Lahav and colleagues (BlindAid), of Bowman and Liu on street crossing and of Giudice and colleagues on maps with sound and vibration, and on projects such as Soundscape and VisionPulse. Citing them does not mean that their authors endorse EntornoLab.

## How to cite

If you use EntornoLab in a work or a publication, you can cite it like this:

> Benítez Corredera, H. J. (2026). EntornoLab (version 0.1.0) [Software]. https://github.com/hxebolax/EntornoLab
