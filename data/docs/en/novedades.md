# What's new in EntornoLab

## Version 0.1.1 - 2026-11-27

A version with speed improvements and a fix when closing the Studio.

### Improvements

- Undo and redo are much faster and use very little memory: each change stores only what was modified. With a large neighborhood, moving a space, changing a property, undoing or redoing takes a fraction of a second, and a hundred undo steps take a few megabytes instead of hundreds.
- After undoing or redoing, the selection returns to the affected item and the Studio announces what was undone or redone.

### Fixes

- Closing the Studio with an environment open could show an error about the environment tree. This no longer happens; environments were saved correctly anyway.

## Version 0.1.0 - 2026-11-26

First public version of EntornoLab: a portable, offline application for learning places before visiting them.

### New features

- The instructor's Studio, accessible with a screen reader and with a mouse: build indoor areas with rooms, levels, doors, stairs, ramps and elevators, and outdoor areas with streets, sidewalks, intersections, crosswalks with traffic lights, and stops.
- Three ways to place things: by size, in relation to something else (attached, against a wall, in a corner, next to another item), or by walking through the environment with Play and pressing F4.
- Catalog of objects in add-ons, with search, filters by classification, favorites, automatic scaling, a warning for overhanging obstacles, and suggested furniture to furnish a space.
- Add-on management, an online catalog with signed add-ons, and a wizard to create your own add-ons and share them.
- Check the environment (F5), measure between two items, a visual map with a grid, and a full text description of the environment.
- Import from OpenStreetMap without making up anything the map does not say, and from DXF and SVG maps, a background image and GPX routes.
- Export the package for the student, the text description, Markdown or HTML, the visual map, the tactile map with a braille legend, GeoJSON and DXF.
- 22 activity types, including games, practice and exams, with hidden rewards (placed by hand, inside objects, scattered, or placed while walking through, with a message and recorded audio), goals, allowed help with a usage limit, help fading levels, Children, Teen and Adult styles, time trial, and the prankster.
- Student records protected with a password and encrypted, with game settings, step length calculation, a work list, rewards, export and complete deletion.
- Live supervision on the same computer or on the local network, encrypted, with a pairing code and fingerprint: messages, hints, live rewards, repositioning, pausing and marking moments.
- Recorded sessions, step-by-step replay of the route, session reports, comparison, progress, exam and real-world assessment, and a log for tests at the real place.
- Play, the student's audio game: 3D sound, keyboard or Xbox or PlayStation controller, tutorial, "Learn the sounds", "Practice the controls", fourteen kinds of help, traffic lights, cars, elevators, stairs and connection with the instructor.
- Four sound engines, head profiles, head tracking with OpenTrack, hearing protection, and three sound packs: Synthetic, Natural and Recorded.
- Full manual (F1), keyboard shortcuts (Ctrl+F1), help for each control (Ctrl+H), and checking for signed updates, turned off until you give permission.

### Still to be tested

- This version has been checked with automated tests. It has not yet been tested with students, by hand with each screen reader, or with physical controllers. Your reports will help improve it.
