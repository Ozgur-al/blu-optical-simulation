# Architecture

**Analysis Date:** 2026-03-14

## Pattern Overview

**Overall:** Layered architecture with strict separation of concerns. Three headless computation layers (`core`, `sim`, `io`) feed into a PySide6 desktop GUI (`gui`). The architecture enforces a unidirectional dependency flow: GUI depends on all lower layers, but lower layers never import from `gui` or PySide6.

**Key Characteristics:**
- **Headless core modules** — `core/`, `sim/`, and `io/` are 100% PySide6-free, allowing use in command-line tools and testing
- **Dataclass-driven data model** — All scene objects (`Project`, `Rectangle`, `PointSource`, `DetectorSurface`, etc.) are frozen dataclasses with numpy array backing
- **Monte Carlo vectorization** — `RayTracer` uses semi-vectorized numpy operations per bounce, with Python loop over bounces and surfaces
- **GUI threading isolation** — Simulation runs in `SimulationThread(QThread)` off the main thread; results posted back via Qt signals
- **Extensible plugin patterns** — Angular distributions, spectral profiles, and optical properties stored as dictionaries for plugin-like registration

## Layers

**Core (`backlight_sim/core/`):**
- Purpose: Scene description and data model (no physics, no simulation)
- Location: `backlight_sim/core/`
- Contains: Dataclasses for geometry, materials, sources, detectors, and project metadata
- Depends on: NumPy only
- Used by: `sim/`, `io/`, `gui/`

**Simulation (`backlight_sim/sim/`):**
- Purpose: Monte Carlo ray tracing engine and sampling utilities
- Location: `backlight_sim/sim/`
- Contains: `RayTracer` (main engine), `sampling.py` (direction sampling), `spectral.py` (wavelength/color utilities)
- Depends on: `core/`, NumPy
- Used by: `gui/` (via `SimulationThread`)

**I/O (`backlight_sim/io/`):**
- Purpose: Project persistence, scene construction, and file format handling
- Location: `backlight_sim/io/`
- Contains: JSON serialization (`project_io.py`), geometry builders (`geometry_builder.py`), format parsers (`ies_parser.py`), reporting (`report.py`), presets (`presets.py`)
- Depends on: `core/`, NumPy
- Used by: `gui/` only

**GUI (`backlight_sim/gui/`):**
- Purpose: PySide6 desktop application interface
- Location: `backlight_sim/gui/`
- Contains: Main window, panels (3D viewport, heatmap, properties), dialogs, and workflow controllers
- Depends on: All lower layers + PySide6 + PyQtGraph
- Used by: `app.py` only

## Data Flow

**Simulation Flow:**

1. User interacts with GUI (adjusts parameters via `PropertiesPanel`)
2. `MainWindow` owns the `Project` dataclass (mutable in-memory representation)
3. User clicks "Run Simulation"
4. `MainWindow` spawns `SimulationThread(QThread)`, passing a copy of `Project`
5. `SimulationThread` instantiates `RayTracer(project)` and calls `tracer.run(progress_callback=...)`
6. `RayTracer._run_single()` or `RayTracer._run_multiprocess()` executes:
   - For each enabled source: sample rays (directions from `sampling.py`)
   - For each bounce (up to `max_bounces`):
     - Vectorized ray-surface intersection (`_intersect_rays_plane()`)
     - Closest-hit determination
     - Material behavior (reflect/absorb/transmit) via `_resolve_material_behavior()`
     - Wavelength-dependent color accumulation (if spectral)
   - Accumulate hits into detector grids
7. Returns `SimulationResult` (contains all detector grids + metadata)
8. `SimulationThread.finished_sim` signal emits `SimulationResult` back to `MainWindow`
9. `MainWindow` updates visualizations:
   - `HeatmapPanel` refreshes 2D detector display
   - `Viewport3D` optionally renders ray paths
   - `PlotTab` recomputes analysis charts
   - `Receiver3DWidget` visualizes 3D receiver sphere results

**File I/O Flow:**

1. User selects File > Save Project
2. `MainWindow` calls `save_project(project, path)` from `io/project_io.py`
3. Serializes all numpy arrays to lists, maintains compatibility via `.get(key, default)` pattern
4. On Load: `load_project(path)` reconstructs numpy arrays and dataclass instances

**State Management:**

- **Single source of truth**: `MainWindow._project` (a `Project` instance)
- **Immutable during simulation**: A copy is passed to `RayTracer`; original remains editable while simulation runs
- **Change notification**: Object tree selection changes (`object_selected` / `multi_selected` signals from `ObjectTree`) trigger `PropertiesPanel` updates
- **Scene visualization**: Any parameter change calls `_refresh_all()` or targeted refresh methods to update `Viewport3D`

## Key Abstractions

**Rectangle (Arbitrarily-Oriented 3D Plane):**
- Purpose: Unified geometry for both scene surfaces and detector surfaces
- Examples: `backlight_sim/core/geometry.py`, `backlight_sim/core/detectors.py` (both use the same pattern)
- Pattern:
  - Internal representation: `center`, `u_axis`, `v_axis` (orthonormal in-plane axes)
  - Outward normal: `cross(u_axis, v_axis)`
  - Factory: `Rectangle.axis_aligned(name, center, size, normal_axis, normal_sign, material_name)` for convenience
  - Properties: `dominant_normal_axis`, `dominant_normal_sign` for UI approximation
  - Ray intersection: General `_intersect_rays_plane(origins, directions, plane)` computes `t`, checks local coords `|u_coord| ≤ width/2` and `|v_coord| ≤ height/2`

**Material / OpticalProperties Duality:**
- Purpose: Support both legacy per-material properties and new per-surface coatings
- Pattern:
  - `Material` (backlight_sim/core/materials.py): Bulk material definition (name, surface_type, reflectance, absorption, transmittance, is_diffuse, haze, refractive_index)
  - `OpticalProperties` (backlight_sim/core/materials.py): Per-surface coating layer (same fields as Material, but stored separately)
  - Resolution order: `Rectangle.optical_properties_name` (if set) → use `Project.optical_properties[name]` else fall back to `Rectangle.material_name` → use `Project.materials[name]`
  - Backward compatibility: Old projects using only materials work unchanged; new code can override per-surface

**DetectorSurface vs SphereDetector:**
- Purpose: Support multiple receiver geometries
- Pattern:
  - `DetectorSurface`: Planar receiver with 2D grid (same u_axis/v_axis pattern as Rectangle)
  - `SphereDetector`: Spherical receiver with spherical bin grid (n_phi × n_theta resolution)
  - Both accumulate ray hits independently in `SimulationResult`

**Project Container:**
- Purpose: Immutable scene definition for serialization and simulation
- Fields: `name`, `sources`, `surfaces`, `materials`, `optical_properties`, `detectors`, `sphere_detectors`, `angular_distributions`, `settings`
- Angular distributions: Dict[str, Dict[str, list[float]]] — keyed by distribution name, contains `{"theta_deg": [...], "intensity": [...]}`
- Settings: `SimulationSettings` dataclass with `rays_per_source`, `max_bounces`, `energy_threshold`, `random_seed`, `record_ray_paths`, `use_multiprocessing`

**Ray Sampling Plugins:**
- Purpose: Pluggable ray direction sampling without code changes
- Pattern in `sim/sampling.py`:
  - `sample_isotropic(n, rng)` → uniform sphere
  - `sample_lambertian(n, normal, rng)` → cosine-weighted hemisphere
  - `sample_angular_distribution(n, normal, theta_deg, intensity, rng)` → user-supplied I(θ) profile via CDF inversion
  - Sources reference distributions by name; tracer looks up `Project.angular_distributions[source.distribution]` at runtime

**Spectral Representation:**
- Purpose: Wavelength-dependent color and flux tracking
- Pattern in `sim/spectral.py` and `sim/tracer.py`:
  - Each ray carries a sampled wavelength (optional, only if spectral sources present)
  - Built-in SPDs: `"white"`, `"warm_white"`, `"cool_white"`, `"mono_<nm>"` (e.g., `"mono_470"` for blue)
  - CIE 1931 2-degree observer lookup for XYZ → RGB conversion
  - Detector grids support optional `grid_rgb` and `grid_spectral` channels (added only if needed)

## Entry Points

**App Launch (`app.py`):**
- Location: `/g/blu-optical-simulation/app.py`
- Triggers: User runs `python app.py` or built executable
- Responsibilities: Create `QApplication`, instantiate `MainWindow()`, enter event loop

**Main Window (`gui/main_window.py` :: `MainWindow`):**
- Location: `backlight_sim/gui/main_window.py` class `MainWindow`
- Triggers: Called by `app.py` at startup
- Responsibilities:
  - Owns the mutable `Project` instance (`self._project`)
  - Assembles UI panels: `ObjectTree` (left), viewport/heatmap/plot tabs (center), `PropertiesPanel` (right)
  - Wires signals/slots between panels
  - Handles menu actions (File, Presets, Simulation, Variants, History, Tools, View)
  - Spawns `SimulationThread` on Run; receives results via `finished_sim` signal
  - Manages undo/redo via design history (`_history` list)

**Simulation Thread (`gui/main_window.py` :: `SimulationThread`):**
- Location: `backlight_sim/gui/main_window.py` class `SimulationThread(QThread)`
- Triggers: Spawned by `MainWindow.run_simulation()`
- Responsibilities:
  - Create `RayTracer(project)` instance
  - Call `tracer.run(progress_callback=self.progress.emit)` off-main-thread
  - Emit `progress` signal (float 0–1) for progress bar
  - Emit `finished_sim` signal with `SimulationResult` when done

**Ray Tracer Entry (`sim/tracer.py` :: `RayTracer.run()`):**
- Location: `backlight_sim/sim/tracer.py` method `RayTracer.run(progress_callback)`
- Triggers: Called by `SimulationThread.run()`
- Responsibilities:
  - Choose execution path: `_run_single()` or `_run_multiprocess()`
  - Emit ray sampling, bouncing, and accumulation
  - Return `SimulationResult` with all detector grids

## Error Handling

**Strategy:** Defensive validation at layer boundaries with early returns; no exceptions raised for data validation (invalid inputs logged and handled gracefully).

**Patterns:**

- **Invalid geometry**: If `u_axis` and `v_axis` are colinear, ray-plane intersection will have zero denominator; handled via `if denom != 0` check with silent skip
- **Missing angular distribution**: If source references distribution not in `Project.angular_distributions`, tracer falls back to isotropic silently
- **Invalid material reference**: If `Rectangle.material_name` not in `Project.materials`, UI will display error message; tracer will skip material lookup and treat as absorber
- **Simulation cancellation**: `RayTracer._cancelled` flag checked at source loop; if set, breaks early and returns partial result
- **File I/O**: `load_project()` uses `.get()` pattern for missing keys; JSON parsing wrapped in try/except with user message box

## Cross-Cutting Concerns

**Logging:** `gui/main_window.py` contains a `LogDock` (text edit) that accumulates status messages. High-level events (simulation start, completion, errors) logged to dock.

**Validation:**
- `core/` dataclasses use `__post_init__` to normalize vectors (e.g., u_axis and v_axis are auto-normalized)
- `PropertiesPanel` enforces range constraints (spin boxes) before updating the project
- No blanket validation layer; each module assumes preconditions are met

**Authentication:** Not applicable (single-user desktop app).

**Performance Monitoring:**
- `RayTracer.run()` returns `SimulationResult.total_emitted_flux` and `escaped_flux` for energy balance checks
- `HeatmapPanel` computes uniformity statistics and design score on result display
- `PlotTab` generates section views and histograms for post-sim analysis

---

*Architecture analysis: 2026-03-14*
