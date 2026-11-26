# Guide to creating object add-ons

An add-on is a folder with objects for the Studio catalog: furniture, appliances, street furniture or obstacles. You do not need to know how to program. This guide summarizes the two ways to do it. The complete step-by-step guide, with a full example, is in the project's source code: [docs/crear-un-complemento.md on GitHub](https://github.com/hxebolax/EntornoLab/blob/main/docs/crear-un-complemento.md), and the reference for each field, in [docs/formato-de-complementos.md on GitHub](https://github.com/hxebolax/EntornoLab/blob/main/docs/formato-de-complementos.md).

## What an object is

An object is not a drawing: it is a shape with real measurements. What matters is:

- how big it really is, in meters, with a minimum, a normal size and a maximum;
- what shape it has seen from above: rectangle, circle or ellipse, L shape, or polygon;
- whether it blocks the way and at what height its base is. A cane does not detect things that hang;
- how it sounds when you hit it and whether it makes noise on its own;
- what you can do with it: open it, sit down, press a button;
- whether it can hide a reward.

## With the Studio wizard

1. Choose Tools, "Create an add-on of your own".
2. On the Details tab, type the "Add-on name", the "Author", the "License" and the "Description". The "Identifier" is generated automatically from the name.
3. On the Objects tab, press "Add" for each object. Fill in the groups "What it is", "Shape and size", "Placement", "Sounds and actions", "Classification" and "Symbol". Ctrl+H explains each field and "Listen to the chosen sound" plays it.
4. On the Save tab, press "Check" and fix whatever it reports.
5. Press "Save on this computer". The add-on appears in the catalog without restarting.
6. To share it, press "Export to share". A `.elabc` file is created.

Limitations of the wizard in this version:

- it only offers the sounds that come with the program. For a recorded sound, copy the file into the add-on's `sonidos` folder (inside `data\plugins`) and type its name in the details by hand, as explained below;
- it always starts empty: it does not open an existing add-on for editing. To change one, edit its `complemento.json`.

## By hand, with a text editor

1. Inside `data\plugins`, create a folder. Its name is the identifier: lowercase letters without accents, digits, hyphens and underscores. For example, `mi-centro`.
2. Inside it, create the file `complemento.json`, saved in UTF-8. It must have `formato`, `id` (the same as the folder), `nombre`, `version`, `autor`, `licencia`, `descripcion`, `categorias` and the `objetos` list.
3. Write the details of each object: `id`, `nombre`, `categoria`, `etiquetas`, `descripcion`, `forma`, `medidas` (three numbers per measurement: minimum, normal and maximum), `colocacion`, `bloquea`, `material` and `sonidos`.
4. For things that hang, add `altura_base` and `"detectable_baston": false`.
5. If you want your own sounds, put them in the `sonidos` subfolder (OGG, WAV or FLAC, short and mono) and refer to them as `sonidos/fichero.ogg`. The program's sounds are referred to without an extension, such as `golpe/madera` or `fuente/frigorifico`.
6. If you want images, put them in `imagenes`; and translations, in `locales`.
7. Close and reopen the Studio, or use Tools, "Installed add-ons", "Check".

Common mistakes: curly quotes instead of straight ones, a decimal comma instead of a period, a comma after the last item in a list, or the file saved as `complemento.json.txt`.

## Sharing and installing

- Whoever receives a `.elabc` file installs it in Tools, "Installed add-ons", "Add from file". They do not have to unzip anything.
- When installing it, the program checks that it contains only data (details, images, sounds and text) and never programs.
- Send the `.elabc` file along with the environments that use it. Without it, the objects appear as boxes with their measurements.
- To publish it in the online catalog, propose it in the project repository with the "Complemento nuevo" (new add-on) issue template.

## Good practices

- Measure real objects.
- Write the description for someone who cannot see: what it is and how it is perceived by touch, with the cane or by ear. Do not give a color as the only information.
- Use only sounds and images that you are allowed to share, and state their license.
- Do not change the `id` of an object in new versions: environments look for it by that name.
- Test each object by walking through an environment with headphones.
