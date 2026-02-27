# Blu Optical Simulation

A desktop application for Monte Carlo optical simulation of backlight units (BLU). Designed for display engineers who need fast design iteration without expensive commercial tools.

---

## Quick Start (Windows — no installation required)

1. Go to the [**Releases**](../../releases) page and download the latest `BluOpticalSim-windows.zip`
2. Extract the zip anywhere on your PC
3. Double-click **`BluOpticalSim.exe`**

No Python, no installation, no admin rights needed.

---

## Features

- **Monte Carlo ray tracing** — physically-based light propagation through reflective cavities
- **Geometry builder** — direct-lit cavity with configurable width, height, depth, and wall angles (separate X/Y tilt)
- **LED grid generator** — specify pitch or LED count; edge offsets auto-calculated
- **Angular distributions** — import any LED I(θ) curve from CSV; built-in isotropic, Lambertian, and batwing profiles; table-based editing
- **Material editor** — reflector, absorber, and diffuser surface types with specular/diffuse control
- **3D viewport** — wireframe / solid / transparent view modes; selection highlighting; XYZ reference axes; six camera preset angles
- **Heatmap output** — 2D flux map on the detector plane; min/avg and min/max uniformity metrics
- **Ray path visualization** — see sampled ray trajectories overlaid in 3D
- **Measurement tool** — point-to-point dX/dY/dZ/distance dialog
- **Project save/load** — JSON format; portable between machines
- **Built-in presets** — Simple Box (50×50×20 mm) and Automotive Cluster (120×60×10 mm, 4×2 LED grid)

---

## Screenshots

> *(Add screenshots here after first run)*

---

## Developer Setup

### Requirements

- Python 3.10+
- Windows, macOS, or Linux

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run from source

```bash
python app.py
```

### Run tests

```bash
pytest backlight_sim/tests/
```

---

## Building the Windows Executable

> Requires Python 3.10+ and a Windows machine (or Wine on Linux).

### One-time setup

```bash
pip install pyinstaller
# or install all dev dependencies:
pip install -r requirements-dev.txt
```

### Build

```bash
python build_exe.py
```

Or on Windows you can double-click **`build_exe.bat`**.

The output appears in `dist/BluOpticalSim/`. Zip that folder and distribute it.

### What the build produces

```
dist/
└── BluOpticalSim/
    ├── BluOpticalSim.exe   ← launch this
    ├── _internal/          ← runtime libraries (keep alongside the exe)
    └── ...
```

---

## Usage Guide

### 1. Create or load a scene

- **File → New Project** to start from scratch, or
- **Presets** menu to load a ready-made scene, or
- **File → Open Project** to load a previously saved `.json` file

### 2. Build geometry

- Open **Tools → Geometry Builder** to generate a reflective cavity and LED grid in one step
- Adjust cavity dimensions, wall angle, LED pitch/count, and material assignments

### 3. Edit objects

- Click any object in the **Scene Tree** (left panel) to select it
- Edit its properties in the **Properties Panel** (right panel)

### 4. Manage angular distributions

- Open the **Angular Dist.** tab to import LED I(θ) data from CSV/TXT
- Built-in profiles (isotropic, lambertian, batwing) are always available
- Assign a distribution to each LED source in its properties form

### 5. Run simulation

- Click **Run** in the status bar (or toolbar)
- Progress is shown in the progress bar
- When complete, the **Heatmap** tab updates automatically and ray paths appear in 3D

### 6. Read results

- **Heatmap tab**: 2D flux distribution on the output plane; uniformity stats shown below
- **3D view**: ray path preview for the first source

### 7. Save your work

- **File → Save Project** writes a `.json` file you can share or reload later

---

## Angular Distribution CSV Format

Two-column CSV with a header row:

```
theta_deg,intensity
0,1.0
10,0.985
20,0.940
30,0.866
...
90,0.0
```

- `theta_deg` — polar angle in degrees (0 = on-axis, 90 = perpendicular)
- `intensity` — relative intensity (any positive scale; normalized internally)

---

## Project File Format

Projects are saved as plain JSON (`.json`). They are human-readable and can be version-controlled. The schema includes:

| Key | Description |
|-----|-------------|
| `name` | Project name |
| `settings` | Simulation parameters (rays, bounces, seed, resolution) |
| `materials` | Array of material definitions |
| `sources` | Array of LED point sources |
| `surfaces` | Array of reflective/absorptive surfaces |
| `detectors` | Array of detector planes |
| `angular_distributions` | Dict of named I(θ) profiles |

---

## Architecture Overview

```
core/   ← pure Python dataclasses, no GUI
sim/    ← NumPy ray tracer, no GUI
io/     ← file I/O, geometry builder, presets (no GUI)
gui/    ← PySide6 UI (imports core/sim/io)
```

`core/`, `sim/`, and `io/` have no Qt dependency — they can be used standalone or in scripts.

---

## Roadmap

- [ ] Export heatmap as PNG / KPI table as CSV
- [ ] Quality presets (Quick / Standard / High)
- [ ] KPI dashboard (uniformity, efficiency proxy)
- [ ] Parameter sweep runner
- [ ] IES / LDT angular distribution import
- [ ] Numba / multiprocessing acceleration
- [ ] Edge-lit / LGP simulation module

---

## License

*Add license here.*
