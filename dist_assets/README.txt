Blu Optical Simulation v2.0.0
===============================

A fast Monte Carlo ray-tracing simulator for backlight unit (BLU) optical
design. Runs entirely from a folder -- no installation, no admin rights needed.


GETTING STARTED
---------------
1. Extract the BluOpticalSim folder anywhere you like (Desktop, Documents, etc.)
2. Open the folder and double-click  BluOpticalSim.exe  to launch the app.
3. Load a sample project: File > Open, then browse to the  samples\  sub-folder.
4. Or start fresh: use the Presets menu to load a built-in scene.

The app stores your settings and history in:
  %LOCALAPPDATA%\BluOpticalSim\
No files are written to the installation folder, so it works fine on read-only
network shares too.


SYSTEM REQUIREMENTS
-------------------
  - Windows 10 (64-bit) or Windows 11
  - No installation required
  - No administrator rights required
  - ~250 MB disk space (the BluOpticalSim folder)
  - Minimum 4 GB RAM recommended for large simulations
  - OpenGL 2.0 compatible GPU (integrated graphics is fine)


WINDOWS SMARTSCREEN WARNING
-----------------------------
Because this application is distributed as a standalone zip and is not yet
signed with a commercial code-signing certificate, Windows SmartScreen may
display a warning the first time you run it.  This is normal.

To proceed:
  1. The dialog says "Windows protected your PC" -- click  More info
     (small blue link below the main message).
  2. A "Run anyway" button appears -- click it.
  3. The app will launch normally.  This dialog only appears on the first run.

If your IT policy prevents running unsigned executables, please contact your
IT administrator and ask them to whitelist BluOpticalSim.exe, or ask for a
signed build from your supplier.


SAMPLE PROJECTS
---------------
The  samples\  sub-folder contains ready-to-run .blu project files:

  Simple_Box_Demo.blu
      A single Lambertian LED in a 50 x 50 x 20 mm white reflective box.
      Good starting point for learning the UI.

  Automotive_Cluster_Demo.blu
      A 4 x 2 LED grid in a 120 x 60 x 10 mm cavity with 10-degree wall tilt.
      Demonstrates uniformity optimization and parameter sweep.

  Edge_Lit_LGP_Demo.blu
      A 310 x 120 x 2 mm light guide plate with 36 LEDs on one coupling edge.
      High bounce-count scene -- use quality preset "Standard" or higher.

To open a sample: File > Open > browse to  samples\  and select a .blu file.
You can also drag .blu files directly onto the application window.


UPDATE NOTIFICATIONS
--------------------
Blu Optical Simulation checks for a newer release when it starts up.
If a new version is found, a brief notification appears in the status bar at
the bottom of the window.

The check is completely optional:
  - It runs in the background and never delays startup.
  - It requires an internet connection; if your network blocks outbound HTTPS
    (corporate firewall, proxy), the check silently times out after 5 seconds
    and you will not see any error message.
  - No usage data is collected or sent -- the check is a single read-only GET
    request to the GitHub Releases API.


USER DATA LOCATION
------------------
  Recent projects list, window layout, and preferences:
    %LOCALAPPDATA%\BluOpticalSim\

  To reset all settings, delete the above folder and restart the app.


SUPPORT & UPDATES
-----------------
  GitHub repository : https://github.com/blu-optical/blu-optical-simulation
  Issue tracker     : https://github.com/blu-optical/blu-optical-simulation/issues

  For internal/corporate deployments, contact your simulation tools team.


LICENSE
-------
  See LICENSE file (if included) or the GitHub repository for licensing terms.
