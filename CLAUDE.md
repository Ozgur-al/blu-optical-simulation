# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Blu Optical Simulation** — a Python desktop application for optical simulation of backlight units (BLU), targeting engineers who need fast design iteration. Uses Monte Carlo ray tracing with a PySide6 GUI.

## Tech Stack

- **GUI**: PySide6 (Qt for Python)
- **3D Viewport**: pyqtgraph.opengl (GLViewWidget)
- **2D Heatmap**: pyqtgraph (ImageItem + ColorBarItem)
- **Math**: NumPy
- **Testing**: pytest

## Package Structure

```
backlight_sim/
├── core/           # Pure data models (dataclasses), no GUI imports
│   ├── geometry.py      # Rectangle (axis-aligned rect in 3D)
│   ├── materials.py     # Material (reflector/absorber/diffuser properties)
│   ├── sources.py       # PointSource (position, flux, distribution)
│   ├── detectors.py     # DetectorSurface + DetectorResult
│   └── project_model.py # Project container, SimulationSettings
├── sim/            # Simulation engine, depends only on core/ + numpy
│   ├── sampling.py      # Ray direction sampling (isotropic, lambertian, specular)
│   └── tracer.py        # RayTracer — Monte Carlo engine
├── gui/            # PySide6 UI
│   ├── main_window.py   # MainWindow, SimulationThread (QThread)
│   ├── object_tree.py   # Scene object tree (QTreeWidget)
│   ├── properties_panel.py # Property editor forms (QStackedWidget)
│   ├── viewport_3d.py   # 3D OpenGL scene preview
│   └── heatmap_panel.py # 2D detector result display
└── tests/
    └── test_tracer.py   # Core simulation tests
app.py              # Entry point
```

**Key constraint**: `core/` and `sim/` must never import PySide6. The GUI builds a `Project` dataclass, passes it to `RayTracer.run()`, gets back `DetectorResult` objects.

## Commands

```bash
pip install -r requirements.txt
python app.py
pytest backlight_sim/tests/
pytest backlight_sim/tests/test_tracer.py::test_function_name
```

## Architecture Notes

- **Geometry**: Only axis-aligned rectangles (`Rectangle` in geometry.py). A box = 6 rectangles. Intersection is plane-ray math: `t = (plane_pos - origin[axis]) / dir[axis]` + bounds check.
- **Ray tracer** (`sim/tracer.py`): Semi-vectorized — numpy arrays for all rays per bounce, Python loop over bounces and surfaces. Rays carry a `weight` (energy). Surfaces absorb/reflect/transmit based on `Material` properties.
- **Detectors terminate rays**: when a ray hits a `DetectorSurface`, its weight is accumulated into a 2D grid bin and the ray dies.
- **GUI threading**: `SimulationThread(QThread)` runs the tracer off-main-thread. Progress callback emits a signal to update the progress bar.
- **Self-intersection avoidance**: after a bounce, ray origin is offset by `1e-6` along the surface normal.

## Roadmap (not yet implemented)

- Project save/load (JSON)
- LED angular distribution import from CSV
- KPI dashboard (uniformity, efficiency)
- Parameter sweep tools
- Edge-lit / LGP simulation engine
- Numba acceleration, multiprocessing
