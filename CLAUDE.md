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
├── core/                   # Pure data models (dataclasses), no GUI imports
│   ├── geometry.py         # Rectangle — arbitrarily-oriented rect in 3D (u_axis/v_axis)
│   ├── materials.py        # Material (reflector/absorber/diffuser + color + haze)
│   ├── sources.py          # PointSource (position, flux, direction, distribution, tolerance, thermal)
│   ├── detectors.py        # DetectorSurface, DetectorResult, SimulationResult
│   └── project_model.py    # Project container + SimulationSettings
├── sim/                    # Simulation engine — depends only on core/ + numpy
│   ├── sampling.py         # Ray sampling: isotropic, lambertian, angular distribution, specular, haze scatter
│   └── tracer.py           # RayTracer — Monte Carlo engine (single-thread + multiprocessing)
├── io/                     # File I/O and scene construction — no GUI imports
│   ├── project_io.py       # JSON project save/load (save_project / load_project)
│   ├── geometry_builder.py # build_cavity() + build_led_grid() + build_optical_stack() — pure logic
│   ├── presets.py          # Built-in scene presets (Simple Box, Automotive Cluster)
│   ├── angular_distributions.py  # Default profile CSVs + load/merge helpers
│   ├── ies_parser.py       # IES (IESNA LM-63) and EULUMDAT (.ldt) file parsers
│   ├── report.py           # HTML report generator from simulation results
│   └── batch_export.py     # ZIP batch export (project + KPIs + grids + report)
├── gui/                    # PySide6 UI
│   ├── main_window.py      # MainWindow + SimulationThread (QThread)
│   ├── object_tree.py      # Scene object tree (QTreeWidget)
│   ├── properties_panel.py # Property editor forms (QStackedWidget)
│   ├── viewport_3d.py      # 3D OpenGL scene preview (wireframe/solid/transparent)
│   ├── heatmap_panel.py    # 2D detector result display + KPI dashboard + uniformity stats
│   ├── angular_distribution_panel.py  # Angular distribution tab (import/export/edit/plot)
│   ├── geometry_builder.py # GUI dialog wrapping io/geometry_builder
│   ├── parameter_sweep_dialog.py  # Single/multi-parameter sweep dialog + batch runner
│   ├── comparison_dialog.py  # Side-by-side project variant comparison
│   ├── plot_tab.py           # Analysis plots: section views, histograms, CDF
│   ├── led_layout_editor.py  # 2D drag-and-drop LED positioning (top view)
│   └── measurement_dialog.py  # Point-to-point measurement dialog
├── data/
│   └── angular_distributions/  # Built-in CSV profiles: isotropic, lambertian, batwing
└── tests/
    └── test_tracer.py      # Core simulation tests (20 tests)
app.py                      # Entry point
build_exe.py                # PyInstaller build script (python build_exe.py [--clean] [--zip])
requirements.txt            # PySide6, pyqtgraph, numpy, PyOpenGL, pytest
PLAN.MD                     # Product feature plan
PLAN_TASKS.md               # Feature implementation status checklist
CODEX.md                    # Session-by-session change log
```

**Key constraint**: `core/`, `sim/`, and `io/` must never import PySide6. The GUI builds a `Project` dataclass, passes it to `RayTracer.run()`, and gets back a `SimulationResult`.

## Commands

```bash
pip install -r requirements.txt
python app.py
pytest backlight_sim/tests/
pytest backlight_sim/tests/test_tracer.py::test_function_name

# Build standalone Windows executable (requires: pip install pyinstaller)
python build_exe.py          # basic build
python build_exe.py --clean --zip  # clean build + zip for distribution
```

## Core Data Model

### `core/geometry.py` — `Rectangle`
Arbitrarily-oriented rectangle in 3D space using two orthonormal in-plane axes:
- `center: np.ndarray` — world-space center
- `u_axis: np.ndarray` — normalized local x-axis of the plane
- `v_axis: np.ndarray` — normalized local y-axis of the plane
- `size: tuple[float, float]` — (width along u, height along v)
- `material_name: str`
- `normal` property — `cross(u_axis, v_axis)`
- Factory `Rectangle.axis_aligned(...)` — convenience constructor for the 6 axis-aligned orientations

### `core/materials.py` — `Material`
- `surface_type: str` — `"reflector"` | `"absorber"` | `"diffuser"`
- `reflectance`, `absorption`, `transmittance` — optical properties
- `is_diffuse: bool` — `True` = Lambertian, `False` = specular reflection
- `haze: float` — forward-scatter half-angle in degrees (0 = no haze, specular only)
- `color: tuple[float, float, float]` — RGB for 3D viewport rendering (auto-defaults per type)

### `core/sources.py` — `PointSource`
- `position: np.ndarray`, `flux: float`, `direction: np.ndarray`
- `distribution: str` — `"isotropic"` | `"lambertian"` | any key in `project.angular_distributions`
- `enabled: bool` — when `False`, the tracer skips this source (grey in scene tree)
- `flux_tolerance: float` — ±% bin tolerance (random per-source variation)
- `current_mA: float`, `flux_per_mA: float` — current-dependent flux scaling
- `thermal_derate: float` — thermal derating multiplier (0–1)
- `effective_flux` property — computes flux after current scaling and thermal derating

### `core/detectors.py`
- `DetectorSurface` — receiver plane with `u_axis`/`v_axis`/`size`/`resolution` — shares the same geometry API as `Rectangle`
- `DetectorResult` — `grid: np.ndarray` (ny, nx), `total_hits`, `total_flux`
- `SimulationResult` — `detectors: dict[str, DetectorResult]`, `ray_paths: list[list[np.ndarray]]`, `escaped_flux: float` (energy that left the scene without hitting anything)

### `core/project_model.py` — `Project`
```python
@dataclass
class Project:
    name: str
    sources: list[PointSource]
    surfaces: list[Rectangle]
    materials: dict[str, Material]
    detectors: list[DetectorSurface]
    angular_distributions: dict[str, dict[str, list[float]]]  # name → {theta_deg, intensity}
    settings: SimulationSettings
```

`SimulationSettings` fields: `rays_per_source`, `max_bounces`, `energy_threshold`, `random_seed`, `record_ray_paths`, `distance_unit`, `flux_unit`, `angle_unit`, `use_multiprocessing`.

## Simulation Engine (`sim/`)

### `sim/tracer.py` — `RayTracer`
Semi-vectorized Monte Carlo engine:
1. **Emit** rays from each `PointSource` according to its `distribution` (numpy arrays for entire batch)
2. **Bounce loop** (Python loop over max_bounces):
   - Intersect all active rays against all surfaces and detectors via `_intersect_rays_plane()`
   - Closest hit wins (t-value comparison)
   - **Detector hit**: accumulate `weight` into `grid` bin → ray dies
   - **Surface hit**: apply material behavior (reflect/absorb/transmit), offset origin by `1e-6 × normal`
   - **Missed**: ray dies
   - Energy threshold kill: rays with `weight < energy_threshold` are culled
3. **Path recording**: first `n_record` rays of the first source are traced for visualization
4. **Multiprocessing mode**: when `use_multiprocessing` is enabled, each source runs in a separate process via `ProcessPoolExecutor`; detector grids are merged after all sources complete. Path recording is disabled in MP mode.

**Intersection math** (`_intersect_rays_plane`): general ray-plane for arbitrary orientations.
`denom = d · n`, `t = (n·c - n·o) / denom`, then check `|u_coord| ≤ hw` and `|v_coord| ≤ hh`.

**Diffuser transmission**: per-ray stochastic roll against `transmittance`. Transmitted rays continue through the plane; reflected rays bounce Lambertian.

**Specular reflection** (`_reflect_batch`): batched, but falls back to per-ray loop for diffuse normals with n ≤ 32 to handle varied normals; uses majority normal approximation for larger batches.

### `sim/sampling.py`
- `sample_isotropic(n, rng)` — uniform sphere sampling
- `sample_lambertian(n, normal, rng)` — cosine-weighted hemisphere (Malley's method)
- `sample_angular_distribution(n, normal, theta_deg, intensity, rng)` — CDF inversion from user I(θ) data (2048-point interpolation grid, weighted by `sin(θ)`)
- `reflect_specular(directions, normal)` — vectorized specular reflection
- `sample_diffuse_reflection(n, normal, rng)` — alias for `sample_lambertian`
- `scatter_haze(directions, half_angle_deg, rng)` — perturb directions within a cone for haze scattering

## I/O Layer (`io/`)

### `io/project_io.py`
- `save_project(project, path)` → JSON file
- `load_project(path)` → `Project`
- All numpy arrays serialized as plain lists; `angular_distributions` stored as-is.

### `io/geometry_builder.py`
- `build_cavity(...)` — generates floor + 4 tilted walls; separate X/Y wall angles
- `build_led_grid(...)` — uniform LED grid; if `count_x`/`count_y` given, pitch is auto-computed
- `build_optical_stack(...)` — adds diffuser and film placeholder surfaces at specified Z heights

### `io/ies_parser.py`
- `load_ies(path)` — parse IESNA LM-63 (.ies) files; averages over C-planes to produce I(θ) profile
- `load_ldt(path)` — parse EULUMDAT (.ldt) files
- `load_ies_or_ldt(path)` — auto-detect by extension

### `io/report.py`
- `generate_html_report(project, result, path)` — self-contained HTML with embedded heatmap PNG (via matplotlib), KPIs, uniformity, and energy balance

### `io/presets.py`
- `PRESETS` dict with two built-in factory functions:
  - `preset_simple_box()` — 50×50×20 mm, 1 LED, lambertian
  - `preset_automotive_cluster()` — 120×60×10 mm, 4×2 LED grid, 10° wall angle

### `io/angular_distributions.py`
- Three built-in profiles: `isotropic`, `lambertian`, `batwing` (as CSV files under `data/`)
- `load_default_profiles()` — loads all CSV files from `data/angular_distributions/`
- `merge_default_profiles(project)` — adds defaults to a project without overwriting existing
- `load_profile_csv(path)` — parse user-supplied CSV/TXT (columns: `theta_deg`, `intensity`)

## GUI Layer (`gui/`)

### `gui/main_window.py` — `MainWindow` + `SimulationThread`
- Central hub: owns the `Project` object, wires all panels together
- **Menus**: File (New/Open/Save/Clone as Variant), Presets, View (wireframe/solid/transparent + camera presets), Simulation (Run/Cancel/Parameter Sweep), Variants, History, Tools (Geometry Builder, Measurement)
- **Layout**: `QSplitter` with object tree (left), 3D viewport + heatmap tabs (center), properties panel (right)
- **`SimulationThread(QThread)`**: runs `RayTracer.run()` off the main thread; emits `progress_signal(float)` via callback; posts `result_signal(SimulationResult)` on completion
- Run/Cancel buttons in status bar

### `gui/object_tree.py`
- `QTreeWidget` with four top-level categories: Sources, Surfaces, Materials, Detectors
- Selection changes drive the properties panel

### `gui/properties_panel.py`
- `QStackedWidget` with per-type forms: SourceForm, SurfaceForm, MaterialForm, DetectorForm, SimSettingsForm
- Forms use `_loading` guard + `blockSignals()` to prevent value-leak on selection changes
- Surface/detector forms expose orientation as rotation angles (X/Y/Z) around each axis

### `gui/viewport_3d.py`
- `pyqtgraph.opengl.GLViewWidget` for 3D preview
- View modes: wireframe, solid, transparent
- Selection highlighting for selected objects
- Material-based surface coloring using `Material.color`
- XYZ reference axes and reference grid at world origin
- Camera preset views: XY+/−, YZ+/−, XZ+/−
- Ray path display after simulation

### `gui/heatmap_panel.py`
- 2D heatmap of `DetectorResult.grid` using pyqtgraph `ImageItem` + `ColorBarItem`
- Interactive ROI: draggable rectangle with live avg/min/max/uniformity stats
- Full KPI dashboard: grid statistics (avg/peak/min/std/CV/hotspot/edge-center), uniformity at multiple center fractions, energy balance (efficiency/absorbed/escaped/LED count), error metrics (NRMSE, MAD), design score
- Export buttons: PNG, KPI CSV, Grid CSV, HTML Report

### `gui/angular_distribution_panel.py`
- Tab for managing angular distributions
- Table-based editing of (theta_deg, intensity) point pairs
- Import CSV/TXT/IES/LDT, export selected, duplicate, delete
- Normalization buttons (peak=1, flux=1, min-max)
- Plot: theta vs intensity using pyqtgraph

### `gui/parameter_sweep_dialog.py`
- Single-parameter sweep: source flux, reflector reflectance, diffuser transmittance, max bounces, rays per source
- 2-parameter grid sweep option via `_MultiSweepThread`
- Column sorting, text filter on results table
- Runs N steps sequentially in a background QThread; live-updating results table and KPI plot
- Sweep can be cancelled mid-run

### `gui/comparison_dialog.py`
- Side-by-side KPI comparison of current project vs a saved variant
- Runs quick simulations (1k rays) on both and presents results in a table

### `gui/plot_tab.py`
- Dedicated analysis plots tab with 6 chart types
- X/Y cross-section views (center or custom pixel position)
- Flux histogram and cumulative distribution function

### `gui/measurement_dialog.py`
- Point-to-point measurement: dX, dY, dZ, direct distance
- Can auto-fill from selected object center

## Architecture Notes

- **Geometry**: `Rectangle` supports arbitrary orientations via `u_axis`/`v_axis`. The `axis_aligned()` factory covers the common case. A box = 1 floor + 4 walls (tilted walls shift center outward).
- **Coordinate system**: Z-up. Floor at z=0, detector at z=depth. LEDs placed slightly above floor (z=0.5 mm by default).
- **Ray tracer**: Semi-vectorized — numpy arrays for all rays per bounce, Python loop over bounces and surfaces. Performance scales with `rays_per_source × max_bounces × (len(surfaces) + len(detectors))`.
- **Self-intersection avoidance**: after a bounce, ray origin is offset by `1e-6` along the oriented surface normal.
- **Detectors terminate rays**: when a ray hits a `DetectorSurface`, its weight is accumulated into a 2D grid bin and the ray dies.
- **GUI threading**: `SimulationThread(QThread)` runs the tracer off-main-thread. Progress callback emits a Qt signal to update the progress bar.
- **Angular distributions**: stored in `Project.angular_distributions` as `{name: {theta_deg: [...], intensity: [...]}}`. The tracer looks up the source's `distribution` string as a key; falls back to isotropic if not found.
- **Material color**: used only for 3D viewport rendering; default colors are blue (reflector), red (absorber), green (diffuser).

## Development Conventions

- `core/`, `sim/`, and `io/` must never import PySide6 — keep them headless/testable.
- When adding new geometry types, implement the `u_axis`/`v_axis`/`normal` pattern consistent with `Rectangle` and `DetectorSurface`.
- When adding new simulation outputs, extend `SimulationResult` (not `DetectorResult`) to keep the per-detector API stable.
- Project JSON format: all numpy arrays as plain lists. Add new fields with `.get(key, default)` to keep backwards compatibility with older save files.
- Run `pytest backlight_sim/tests/` (currently 20 tests) before committing simulation or core changes.
- Session changes should be appended to `CODEX.md` with a session ID, title, files touched, and validation notes.

## Feature Status Summary

**98 of 110 tasks Done, 0 Partial, 12 Phase 2+** (see `PLAN_TASKS.md` for full checklist).

Implemented: project save/load (JSON), geometry builder with wall angles + diffuser distance + film placeholders, LED grid builder with count/pitch modes + 2D drag-and-drop layout editor, two scene presets, angular distribution import/edit/export with normalization + IES/LDT import, 3D viewport with selection + material colors + view modes, full KPI dashboard (uniformity/efficiency/hotspot/edge-center/error metrics/design score), export PNG/KPI CSV/Grid CSV/HTML Report/Batch ZIP, quality presets (Quick/Standard/High), single + multi-parameter sweep with sort/filter + Pareto front, LED enable/disable + bin tolerance + current scaling + thermal derating, peak cd conversion, variant cloning + comparison dialog, design history snapshots, loss breakdown (absorbed/escaped), log dock panel, measurement tool, interactive ROI on heatmap, section view + analysis plot tab, haze/scatter proxy, multiprocessing.

Phase 2+ (not implemented): edge-lit/LGP engine, Numba acceleration, adaptive sampling/BVH, non-rectangular geometry, CAD/DXF import, spectral/color/BRDF, refractive index/TIR, temperature dependence, far-field detector, Pareto optimization.
