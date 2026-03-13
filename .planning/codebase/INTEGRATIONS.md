# External Integrations

**Analysis Date:** 2026-03-14

## APIs & External Services

**None Detected:**
- No network APIs (HTTP, REST, gRPC)
- No third-party cloud services (AWS, Azure, GCP)
- No payment processors or authentication services
- No remote collaboration or sync APIs
- Application is fully offline/standalone

## Data Storage

**Databases:**
- None - Application uses no persistent database
- All project data stored as JSON files on local filesystem
- User manages projects manually via File > Save/Open

**File Storage:**
- Local filesystem only
- Project files: `.json` format in user's chosen directory
- Angular distribution profiles: built-in CSV files in `backlight_sim/data/angular_distributions/`
- Simulation results: transient (stored in memory after run) or exported to disk (CSV, PNG, ZIP, HTML)

**Caching:**
- None - No explicit caching layer
- Results held in memory during session (`SimulationResult` object in `MainWindow`)
- History stored in-memory: `MainWindow._history` list (20 design snapshots max)

## Authentication & Identity

**Auth Provider:**
- None - Application requires no authentication
- Single-user desktop application
- No user accounts, login, or access control

## Monitoring & Observability

**Error Tracking:**
- None detected - No Sentry, DataDog, or similar error reporting
- Errors handled locally via `QMessageBox` dialogs in `backlight_sim/gui/main_window.py`

**Logs:**
- Python standard logging not detected in codebase
- Log dock panel (`_log_dock` in `MainWindow`) exists but appears to be placeholder/minimal logging
- No file-based logging configured

## CI/CD & Deployment

**Hosting:**
- None - Desktop application only
- Users run `python app.py` directly or execute bundled `.exe` from `build_exe.py`

**CI Pipeline:**
- Not detected - No GitHub Actions, Jenkins, GitLab CI config found

**Distribution:**
- PyInstaller-based standalone executable generation via `build_exe.py`
- Manual build process: `python build_exe.py [--clean] [--zip]`
- Output: `dist/BluOpticalSim/BluOpticalSim.exe` (optionally zipped as `dist/BluOpticalSim-windows.zip`)

## Environment Configuration

**Required env vars:**
- None - Application has no external env var dependencies
- All settings configured via GUI or embedded in project JSON

**Secrets location:**
- Not applicable - No secrets or credentials used

## File Format Integrations

**Input Formats:**

- **IES (IESNA LM-63)** - Photometric intensity distribution
  - Parser: `backlight_sim/io/ies_parser.py` → `load_ies(path)`
  - Converts to internal `{theta_deg: [...], intensity: [...]}` format
  - Multi-plane data averaged to single radial profile

- **LDT (EULUMDAT)** - Alternative photometric format
  - Parser: `backlight_sim/io/ies_parser.py` → `load_ldt(path)`
  - Converts to same internal format as IES

- **CSV/TXT (Angular Distributions)** - User-defined intensity profiles
  - Parser: `backlight_sim/io/angular_distributions.py` → `load_profile_csv(path)`
  - Expected columns: `theta_deg`, `intensity`

- **JSON (Project Files)** - Complete simulation project serialization
  - Serializer: `backlight_sim/io/project_io.py`
  - Stores: sources, surfaces, materials, detectors, angular distributions, simulation settings
  - Format: Plain lists for numpy arrays; backward compatible with `.get(key, default)` pattern

**Output Formats:**

- **CSV** - KPI metrics and detector grid data
  - Generator: `backlight_sim/gui/heatmap_panel.py` → `_export_kpi_csv()`, `_export_grid_csv()`

- **PNG** - Heatmap visualization
  - Generator: pyqtgraph `ImageItem.save()` or matplotlib for HTML report

- **HTML** - Self-contained simulation report
  - Generator: `backlight_sim/io/report.py` → `generate_html_report()`
  - Embeds heatmap PNG as base64-encoded data URI
  - Includes KPI table, uniformity stats, energy balance metrics

- **ZIP** - Batch export archive
  - Generator: `backlight_sim/io/batch_export.py` → `export_batch_zip()`
  - Contents: `project.json`, `kpi.csv`, detector grid CSVs, `report.html`

## Built-in Data

**Angular Distribution Profiles:**
- Location: `backlight_sim/data/angular_distributions/`
- Built-in profiles: `isotropic.csv`, `lambertian.csv`, `batwing.csv`
- Loaded via: `backlight_sim/io/angular_distributions.py` → `load_default_profiles()`
- Format: CSV with `theta_deg` and `intensity` columns

**CIE 1931 Color Matching Functions:**
- Location: `backlight_sim/sim/spectral.py` (inline numpy arrays)
- Data: X, Y, Z tristimulus values from 380–780 nm at 10 nm intervals
- Used for: Spectral to XYZ color space conversion (if spectral simulation enabled)
- No external file dependencies

## Webhooks & Callbacks

**Incoming:**
- None - No webhook endpoints

**Outgoing:**
- None - No external callbacks or event publishing

## Thread & Process Communication

**GUI Threading:**
- `SimulationThread(QThread)` in `backlight_sim/gui/main_window.py`
- Signals: `progress` (float: 0.0–1.0), `finished_sim` (SimulationResult)
- Runs ray tracer off main thread without blocking UI

**Multiprocessing:**
- `ProcessPoolExecutor` in `backlight_sim/sim/tracer.py` for parallel source simulation
- Worker processes run `_trace_single_source()` function independently
- Detector grids merged on main process via `+=` accumulation
- IPC: Results returned as dicts with pickled numpy arrays

## Spectral Engine

**Optional Feature:**
- `backlight_sim/sim/spectral.py` - Wavelength sampling infrastructure
- Constants: `LAMBDA_MIN=380nm`, `LAMBDA_MAX=780nm`, `N_SPECTRAL_BINS=40` (10nm bins)
- Not yet integrated into main ray tracing (Phase 2+ feature)

## Summary

**Zero External Dependencies:**
- No network calls, APIs, cloud services, or databases
- Completely self-contained offline application
- All data flow is local file system (JSON) or in-memory objects
- Distribution is standalone executable with bundled dependencies

---

*Integration audit: 2026-03-14*
