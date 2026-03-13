# Technology Stack

**Analysis Date:** 2026-03-14

## Languages

**Primary:**
- Python 3.x - All application code (core simulation, GUI, I/O)

**Secondary:**
- None - Pure Python project

## Runtime

**Environment:**
- Python 3.7+ (inferred from f-strings and modern syntax)

**Package Manager:**
- pip - Standard Python package manager
- Lockfile: `requirements.txt` and `requirements-dev.txt` present

## Frameworks

**Core:**
- PySide6 >=6.6 - Qt6 bindings for Python; used for all GUI (windows, dialogs, widgets, signals/slots)
- pyqtgraph >=0.13 - High-performance plotting and graphics library; used for 2D heatmaps (`ImageItem`, `ColorBarItem`), 3D visualization, and analysis plots

**Graphics & 3D:**
- PyOpenGL >=3.1 - OpenGL bindings for Python; used by pyqtgraph for 3D rendering via `GLViewWidget` in viewport and 3D sphere detector visualization

**Scientific Computing:**
- NumPy >=1.24 - Vectorized numerical computing; core for ray tracing, matrix operations, random number generation

**Testing:**
- pytest >=7.0 - Unit testing framework; test suite in `backlight_sim/tests/`

**Build & Distribution:**
- PyInstaller - For creating standalone Windows executable via `build_exe.py` (not in requirements.txt, installed separately)

## Key Dependencies

**Critical:**
- PySide6 - Entire GUI layer depends on this; signals/slots architecture for cross-panel communication
- NumPy - Monte Carlo ray tracing engine (`backlight_sim/sim/tracer.py`) uses vectorized operations exclusively
- pyqtgraph - Interactive 2D heatmap visualization and 3D OpenGL viewport rendering

**Scientific:**
- NumPy only listed; no scipy, scikit-learn, or other heavy scientific stack

**Optional (auto-imported if available):**
- matplotlib >=3.x (inferred) - Used for HTML report generation; attempt import in `backlight_sim/io/report.py` with fallback if missing

## Configuration

**Environment:**
- No external configuration files (.env, .config) detected
- Hardcoded paths and defaults in source code
- Project settings stored in JSON project files saved by user

**Build:**
- `build_exe.py` - PyInstaller wrapper script
- `BluOpticalSim.spec` - PyInstaller spec file (not read, but referenced)
- Produces standalone `.exe` for Windows distribution

## Platform Requirements

**Development:**
- Python 3.7+ with pip
- Windows 11 Pro (from environment context)
- Virtual environment recommended

**Production:**
- Windows (PyInstaller targets Windows `.exe`)
- Supports Qt6 on Windows platform
- OpenGL support required (for 3D viewport)

## Data Formats Supported

**Input:**
- JSON (`.json`) - Project save files via `backlight_sim/io/project_io.py`
- CSV/TXT (`.csv`, `.txt`) - Angular distribution profiles
- IES (`.ies`) - IESNA LM-63 photometric files via `backlight_sim/io/ies_parser.py`
- LDT (`.ldt`) - EULUMDAT format photometric files

**Output:**
- JSON - Project export
- CSV - KPI metrics and grid data export
- PNG - Heatmap image export via pyqtgraph
- HTML - Self-contained report with embedded heatmap PNG via matplotlib
- ZIP - Batch export (project + KPI CSV + grid CSV + HTML report)

## Entry Point

**Application Entry:**
- `app.py` - Main entry point; creates `QApplication`, instantiates `MainWindow`, runs event loop

## Multiprocessing

**Concurrency:**
- `concurrent.futures.ProcessPoolExecutor` - Used in `backlight_sim/sim/tracer.py` for multiprocessing simulation across multiple LED sources
- `multiprocessing` module - Process management for parallel ray tracing when `SimulationSettings.use_multiprocessing` enabled
- Worker count: `min(num_sources, cpu_count - 1)` to avoid saturation

## Testing Infrastructure

**Test Framework:**
- pytest >=7.0

**Test Location:**
- `backlight_sim/tests/test_tracer.py` - 20+ unit tests for ray tracing core functionality

**Run Commands:**
- `pytest backlight_sim/tests/` - Run all tests
- `pytest backlight_sim/tests/test_tracer.py::test_name` - Run specific test

---

*Stack analysis: 2026-03-14*
