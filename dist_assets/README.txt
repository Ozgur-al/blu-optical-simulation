Blu Optical Simulation v1.0.0
===============================

Monte Carlo ray-tracing simulator for backlight unit (BLU) optical design.
No installation required -- extract the folder, run the exe.


GETTING STARTED
---------------
1. Extract the BluOpticalSim folder anywhere (Desktop, USB drive, network share).
2. Double-click BluOpticalSim.exe.
3. Load a sample project from File > Open, then browse to the samples\ folder.
4. Or start from scratch with one of the built-in presets (Presets menu).

Your settings are stored in %LOCALAPPDATA%\BluOpticalSim\, not in the app
folder, so it runs fine from read-only locations.


WHAT IT DOES
------------
  - Ray trace: Semi-vectorized Monte Carlo engine with configurable ray count,
    bounce limit, and energy threshold. Runs off the main thread so the UI
    stays responsive.

  - 3D preview: OpenGL viewport with wireframe, solid, and transparent modes.
    Six camera presets (XY, YZ, XZ planes), object selection highlighting,
    material-coloured surfaces, ray path display after simulation.

  - 2D heatmap: Detector output as a colour-mapped image with draggable ROI
    for live region statistics. Full KPI dashboard -- uniformity, efficiency,
    hotspot ratio, edge-to-centre, error metrics, design score.

  - Solid bodies: Box, cylinder, and prism geometries with Fresnel reflection,
    Snell refraction, and total internal reflection. Per-face optical overrides
    (absorber, reflector, diffuser coatings on individual faces).

  - Sphere detector: Far-field intensity capture on a spherical surface.

  - Geometry builder: Guided dialog for cavities (tilted walls), LED grids,
    optical stacks (diffuser + film layers), and light guide plates.

  - LED layout editor: 2D top-view drag-and-drop positioning of LEDs.

  - Angular distributions: Import CSV, IES (IESNA LM-63), or EULUMDAT (.ldt)
    files. Edit point-by-point, normalise, plot, and assign to sources.

  - Parameter sweep: Vary one or two parameters across a range, view results
    in a sortable table with live KPI plot. Multi-parameter grid sweep for
    Pareto analysis.

  - Variants & history: Clone projects as named variants, compare side-by-side,
    and snapshot design history for A/B review.

  - Export: PNG heatmap, KPI CSV, detector grid CSV, self-contained HTML report,
    or a batch ZIP with everything.

  - Multiprocessing: Each source traces in a separate process for faster runs
    on multi-core machines.


SAMPLE PROJECTS
---------------
The samples\ folder contains three ready-to-run .blu files:

  Simple_Box_Demo.blu
      Single Lambertian LED in a 50 x 50 x 20 mm reflective box.
      Good starting point for learning the interface.

  Automotive_Cluster_Demo.blu
      4 x 2 LED grid in a 120 x 60 x 10 mm cavity with 10-degree wall tilt.
      Try a parameter sweep on wall reflectance or LED flux.

  Edge_Lit_LGP_Demo.blu
      310 x 120 x 2 mm light guide plate with 36 edge-coupled LEDs.
      High bounce count -- use the Standard or High quality preset.


KEYBOARD SHORTCUTS
------------------
  F5          Run simulation
  Escape      Cancel simulation
  Ctrl+N      New project
  Ctrl+O      Open project
  Ctrl+S      Save project
  Ctrl+Z      Undo
  Ctrl+Y      Redo


SYSTEM REQUIREMENTS
-------------------
  - Windows 10 64-bit or Windows 11
  - No admin rights needed
  - ~300 MB disk space
  - 4 GB RAM minimum (8 GB recommended for large scenes)
  - Any GPU with OpenGL 2.0 (integrated graphics works)


WINDOWS SMARTSCREEN
-------------------
Windows may show a "Windows protected your PC" warning on first launch because
the exe is not code-signed. This is expected for standalone-distributed apps.

  1. Click "More info" (blue text below the warning).
  2. Click "Run anyway".
  3. The warning will not appear again.

If your IT policy blocks unsigned executables, ask your administrator to
whitelist BluOpticalSim.exe by path or hash.


UPDATE NOTIFICATIONS
--------------------
On startup the app checks GitHub for a newer release. If one exists, a brief
message appears in the status bar. The check:

  - Runs in a background thread and never blocks the UI.
  - Times out silently after 5 seconds if the network is unavailable.
  - Sends no usage data -- it is a single read-only API request.


USER DATA
---------
Settings, recent file list, and window layout are stored in:
  %LOCALAPPDATA%\BluOpticalSim\

Delete that folder to reset everything to defaults.


LINKS
-----
  Source code  : https://github.com/Ozgur-al/blu-optical-simulation
  Bug reports  : https://github.com/Ozgur-al/blu-optical-simulation/issues
  Releases     : https://github.com/Ozgur-al/blu-optical-simulation/releases
