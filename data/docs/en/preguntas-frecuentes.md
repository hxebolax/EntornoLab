# Frequently asked questions about EntornoLab

## About the application

### What is EntornoLab?

A portable, offline Windows application for learning places before visiting them. The instructor builds the place in the Studio and the student walks through it in Play, an audio game with 3D sound.

### How much does it cost?

Nothing. It is free software, licensed under GPL 3 or later. If you find it useful, you can buy the author a coffee from the Help menu.

### Does it replace orientation and mobility lessons?

No. It is an educational and training tool. It does not diagnose or treat, and it does not replace learning at the real place with an instructor.

### Is it proven to work?

There are studies with similar games showing that people can learn a specific building by playing, especially how to find the nearest exit. They are small studies, of a single building. It has not been proven to work for whole neighborhoods, to last for months, or to improve mobility in places that were not practiced. EntornoLab has not yet been tested with students. The "Scientific basis and its limits" section of the manual explains this.

### Does it need the Internet?

No. It only connects if you ask it to: to check for updates, download add-ons or import from OpenStreetMap. Supervision uses the computer itself or the local network, not the Internet.

### Which languages is it available in?

In Spanish and English: the interface, the manual, the keyboard shortcuts and the guides. You change the language in Preferences, General tab; by default, the Windows language is used.

## Installation and computer

### How do I install it?

It is not installed: you unzip the ZIP file into a folder you have write permission for and open `EntornoLab.exe` (the Studio) or `EntornoLabJugar.exe` (Play). To remove it, delete the folder.

### What computer do I need?

64-bit Windows 10 or 11 and stereo headphones. A screen reader is recommended. An Xbox or PlayStation controller is optional.

### Does it work with my screen reader?

The Studio uses standard Windows controls, and Play speaks through the running screen reader or with the Windows voice (you can choose another speech output, or none). It has not yet been checked by hand with each screen reader; if something is not read correctly, let us know.

### Can I carry it on a USB drive?

Yes. Everything, including the data, is in the program folder.

## The Studio

### Do I need to be able to see to build an environment?

No. Everything is done with the keyboard and the screen reader, with measurements or in relation to what is already there. The visual map is an extra for sighted users.

### Can I start from a map I already have?

Yes: File, Import, accepts DXF and SVG maps, and a background image to trace over. You can also import the streets of a real place from OpenStreetMap.

### Why does the environment imported from OpenStreetMap say "the map does not say"?

Because the program does not make anything up. If the map does not say, for example, whether a traffic light is an accessible pedestrian signal, it leaves it that way so that you can check it at the place.

### Can I change the timing of a traffic light?

Not in this version. All traffic lights have 25 seconds of green, 5 of flashing and 45 of red.

### How do I enter a building from the street?

Put the building's rooms on the same street level and open an entrance or a door in their wall that leads to the sidewalk. A "Building with entrance" is solid, and its entrance is only a landmark.

### Is my work lost if the power goes out?

The Studio saves a recovery copy every 5 minutes if there are changes, and when saving it keeps the previous version with the `.bak` extension. When you open it after an unexpected shutdown, it offers to recover your work.

## Students and data

### What happens if I forget the instructor password?

The encrypted data cannot be recovered: the real name, the notes and the observations. The password is not stored anywhere. Write it down in a safe place.

### What student data does it store, and where?

Everything stays in the program's `data` folder. The real name and the notes are encrypted with the password; the alias, the routes and the measurements are not. There is no cloud and no telemetry. The manual gives the details in "Privacy and data".

### Why shouldn't the alias be the student's name?

Because the alias is not encrypted, it appears in Play, and it is the only thing that travels over the network during supervision.

### Do the game settings in the student record reach Play?

Yes, through the supervision room. When Play connects with the alias of a student who has a record (and the student data is open in the Studio), it receives their game settings, their style, their work list and the level they have reached in each activity, and these take priority over whatever Play has in Options. If you change the record while they are playing, the change reaches them immediately. Play saves it on that computer for days without a connection. The real name and the notes never travel.

### Does Play remember the help level from one game to the next?

Yes. In activities with "Fade help by levels", Play starts the next game at the level the student reached. When the sessions are added, that level goes into the student record, along with the rewards earned.

### Do I have to restart Play when I change the Studio Preferences?

No. If Play is connected to the room, the Studio asks it to reload the preferences, and it applies the new sound pack, engine, volumes or voice immediately. If it is not connected, it applies them when it returns to its main menu.

### How do I bring in the sessions of a student who plays on another computer?

The sessions are saved in the `data\sessions` folder of the computer where the game is played, and they move into the database when the student data is opened there. In this version there is no command to import them from another computer.

### What do the figures in the reports mean?

They describe what happened in the simulator: time, distance, collisions, help used, the path walked compared with the shortest one, and the way of exploring. They are not a grade or a diagnosis. The manual explains each one in "How to read the figures".

## Play

### Why can't I tell clearly whether a sound is in front of me or behind me?

Try another "Head profile" in Options, Sound, and check that the headphones are on correctly. The built-in binaural engine is the one that best places sounds in front and behind.

### Play talks too much.

Lower "How much the game tells you" in Options, "Speech and braille".

### I have no screen reader and I do not want the Windows voice. Can I play without speech?

Yes. In Play, Options, "Speech and braille", set "Speech by" to "nobody: no speech" (or in the Studio Preferences, Speech tab, "Speech output", "No speech: never speak"). Messages are shown at the bottom of the screen, kept in the history (F2 and F3) and, if a screen reader is running, sent to the braille display. With "only your screen reader", Play speaks through the screen reader when there is one and stays silent when there is not, never switching to the Windows voice.

### I have been left without speech in Play and I do not know how to get it back.

Press Ctrl+F12 on any screen: automatic speech comes back (the screen reader or, if there is none, the Windows voice).

### Can I change the keys?

Yes, in Options, Keyboard, and the controller buttons in Options, Controller. "Practice the controls" tells you what each key does.

### Which controllers can I use?

Xbox and PlayStation controllers. They have not yet been tested with physical controllers.

### Can I save a game halfway through?

No. "Continue" starts the last activity again.

### What happens if I cross on red?

You are warned and it is recorded, but you do not lose the game. It is a simulator: it is not a basis for deciding a real crossing.

## Help

### Where do I report a bug?

In the Studio, Help, "Report a bug". Say what you were doing, what you expected and what happened, and attach the log from Tools, "Open the logs folder". Never publish student data.

### How do I update it?

Help, "Check for updates". The update keeps your environments, student records, sessions and preferences.
