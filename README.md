# Blu Optical Simulation

A desktop application for optical simulation of backlight units (BLU), built for display engineers who need fast design iteration. Uses Monte Carlo ray tracing with a modern PySide6 GUI.

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-orange)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey)

---

## Quick Start (Windows — no installation required)

1. Go to the [**Releases**](../../releases) page and download the latest `BluOpticalSim-windows.zip`
2. Extract the zip anywhere on your PC
3. Double-click **`BluOpticalSim.exe`**

No Python, no installation, no admin rights needed.

---

## Features

### Simulation Engine
- **Monte Carlo ray tracing** — physically-based light propagation through reflective cavities
- **Angular distribution support** — isotropic, Lambertian, batwing, or custom I(theta) profiles
- **IES / EULUMDAT import** — load measured photometric data from .ies and .ldt files
- **Haze / scatter proxy** — forward-scatter cone with configurable half-angle
- **Multiprocessing** — parallel per-source tracing for multi-core speedup
- **Numba JIT acceleration** — optional 10-50x speedup for tracer inner loops (graceful NumPy fallback)

### Geometry & Scene
- **Geometry builder** — parametric direct-lit cavity with tilted walls, diffuser layer, and film placeholders
- **LED grid builder** — uniform grid by count or pitch, with 2D drag-and-drop layout editor
- **Arbitrary surface orientations** — general u-axis / v-axis representation for all geometry
- **Built-in presets** — Simple Box (50x50x20 mm) and Automotive Cluster (120x60x10 mm, 4x2 grid)

### Analysis & Output
- **2D heatmap** with interactive ROI and live statistics
- **KPI dashboard** — uniformity, efficiency, hotspot ratio, edge-center ratio, CV, NRMSE, design score
- **Section views** — X/Y cross-sections, flux histogram, cumulative distribution
- **Parameter sweep** — single or 2-parameter grid sweep with sortable results and Pareto front
- **Export** — PNG, KPI CSV, grid CSV, self-contained HTML report, batch ZIP

### GUI
- **3D viewport** — wireframe, solid, and transparent view modes with material-based coloring
- **Object tree** with per-source enable/disable, bin tolerance, current scaling, and thermal derating
- **Variant cloning** and side-by-side comparison dialog
- **Design history** snapshots
- **Measurement tool** — point-to-point distance in 3D
- **Ray path visualization** — sampled ray trajectories overlaid in the 3D view

---

## Developer Setup

### Requirements

- Python 3.12+
- Windows 10/11

### Install dependencies

```bash
git clone https://github.com/Ozgur-al/blu-optical-simulation.git
cd blu-optical-simulation
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

```bash
pip install pyinstaller
python build_exe.py --clean --zip
```

The output appears in `dist/BluOpticalSim/`. The `--zip` flag produces a ready-to-distribute archive.

---

## Usage Guide

### 1. Create or load a scene

- **File → New Project** to start from scratch
- **Presets** menu to load a ready-made scene
- **File → Open Project** to load a previously saved `.json` file

### 2. Build geometry

- Open **Tools → Geometry Builder** to generate a reflective cavity and LED grid in one step
- Adjust cavity dimensions, wall angles, LED pitch/count, and material assignments

### 3. Edit objects

- Click any object in the **Scene Tree** (left panel) to select it
- Edit its properties in the **Properties Panel** (right panel)

### 4. Manage angular distributions

- Open the **Angular Dist.** tab to import LED I(theta) data from CSV, TXT, IES, or LDT files
- Built-in profiles (isotropic, lambertian, batwing) are always available
- Assign a distribution to each LED source in its properties form

### 5. Run simulation

- Click **Run** in the status bar
- Progress is shown in the progress bar
- When complete, the **Heatmap** tab updates automatically and ray paths appear in 3D

### 6. Analyze results

- **Heatmap tab** — 2D flux distribution with interactive ROI and full KPI dashboard
- **Plot tab** — cross-section views, histogram, and CDF analysis
- **3D view** — ray path preview overlaid on the scene
- **Parameter Sweep** — explore design space across one or two parameters

### 7. Export & save

- **File → Save Project** writes a `.json` file you can share or reload
- Export heatmap PNG, KPI CSV, grid CSV, or a self-contained HTML report
- **File → Batch Export** packages everything into a single ZIP

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

## Architecture

```
backlight_sim/
├── core/       # Pure data models (dataclasses) — no GUI imports
├── sim/        # Monte Carlo ray tracer + sampling — depends only on core/ + numpy
├── io/         # File I/O, scene builders, report generation — no GUI imports
├── gui/        # PySide6 UI (3D viewport, heatmap, property editors, dialogs)
├── data/       # Built-in angular distribution CSV profiles
└── tests/      # pytest test suite (20 tests)
```

**Key design rule**: `core/`, `sim/`, and `io/` never import PySide6, keeping the simulation engine headless and independently testable.

| Component | Library |
|-----------|---------|
| GUI framework | PySide6 (Qt for Python) |
| 3D viewport | pyqtgraph.opengl |
| 2D heatmap / plots | pyqtgraph |
| Numerics | NumPy |
| JIT (optional) | Numba |
| Testing | pytest |

---

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE.md).

You are free to use, modify, and share this software for **noncommercial purposes only**. See the full license text for details.
