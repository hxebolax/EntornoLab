# EntornoLab manual

## About this manual

This manual explains all of EntornoLab: the Studio, where the instructor builds the places and prepares the work, and Play, where the student explores them. It is designed to be read with a screen reader.

- In the Studio, open it with F1, or from the Help menu, «User manual».
- If the viewer shows it as a page, your screen reader's H key jumps from heading to heading, and the 2, 3 and 4 keys jump to headings of that level.
- If it shows it as text, the «Sections» list takes you to each section: choose one and press Enter.
- Ctrl+F searches for text and F3 finds the next match. Escape closes the viewer.

The manual has four parts: the Studio, Play, sound, and data, help and reference. The full list of keys is in a separate document: in the Studio, open it with Ctrl+F1.

Next to this manual, in the program's `data\docs` folder, there are also short guides: «guia-rapida-profesional.md», «guia-rapida-alumno.md», «guia-crear-complementos.md» and «preguntas-frecuentes.md». You can open them with any text editor or with your web browser.

Names of menus, buttons and fields are written here exactly as the screen reader announces them, between angle quotes. Keys are joined with a plus sign: Ctrl+Shift+S means hold down Control and Shift and press S.

## What EntornoLab is

EntornoLab is a portable, offline Windows application for learning places before visiting them. It has two sides that share the same engine:

- **The Studio**, for the rehabilitation or orientation and mobility instructor. Here you build indoor environments (rooms, levels, stairs, ramps and elevators) and outdoor areas (streets, sidewalks, intersections, crosswalks with traffic lights, and stops). Then you furnish them with objects, prepare activities, games and tests, keep student records, supervise live and produce reports.
- **Play**, for the blind or low-vision student. It is a first-person audio game with 3D sound. The student explores the place with the keyboard or with an Xbox or PlayStation controller, hears their footsteps, bumps into things, opens doors, climbs stairs, takes the elevator, crosses the street and looks for hidden rewards.

The author is Héctor J. Benítez Corredera. EntornoLab is free software, licensed under GPL 3 or later.

### Who it is for

- **Rehabilitation and orientation and mobility instructors**, whether blind and using a screen reader or sighted and using a mouse and the visual map. The whole Studio works with the keyboard and a screen reader; the visual map is an extra for sighted users.
- **Blind and low-vision students** of any age: children, teenagers and adults. Messages change their tone according to the style: children, teens or adults.
- **Families**, who can join in the game at home with the environment the instructor has prepared.
- **Centers**, which can use the same program folder on several computers and supervise several students at once over the local network.

### What it can and cannot do

EntornoLab is useful for:

- learning the layout of a place before going there: what spaces it has, how they connect, where the doors, the stairs and the objects in the way are;
- practicing routes, returning to the starting point, finding the nearest exit or following a shoreline, as a game or as practice;
- training street decisions, such as waiting for the walk signal at an accessible pedestrian signal, in a simulated environment;
- giving tests that record what happens, with no hints or help;
- keeping track of each student and logging assessments in the real place.

EntornoLab is not meant for:

- diagnosing or treating anything. It is an educational and training tool;
- replacing learning in the real place with an instructor. What is learned in the simulation must be checked and completed there;
- deciding whether a real intersection is safe. The simulator does not know what the real traffic at a place is like;
- street navigation. It does not use GPS or give real-time guidance.

### Scientific basis and its limits

EntornoLab is inspired by studies on learning places with audio-based virtual environments. Here is what they say, with their limits:

- **The strongest evidence.** In the work with the AbES game (Connors et al., 2014), adults with profound blindness trained on a real two-story building using a keyboard and headphones, in 3 sessions of 30 minutes. Afterwards, in the real building, those who had played did as well as those who received directed instruction on point-to-point routes (between 88 and 93 percent), and did clearly better at finding the shortest exit from any point. The group that played in a different building did not learn the real building: you learn the place you trained on, not a general skill.
- **With teenagers** (7 participants, no control group), after 60 minutes of play, the game score was related to performance in the real building.
- **With children** (7 participants, no control group), the game mode produced the best representation of the space, although the difference was not statistically significant because of the group size.
- **Street crossing** (Bowman and Liu, 2017, 12 people with severe low vision): virtual training for deciding when to cross matched real-world training.
- **Interactive maps** (Giudice et al., 2020): learning a map with sound and vibration was equivalent to learning it with a tactile map.

What has not been shown:

- that a whole neighborhood can be learned with a simulator;
- that the effect lasts for months;
- that the controller works as well as the keyboard;
- that it improves mobility in places that were not trained.

Cautions: almost all the studies have between 4 and 17 participants and a single building, and exploring a virtual place is several times slower than a real one. That is why EntornoLab includes what those studies point to as most useful (collecting objects and taking them out through the nearest exit, step-by-step movement, «where am I» without giving the route, tests without hints and with a stopping rule, help that is gradually withdrawn, and a log for the assessment in the real place), but it does not promise results. The full references are in the «Licenses and credits» section.

EntornoLab has not yet been tested with students or in a rehabilitation program. Nor has it been checked by hand with every screen reader or with physical controllers: what has been checked are automated tests.

### Responsible use and safety

- **Do not decide on a real crossing based on what happened in the simulation.** On the street, what you hear and what the instructor says are what count.
- An environment built by hand or imported from a map may contain errors. Whatever the map does not say is marked as unverified, and must be checked on site.
- Use moderate volumes and take breaks. With headphones, keep hearing protection turned on.
- Stars, medals and scores are part of the game: they motivate, but they do not measure competence in the real place.
- Reports describe what happened in the simulator. They are not a clinical assessment.

## Installation and getting started

### Requirements

- Windows 10 or 11, 64-bit.
- Stereo headphones: the 3D sound is designed for them.
- A screen reader, recommended: NVDA, JAWS or another compatible one. If none is running, Play speaks with the Windows voice, unless another speech output, or none, is chosen (section «Speech and braille»).
- An Xbox or PlayStation controller, optional.
- No Internet connection is needed. It is only used if you ask for it: to check for updates, download add-ons, import from OpenStreetMap or supervise over the local network.

### Installing the compiled version

EntornoLab is portable: it is not installed, it is unzipped.

1. Download the ZIP of the latest version from the project's releases page: <https://github.com/hxebolax/EntornoLab/releases>. Its name is `EntornoLab_v` followed by the version number.
2. Unzip it into a folder where you have write permission, for example in Documents or on a USB drive. Do not put it in «Program Files»: the program saves its data next to itself.
3. Open the folder. Inside are the two programs and the `data` folder.

To uninstall it, delete the folder. To take it to another computer, copy the whole folder.

### The two programs

- **EntornoLab.exe** is the Studio, for the instructor.
- **EntornoLabJugar.exe** is Play, for the student.

Both share the `data` folder: environments saved in the Studio appear in Play. The Studio can open Play by itself to test an activity, to walk through the environment or to start a supervised session.

If the Studio is already open, even if it is hidden in the system tray, opening it again brings the existing window to the front.

### What is in the program folder

Inside `data` there are folders that come with the program and folders it creates as you use it:

- they come with the program: `bin` (sound libraries), `sounds` (sound packs), `plugins` (object add-ons), `ejemplos` (example environments), `docs` (this manual and the licenses), `locales` (languages) and `icons`;
- they are created as you use it: `entornos` (your environments), `config` (preferences), `db` (student records and sessions), `sessions` (Play sessions not yet imported), `backups` (database backups), `logs` (logs), `cache` and `temp`.

To make a full backup, copy the program folder.

### Screen reader, headphones and controller

- **Screen reader.** The Studio uses standard Windows controls: the screen reader reads them as in any application. Play speaks through whichever screen reader is running and, if there is none, with the Windows voice. In Play, Options, «Speech and braille», and in the Studio Preferences, Speech tab, you choose who speaks: automatic, only the screen reader, always the Windows voice or nobody (no speech).
- **Headphones.** Put them on with the left side on your left ear. With the built-in engine, sounds are heard in front, behind, to the sides, above and below. With speakers, choose in Options, Sound, «Listening with: Speakers».
- **Controller.** Connect an Xbox or PlayStation controller before or during the game. Play detects it automatically and says its name. The voice always names the buttons of the connected controller.

### Starting the Studio for the first time

1. Open `EntornoLab.exe`.
2. The first time, the program asks whether it may check for a new version at startup. The default button is «Don't connect». If you choose «Yes, check at startup», it will check at most once a day. You can change this later in Preferences.
3. Focus starts on the environment tree. To begin, open an example with File, «Open example», or create one with File, «New environment» (Ctrl+N).

### Starting Play for the first time

1. Open `EntornoLabJugar.exe`.
2. Play greets you and opens «Who is playing?». Choose an alias from the list, «I'm new: type my alias» or «Play as a guest».
3. In the main menu, start with «Tutorial»: it teaches you to walk, bump into things, turn, go around a table, ask where you are, open a door and find a reward.

To move through the Play menus, use the Up and Down Arrow keys, Enter to choose and Escape to go back. F1 says the explanation of the option.

## Part 1. The Studio

### The main window

#### The menus

The menu bar has, in this order: File, Edit, Insert, View, Students, Supervision, Tools and Help. Students and Supervision only appear if the tracking component is installed, which it is by default.

- **File**: «New environment» (Ctrl+N), «Open» (Ctrl+O), «Open example», «Recent», «Save» (Ctrl+S), «Save as» (Ctrl+Shift+S), the «Import» and «Export» submenus, «Environment properties» and «Exit».
- **Edit**: «Undo» (Ctrl+Z), «Redo» (Ctrl+Y), «Item properties» (F4), «Duplicate» (Ctrl+D), «Rename» (F2), «Move» (Ctrl+M), «Rotate» (Ctrl+G), «Change size» (Ctrl+R), «Delete», «Find item» (Ctrl+F) and «Set the start point here».
- **Insert**: «Level», «Room by size», «Room attached to another», «Polygonal space», «Door, doorway, window or entrance», «Freestanding wall», «Stairs», «Ramp», «Elevator», «Catalog object», «Sound source», «Landmark», «Surface zone» and the «Outdoor» submenu.
- **View**: the panes, «Go to level», «Level above» and «Level below», map zoom, «Map tool», «Show grid», «Snap to grid», «Show the visual map» and «Status bar».
- **Students**: «Student records» (Ctrl+L), «Sessions» (Ctrl+T), «Reports» (Ctrl+I), «Real-world assessment log» (Ctrl+U), «Change the password» and «Lock student data».
- **Supervision**: «Supervision room» (F7), «Start a session on this computer» and «Voice announcements».
- **Tools**: «Check the environment» (F5), «Measure between two items» (Ctrl+Shift+M), «Furnish the space», «Walk through the environment» (F9), «Walk through from the selected item» (Shift+F9), «Stop the walkthrough», «Installed add-ons», «Online add-on catalog», «Create an add-on of your own», «Open the data folder», «Open the logs folder» and «Preferences» (Ctrl+,).
- **Help**: «User manual» (F1), «Keyboard shortcuts» (Ctrl+F1), «What's new», «Help for the focused control» (Ctrl+H), «Check for updates», «Project website», «Report a bug», «Create a diagnostic package», «Buy me a coffee if you like my work» and «About EntornoLab».

While you move through a menu, the status bar shows what each command does.

#### The Environment page

The work area is a notebook of pages: «Environment», «Description» and «Activities». Ctrl+Tab moves from one to another.

The Environment page has four parts:

- **«Environment tree»**: the environment, its levels, the spaces on each level and what each space contains. A door appears under both spaces it connects. Each level also has groups such as «Freestanding walls», «Streets» and «Outside any space», and at the end there is the «Stairs, ramps and elevators» group. Each node says its name and its type.
- **«Item list»**: what is inside the node chosen in the tree, with four columns: Name, Type, Size and Position. The Left and Right Arrow keys read the columns.
- **«Selected item»**: a read-only field with a sentence that says what the item is, how big it is and where it is.
- **Properties**: the form for the selected item, with the «Apply changes» and «Discard changes» buttons.
- **«Visual map»**: the drawing of the level, for sighted users. You can hide it with View, «Show the visual map».

#### Moving between panes

- Alt+1 takes you to the tree, Alt+2 to the list, Alt+3 to the properties, Alt+4 to the map and Alt+5 to the description.
- F6 moves to the next pane and Shift+F6 to the previous one: tree, list, properties and map.
- Alt+Page Up and Alt+Page Down switch to the level above and the level below. View, «Go to level», shows the list of levels.
- In the tree and in the list, Enter opens the properties, Delete deletes after confirmation and the Applications key opens the context menu.

The context menu of the tree, the list and the map has: «Properties», «Rename», «Duplicate», «Move», «Rotate», «Change size», «Delete», «Insert a catalog object», «Set the start point here» and «Walk through from here».

#### The Description and Activities pages

- **Description** (Alt+5) shows the whole environment as text, one sentence per line: name and author, how many levels it has, where it starts, and each space with its neighbors, its doors, its objects, its sound sources and its landmarks. At the end come the streets and the connectors between levels. It is the same text that is exported with File, Export, «Text description». In a large environment (an imported neighborhood), the page first says «Composing the description of the environment…» and, once it is ready, announces «Description ready» with its number of lines; meanwhile you can keep using the program.
- **Activities** shows the environment's activities. It is explained in the «Activities» section.

#### Large environments

A neighborhood imported from OpenStreetMap can have thousands of spaces, doors and landmarks. The Studio is built to keep responding instantly with them:

- In the tree, the level shows its spaces, but what is inside each space and each group appears when you expand it with Right Arrow. In a small environment the tree opens fully expanded, as always.
- The item list of a level can have thousands of rows and can be browsed without waiting.
- On the map, when the whole neighborhood is in view, it is drawn without labels or small symbols; the details come back when you zoom in.
- Whatever reviews the whole environment and takes a few seconds with a neighborhood («Check the environment», exporting, the Description page) is done in the background. A progress box says in its «Status» field what is being done and with what figures («Checking the objects on Street: 300 of 1424.») and the time elapsed; the voice announces each new phase without interrupting and, if 15 seconds pass with nothing new, reminds you that it is still going. Escape or the button to stop the task cancels it.

If the program ever stops responding for more than three seconds, it writes this down in the logs folder along with what it was doing; the diagnostic package (Help) includes it.

#### Status bar and title

- The status bar repeats the last spoken message and says the current level. You can hide it with View, «Status bar».
- When there are unsaved changes, the window title starts with an asterisk.
- When you close or open another environment with unsaved changes, the program asks, with the «Save», «Don't save» and «Cancel» buttons.

#### Units and orientation

- All measurements in the Studio are in meters. You can type them with a decimal comma or a decimal point, and with the unit after them («3.5 m»).
- x increases toward the east and y toward the north. North is at the top of the map.
- Headings are in degrees: 0 is north, 90 east, 180 south and 270 west.
- Lists of points are written with x and y separated by a space, and the points separated by semicolons: «0 0; 4 0; 4 3».

### Tutorial: a home from scratch

This tutorial creates a small apartment: a hallway, a living room, a kitchen and a bathroom, with their doors and some furniture.

1. Press Ctrl+N. The «New environment» form opens.
2. In «Environment name» type «My apartment». In «Start from» leave «Blank indoor». Press Enter.
   The program announces that it has opened the environment with one level.
3. Create the hallway: Ctrl+Shift+H opens «Room by size».
   - In «Name» type «Hallway» and in «Kind of space» choose «Hallway».
   - In «Width, west to east (meters)» type 6 and in «Depth, south to north (meters)» type 1.2.
   - Leave the corners as they are and press Enter. The hallway stays selected and the program describes it.
4. Create the living room north of the hallway: Ctrl+Shift+A opens «Room attached to another».
   - In «Next to» choose «Hallway» and in «Side of that space» choose «North».
   - In «Name of the new room» type «Living room», width 4 and depth 3.5.
   - In «Alignment along the wall» choose «Aligned at the west or south end».
   - Leave «Add a door in the shared wall» checked and press Enter. The two rooms share the wall and already have a door.
5. Repeat step 4 for the kitchen, also north of the hallway but «Aligned at the east or north end», 2 meters wide and 3.5 deep.
6. Repeat for the bathroom south of the hallway, 2 by 2 meters.
7. Add the front door: Ctrl+Shift+U opens «Door, doorway, window or entrance».
   - In «Space» choose «Hallway» and in «Wall» choose «West».
   - In «What opens» leave «Door». Check «Counts as a building exit».
   - In «Name» type «Front door» and press Enter.
8. Add a window in the living room: Ctrl+Shift+U again, space «Living room», wall «North», «What opens: Window».
9. Furnish the living room: choose Tools, «Furnish the space». In «Space» choose «Living room» and in «Furnish it as» choose «Living room». Review the «Proposed furniture» list and press «Accept the proposal». For the kitchen, repeat with «Kitchen».
10. Add a single object: Ctrl+Shift+O opens the catalog. Type «coat rack» in «Search», go down to the object list and press Enter. In the placement form choose «Against a wall», space «Hallway», wall «North», and press Enter.
11. Add a sound landmark: Ctrl+Shift+F opens «Sound source». Choose the level, type «Wall clock», choose a sound from the list and accept the proposed position.
12. Set the start point: choose «Front door» in the tree and then Edit, «Set the start point here».
13. Check the environment with F5. If the list of problems is empty, the result says «No problems». If there is something, pressing Enter on the problem takes you to the item.
14. Save with Ctrl+S. The first time it asks where; by default, in the `entornos` folder.
15. Press F9 to walk through it with Play. When you finish, close Play or choose Tools, «Stop the walkthrough».

The «New environment» form also offers templates in «Start from»: «Blank indoor», «Blank outdoor», «Typical home», «Classroom», «Office floor», «Street section with an intersection» and «Bus stop». The «Furnish with the installed add-ons» check box places furniture in the templates that come with suggested furniture.

### Three ways to place things

#### By size

All the forms in the Insert menu ask for the position in meters. For example, «Southwest corner east, x (meters)» and «Southwest corner north, y (meters)». This is the most precise way when you have a plan with dimensions.

#### Relative to something else

This is the most convenient way without a plan. The program works out the coordinates:

- «Room attached to another» places a room against one side of another, sharing a wall, and can add the door between the two.
- «Door, doorway, window or entrance» is placed on a wall of a space: centered, or at a distance from the west or south corner.
- A catalog object is placed «Against a wall», «In a corner» or «Next to another item». Only the fourth option, «At a point, by coordinates», asks for numbers.

#### By walking

The instructor walks through the environment with Play and places things where they are standing:

1. Press F9 (or Shift+F9 to start next to the selected item). The Studio saves the environment and opens Play in walkthrough mode.
2. Walk to the spot with the usual keys. F7 turns on ghost mode, which goes through walls and objects. F8 jumps to any place or level.
3. Press F4 to open the «Edit menu». It has these options:
   - «Place an object here»: you choose the object and it is left where you are, facing the way you are facing. If it does not fit, it is not placed. Since there are more than two thousand objects, they do not all appear in one list: choose «The ones already in this environment», «Search by name» (type one or more words, such as «umbrella stand» or «wheelchair», and press Enter), «Again» to repeat the last one, or an add-on and, inside it, its category and subcategory.
   - «Put a reward here»: asks for the name and adds it to the activity chosen on the Activities page.
   - «Mark this point»: creates a named landmark.
   - «Measure from here» and «Measure to here»: say the straight-line distance and which direction it is in.
   - «Set the start point here»: your position and heading become the environment's start point.
4. Each change is made in the Studio, goes into the Undo history, and Play reloads the environment at the same spot.
5. To finish, close Play or choose Tools, «Stop the walkthrough». The Studio announces «Walkthrough finished». If Play closes by itself because of a failure, the Studio says so («closed unexpectedly»).

There is only one walkthrough at a time. «Place by walking» in the reward editor uses the same one: if one is already open, it reuses it instead of opening another Play.

With a controller, the PlayStation touchpad or the extra button opens the edit menu.

### Editing what is already done

- **Item properties** (F4 or Enter): the full form. Those for spaces and for the environment have tabs. In a space you can change the type, the flooring, the acoustics («Dry», «Room», «Large hall», «Hallway», «Bathroom», «Stairs», «Warehouse», «Outdoor», «Street» or «Park»), the wall material, whether it has walls and whether it is solid.
- **Duplicate** (Ctrl+D): creates a copy half a meter to the east. A level is duplicated whole, above the highest one.
- **Rename** (F2).
- **Move** (Ctrl+M): «Shift it a few meters» or «Bring its center to a point». The «Take its contents along» check box also moves its doors and furniture. Stairs, ramps and elevators cannot be moved: you have to delete them and create them again.
- **Rotate** (Ctrl+G): in degrees, clockwise. With -90 it rotates to the left.
- **Change size** (Ctrl+R): the fields depend on the item. For an object, the height too.
- **Delete** (Delete in the tree or the list): asks first. It also deletes whatever depends on the item: the doors in a wall, the sidewalks and crosswalks of a street, or the entire contents of a level. It can be undone.
- **Find item** (Ctrl+F): searches by name, type or identifier, ignoring accents. Enter in the text box moves to the list and Enter in the list selects the item.
- **Undo and Redo** (Ctrl+Z and Ctrl+Y): the menu says which operation will be undone. By default, 100 operations are remembered.
- **Environment properties** (File menu): name, description, author, source and the «Start point» tab, with the level, the position and the direction faced at the start.

### Levels, stairs, ramps and elevators

- **Level** (Ctrl+Shift+P): name, «It is a street map», level and floor height. If you leave the level empty, it goes above the highest one.
- **Stairs**: connect the «Lower level» with the «Upper level». You specify where the bottom end is, the «Climbing direction» (eight headings), the «Length on the map», the steps, the width and the handrail («On the left», «On the right», «On both sides» or «No handrail»). The top end is in a straight line, at that length.
- **Ramp**: like stairs, without steps.
- **Elevator**: you check the «Levels where it stops» (at least two), the point in front of the door, which is the same on every level, the «Direction faced to get in» and whether it «Announces the level on arrival».

The ends of stairs and ramps and the elevator stop must fall inside a space; otherwise, Check gives an error. In the tree they appear in the «Stairs, ramps and elevators» group.

#### Tutorial: a two-story building

1. Create a new environment with «Blank indoor». It already has a ground level.
2. On the ground level, create a «Lobby» of 8 by 6 meters and a «Stairwell» attached to the east, 3 by 6 meters, with its door.
3. Create the upper level with Ctrl+Shift+P. Name it «First floor» and leave the level empty.
4. Move to the first floor with Alt+Page Up. Create a «Hallway» and a stairwell in the same spot as the one below.
5. Insert the stairs: Insert, «Stairs». «Lower level», the ground level; «Upper level», the first floor. Put the bottom end inside the stairwell, «Climbing direction: North», 4 meters long and 16 steps.
6. Insert the elevator: Insert, «Elevator». Check both levels and put the point in front of the door inside the lobby downstairs and the hallway upstairs.
7. Check with F5 and walk through with F9. When climbing, Play says the steps and, on arrival, the level.

The «Two-story center» example, in File, «Open example», has stairs with 18 steps and an elevator already built.

### Outdoor areas

Outdoor areas are built on a level that is a street map. You create it with the «Blank outdoor» template or with Insert, «Level», checking «It is a street map». All the commands in the Insert, «Outdoor» submenu need a street map.

- **«Street with sidewalks»**: the «Centerline points», the roadway width, the width of each sidewalk (0 creates no sidewalks), the lanes, the direction of travel («Two-way», «One-way, from start to end» or «One-way, from end to start»), the traffic («No traffic», «Light traffic», «Moderate traffic» or «Heavy traffic») and the speed of the cars. It creates the roadway and the two sidewalks.
- **«Intersection»**: resolves the intersection of two existing streets and cuts the sidewalks into sections.
- **«Crosswalk»**: the street it crosses, the point (it snaps to the centerline automatically), the width, «Has a traffic light», «Accessible pedestrian signal», «Has a push button», «Has a median island» and «Add tactile paving on each side». With a traffic light, it creates a pole on each side.
- **«Building with entrance»**: a solid building, which you cannot enter, with its entrance on one facade as a landmark for orientation.
- **«Block»**: a solid block of any shape.
- **«Stop»**: a landmark of type «Transit stop».

The traffic light at a crosswalk always has 25 seconds of green, 5 of flashing and 45 of red. These times cannot be changed at present. Traffic light, accessible signal, push button and median island can be changed later in the crosswalk's properties.

#### Tutorial: a street with an intersection, a crosswalk with a traffic light, and a stop

1. Press Ctrl+N and choose the «Blank outdoor» starting point.
2. Choose Insert, Outdoor, «Street with sidewalks». Name «Main Street», centerline «-30 0; 30 0», 6-meter roadway, 2-meter sidewalks, «Two-way» and «Moderate traffic».
3. Repeat with «River Street», centerline «0 -30; 0 30» and «One-way, from start to end».
4. Choose Insert, Outdoor, «Intersection». First street «Main Street», second «River Street». The sidewalks are cut into sections.
5. Choose Insert, Outdoor, «Crosswalk». Street «Main Street», point x 10 and y 0. Check «Has a traffic light», «Accessible pedestrian signal» and «Has a push button».
6. Choose Insert, Outdoor, «Stop». Name «Main Street bus stop», at x 20 and y 4, on the north sidewalk (the roadway reaches y 3 and the sidewalk, y 5).
7. Set the start point on the sidewalk, check with F5, save and walk through with F9. As you approach the crosswalk, Play announces it, and when you step from the sidewalk onto the roadway it says «Curb».

The «Street section with an intersection» and «Bus stop» templates, and the «Example neighborhood» example, come with this already built.

#### Connecting indoors and outdoors

- The way to walk into a building from the street is to put its indoor rooms on the same street level: create a room with «Room by size» on the street map and add an «Entrance» or a «Door» in its wall that opens onto the sidewalk. That way you walk across without changing levels. The «Example neighborhood» does this with the lobby of the community center.
- You can also connect the street map to an indoor level with stairs, a ramp or an elevator.
- A «Building with entrance» is solid: its entrance is only a landmark and does not lead to any interior.

### Objects and add-ons

Objects (furniture, appliances, street furniture, obstacles) come in add-ons. Each add-on is a folder with its object definitions, its images and its sounds. EntornoLab comes with several built-in add-ons, and you can add more. The full list of built-in objects is in the `CATALOGO.md` file in the `data\plugins` folder, when your version includes it.

Each object has a normal size with a minimum and a maximum, a shape, where it usually goes, whether it blocks the way, how high its base is, whether the cane detects it, its material, its sounds and, sometimes, states and actions, such as opening and closing.

If an environment uses an add-on that is not installed, it still opens: its objects appear as boxes with their sizes. When you open it, the Studio warns you once with a message that names the missing add-ons and asks whether you want to look for them in the online catalog. "Search the online catalog" opens the catalog (filtered by that add-on if only one is missing); "Close" continues without connecting to the Internet.

#### Inserting a catalog object

1. Press Ctrl+Shift+O. "Insert catalog object" opens with the focus on "Search".
2. Type part of the name, for example "table". The list filters itself shortly after you stop typing; Enter filters right away.
3. Press Tab to move down to the "Objects" list. Its columns are Name, Category, Size and Add-on. Below it, a text says how many objects there are.
4. The "Description" field tells you everything about the chosen object: size, shape, where it goes, whether it blocks the way, the height of its base, whether the cane detects it, whether it can hide a reward, its sounds and its states. In "Variant" you choose a size.
5. Press Enter in the list, or the "OK" button. The "Place" form opens, with the object's name.
6. Choose "How to place it": "Against a wall", "In a corner", "Next to another item" or "At a point, by coordinates". The other fields change depending on the method:
   - against a wall: space, "Wall" (the one behind the object), "Position along the wall" and "Distance from the wall";
   - in a corner: space and corner;
   - next to another item: "Reference item", "Which side of the item" and "Distance from the item";
   - by coordinates: meters east, meters north and "Front heading, in degrees".
7. If you like, type a "Custom name" and press Enter.

Ctrl+D marks the chosen object as a favorite, or removes it. The "Related objects" button shows other similar ones.

#### Searching and filtering by classification

- The "Classification" tree has "All", "Favorites", "Recently used" and each add-on with its categories and subcategories. Each branch says how many objects it has.
- "Setting" filters by "Indoor" or "Outdoor". It starts with the setting of the current level.
- "Place", "Room", "Purpose" and "Obstacle type" filter by that classification. They only appear if some object declares it.
- The "Can hide a reward" and "Has its own sound" check boxes leave only containers or objects that make sounds on their own.
- The search ignores accents and capitalization, and looks at the name, the keywords, the description and the classification.

#### Fitting to scale

Before placing it, the program tries out the placement on a copy of the environment:

- if the object does not fit at its size, it tries a smaller variant or shrinks it within its range, and tells you so;
- if it still does not fit, it warns "It does not fit" and changes nothing;
- if it fits but blocks a door or leaves a narrow passage, it asks you, with the buttons "Keep it as is" and "Remove it".

The minimum clear passage is 0.8 meters by default and can be changed in Preferences, Editor. To change the size later, use "Change size" (Ctrl+R).

#### Hanging obstacles and hazards

The "Obstacle type" facet says at what height the object gets in the way: "Floor level: you step on it", "Low: below the knee", "Mid height: from knee to chest", "Tall: full body height", "Overhanging: the cane passes underneath", "At head height" and "Above head height". If the object definition does not say, it is worked out from the height of its base.

Hanging or overhanging objects are important in orientation and mobility because the cane does not detect them. In Play, the sound cane does not detect them either: you find them by bumping into them or with "Look ahead". Each object's description also states its hazards, such as "Moves", "Drop-off or gap", "Hot: burns" or "Slippery or wet".

#### Furnishing a space

1. Choose Tools, "Furnish the space".
2. Choose the level, the space and "Furnish it as": "Bedroom", "Living room", "Kitchen", "Bathroom", "Classroom" or "Office".
3. The program suggests the typical furniture for that use, from the installed add-ons, spread along walls and corners without blocking doors.
4. Review the "Proposed furniture" list, with the columns Object, Size and "Where it goes".
5. Press "Accept the proposal" to place everything at once, or "Discard". What was placed can be undone with a single command.

#### Managing installed add-ons

Tools, "Installed add-ons", shows the list with Name, Version, Objects, Categories, Status and Source ("Built-in" or "User-added").

- "Activate or deactivate": a deactivated add-on does not appear in the catalog. You do not need to restart.
- "Add from file": installs a shared add-on (an `.elabc` file).
- "Check": checks sizes, sounds and images.
- "Details" (or Enter): the add-on's details.
- "Remove" (or Delete): only user-added ones. Built-in add-ons can be deactivated, but not removed.

#### The online add-on catalog

Tools, "Online add-on catalog", downloads the official list of add-ons.

- You search with "Search" and "Category". The list gives the status of each one: "Available", "Update available", "Up to date", "Only on this computer" or "Needs a newer version of the application".
- Buttons: "Install", "Update", "Update all", "Uninstall", "Previous version", "Details", "Refresh" (F5) and "Close".
- Each package is checked before it is installed: the list is signed, each package is verified, and only data is accepted (object definitions, images, sounds and texts), never programs.
- Before updating, the previous version is saved, and "Previous version" goes back to it.

If you allowed checking for updates at startup and "Also check the add-on catalog" is checked, the program only tells you by speech that there are add-ons with updates. It never installs anything on its own.

#### Creating an add-on of your own

Tools, "Create an add-on of your own", opens a dialog with three tabs. Ctrl+Tab moves from one to the next.

1. **Details**: "Add-on name", "Identifier" (taken from the name if left empty), "Version", "Author", "License" and "Description".
2. **Objects**: the list of objects, with "Add", "Edit", "Duplicate" and "Remove". Each object has a name, a category, words to search for it, a spoken description, a shape, a size with minimum, normal and maximum, variants, where it goes, whether it blocks the way, the height of its base, whether the cane detects it, whether it can hide a reward, the material, the sounds, and the states and actions. "Listen to the chosen sound" plays it.
3. **Save**: "Check" checks it without saving, "Save on this computer" puts it in the catalog without restarting, and "Export to share" creates an `.elabc` file that another person installs with "Add from file".

The wizard offers the built-in sounds. To use your own recordings, and for all the details of the format, see the guide "guia-crear-complementos.md" in the `data\docs` folder. The wizard always starts empty: it does not open an existing add-on for editing.

### The visual map

The map is for people who can see. Everything you do on it can also be done from the tree, the list and the menus. The map does not speak: for the screen reader, the selection is announced in the "Selected item" field, the tree, the list and the properties.

Map tools, in View, "Map tool":

- **"Select and move"**: clicking selects, dragging moves, double-clicking opens the properties and the right button opens the context menu.
- **"Draw a room"**: dragging a rectangle opens "Room by size" with the size filled in.
- **"Draw a wall"**: two clicks open "Freestanding wall" with the ends filled in.
- **"Place a catalog object"**: a click opens the catalog and places the object at that point.

With the mouse, the wheel zooms in and out, and the middle button, or holding Space while dragging, pans the view.

Keyboard equivalents, with the focus on the map:

- the arrow keys move the selected item one grid step (0.5 meters by default), and Shift with the arrow keys moves it one fine step (0.05 meters by default). After it moves, the new position is announced;
- Ctrl++ and Ctrl+- zoom in and out, and F8 shows the whole level;
- Ctrl+Shift+G shows or hides the grid;
- Escape cancels the drawing or dragging in progress.

The selected item is drawn with a thick outline and handles at the corners, not just in a different color. The map also draws the scale, the north mark, the background image if there is one, and the rewards and the start of the activity chosen in the Activities tab; a reward hidden inside an object is drawn at the center of the object with a dashed outline. The same information can be read as text at the end of the Description page (Alt+5) and with Ctrl+H on the map. With Windows high contrast, it uses the system colors.

### Checking the environment

Tools, "Check the environment" (F5), checks the environment and its activities. Problems in an activity start with its name ("Activity “Find the keys”: …"); among them is the warning about a reward whose recorded audio is not saved in the environment.

- "Result" says "No problems" or how many errors and warnings there are.
- The "Problems found" list has the columns Severity, Problem, Suggestion and Where.
- Enter on a problem closes the dialog and takes you to the item. "Check again" repeats the check.

Errors include, among others: a level without spaces where they are needed, a door that is not on any wall, stairs whose opening is outside every space, an elevator with fewer than two levels, the start outside the spaces or inside an object, and an object that goes through a wall or overlaps another.

Warnings include, among others: an enclosed space with no door, a door narrower than 0.6 meters, an add-on that is not installed, a sound source outside the spaces, stairs without steps, and an object that blocks a door or leaves a narrow passage.

### Measuring

Tools, "Measure between two items" (Ctrl+Shift+M):

1. Choose "From" and "To".
2. Press "Calculate the measurement".
3. "Measure" gives the center-to-center distance, the direction, and the clear gap. For example: "From Table to Door: 3.2 meters to the northeast (clear gap: 1.5 meters)". If they are on different levels, it says so.

In walkthrough mode, you can also measure with "Measure from here" and "Measure to here".

### Importing

File, "Import", creates a draft. When it finishes, a report opens with what was imported, what was inferred, what the source does not say and what you should review, with the buttons "Use this draft" and "Discard".

#### OpenStreetMap

Creates an outdoor area with the streets of a real place.

1. Choose File, Import, "OpenStreetMap".
2. The first time, the "Connecting to OpenStreetMap" notice explains what is sent: only the search text or the coordinates of the area. Press "Connect" or "Don't connect".
3. In "Search by address or place name", type the address and press Enter. Choose from "Places found".
4. Review "Latitude", "Longitude" and "Radius in meters" (from 20 to 400; 150 is suggested).
5. Type the "Environment name" and review "Import options": sidewalks from the map, infer sidewalks, buildings, points of interest and stops, obstacles and street furniture, service roads, base terrain and building interiors.
6. Press "Download and import". Escape cancels.

The rule is **invent nothing**. Whatever the map does not say is written as "the map does not say": for example, whether a crosswalk has an accessible pedestrian signal. Inferred sidewalks are marked as assumed, and Play warns about this when you step on them. Sounds that the map does not have are never created. Everything imported carries the attribution "© OpenStreetMap contributors", which is kept when exporting.

Without a connection, the "Open a file" button imports an `.osm` or Overpass file saved earlier.

**Importing a large area.** If the radius is over 200 meters, before downloading you are told how big the area is, about how many spaces it will produce, how many megabytes will be downloaded and how long it may take; you can go ahead with "Download" or go back with "Change the radius". During the import, the "Status" field says at all times what is being done and with what figures: which server the data is requested from, how long it has been waiting for the server to prepare it, how many kilobytes have arrived, whether it is retrying or trying another server, and then each phase of the conversion ("Converting streets: 12 of 30"), with the time elapsed below. The voice announces each new phase without interrupting and, if 15 seconds pass with nothing new, reminds you that it is still working and how long it has taken. The part that can take longest is waiting for the OpenStreetMap server, especially if it is busy; the conversion takes a few seconds. Escape or the "Stop the task" button cancels at any time, also while waiting for the server, and nothing is created.

#### DXF and SVG maps

1. Choose File, Import, "DXF map" or "SVG map".
2. In "Map file", use "Browse".
3. In "Map layers", choose each layer and state its use: "Walls", "Spaces", "Doors", "Text" or "Ignore".
4. State the "Drawing units" (millimeters, centimeters, meters, inches, feet or other). "Suggested by the program" shows what it inferred.
5. In "Destination", choose "A new environment" or "A new level of the open environment", and press "Import".

The DXF file must be saved as text, not binary. In SVG, the scale is required and doors are not detected.

#### Background image

Places a scanned map under the visual map, so you can trace over it with the mouse. It is not turned into walls.

1. Choose File, Import, "Background image".
2. Choose the image (PNG or JPG) and the level.
3. Give two calibration points: for each one, its horizontal and vertical pixel in the image and its meters east and north on the map.
4. Adjust the "Image opacity".

#### GPX route

Places a recorded route (GPX or GeoJSON) on an outdoor area imported from OpenStreetMap. With "Leave landmarks at the route's vertices", each point becomes a landmark. Anything more than 50 meters from the environment is left out.

### Exporting

File, "Export":

- **"Package for the student"**: checks the environment and saves an `.elab` file with the environment, its activities and its resources, ready to take to another computer. If there are errors, it asks, with "Export anyway" and "Don't export".
- **"Text description"**: the whole environment described in text, Markdown or "Accessible web page".
- **"Visual SVG map"**: a scale drawing of each level, in A4 or A3, with its legend in text. Print it at 100 percent.
- **"Tactile map"**: a drawing of each level prepared for a raised-line drawing (swell paper or an embosser), without color, with patterns, thick walls, numeric keys in braille and a filled corner to orient the sheet. It comes with its legend in text and in Spanish grade 1 braille, in a `.brf` file.
- **"GeoJSON"**: for mapping programs.
- **"DXF"**: for CAD programs, in layers and in meters. It can be imported again.

When it finishes, the program offers "Open the folder". Maps are exported only as SVG: there is no PDF or PNG.

To take an environment to a student, copy the `.elab` file into the `data\entornos` folder of their EntornoLab. Play shows it in "Choose environment".

### Activities

Activities are what the student does in an environment: games, practice sessions and tests. They live inside the environment file and are prepared on the "Activities" page (Ctrl+Tab from the Environment page).

#### The activity list

The "Activities in this environment" list has the columns Name, Type, Mode and Summary. Its buttons are:

- "New activity": choose the "Group" (Games, Practice sessions or Tests) and the "Activity type", with its description, and it opens the form with sensible values already filled in.
- "Edit" (or Enter).
- "Duplicate": copies the activity below, as "Copy of" its name.
- "Delete" (or Delete): sessions played with it are kept.
- "Move up" and "Move down": the order is the one the student will see.
- "Check": reports the activity's errors and warnings.
- "Try now": saves the environment and opens Play with that activity.
- "Assign to students": puts it on the work list of the chosen student records.
- "Package for the student": saves an `.elab` file with only the chosen activities, without student data.

The Applications key opens a menu with the same actions.

#### The activity form

Its title is "Activity:" followed by the type. It has tabs, which you switch with Ctrl+Tab. Ctrl+H explains each field. The "Check" button checks the activity without saving it.

- **General**: "Name", "Description" (only for the instructor), "Mode", "Presentation style", "Start point" (with "Choose start point" and "Remove start point") and "Time trial (seconds)".
- The tabs specific to the type: **Rewards**, **Goals**, **Exam** or **Scoring**.
- **Messages**: "Start message", "Achievement message", "Final message", "With a companion character" and "Companion's name".
- **Help**: "Allowed help", the fading levels, "Sound beacon toward the goal", "Fade help by levels", "Starting level" and "Failures in a row before offering help".
- **Ending**: "Ask at the end", "Unlockable reward" and "Stars needed to unlock it".

When you accept, if there are errors, it asks, with "Fix it" and "Save anyway".

In "Mode", Game and Practice behave the same; they are used for sorting and for reports. "Exam" removes hints, celebrations, time trials and levels.

#### The games

- **Treasure hunt**: find all the hidden rewards. Options: "In order", "Say how many there are" and the prankster.
- **The errand runner**: pick something up in one place and take it to another; the "Errands" are chained.
- **Get the treasures out**: collect the treasures one at a time and take them out through the nearest exit. Each exit scores 3, 2, 1 or 0 depending on how close it is. This is the game most similar to the one in the AbES studies.
- **Hide and seek**: find a hidden character that makes a noise every few seconds, over several rounds.
- **Follow the guide**: follow a guide by the sound of their footsteps to a destination. The guide waits if the student falls behind.
- **The explorer**: discover all the spaces, or the portion you specify.
- **Chained hints**: each reward gives the hint for the next one. The program can write any missing hints.
- **Cross with the beep**: on the street, decide when to cross, a number of times. Each crossing is scored by whether the student waited for the green light and whether cars were passing. It is a simulator: it does not tell you whether a real crossing is safe.

#### The practice sessions

- **Free exploration**: move around the environment with no goal and no score.
- **Guided tour**: hear a text in each zone, in order or not. It can be narrated live from supervision.
- **Route**: go from one point to another, with intermediate stops if you like.
- **Reverse route**: go there and come back the way you came.
- **Return to start**: go through several places and return to the starting point.
- **Alternative route**: reach a destination with a blocked path.
- **Find a space**: find a space knowing only its name. With "Confirm arrival", the student has to say they have arrived with the "Confirm" action (M key).
- **Room familiarization**: first go around the perimeter and then the interior of a room.
- **Follow a shoreline**: follow a wall or a curb without moving away from it.

#### The tests

- **Route test**: go from one point to another, with the variants "Routes", "Reverse route" or "Shortcuts".
- **Shortest exit test**: leave through the nearest exit from a point; scores 3, 2, 1 or 0.
- **Pointing test**: turn toward a place and confirm. It counts the error in degrees.
- **Distance test**: choose which of two places is farther away, on foot or in a straight line.
- **Reconstruction test**: choose the correct answer about what the place is like.

All tests share these fields: "Number of trials", "Trials defined by hand", "Time limit per trial (seconds)", "Seed", "Stopping rule", "First trials checked", "Minimum correct answers to continue" and "Say the result at the end".

What a test is like for the student:

- it begins with "The test begins. There are no hints, and you won't be told if you're right. Go at your own pace";
- each trial places them at a point and tells them where they are and what they have to do;
- they confirm their answer with the "Confirm" action (M key, or the left trigger plus Y or Triangle on the controller): "I have arrived", "I am facing that way" or "this is my answer". In the exit test there is nothing to confirm: leaving is the answer. In tests with a question (distances and reconstruction), a menu with the answers opens on its own; they choose one and accept it, and "Confirm" opens it again;
- after each trial they only hear "Noted". They are never told whether they were right;
- the stopping rule ends the test as soon as the minimum number of correct answers can no longer be reached, to avoid frustration;
- with the same seed and the same environment, the test repeats exactly the same way.

In a test there are no hints, beacon, prankster, stars or offered help. By default there is also no "Where am I", description, list of nearby things or discovered places; the instructor can allow those four again. There is no pass or fail: the report says what happened.

Currently, trials written by hand in the form only work properly in the shortest exit test. In the other tests, it is better to let the program generate them with the seed.

#### Hidden rewards

Rewards are added in the activity's Rewards tab, in the "Hidden rewards" list, with the columns Reward, Where it is, Visibility, Sound and Message. There are four ways to add them:

1. **By hand**, with "Add reward". In the "Hidden reward" dialog, you type the "Reward name" and choose the place: level, space and "Where, inside the space" ("Inside an object (cupboard, drawer...)", "Next to an object, a door or a landmark", "In the center of the space", "In a corner of the space" or "At specific coordinates").
2. **Inside objects**: with the "Inside an object" option. Only objects that can hide something are offered. The student has to use the object to find it.
3. **Spread out**, with "Place automatically". You say how many, on which levels, their visibility and whether some are hidden inside objects. "Generate the preview" gives a different distribution each time. The distribution starts with the spaces farthest from the start.
4. **By walking**, with "Place by walking". Play opens in walkthrough mode; the instructor walks to the spot, presses F4 and chooses "Mark this point". Then the reward dialog opens.

Each reward also has:

- "Reward sound", with the "Listen" button;
- "Visibility": "Heard from far away", "Heard only up close" or "Hidden until something is opened or used";
- "Message on finding it" and "Hint to find it", optional;
- "Recorded audio", optional: a WAV, OGG or FLAC file that plays after it is found. It is saved inside the environment.

A new Treasure hunt, Chained hints or Get the treasures out activity already comes with some rewards spread out. In Treasure hunt, Chained hints and Get the treasures out, all rewards are required; in other types they are bonus rewards along the way. The instructor can also add rewards live, from supervision.

#### Goals

Goal lists (errands, hiding places, tour zones, stops, places to go through) are filled in with "Add goal". Each goal states "What to do" ("Go to a place", "Pick something up at a place", "Deliver what you picked up to a place", "Leave through an exit", "Find a space by its name" or "Point toward a place"), "Where" (with "Choose an item" or "Choose a point") and an optional text for the student.

The "They must be completed in this order" check box currently only has an effect in the guided tour; the errand runner and the routes always go in order.

#### Help, limits and levels

In the Help tab, the "Allowed help" table has the fourteen kinds of help: "Where am I", "Place description", "Look to the sides and behind", "What's ahead", "What's around", "Sound cane", "List of nearby things", "Discovered places", "Compass", "Echo", "Remind me of the goal", "Hint", "Sound beacon" and "Automatic alerts".

- Each kind of help is "As in the student record", "Allowed" or "Not allowed".
- "Use limit" keeps it allowed a set number of times.
- If the student asks for a help that is not allowed, they hear "That help is not available in this activity".

**Progressive fading levels** remove help little by little. There are four by default, from easiest to hardest: "With beacon", "Beacon only on request", "No beacon" and "No beacon and no “where am I”". You edit them with "Edit the levels". With "Fade help by levels", the student passes a level by completing the activity without asking for hints. Play remembers the level reached in each activity, by alias: the first time, the student starts at the "Starting level", and after that at the level they reached. When sessions are added, the level goes into the student record, and from the record it goes back to Play through the room; if the instructor changes the level in the record, the record's level takes precedence.

"Failures in a row before offering help" makes the game say "If you need it, you can ask for a hint" after several bumps in a row or a long time without progress. Never in a test.

#### Styles, messages and companion

- "Presentation style": "The one in the student record", "Children", "Teen" or "Adult". The children's style celebrates and can have a companion, who is called Tiko by default. The teen style talks about missions and gives the time record. The adult style is plain.
- If the start, achievement and final messages are left empty, the style's default messages are used.

#### Time

- "Time trial (seconds)": 0 means no limit. The time is announced at the start; if it is more than a minute, a warning is given when one minute is left; when it reaches zero, the activity ends. Pauses do not count.
- Tests have a "Time limit per trial (seconds)".

#### The prankster

In Treasure hunt and Get the treasures out, the "With the prankster" check box adds a character who now and then moves an uncollected reward to another spot, so the student has to go around again. It is adjusted with "Seconds between pranks" and "Maximum pranks". When it acts, an alert sounds. It never acts in a test.

#### What the student hears at the end

At the end, Play says whether the activity was completed, the stars, how many goals were achieved, the points, the time and distance, the bumps and the help requested, and the new rewards. Stars are earned for things such as completing the activity, asking for little help, not bumping into things or exploring everything; tests do not give stars. With "Ask at the end", the student can answer three optional questions about effort, confidence and enjoyment.

#### Example activities

The three example environments come with ready-made activities. To use one as a template, open the example, choose the activity and press "Duplicate".

### Students

The Students menu keeps the student records, sessions, reports and the real-world assessment log. This part is protected with a password.

#### The instructor password

1. The first time you open Student records, Sessions, Reports or Real-world assessment log, the program asks you to create the password, at least 8 characters long, and to repeat it.
2. After that, it asks for it once each time the program is opened.
3. "Lock student data" closes those windows and forgets the key until next time.
4. "Change the password" re-encrypts everything with the new one.

**Very important: the password is not stored anywhere. If you forget it, there is no way to recover the encrypted data.** Write it down in a safe place.

The password is used to encrypt the real name, the record notes, the session notes, the text of the markers and the observations in the log. The alias, measurements and routes are not encrypted. Encryption uses AES-256-GCM and the key is derived from the password: that is why the data stays encrypted when the folder is moved to another computer.

#### Student records

Students, "Student records" (Ctrl+L), opens the "Students" window with "Search by alias", the "Also show archived students" check box and the list with Alias, Profile, Style, Last session, Sessions and Status.

To create a record, press "New". The Details tab has:

- "Alias (required)": the name the student is known by. **Do not use the full name**: it is what travels over the network and what appears in Play;
- "Real name (optional, saved encrypted)";
- "Year of birth (optional)";
- "Mobility profile": "Cane", "Guide dog", "Low vision" or "Other";
- "Presentation style": "Children", "Teen" or "Adult";
- "Notes (optional, saved encrypted)".

The other buttons: "Edit the record", "Archive or restore", "Rewards", "Work list", "Sessions", "Reports", "Real-world log", "Export data", "Delete completely", "Change password" and "Lock the data".

#### Game settings and calculating the step

The record's "Game settings" tab stores the way of moving, the step length, turning, speed, the direction format, the distance unit and the level of detail.

"Calculate the step" helps you measure the student's real step length:

1. The student walks in a straight line over a known distance, for example 10 meters, at their own pace, and counts the steps.
2. Type "Meters walked" and "Steps counted".
3. The program divides them and puts the result in the step field. If it is outside the normal range (less than 0.25 or more than 1.5 meters), it warns you.

These settings reach Play through the supervision room: when Play connects with the alias of a student who has a record, and the student data is unlocked, it receives their game settings, the style, their work list and the level they have reached in each activity. This happens with "Start a session on this computer", with "Try now" when choosing a student, and with Play on another computer connected to the room. If the record changes while the student is playing, the change reaches them immediately, even in the middle of a game. What the record says takes precedence over what the student has set in Options; if the student later changes an option themselves, their setting applies until the record arrives again. Play saves what it receives in the alias's profile, so it is also used on days when the student plays offline. The real name, notes, year of birth and mobility profile never travel. The Studio also uses the step from the record to count in steps when replaying a route.

#### Work list and rewards

- The "Work list" shows the activities assigned with "Assign to students" on the Activities page. "Remove from the list" does not delete the activity. Play receives it through the room with the record: in "Choose environment", the option "What your instructor assigned you" appears first, within each environment the assigned activities come first, and "Continue" starts the first assigned activity if the student has not played anything yet. To play it, the environment has to be on that computer (for example, copied with "Package for the student").
- "Rewards" shows the student's collection and lets you give one by hand ("Star", "Medal" or "Object"). Rewards motivate; they are not a measure of learning.

#### Exporting and deleting a student's data

- "Export data" saves a ZIP with all of the student's data: record, sessions, assessments and rewards, with CSV tables. **The ZIP is not encrypted**: hand it over or store it with care.
- "Delete completely" tells you what will be deleted (record, sessions, assessments, rewards, session files and all backups of the database), asks you to type the alias and cannot be undone. If you want to keep anything, export it first.

### Live supervision

Supervision lets you follow and help one or more students while they play, on the same computer or on others on the local network. It does not use the Internet.

#### Open the room

1. Press F7. "Live supervision" opens.
2. In "Connection mode", choose "This computer only" or "Local network, with an encrypted connection".
3. Press "Open the room". The program announces the pairing code, which has 6 digits and changes every time. "Copy the code" copies it.
4. On the local network, "Room status" also gives the address of this computer, the port and the fingerprint. Read them out to the student.

The first time on the network it takes a few seconds, because it creates its certificate.

#### Code and fingerprint

- The code does not travel over the network: each side proves that it knows it. After 5 wrong codes in one minute, that address is blocked for one minute.
- The fingerprint identifies the room. The first time a student connects over the network, Play spells out a key for them: compare it with the "Fingerprint" in the room status. If it changes one day, Play does not connect without asking.
- Up to 16 students can connect.

#### The student connects

In Play, the student chooses "Connect to my instructor" and then:

- "Search for rooms on the network", which shows the rooms open on the local network;
- "Type the room address", for example 192.168.1.20, or with the port after a colon;
- "My instructor is on this same computer".

Then they type the code. If the connection drops, Play reconnects by itself and the game goes on.

#### Start a session on this computer

Supervision, "Start a session on this computer", chooses the student (or "Guest (no record)"), the environment and the activity, and opens Play already connected to a local room. When it connects, Play receives the game settings, the work list and the levels from the student record.

If a Play opened from the Studio closes, the Studio says so ("The player of Luna has closed") and notes it in the student events. If it closed unexpectedly, it always says so, even if connection announcements have not been chosen, and adds that it can be opened again.

#### What you see and hear

- The "Connected students" list has the columns Alias, Status, Environment, Activity, Where it is, Heading, Active time, Collisions, Help and Goals. It updates without moving the focus.
- For the selected student: "Position of the selected student", "Last thing heard", "History of what was heard" and "Student events".
- A small map shows their position if the student's environment is open in the Studio.
- F6 says the status of the selected student without moving the focus.
- The game sound is not sent over the network. If the student is on the same computer and the classic sound engine is used, the "Send the student's sound to the second audio output" check box lets the instructor hear the same thing on other headphones.

#### Commands

With a student selected in the list:

- "Pause or resume" (Ctrl+P);
- "Send a message" (Ctrl+M): the game speaks the sentence to them;
- "Give a hint" (Ctrl+I): a text, or a sound beacon toward the goal for 10, 20, 30 or 60 seconds;
- "Relocate" (Ctrl+R): takes them to a point. Their environment must be open;
- "Change help" (Ctrl+U);
- "Add a reward" (Ctrl+E). Their environment must be open;
- "Mark this moment" (Ctrl+K): a note that stays in the session;
- "Restart" (Ctrl+Shift+R) and "End" (Ctrl+Shift+T), with confirmation.

An exam test in which the instructor gives a hint is marked "with instructor help". In a narrated tour, the activity also counts the instructor's messages.

Besides these commands, the Studio sends two others by itself, without the instructor doing anything:

- **the student record**, when the student connects and every time it changes (game settings, work list and levels);
- **"reread the settings"**, when you accept or apply Preferences with any change that Play uses (sound pack, sound engine, volumes, speech, movement, controller, keyboard, language, text size or high contrast): each connected Play reads the preferences again and applies at once only what has changed, without restarting or interrupting the game.

#### Voice announcements

Supervision, "Voice announcements", chooses what is spoken to the instructor: connections, collisions, help requested, rewards found, goals achieved, unsafe crossings, end of the session, wrong codes, changes of space and, if you want, everything the student hears.

#### Windows Firewall

On the local network, Windows Firewall has to let EntornoLab accept connections on private networks. The first time the room is opened on the network, Windows asks: you have to answer "Allow". The room uses TCP port 47900 (it can be changed in Preferences) and UDP port 47901 so that students can find it.

### Sessions, reports and assessment log

#### Sessions

Play records every game (not the tutorial or walkthrough mode): the position four times per second and the events, such as collisions, help, goals and rewards. The session is saved on the computer where the game is played. When the instructor opens the student data on that computer, the sessions move into the database and are assigned to the record with the same alias; if there is none, a record with only the alias is created. With each session, the rewards earned (stars, medals and objects) and the help level the student will start with next time in that activity also move into the record. If the student is connected to the room at that moment, their Play receives the updated record.

Students, "Sessions" (Ctrl+T), shows the list with filters by student, environment, activity, mode and dates. Buttons: "Search with these filters", "View details", "Replay the route", "Reports" and "Remove the session". The details have the summary, the "Instructor notes (stored encrypted)" and the marks.

If the student plays on another computer, their sessions stay in the `data\sessions` folder of that computer. There is currently no command to bring them over: they are added when the student data is opened on that same computer.

#### Replay the route

"Replay the route" tells what the student did, step by step, in a list: "Starts in Living room, facing east", "Moves forward 4.0 meters", "Turns left, about 90 degrees", "Bumps into the table". Move through it with the Down Arrow. Distances can be given in meters or in the student's steps. It is not a replay with sound.

#### Reports

Students, "Reports" (Ctrl+I):

1. Choose the "Report type": "Report on one session", "Comparison of several sessions", "A student's progress over time", "Exam report" or "Real-world assessment compared with simulator sessions".
2. Choose the student. To compare, check two or more sessions with Space.
3. Press "Generate the preview" and read the result.
4. Save as text, HTML or CSV, or press "Open in the browser". **Saved reports are not encrypted.**

#### How to read the figures

- **Active time**: the playing time, without the pauses.
- **Time moving** and **time stopped**.
- **Distance traveled**: the sum of what was walked. Jumps (back to the start, relocating) do not count and are given separately.
- **Average speed**: distance divided by active time.
- **Collisions**: how many, where and with what.
- **Help**: how many of each type.
- **Actual path divided by shortest path**: 1 means the student walked the same as the shortest path; 2, twice as much.
- **Spaces visited and not visited**, with the time in each one.
- **Exploration pattern**: "Along the perimeter", "Grid pattern", "From object to object" or "No recognizable pattern", with high, medium or low confidence. It is an approximate description, not an assessment.
- **Exam scores**: correct answers, times and whatever is specific to each exam.

What they do not mean:

- More collisions do not mean worse orientation: bumping into things is a way of exploring.
- A high ratio is not a failure: it can be exploration.
- Comparisons between different environments or activities are not valid; the report warns about this.
- The thresholds for the exploration pattern are conventions, not measures validated with students.
- No figure is a diagnosis or is equivalent to competence in the real place. All reports remind you of this at the end.

#### The real-world assessment log

Students, "Real-world assessment log" (Ctrl+U), is for recording tests in the physical place. The program does not score or interpret.

Each assessment has a date, a place, the related simulator environment, the days since the last training (calculated), the routes done with their result ("Achieved without assistance", "Achieved with assistance", "Not achieved" or "Not attempted"), the "Level of assistance", the "Route type", the mobility aids used and "Observations (saved encrypted)". The notes for each route are not encrypted: do not write personal data in them.

The "Real-world assessment compared with simulator sessions" report puts the two together, without calculating correlations.

### Preferences

Tools, "Preferences" (Ctrl+,). Ctrl+Tab switches tabs. The preferences apply to both the Studio and Play.

- **General**: "Language", "Show what's new after updating", "Colors" (the Windows ones, light or dark), "Text size, in percent", "High contrast on the map and in the player", "Say “Starting” at startup", "Minimize to the system tray", "Hide in the tray when closing" and "Start hidden in the tray".
- **Sound**: "Sound engine", "Head profile", "Sound pack" and its description, "Even out the volume of the packs", "Sound output", "Second output, for the instructor", "Output type", "Hearing protection", "Boost sounds from behind", "Head tracking with OpenTrack" and "OpenTrack port".
- **Volumes**: General, Effects, Steps, Ambience, Help sounds, Interface, Background music and Speech.
- **Speech**: "Speech output" (automatic, only the screen reader, always the Windows voice or no speech; it applies to both the Studio and Play), "Windows voice", "Windows voice rate", "Windows voice volume", "Send messages to the braille display", "A new message interrupts the previous one", "Messages kept for review", "Detail of descriptions" and "Speech channels turned on" (game, help, alerts and instructor messages).
- **Game**: "Movement mode", "Step length", "Turn per key press, in degrees", "Speed in continuous mode, in meters per second", "How directions are given", "Distance unit", "Message style", "Draw the map in the player", "Black screen in the player" and "Say the position in player menus".
- **Keyboard and controller**: how keys are changed (from Play), "Restore the default key map when pressing OK", "Restore the default controller buttons when pressing OK", "Stick dead zone", "Controller vibration" and "Vibration strength".
- **Editor**: "Show the visual map", "Snap to grid when drawing and moving", "Grid spacing", "Fine movement", "Minimum clear passage", "Undo levels", "Minutes between autosaves", "Environments folder", "Recent environments remembered" and "Clear the recent environments when pressing OK".
- **Supervision and privacy**: "Supervision room port", "Announce what happens to the student", "Hear the student on the second output", "Encrypt personal data in student records" and "Days sessions are kept" (0, they never expire).
- **Accessibility**: "Columns read in lists", "Say the column name", "Announce the progress of long tasks", "Percentage points between announcements" and "Studio interface sounds".
- **Network and logging**: "Check for updates at startup", "Versions offered", "Also check the add-on catalog", "Add-on catalog address", "Custom Overpass server", "Custom Nominatim server", "Radius suggested when importing from OpenStreetMap, in meters" and "Log detail".

Ctrl+H explains each preference. Many apply at once; the language of menus that are already open changes after restarting.

The Studio and Play preferences are in the same file, and they also reach a Play that is already open, without restarting it: if it is connected to the room, at once (the Studio asks it to "reread the settings"); if not, as soon as the student goes back to its main menu. Neither program erases, when saving, what the other has just saved. Each student's game options (movement, directions, distances, detail and style) are saved in their profile and do not change the Studio preferences: the ones in the Game tab are the default values for anyone who does not have their own.

### Updates

Help, "Check for updates", opens the "Updates" dialog:

- "Status" and "What's new in the new version";
- the "Check for a new version at startup (once a day)" check box;
- "Channel": "Stable" or "Testing (pre-release versions)";
- the "Check now", "Update now", "Skip this version" and "Close" buttons.

When updating, the program downloads the new version from the project's releases on GitHub, checks its signature and integrity, closes, replaces itself and opens again. If the new version does not start, it goes back to the previous one by itself. It never touches your environments, preferences, records, sessions or logs, or the add-ons you added. If Play is open, it asks you to close it first.

#### If the update does not go well

Before closing, the program checks that it can write to its folder, that there is free space on the disk and that the paths are not too long. If something fails, it says so at that moment and closes nothing. For example, if EntornoLab is in "Program Files", the message asks you to move it to a folder of your own, such as Documents.

Once closed, before changing any file it waits for the Studio and every Play from that folder to close, including the one that opened the room. It does not force them to close. If any of them is still open after a minute and a half, the update is canceled without touching anything.

If the antivirus or the Windows indexer has a file open, the program keeps trying for a few seconds. If another program does not let go of it, the update does not happen and the installation stays as it was.

If something fails halfway, the program puts every file back in its place, checks that the previous version is complete and opens it. If the power goes out halfway, opening EntornoLab again undoes what was started and opens the previous version. If it does not even open, run `recuperar.bat`, in the `data\temp\actualizacion` folder, and it will do the same.

In every case, when the program opens again it tells you in a message what happened: for example, "Could not update to version 0.1.1 because another program was using the file lib\…. You are still on version 0.1.0, and your data has not been touched". You can try again from Help, "Check for updates". If it was the new version that did not start, it is not offered to you again automatically. Every step is written down in `data\logs\actualizacion.log`.

By default, the program does not connect to the Internet on its own. The new features of each version are shown once, the first time the new version is opened, and they are always in Help, "What's new".

### Backups and recovery

- **Recovery copy.** Every 5 minutes, if there are unsaved changes, the Studio saves a separate copy (this is changed in "Minutes between autosaves"; 0 turns it off). If the program closes incorrectly, when you open it again it asks "Recover your work", with "Recover", "Discard the copy" and "Cancel". After recovering, save the environment.
- **File copy.** Every time you save, the previous version is kept next to it with the `.bak` extension. If an environment is damaged and its copy exists, the program offers "Open the backup copy".
- **Student database.** It is copied automatically to `data\backups` before important changes, such as changing the password or deleting a student.
- **Full backup.** Copy the entire program folder, with the program closed.

## Part 2. Play

Play is the student's part. Everything that appears on the screen is spoken, and everything is done with the keyboard or the controller. This part of the manual is for the student, their family and the instructor.

### Start and choose who is playing

1. Open `EntornoLabJugar.exe`. It also opens from the Studio with "Try now", F9 or "Start a session on this computer".
2. Play says hello and tells you which keys move you through the menu.
3. If it is the first time, "Who is playing?" opens:
   - the list of aliases that have already played on this computer;
   - "I'm new: type my alias": you type an alias of up to 40 characters. A nickname is better than your real first and last name;
   - "Play as a guest".

Each alias stores its options, its rewards and its last activity on that computer. It has no password.

To open an environment directly, you can drag its `.elab` file onto `EntornoLabJugar.exe`.

### The main menu

Its title is "EntornoLab. Main menu". Its options are:

- **"Continue"**: starts the last activity played again. It does not save games halfway through.
- **"Choose environment"**: the environments in the `entornos` folder, in the Studio environments folder and the examples. When you choose one, you see its activities and, at the end, "Free exploration". F1 says the description of each one.
- **"My rewards"**: the stars, medals and objects earned, from the last to the first.
- **"Learn the sounds"**: to hear each sound and its explanation.
- **"Practice the controls"**: each key or button says what it is for, without anything happening.
- **"Tutorial"**.
- **"Options"**.
- **"Connect to my instructor"**: for live supervision.
- **"Change player"**: opens "Who is playing?".
- **"Help"**: the game keys or buttons.
- **"About"**: version, author, license, links and notices.
- **"Exit"**.

Use the Up Arrow and Down Arrow to move between options, Enter to choose, Escape to go back, Home and End to go to the first and the last, and a letter to jump to the option that starts with it. F1 explains the option. If it is turned on, each option says its position, for example "3 of 9".

### The tutorial

The tutorial takes place in a small room with a table in the middle and a room with a reward behind a closed door. It teaches, in this order:

1. moving forward two steps;
2. continuing until you bump into the table ("Bumping into things is not bad: it tells you where things are");
3. turning;
4. going around the table;
5. asking where you are;
6. asking what is around you;
7. using the sound cane;
8. opening the door;
9. walking toward the sound of the reward until you reach it.

At any time, the goal key (O) repeats what you have to do and the hint key (P) says where to go. The tutorial is not recorded as a session and can always be repeated.

### Large environments

When an environment is large (for example, a neighborhood imported from OpenStreetMap with hundreds or thousands of places), Play prepares it in the background before the game starts and keeps saying how it is going: first «Loading the environment…» with how many spaces it has; then each phase («Preparing the paths…», «Preparing the sound…») and, if a phase takes long, a reminder every few seconds. On the screen you see «Loading…», the status and «Escape: cancel.». While it loads, the window keeps responding: Enter or F1 say how it is going, and Escape cancels and goes back to where you were. If the instructor restarts the activity or the Studio updates the environment, the same happens, and if it is canceled the game that was in progress continues. Once in the game, Play keeps calculating the nearby paths little by little, so the list of nearby places and the routes respond instantly. A small environment opens instantly, without any notice.

### How to play

#### Moving and turning

- **Move forward and back**: Up Arrow and Down Arrow. In the default "step by step" mode, each press is one step; if you hold it down, you keep walking. Each step sounds according to the floor.
- **Turn**: Left Arrow and Right Arrow. By default, 45 degrees per press. When you turn, it says which way you are facing, for example "Northeast".
- **Side step**: Shift with Left Arrow or Right Arrow.
- **Turn around**: U.

Movement modes, in Options, Movement:

- "step by step", the default;
- "continuous": you walk while you hold down the key;
- "compass": each arrow is a cardinal point: up goes north, right east, down south and left west;
- "room by room": turning chooses an exit from the space and moving forward goes through it;
- "along sidewalks, from one change to the next": you walk straight until something happens, such as an intersection or a curb.

#### Bumping into things and going around them

- When you bump into something head-on, the impact sound of the material plays and it says what it is: "Wall", "Table", "Closed door". The controller vibrates.
- When you brush against a wall, you slide along it: the brushing sound plays and the side of the controller that touches it vibrates.
- There is no command to go around something: you go around by turning and moving forward, as in real life.
- Bumping into things does not make you lose: it only counts in the result.
- At the edge of the environment it says "The environment ends here".

#### Doors

- Enter or Space in front of a door opens or closes it: "Kitchen door: open".
- A locked door cannot be opened: it makes a sound and says so.
- Automatic doors open by themselves when you get close.
- If there is nothing in front, it says "There is nothing to use here".

Interacting also operates objects with states, such as opening a cupboard, and picks up a reward that is nearby.

#### Stairs and ramps

- You enter stairs by walking toward their opening. It says "Stairs, goes up 12 steps" and the handrails.
- Each step makes a sound, higher as you go up, and the controller gives a tap.
- On the stairs, interacting says how many steps you have climbed.
- When you arrive it says "You have reached" and the level.

#### Elevator

1. In front of the elevator door, press Enter to call it. You hear "called. Wait".
2. When it arrives, it says "The elevator has arrived. Move toward the door to get in".
3. Inside, turn left or right to choose a level: each one is spoken.
4. Press Enter to go. You hear the ride.
5. When you arrive it says the level and "Door open. Move forward to get out".

#### The street

- When you go from the sidewalk to the roadway, the curb sounds and it says "Curb".
- Crosswalks are announced as you approach: with an accessible pedestrian signal, without sound or without a traffic light, and whether they have a push button or a refuge island.
- Intersections are described by their shape: T-shaped, cross-shaped, roundabout.
- A sidewalk that the map did not have and that the program has assumed is announced when you step on it.
- Bus stops are objects for orienting yourself. Buses do not stop.

#### Traffic lights and cars

- Accessible pedestrian signals sound different when green, flashing and red.
- With the push button, Enter next to the pole shortens the wait on red.
- If the streets have traffic, cars, motorcycles and buses go by. They stop on the pedestrian green and yield at crosswalks without traffic lights.
- Crossing on red or while cars are passing is announced ("You crossed while cars were passing") and is recorded, but it does not make you lose.

Remember: it is a simulator. It is not for deciding on a real crossing.

### Help

Each kind of help is a question the student can ask. An activity can forbid some or limit how many times they can be used; then you hear "That help is not available in this activity" or "There are no uses of that help left".

- **Where am I** (C): says the space, the level if there are several, and which way you are facing. It never says the route. Pressed twice in a row, it adds the description of the place, the floor and how many doors it has.
- **Look ahead, left, behind and right** (W, A, S and D): say what is in that direction and how far away, up to 20 meters. For example: "On your right: open door to Kitchen 2 meters away; Wall 4 meters away". Look ahead adds what is close by, in front.
- **Around** (Q): describes in parts what is around you: in front, on the right, behind and on the left.
- **List of nearby things** (Tab and Shift+Tab): goes through what is nearby, from the closest to the farthest on foot. Each thing sounds from where it is: "Table, 3 meters, at 2 o'clock".
- **Discovered places** (L): the places you already know and which ones you have not fully explored.
- **Compass** (K): north sounds from the north and it says which way you are facing.
- **Sound cane** (B): a series of tones, one for each step, goes over what is in front. Each tone changes if it crosses a door, a curb or a step, and at the end what is there sounds. Counting the tones is counting the steps left. If you hold it down, it repeats. It does not detect things that hang.
- **Echo** (E): a click whose echo gives an idea of the size of the place and how close the walls are.
- **Goal** (O): repeats what you have to do.
- **Hint** (P): gives help toward the goal; each time it says a bit more. Depending on the activity, it turns on the beacon for a while.
- **Confirm** (M): in an exam or when locating a place, says that you have arrived, that you are facing it or that this is your answer. If there is a question, it opens its answers. If there is nothing to confirm, it says so.
- **Back to the start** (Home): takes you to the start point.
- **Repeat and review** (F2, F3 and Shift+F3): repeats the last message or goes through the previous ones.
- **Silence the speech** (Ctrl).

Also:

- **The beacon** is a sound that comes from the destination. It sounds different if you are facing it, if it is behind you, if you are close or if you have arrived. Only the activity or the instructor turns it on.
- **Automatic alerts** say, depending on the level of detail, the stairs, elevators, crosswalks, doors and objects near you. With "How much the game tells you" at 0, nothing is said.

### Understanding the sounds

In the main menu, **"Learn the sounds"** presents each sound in groups: orientation (beacons, cane, compass and echo), steps on each floor surface, collisions and brushing, doors, stairs and elevator, rewards and achievements, the street, things that make sounds in places, ambiences and menus. Enter plays the sound and F1 says what it means.

It is a good idea to go through this before playing, especially for the beacon and the sound cane. The sounds are played with the pack chosen in Options.

### Games, rewards and exams

- In "Choose environment", each activity says its type. Exams are announced as "exam".
- At the start, the activity says what you have to do. O repeats it.
- Rewards sound from where they are: some can be heard from far away, others only from close by, and others are inside an object that you have to use to find them. When you find one you hear, for example, "You found the key!".
- In an exam there are no hints and it does not say whether you got it right. When you think you have arrived or are facing the requested place, press M (Confirm). If the test is a question, its answers open: choose one with the arrow keys and accept it with Enter. After each test you only hear "Noted".
- If the instructor is connected, they can send messages, hints or new rewards: you hear them as instructor messages.

### Pause and the end

- **Escape** opens the pause: "Continue", "Remind me of the goal", "Repeat the instructions", "Quick options", "Back to the start", "Help" and "Quit the activity" (or "Finish exploring"). The pause stops the time. If the window loses focus, the game pauses by itself.
- **When you finish**, the result is spoken: whether it was completed, the stars, what was achieved, the points, the time, the distance, the collisions, the help and the new rewards. Afterward you can hear it again, answer some questions if the activity asks for it, repeat, choose another activity or go back to the menu.

### Play options

Options are changed with the Left Arrow and Right Arrow, you hear them at once, and they are saved automatically, even in the middle of a game.

- **Sound**: "Sound engine", "Listening with" (headphones or speakers), "Head profile", "Sound pack", "Sound output", the volumes (general, effects, your steps, ambience, help, menus, music and recorded voices), "Hearing protection", "Soften sounds behind you a little", "Head tracking" and "Center head tracking".
- **Speech and braille**: "Speech by" ("automatic", "only your screen reader", "always the Windows voice" or "nobody: no speech"), "Windows voice", its rate and its volume, "Messages on the braille display", "A new message interrupts the previous one", "How much the game tells you" (from "0, sounds only" to "3, everything") and "Say the position in menus".
- **Movement**: "Movement mode", "Step length" (from 25 to 150 centimeters), "Each turn" (15, 30, 45 or 90 degrees), "Continuous walking speed", "Directions are given" (like a clock, by sides, by cardinal points or in degrees) and "Distances are given in" (meters or steps).
- **Controller**: the connected controller, "Stick dead zone", "Vibration", "Vibration strength", "Test the vibration" and the commands to change the buttons.
- **Keyboard**: "Change the game keys", "Change the menu keys", "Hear the keys I changed" and "Reset the default keys".
- **Style and language**: "Style" (children, teen or adult) and "Language".
- **Screen**: "Show the map while I play", "Black screen", "High contrast" and "Text size".

From the pause, "Quick options" gives the most used ones: the general and ambience volume, how much the game tells you, directions, distances and the sound pack.

### Keyboard and controller

The full tables are in the keyboard shortcuts list (Ctrl+F1 in the Studio). Summary of the default keys for playing: arrow keys to walk and turn, Enter or Space to interact, C where am I, W, A, S and D to look, Q around, Tab list of nearby things, L places, K compass, B cane, E echo, O goal, P hint, M confirm, F2 repeat, Ctrl silence, Home back to the start, F1 help and Escape pause.

With the controller, the left stick walks and turns, A or Cross interacts, X or Square says where you are, Y or Triangle looks ahead, the right trigger is the sound cane and the Menu or Options button pauses. The left trigger, held down, gives each button a second function.

#### Change a key

1. Open Options, Keyboard, "Change the game keys" (or "Change the menu keys").
2. Choose the action and press Enter. You hear "Press the key you want to use. Escape cancels".
3. Press the new key. If it already did something else, the two are swapped and it says so.

Escape, Enter, F1 and the screen keys cannot be changed. "Reset the default keys" puts everything back as it came.

#### Change a controller button

1. Open Options, Controller, "Change the game buttons", "Change the second function buttons" or "Change the menu buttons".
2. Choose the button and press accept. The list of actions opens.
3. Choose the action. If another button had it, they are swapped.

#### Practice the controls

In the main menu, "Practice the controls" says what each key or button does when you press it, without anything happening. It respects whatever has been changed. To leave, press Escape twice in a row.

### Connect to the instructor

1. In the main menu, choose "Connect to my instructor".
2. Choose "Search for rooms on the network", "Type the room address" or "My instructor is on this same computer".
3. Type the code the instructor tells you and press Enter.
4. The first time on the network, Play spells out a key. Compare it with the one the instructor sees on their screen.

If you cannot find the room, ask the instructor for the address and type it. If the connection drops, Play reconnects by itself. To leave the room, go back to "Connect to my instructor" and choose "Disconnect".

### The screen and low vision

- **F5** shows or hides the map of the level: seen from above, to scale, with north at the top. Walls are thick lines, closed doors a double line, windows a dashed line, objects their shape with a letter, rewards a diamond and the student an arrow that points where they are facing. There are no flashes or animations.
- **F6** blacks out the screen, for those who do not use it or do not want visual clues. Press it again to see it.
- In Options, Screen, "High contrast" uses white and yellow on black, and "Text size" makes it larger, up to 300 percent.
- The title and the last lines of what the speech has said are always shown.

### Tips for families

- Follow the environment and the activities the instructor has prepared. Play does not replace orientation and mobility lessons.
- Short sessions, 15 to 30 minutes, with breaks. Several days in a row are better than one long afternoon.
- Use comfortable headphones and a low volume. Leave hearing protection turned on.
- Start with the tutorial and with "Learn the sounds".
- Let the student bump into things and explore. Bumping into something is information, not a mistake.
- Ask out loud: "Where is the kitchen?", "Which way would you go out?". This checks their mental picture of the place.
- For the youngest, the children style celebrates achievements and brings a game companion.
- After playing, if possible, visit the real place with the instructor.
- Do not use Play to decide whether it is safe to cross a real street.

## Part 3. Sound

### Headphones and speakers

3D sound is heard best with stereo headphones, worn correctly: left on the left. With them, sounds are placed in front, behind, to the sides and, with the default engine, above and below. With speakers, choose «Listening with: speakers» in Play, or «Output type: Speakers» in the Studio Preferences: the sound becomes simple left-to-right panning.

Distance sounds as it does in real life: a sound 2 meters away is half as loud as one 1 meter away. While the speech is talking, the ambient sound is lowered a little.

### Sound engines

The sound engine is chosen in Play, Options, Sound, «Sound engine», or in Preferences, Sound. If the chosen one fails, the next one is used.

- **«Binaural (OpenAL Soft, for headphones)»**, the default. It places sounds in front, behind, above and below, and adds the echo of each place (a room, a hallway, a bathroom, a warehouse or the street each sound different). Choose it with headphones.
- **«Classic (own mix, supports a second output)»**. It places sounds left and right and somewhat in front and behind, without above or below and without the echo of the place. It is the only one that lets the instructor hear the same thing on a second output, with the student on the same computer.
- **«Simple stereo (modest computers and speakers)»**. Simple panning. For very modest computers or speakers.
- **«3D with BASS (panning without HRTF; non-commercial use only)»**. 3D panning, without above, below or echo. Use it if OpenAL causes problems.

Note about BASS: the BASS library, by Un4seen Developments, is not free software and is free of charge only for non-commercial use. Commercial use requires its paid license, or choosing another engine and deleting the `bass.dll` file. The rest of the program works the same without it.

### Head profiles

Each person hears the direction of sounds according to the shape of their head and ears. With the binaural engine you can choose the «Head profile»: «the built-in one», «dummy head with normal ear», «dummy head with large ear», «studio artificial head» and «person 1» to «person 4». Try several with «Learn the sounds», for example with the beacon, and keep the one that best tells front from back.

### Head tracking with OpenTrack

With a sensor or a webcam and the free program OpenTrack, the turning of your head is added to the character's: sounds stay in place when you move your head.

1. In OpenTrack, choose the «UDP over network» output, with the address 127.0.0.1 and port 4242.
2. In Play, turn on Options, Sound, «Head tracking».
3. Look straight ahead and choose «Center head tracking».

The port is changed in the Studio Preferences, «OpenTrack port». If no data arrives for one second, the head is assumed to be facing straight ahead. This feature has not been tested with a real sensor.

### Hearing protection

Turned on by default. It puts a ceiling on the volume of each sound and of the mix, makes volume increases gradual (the sound starts from silence) and silences everything if the game freezes. If you turn it off, the protection does not disappear: it is only relaxed. Always use it with headphones.

### Sound outputs and second output

- «Sound output» chooses where Play sounds. By default, «the Windows one», and the program follows it if Windows changes output, for example when you plug in headphones.
- The «Second output, for the instructor» lets the instructor hear the same thing as the student, on the same computer, through other headphones. It only works with the classic engine. It is chosen in Preferences, Sound, and turned on with «Hear the student on the second output», in Supervision and privacy, or with the check box in the supervision window.

### Sound packs

A sound pack is a complete collection of the game's sounds. There are three:

- **«Synthetic (default)»**: clean, short sounds, very different from each other, synthesized one by one.
- **«Natural»**: acoustic instruments and objects with body, such as marimba, xylophone and bells, and footsteps, knocks and doors made with physical models.
- **«Recorded»**: real, freely usable recordings for footsteps, knocks, doors, water, traffic and ambient sounds. It is partial: whatever it does not include sounds with the default sounds. On purpose, it does not change the cues that carry information, such as the beacon, the cane, the compass, the traffic lights or the steps.

To change packs, in Play choose Options, Sound, «Sound pack», with the Left Arrow and Right Arrow keys. Enter plays a sample. In the Studio it is in Preferences, Sound. The change is heard immediately. «Even out the volume of the packs», in Preferences, brings all of them to the level of the default sounds.

#### Creating your own pack

1. Create a folder inside `data\sounds`. Its name can only contain lowercase letters, digits, hyphens and underscores.
2. Copy into it the sounds you want to change, with the same name and the same subfolder as in the `por_defecto` folder, for example `puerta\abrir.ogg`. OGG, FLAC and WAV are accepted.
3. If you want, add a `pack.json` file with the name, description, author and license, and a `CREDITOS.txt` file with the source of each sound.
4. The pack appears in the list without restarting. Whatever it does not include sounds with the default sounds.

Tips: sounds that are placed in space must be mono; loops must join without a click; a floor surface needs its six footsteps; and cues that carry a code (for example, the number of beeps of the cane or the notes of the compass) must keep it or not be included. The details are in the `LEEME.md` file in the `data\sounds` folder.

### Speech and braille

- You choose who speaks in Play, Options, Speech and braille, «Speech by», or in the Studio Preferences, Speech tab, «Speech output». The preference is the same for the Studio and for Play:
  - **Automatic** (the default): the screen reader that is running and, if there is none, the Windows voice.
  - **Only the screen reader**: if no screen reader is running, nothing is spoken; the Windows voice is never used. If the screen reader is started while Play is running, this is noticed within a couple of seconds.
  - **Always the Windows voice**: even if there is a screen reader, using the chosen voice, rate and volume.
  - **Nobody (no speech)**: nothing is ever spoken. Messages are still kept in the history (F2 and F3), Play writes them at the bottom of the screen, the Studio in the status bar and, if a screen reader is running and braille is turned on, they reach the braille display. When you choose it in Play, an alert sounds and the screen shows how to get speech back.
- **Ctrl+F12**, on any Play screen, goes back to automatic speech. It helps if someone has been left without speech and cannot reach the options by ear. F12 cannot be assigned to another action.
- With «Messages on the braille display», each message is also sent to the braille display, through the screen reader.
- With «A new message interrupts the previous one» turned off, messages are spoken one after another. This is useful with a braille display or for deafblind people.
- F2 repeats the last message and F3 goes through the previous ones. The history keeps 50 messages by default.
- In the Studio Preferences, «Speech channels turned on» can silence one type of message (game, help, alerts or instructor messages). What is silenced stays in the history.

## Part 4. Data, help and reference

### Privacy and data

EntornoLab has no accounts, no cloud and no telemetry. Everything is saved in the `data` folder next to the program.

What is saved and where:

- `entornos`: the environments (`.elab` files).
- `config`: the preferences, the options of each Play alias, the password data (never the password itself), the room certificate and the known rooms.
- `db`: the tracking database: student records, imported sessions, assessments and rewards.
- `sessions`: the Play sessions that have not been imported yet. They are not encrypted and only carry the alias.
- `backups`: database backups. `logs`: the logs. `cache` and `temp`: temporary data.

What is encrypted: with the instructor's password, the real name and the notes of the student record, the session notes, the text of the bookmarks and the observations in the log. The alias, year of birth, settings, routes and measurements are not encrypted. ZIP exports and saved reports are not encrypted. To encrypt the whole disk, use the Windows tools.

What connections it makes, and when:

- **Updates and add-on catalog**: only if you ask for it, or if you gave permission to check at startup. It connects to GitHub. It does not send personal data: it only requests files and identifies itself as «EntornoLab» and its version.
- **OpenStreetMap**: only when importing, and after a notice the first time. It sends the search text or the coordinates of the box.
- **Supervision**: only on the same computer or on the local network, encrypted over the network. Through the room travel the alias, the position, what the student hears, the events, the commands and, from the student record, only what is needed to play (game settings, style, worklist and levels); never the real name, the notes, the year of birth or the mobility profile.

The logs in `data\logs` do not save students' aliases, names, notes or texts.

To export all of a student's data, use «Export data» in their record. To delete it, «Delete completely». Sessions can expire on their own with «Days sessions are kept».

### Accessibility

- The Studio uses standard Windows controls with labels, access keys and per-control help (Ctrl+H).
- Multi-column lists are read column by column with the Left Arrow and Right Arrow keys, or with Ctrl and a number.
- Long tasks announce their progress and can be canceled with Escape.
- Nothing depends only on color: the visual map uses lines and shapes, and everything on the map can be done without it.
- Play speaks everything it shows, can be used entirely with the keyboard or a controller, and has high contrast, large text and a black screen.
- The interface is in Spanish and English, as are this manual and the keyboard shortcuts. You choose the language in Preferences; by default, the Windows language is used.

The design follows accessibility guidelines for screen readers, but it has not been tested by hand with every screen reader. If something is not read correctly, let us know (section «Report a bug»).

### Troubleshooting

#### Nothing can be heard in Play

1. Check the Windows volume and that the headphones are connected.
2. In Play, Options, Sound, check «Master volume» and «Sound output» (try «the Windows one»).
3. Change the «Sound engine». If the binaural one does not sound, try «Classic» or «Simple stereo».
4. Check that `data\bin\openal\soft_oal.dll` exists. If it is missing, unzip the program again.

#### The screen reader reads too much or too little

- If Play talks too much, lower «How much the game tells you» to «1, the essentials».
- If messages overlap, turn off «A new message interrupts the previous one», or the other way around.
- If the screen reader and Play speak at the same time, choose «Speech by: always the Windows voice».

#### Play or the Studio do not speak

- Press Ctrl+F12 in Play: it goes back to automatic speech.
- Check «Speech by» in Play, Options, Speech and braille, or «Speech output» in the Studio Preferences. With «nobody» nothing is ever spoken; with «only the screen reader», only when a screen reader is running.
- What you did not hear is still in the history: F2 repeats the last message and F3 the earlier ones.
- In the Studio, if the lists read too much, change «Columns read in lists» and «Say the column name» in Preferences, Accessibility.

#### The controller does not respond

1. Disconnect it and connect it again with Play open. Play says its name when it detects it.
2. Check in Options, Controller, whether «Controller connected» appears.
3. If the character moves on its own, raise «Stick dead zone».
4. Use «Practice the controls» to hear what each button does.

Only Xbox and PlayStation controllers are supported. Controllers have been tested with automated tests, not with physical controllers.

#### Supervision does not connect

- Check that the room is open and that the code is the latest one: it changes every time the room is opened.
- For another computer, the mode must be «Local network, with an encrypted connection» and both computers must be on the same network.
- The first time, answer «Allow» to the Windows Firewall prompt. If you answered no, change the EntornoLab permission in the firewall for private networks.
- If «Search for rooms on the network» finds nothing, type the address that the room status says.
- After five incorrect codes, wait one minute.

#### An environment does not open

- If the file is damaged and has a `.bak` copy, the program offers «Open the backup copy».
- If the program closed unexpectedly, it offers to recover your work when you open it.
- In Play, a damaged environment appears as «cannot be opened».

#### Diagnostic package and logs

If you report a bug, attach the diagnostic package:

- In the Studio, Help, «Create a diagnostic package». It is prepared in the background; when it finishes, a message says the name of the file and which folder it is in (`data\diagnostico`) and offers «Open the folder».
- In Play, in the help (the list of keys), the last line is «Create diagnostic package». When it finishes, it says the name of the file and the folder.

The package is a ZIP with the latest Studio and Play logs, `incidencias.log`, the unexpected shutdown notices and `sistema.txt` (version of the program, of Windows and of Python, and the screen readers that are running). It does not include the configuration, student records, sessions, environments or passwords, and in the paths your Windows account name is replaced with `<usuario>`.

Tools, «Open the logs folder», opens `data\logs` in case you prefer to attach a single log: the most recent `sesion_` file (or the most recent `jugar_` file if Play failed) and `arranque_fallido.log` if it exists, together with the version shown in Help, «About». The logs do not contain student data.

#### Checking Play without a window or sound

To find out whether Play starts, whether it loads binaural sound, or whether an environment has all its add-ons, without opening the sound card or any window, you can give it a script: a text file with the steps the student would take. From the program folder, in a command prompt window:

```
EntornoLabJugar.exe --guion comprobar.json --informe informe.json data\ejemplos\vivienda-de-ejemplo.elab --actividad busqueda-del-tesoro
```

A simple `comprobar.json`:

```json
{"motor": "openal", "pasos": [{"hasta": "partida"}, {"comprobar": "hrtf"}, {"comprobar": "sin_complementos_que_faltan"}, {"salir": true}]}
```

Play is neither seen nor heard: it follows the steps, closes and leaves `informe.json` with what it would have said, the sound engine that ended up in use and whether binaural sound (HRTF) was turned on, the sound packs and the missing add-ons. It exits with 0 if everything went well and with 4 if any check failed. The engine opens «in memory», without touching the sound card, and does not change your preferences. To avoid cluttering your data, first run `set APP_DATA_DIR=C:\una\carpeta\de\pruebas`. You can attach the report when you report a bug.

#### I don't remember the password

There is no way to recover the encrypted data. The unencrypted data (aliases, sessions, measurements) are still in the database, but the program only opens it with the password. If you have a copy of the `data` folder from before you changed the password, your data opens with the password you had then.

### Orientation and mobility glossary

- **Around you**: a description of what is around the person, part by part, without moving.
- **Self-familiarization**: getting to know a new place by exploring it yourself, with a method.
- **Sound beacon**: a sound that comes from the destination so you can head toward it.
- **Cane**: the long white cane, which detects what is on the ground in front. It does not detect what is hanging.
- **Curb**: the step between the sidewalk and the roadway.
- **Path ratio**: the path walked divided by the shortest possible path.
- **Echolocation**: perceiving space through the echo of a sound you make, such as a click.
- **Grid search**: going through a space in parallel strips.
- **Perimeter search**: first going around the edge of a space, following the walls.
- **Shoreline**: a continuous edge that you follow so you don't get lost: a wall, a curb, a strip of tactile paving.
- **Mental or cognitive map**: the image of a place that a person forms: what is there and how it relates.
- **Overhanging or head-height obstacle**: something that sticks out above the reach of the cane.
- **Tactile paving**: ground with bumps (warning, for example before a crosswalk) or with bars (direction).
- **Landmark**: something fixed and recognizable that helps you know where you are: a sound, a smell, a change in the ground surface.
- **Heading**: the direction you are facing, in degrees or in cardinal points.
- **Reverse route**: going back the same way you came.
- **Accessible pedestrian signal (APS)**: a traffic light that makes a distinct sound when pedestrians can cross.
- **Transfer**: using in the real place what was learned in the simulator.

### Licenses and credits

EntornoLab, Copyright 2026 Héctor J. Benítez Corredera, is free software under the GNU General Public License, version 3 or later, with an additional permission to use it together with the BASS library. It is distributed without any warranty.

- Third-party libraries keep their licenses. The list and the texts are in the `data\docs\licencias` folder, with its `LEEME.md`.
- OpenAL Soft, the default binaural engine, is licensed under the LGPL.
- BASS is free of charge only for non-commercial use (section «Sound engines»).
- The «Synthetic» and «Natural» sound packs have the same license as EntornoLab. The recordings in the «Recorded» pack are in the public domain (CC0); the details are in its `CREDITOS.txt`.
- The default add-ons have the license stated in each one's details (Tools, «Installed add-ons», «Details»).
- Data imported from OpenStreetMap belongs to the OpenStreetMap contributors, under the ODbL license.

EntornoLab is inspired by studies and projects on learning places through sound, without their authors endorsing it. The main references:

- Sánchez, Sáenz, Pascual-Leone and Merabet (2010). Enhancing Navigation Skills through Audio Gaming.
- Merabet, Connors, Halko and Sánchez (2012). Teaching the Blind to Find Their Way by Playing Video Games.
- Connors, Chrastil, Sánchez and Merabet (2014). Action video game play and transfer of navigation and spatial cognition skills in adolescents who are blind.
- Connors, Chrastil, Sánchez and Merabet (2014). Virtual environments for the transfer of navigation skills in the blind.
- Lahav, Schloerb and Srinivasan (2015). Rehabilitation program integrating virtual environment.
- Bowman and Liu (2017). Virtual training for street crossing with low vision.
- Giudice et al. (2020). Learning floor plans with audio and vibration maps.
- Façanha, Darin, Viana and Sánchez (2020). Systematic review of virtual environments for the orientation of blind people.

### Report a bug or suggest an improvement

1. In the Studio, choose Help, «Report a bug». In Play, choose «About» and «Report a bug or suggest an improvement». The project's issues page opens: <https://github.com/hxebolax/EntornoLab/issues>.
2. Say what you were doing, what you expected and what happened, the version (Help, «About») and your screen reader.
3. Attach the diagnostic package (Help, «Create a diagnostic package»), as explained in «Diagnostic package and logs».

**Never publish student data** (names, notes, sessions or reports) in an issue. A security or privacy problem is not published: it is reported privately, as explained in the project's SECURITY.md file.

### Buy the author a coffee

EntornoLab is free. If you find it useful and want to support its development, in the Studio choose Help, «Buy me a coffee if you like my work», or in Play, «About». The author's donation page opens: <https://www.paypal.com/paypalme/hjbcdonaciones>. Thank you.
