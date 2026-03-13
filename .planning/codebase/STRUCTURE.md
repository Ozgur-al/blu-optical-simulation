# Codebase Structure

**Analysis Date:** 2026-03-14

## Directory Layout

```
G:/blu-optical-simulation/
├── app.py                       # Entry point (creates QApplication, MainWindow)
├── build_exe.py                 # PyInstaller build script
├── requirements.txt             # pip dependencies
├── CLAUDE.md                    # Development guide
├── PLAN.md                      # Product feature plan
├── PLAN_TASKS.md                # Feature checklist (98/110 done)
├── CODEX.md                     # Session change log
├── backlight_sim/               # Main package
│   ├── __init__.py
│   ├── core/                    # Data model (no GUI imports)
│   │   ├── __init__.py
│   │   ├── geometry.py          # Rectangle — arbitrarily-oriented 3D plane
│   │   ├── materials.py         # Material, OpticalProperties — optical properties
│   │   ├── sources.py           # PointSource — light source definition
│   │   ├── detectors.py         # DetectorSurface, SphereDetector, results
│   │   └── project_model.py     # Project, SimulationSettings — scene container
│   ├── sim/                     # Simulation engine (no GUI imports)
│   │   ├── __init__.py
│   │   ├── tracer.py            # RayTracer — Monte Carlo engine
│   │   ├── sampling.py          # Direction sampling utilities
│   │   └── spectral.py          # Wavelength/color utilities
│   ├── io/                      # File I/O and scene construction (no GUI imports)
│   │   ├── __init__.py
│   │   ├── project_io.py        # JSON save/load
│   │   ├── geometry_builder.py  # Cavity/LED grid/optical stack builders
│   │   ├── presets.py           # Built-in scene presets
│   │   ├── angular_distributions.py  # Profile loading/merging
│   │   ├── ies_parser.py        # IES/EULUMDAT file parsing
│   │   ├── report.py            # HTML report generation
│   │   └── batch_export.py      # ZIP batch export
│   ├── gui/                     # PySide6 desktop UI
│   │   ├── __init__.py
│   │   ├── main_window.py       # MainWindow, SimulationThread
│   │   ├── object_tree.py       # QTreeWidget scene browser
│   │   ├── properties_panel.py  # QStackedWidget property editor
│   │   ├── viewport_3d.py       # GLViewWidget 3D visualization
│   │   ├── heatmap_panel.py     # 2D detector heatmap + KPI dashboard
│   │   ├── angular_distribution_panel.py  # Distribution editor/importer
│   │   ├── geometry_builder.py  # Dialog wrapping io/geometry_builder
│   │   ├── parameter_sweep_dialog.py     # Single/multi-parameter sweep UI
│   │   ├── comparison_dialog.py  # Variant comparison dialog
│   │   ├── led_layout_editor.py  # 2D drag-and-drop LED positioning
│   │   ├── measurement_dialog.py  # Point-to-point distance tool
│   │   ├── plot_tab.py          # Analysis plots (section, histogram, CDF)
│   │   ├── receiver_3d.py       # 3D sphere detector visualization
│   │   └── __init__.py
│   ├── data/                    # Data files (not code)
│   │   └── angular_distributions/  # Built-in CSV profiles
│   │       ├── isotropic.csv
│   │       ├── lambertian.csv
│   │       └── batwing.csv
│   └── tests/                   # Unit and integration tests
│       ├── __init__.py
│       └── test_tracer.py       # RayTracer test suite (20 tests)
├── build/                       # PyInstaller build output (generated)
└── dist/                        # PyInstaller dist directory (generated)
```

## Directory Purposes

**`backlight_sim/core/`:**
- Purpose: Immutable dataclass definitions for scene objects
- Contains: Python dataclasses backed by NumPy arrays
- Key files: `geometry.py` (Rectangle), `sources.py` (PointSource), `detectors.py` (DetectorSurface, SphereDetector), `project_model.py` (Project container)
- Constraint: Zero PySide6 imports (100% headless)

**`backlight_sim/sim/`:**
- Purpose: Monte Carlo ray tracing algorithm and sampling utilities
- Contains: Semi-vectorized NumPy ray tracing, direction sampling, spectral utilities
- Key files: `tracer.py` (RayTracer), `sampling.py` (isotropic/lambertian/angular-dist sampling), `spectral.py` (wavelength/color mapping)
- Constraint: Zero PySide6 imports; depends only on `core/` and NumPy

**`backlight_sim/io/`:**
- Purpose: Project persistence, file format conversion, and scene builders
- Contains: JSON serialization, geometry construction dialogs, IES/EULUMDAT parsers, HTML report generator
- Key files: `project_io.py` (save/load), `geometry_builder.py` (cavity/grid/stack builders), `ies_parser.py` (photometry file import), `report.py` (HTML export)
- Constraint: Zero PySide6 imports; uses `core/` dataclasses for all data

**`backlight_sim/gui/`:**
- Purpose: PySide6 desktop application UI and workflows
- Contains: Main window, panels (tree, properties, viewport, heatmap, plots), dialogs, threading controller
- Key files: `main_window.py` (entry point and orchestrator), `object_tree.py` (scene browser), `properties_panel.py` (editor), `viewport_3d.py` (3D preview)
- Depends on: All lower layers + PySide6 + PyQtGraph

**`backlight_sim/data/`:**
- Purpose: Distributable data files (CSV, presets)
- Contains: Angular distribution profiles (isotropic, lambertian, batwing)
- Generated: No
- Committed: Yes
- Packaged: Included in PyInstaller distribution

**`backlight_sim/tests/`:**
- Purpose: Unit and integration tests
- Contains: pytest test suite for core simulation
- Key files: `test_tracer.py` (RayTracer validation, 20 tests)
- Run: `pytest backlight_sim/tests/`

## Key File Locations

**Entry Points:**
- `app.py`: Application launcher — creates `QApplication`, shows `MainWindow`, enters event loop
- `backlight_sim/gui/main_window.py` (`MainWindow` class): Primary application window and state container

**Configuration:**
- `requirements.txt`: pip dependencies (PySide6, pyqtgraph, numpy, PyOpenGL, pytest)
- `build_exe.py`: PyInstaller configuration for standalone Windows executable
- `.claude/settings.local.json`: IDE settings (not code-relevant)

**Core Data Model:**
- `backlight_sim/core/geometry.py` (`Rectangle`): Arbitrarily-oriented 3D plane geometry
- `backlight_sim/core/sources.py` (`PointSource`): Light source definition with flux, direction, distribution
- `backlight_sim/core/detectors.py` (`DetectorSurface`, `SphereDetector`): Receiver definitions
- `backlight_sim/core/materials.py` (`Material`, `OpticalProperties`): Optical properties
- `backlight_sim/core/project_model.py` (`Project`, `SimulationSettings`): Scene container

**Simulation Engine:**
- `backlight_sim/sim/tracer.py` (`RayTracer`): Main Monte Carlo engine; entry point is `RayTracer.run()`
- `backlight_sim/sim/sampling.py`: Ray direction sampling (isotropic, Lambertian, angular distribution)
- `backlight_sim/sim/spectral.py`: Wavelength sampling and CIE color conversion

**I/O and Construction:**
- `backlight_sim/io/project_io.py`: JSON project save/load functions
- `backlight_sim/io/geometry_builder.py`: Cavity, LED grid, optical stack builders (pure functions)
- `backlight_sim/io/presets.py`: Built-in scene presets (Simple Box, Automotive Cluster)
- `backlight_sim/io/ies_parser.py`: IES/EULUMDAT photometry file import
- `backlight_sim/io/report.py`: HTML report generator from simulation results
- `backlight_sim/io/batch_export.py`: ZIP batch export (project + KPIs + report)

**GUI Panels:**
- `backlight_sim/gui/object_tree.py` (`ObjectTree`): Scene object tree widget (QTreeWidget)
- `backlight_sim/gui/properties_panel.py` (`PropertiesPanel`): Property editor (QStackedWidget with per-type forms)
- `backlight_sim/gui/viewport_3d.py` (`Viewport3D`): 3D OpenGL preview (GLViewWidget)
- `backlight_sim/gui/heatmap_panel.py` (`HeatmapPanel`): 2D detector heatmap + KPI dashboard
- `backlight_sim/gui/angular_distribution_panel.py` (`AngularDistributionPanel`): Distribution editor and importer
- `backlight_sim/gui/plot_tab.py` (`PlotTab`): Analysis plots (section views, histograms, CDF)
- `backlight_sim/gui/receiver_3d.py` (`Receiver3DWidget`): 3D sphere detector visualization

**GUI Dialogs:**
- `backlight_sim/gui/geometry_builder.py` (`GeometryBuilderDialog`): GUI wrapper for cavity/grid/stack builders
- `backlight_sim/gui/parameter_sweep_dialog.py` (`ParameterSweepDialog`): Single/multi-parameter sweep runner
- `backlight_sim/gui/comparison_dialog.py` (`ComparisonDialog`): Variant comparison side-by-side
- `backlight_sim/gui/led_layout_editor.py` (`LEDLayoutEditor`): 2D drag-and-drop LED positioning
- `backlight_sim/gui/measurement_dialog.py` (`MeasurementDialog`): Point-to-point distance measurement

**Testing:**
- `backlight_sim/tests/test_tracer.py`: RayTracer unit tests (20 tests covering core simulation logic)

## Naming Conventions

**Files:**
- Core data models: snake_case, matches class name (`geometry.py` for `Rectangle`, `sources.py` for `PointSource`)
- Panels/widgets: snake_case with suffix hint (`*_panel.py`, `*_dialog.py`)
- Tests: `test_*.py` (pytest discovery convention)
- Data files: Descriptive lowercase with extension (e.g., `isotropic.csv`)

**Directories:**
- Package names: lowercase, plural for multi-file modules (`core`, `sim`, `io`, `gui`)
- Data directories: Descriptive lowercase (`angular_distributions`, `data`)

**Classes:**
- Scene objects: PascalCase (`Rectangle`, `PointSource`, `DetectorSurface`, `Material`, `Project`)
- Qt widgets: PascalCase suffix with type hint (e.g., `PropertiesPanel`, `Viewport3D`, `ObjectTree`)
- Dialogs: PascalCase suffix `Dialog` (e.g., `GeometryBuilderDialog`, `ParameterSweepDialog`)

**Functions:**
- Module-level: snake_case (e.g., `save_project()`, `load_project()`, `sample_isotropic()`)
- Private (leading underscore): `_helper_function()`

**Variables:**
- Local variables: snake_case
- Class attributes: snake_case (used as `self.attribute`)
- Constants: UPPER_SNAKE_CASE (e.g., `LAMBDA_MIN`, `N_SPECTRAL_BINS`)

## Where to Add New Code

**New Feature (Simulation Enhancement):**
- Primary code: `backlight_sim/sim/tracer.py` (add method to `RayTracer` or new utility in `sampling.py`)
- Tests: `backlight_sim/tests/test_tracer.py` (add pytest test function)
- Data model: Update `backlight_sim/core/project_model.py` if new settings/parameters needed
- UI: Add control to appropriate `backlight_sim/gui/properties_panel.py` form

**New GUI Component:**
- Implementation: `backlight_sim/gui/{component_name}.py`
- Pattern: Class inheriting from QWidget (or subclass), with `set_project()` method
- Integration: Register in `MainWindow._setup_ui()` and wire signals in `MainWindow._connect_signals()`

**New Scene Type (Geometry Builder):**
- Implementation: Pure function in `backlight_sim/io/geometry_builder.py` (returns list[Rectangle])
- GUI Dialog: Add button/option in `backlight_sim/gui/geometry_builder.py` to expose the builder
- Preset: Register in `backlight_sim/io/presets.py` if it's a common pattern

**New File Format Import:**
- Implementation: Parser function in `backlight_sim/io/` (e.g., `ies_parser.py` pattern)
- UI: Add import option to relevant panel (e.g., `AngularDistributionPanel` for angle distributions)
- Return type: Reconstruct core dataclasses (`Project`, `PointSource`, etc.) from file data

**Utilities / Shared Helpers:**
- Small helpers: Place in `backlight_sim/core/` if data-related; `backlight_sim/sim/` if math-related
- GUI-only helpers: Place in same module or create `backlight_sim/gui/common.py`

## Special Directories

**`backlight_sim/data/angular_distributions/`:**
- Purpose: Built-in CSV angular distribution profiles
- Generated: No
- Committed: Yes
- Loaded by: `backlight_sim/io/angular_distributions.py` at application startup
- File format: Two-column CSV (theta_deg, intensity) — case-insensitive header or no header
- Examples: `isotropic.csv`, `lambertian.csv`, `batwing.csv`

**`build/` and `dist/`:**
- Purpose: PyInstaller output directories
- Generated: Yes (by `python build_exe.py`)
- Committed: No (in .gitignore)
- Contents: Standalone Windows executable and bundled dependencies

**`backlight_sim/__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (automatically by Python)
- Committed: No (in .gitignore)

## Import Patterns and Dependencies

**Forward dependency (allowed):**
- `gui/` imports from `core/`, `sim/`, `io/` ✓
- `io/` imports from `core/` ✓
- `sim/` imports from `core/` ✓

**Reverse dependency (forbidden, enforced):**
- `core/` imports from `gui/` ✗ (no PySide6)
- `sim/` imports from `gui/` ✗ (no PySide6)
- `io/` imports from `gui/` ✗ (no PySide6)
- `sim/` imports from `io/` ✗ (allows independent testing)

**Cross-layer imports (within allowed direction):**
- `gui/main_window.py` imports: `core.project_model`, `core.geometry`, `core.sources`, `core.detectors`, `sim.tracer`, `io.project_io`, `io.geometry_builder`, `io.presets`, `io.angular_distributions`
- `sim/tracer.py` imports: `core.project_model`, `core.geometry`, `core.detectors`, `sim.sampling`, `sim.spectral`

**External dependencies:**
- NumPy: `core/`, `sim/`, `io/` only
- PySide6: `gui/`, `app.py` only
- PyQtGraph: `gui/` only
- PyOpenGL: `gui/viewport_3d.py` only
- pytest: Tests only

---

*Structure analysis: 2026-03-14*
