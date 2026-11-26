# Quick guide for the instructor

From zero to the first session with a student, in ten steps. Each step points to the section of the manual (F1 in the Studio) where you will find the details.

## Before you start

- Unzip EntornoLab into a folder you have write permission for, for example in Documents.
- Have a pair of headphones ready for the student.
- If you are going to supervise from another computer, both have to be on the same local network.

## The ten steps

1. **Open the Studio** with `EntornoLab.exe`. The first time, it asks whether it can check for updates at startup; "Don't connect" is the default answer.
2. **Look at an example.** Choose File, "Open example", and open the home. Go through the tree with the arrow keys and read the description with Alt+5. This way you will see how an environment is made.
3. **Create your environment.** Press Ctrl+N, type the name and choose a starting point: "Blank indoor", a template such as "Typical home" or "Classroom", or "Blank outdoor" for the street.
4. **Build the spaces.** Use Ctrl+Shift+H for the first room and Ctrl+Shift+A for the ones attached to it, with the door in the shared wall. Add any missing doors with Ctrl+Shift+U. For several levels, Ctrl+Shift+P and then Insert, "Stairs" or "Elevator".
5. **Furnish and add landmarks.** Tools, "Furnish the space", suggests the furniture for each space. Ctrl+Shift+O places a single object and Ctrl+Shift+F adds a fixed sound to serve as a landmark.
6. **Set the start point and check.** Choose the starting spot and Edit, "Set the start point here". Press F5 and fix whatever "Check the environment" reports. Save with Ctrl+S.
7. **Walk through it yourself.** Press F9: Play opens in walkthrough mode. Walk as the student would, with headphones. With F4 you can place objects, rewards or landmarks where you are. When you finish, close Play.
8. **Prepare an activity.** Go to the Activities page with Ctrl+Tab, press "New activity" and choose, for example, Games, "Treasure hunt" or "Get the treasures out". Review the rewards, the help and the style, press "Check" and accept. Try it with "Try now".
9. **Create the student record.** Press Ctrl+L. The first time, create the instructor password (at least 8 characters; it cannot be recovered if you forget it). Press "New", type an alias that is not their full name, and choose a profile and style.
10. **Start the session.** Choose Supervision, "Start a session on this computer", the student, the environment and the activity, and press "Start". Play opens connected. Press F7 to see the supervision: position, what the student hears and the events, and to send them messages or hints. When you finish, open Students, "Reports" (Ctrl+I) to see the session.

## If the student plays on another computer

1. Export the environment with File, Export, "Package for the student", and copy the `.elab` file into the `data\entornos` folder of the student's EntornoLab.
2. On your computer, press F7, choose "Local network, with an encrypted connection" and "Open the room". Answer "Allow" if Windows asks about the firewall.
3. In Play, the student chooses "Connect to my instructor", looks for the room or types the address, and types the code. Compare the fingerprint the first time.
4. The sessions are saved on the student's computer and move into the database when the student data is opened there.

## Remember

- EntornoLab is an educational and training tool. It does not diagnose or treat, and it does not replace learning at the real place.
- What the student does in the simulated street is not a basis for deciding a real crossing.
- The reports describe what happened in the simulator; record real-world tests in the log (Ctrl+U).
