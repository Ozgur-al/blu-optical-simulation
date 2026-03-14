---
phase: 05-ui-rewamp
plan: 01
status: complete
started: "2026-03-15"
completed: "2026-03-15"
commits:
  - 82eb8ea
  - 3db662e
  - 9bb33f0
---

## What was built

Dark theme foundation with teal accent (#00bcd4) and complete layout rework from QDockWidget panels to a splitter+tab architecture.

### Layout
- Left sidebar: QSplitter with ObjectTree (top) + PropertiesPanel (bottom)
- Center: QTabWidget with closable, reorderable tabs
- Default tabs: "3D View" and "Heatmap" (non-closable)
- Window menu: open any panel as a new tab (Plots, Angular Dist., Far-field, 3D Receiver, Spectral Data, BSDF, Convergence, Log)
- Top toolbar: New, Open, Save | Run, Cancel | Add LED, Add Surface, Add Detector, Add SolidBox

### Theme
- `backlight_sim/gui/theme/__init__.py`: palette constants + `apply_dark_theme(app)`
- `backlight_sim/gui/theme/dark.qss`: comprehensive QSS covering all widget types
- pyqtgraph configured for dark background via `pg.setConfigOption`
- GLViewWidget forced to dark background (OpenGL ignores QSS)

### Bug fixes included
- Ray path collection was outside source loop — only last source's paths recorded (tracer.py indentation fix)
- Adaptive convergence tracked cumulative flux — later sources saw artificially low CV% and stopped early (now tracks per-source delta)
- QFont::setPointSize warnings from px-based font sizes (changed to pt)
- ObjectTree branch indicators rendered as black boxes (replaced with Unicode ▼/▶ arrows)

## key-files

### created
- `backlight_sim/gui/theme/__init__.py`
- `backlight_sim/gui/theme/dark.qss`

### modified
- `backlight_sim/gui/main_window.py`
- `backlight_sim/gui/object_tree.py`
- `backlight_sim/gui/viewport_3d.py`
- `backlight_sim/sim/tracer.py`
- `app.py`

## Deviations

- **Layout changed from QDockWidget to QSplitter+QTabWidget** — user feedback during checkpoint: docks were hard to re-dock, too many panels cluttering the right side. Switched to fixed left sidebar + tabbed center area per user direction.
- **Bug fixes bundled** — ray path and convergence bugs discovered during testing were fixed in this plan since they affected the user's ability to verify the UI.

## Self-Check: PASSED
- Application launches with dark theme ✓
- 3D View and Heatmap tabs present ✓
- Scene tree + Properties in left sidebar ✓
- Toolbar with all expected buttons ✓
- Window menu opens panels as tabs ✓
- 101 tracer tests pass ✓
