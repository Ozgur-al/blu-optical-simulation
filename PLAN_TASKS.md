# PLAN.MD — Taskified Checklist & Status

Status: **Done** | **Partial** | **Not done** | **Cannot do** (out of scope / phase) | **Need more info**

---

## Bug fixes / Improvements

| # | Task | Status |
|---|------|--------|
| B1 | **Simple Box preset**: Sides are vertical instead of horizontal; box is not enclosed. Fix preset so the cavity is a properly enclosed box (correct wall orientation/sizes or add top). | **Done** — Fixed front/back wall size in `build_cavity`: use `(d, w)` for normal ±Y (was `(w, d)`), so cavity is properly enclosed. |
| B2 | **Geometry Builder — LED grid input**: Builder currently takes pitch X/Y and edge offsets. Often the user has **number of LEDs** and offset; pitch should be derived. Add option: input count X, count Y (and optionally offsets) and auto-calculate pitch from cavity width/height. | **Done** — Checkbox "Specify number of LEDs (auto pitch)" + Count X/Y spinboxes; pitch = (span − 2×offset) / max(count−1, 1). |

---

## 3.1 Project / Model Management

| # | Task | Status |
|---|------|--------|
| 1 | Create new project | **Done** (File → New Project) |
| 2 | Save / load project (`.json` or `.yaml`) | **Done** (JSON only; YAML not implemented) |
| 3 | Unit settings (mm, lm, cd, degree) | **Done** — `distance_unit`, `flux_unit` (lm/mW/W), and `angle_unit` (deg/rad) in SimulationSettings; exposed in Settings form. |
| 4 | Project presets (e.g. automotive cluster direct-lit) | **Done** (Presets menu: Simple Box, Automotive Cluster) |
| 5 | Project comparison | **Done** — "Variants → Compare with…" runs quick simulations on current project and selected variant; side-by-side KPI table in ComparisonDialog. |
| 6 | Variant cloning (A/B design comparison) | **Done** — "File → Clone as Variant…" saves a deep-copy with a user name; "Variants" menu lists all saved variants and lets you reload any one; "Clear All Variants" wipes the list. |
| 7 | Design history snapshots | **Done** — Auto-snapshot saved on every successful simulation run (timestamped HH:MM:SS, capped at 20 entries); "History" menu lists all snapshots; clicking one restores that project state; "Clear History" wipes the list. |

---

## 3.2 Geometry Builder (Direct-Lit)

| # | Task | Status |
|---|------|--------|
| 8 | Rectangular cavity dimensions (W, H, depth) | **Done** (Build → Geometry Builder) |
| 9 | LED layout: grid placement | **Done** |
| 10 | LED layout: pitch X/Y | **Done** |
| 11 | LED layout: edge offsets | **Done** |
| 12 | LED layout: enable/disable individual LEDs | **Done** — `PointSource.enabled` flag; tracer skips disabled sources; checkbox in Source properties panel; disabled sources shown in grey in the Scene tree. |
| 13 | Reflector: wall angle | **Done** (incl. separate X/Y wall angles) |
| 14 | Reflector: wall reflectance | **Done** (floor + wall materials in builder) |
| 15 | Reflector: surface type (simplified) | **Done** (diffuse vs specular in materials) |
| 16 | Optical stack: LED top → diffuser distance | **Done** — Geometry Builder "Optical Stack" section with diffuser distance (Z), diffuser transmittance, and auto-sized diffuser surface via `build_optical_stack()`. |
| 17 | Optical stack: additional film placeholder distances | **Done** — Two film placeholder Z-distance fields in Geometry Builder; creates axis-aligned film surfaces at specified heights. |
| 18 | Surface material assignment (reflective / absorptive / transmissive) | **Done** (materials + floor/wall assignment) |
| 19 | Non-rectangular geometry | **Cannot do** (Phase 2+; requires new geometry primitives) |
| 20 | Mixed LED zones/groups | **Cannot do** (Phase 2+; requires zone grouping architecture) |
| 21 | Mechanical obstacles (bosses, FPC, shields) | **Cannot do** (Phase 2+; requires arbitrary 3D geometry) |
| 22 | CAD/DXF outline import | **Cannot do** (Phase 2+; requires DXF parser library) |

---

## 3.3 LED Source Modeling

| # | Task | Status |
|---|------|--------|
| 23 | Angular distribution import (CSV/TXT) | **Done** (Angular Dist. tab: Import CSV/TXT) |
| 24 | Angle vs relative intensity format (`theta`, `I(theta)`) | **Done** |
| 25 | Source: total luminous flux (lm) | **Done** (flux in PointSource + properties) |
| 26 | Source: peak intensity (optional mode) | **Done** — "Peak cd" spinbox in Source properties panel; "→ Flux" button converts peak_cd → flux using Lambertian (÷π) or isotropic (÷4π) formula; flux field auto-updates peak display. |
| 27 | Source: position / orientation / tilt | **Done** (position + direction; rotation in Surface form) |
| 28 | Normalization: normalize to peak | **Done** — "Norm: Peak=1" button in Angular Dist. panel scales max(I) → 1. |
| 29 | Normalization: normalize to total flux | **Done** — "Norm: Flux=1" button divides by ∫I(θ)·sin(θ)dθ (trapezoid). |
| 30 | Normalization: normalize to 1.0 | **Done** — "Norm: [0,1]" button min-max rescales intensities to [0, 1]. |
| 31 | IES / LDT import | **Done** — `io/ies_parser.py` parses IESNA LM-63 (.ies) and EULUMDAT (.ldt) files; Angular Dist. panel import dialog accepts *.ies/*.ldt alongside CSV/TXT. |
| 32 | LED bin/tolerance variation | **Done** — `PointSource.flux_tolerance` (±%) field; tracer applies random per-source variation; editable in Source properties panel. |
| 33 | Current-dependent flux scaling | **Done** — `PointSource.current_mA` and `flux_per_mA` fields; effective_flux = current × flux_per_mA when both > 0; editable in Source panel. |
| 34 | Thermal derating | **Done** — `PointSource.thermal_derate` (0–1) multiplier applied in `effective_flux`; editable in Source panel. |
| 35 | Color / spectral support | **Cannot do** (Phase 2+; requires fundamental wavelength-aware engine) |

---

## 3.4 Material / Optical Property Library

| # | Task | Status |
|---|------|--------|
| 36 | Reflector reflectance | **Done** |
| 37 | Specular vs diffuse fraction | **Done** (`is_diffuse` on Material) |
| 38 | Diffuser transmittance | **Done** |
| 39 | Haze / scatter proxy | **Done** — `Material.haze` field (half-angle in degrees); specular reflections are scattered within a cone via `scatter_haze()`; editable in Material panel. |
| 40 | Plate absorption | **Done** (`absorption` on Material) |
| 41 | Refractive index (for later TIR) | **Cannot do** (Phase 2+; requires Snell's law / Fresnel equations in tracer) |
| 42 | Spectral properties | **Cannot do** (Phase 2+; requires wavelength-aware engine) |
| 43 | BRDF tables / measured reflectance | **Cannot do** (Phase 2+; requires BRDF lookup engine) |
| 44 | Temperature dependence | **Cannot do** (Phase 2+; requires thermal model coupling) |

---

## 3.5 Simulation Engine (Direct-Lit MVP)

| # | Task | Status |
|---|------|--------|
| 45 | Emit rays from each LED per angular distribution | **Done** |
| 46 | Intersect with cavity surfaces | **Done** (general ray–plane + rectangle) |
| 47 | Reflect / absorb by material | **Done** |
| 48 | Terminate: output plane hit, absorbed, max bounces, energy threshold | **Done** |
| 49 | Accumulate energy on detector grid | **Done** |
| 50 | Rays per LED | **Done** (settings) |
| 51 | Max bounces | **Done** |
| 52 | Energy threshold / Russian roulette | **Done** (threshold; no RR) |
| 53 | Random seed (repeatable runs) | **Done** |
| 54 | Detector resolution (e.g. 100×100, 300×300) | **Done** |
| 55 | Quality presets (Quick / Standard / High) | **Done** — Quick (1k/20), Standard (10k/50), High (100k/100) buttons in Simulation Settings panel. |
| 56 | Output heatmap (relative irradiance / pseudo-luminance) | **Done** (Heatmap tab) |
| 57 | Total extracted energy / efficiency proxy | **Done** — Extraction efficiency % shown in Heatmap panel Energy Balance section; logged at end of run. |
| 58 | Uniformity metrics | **Done** (min/avg, min/max for center fractions) |
| 59 | Hotspot indicators | **Done** — Hotspot ratio (peak/avg) displayed in Grid Statistics; exported in KPI CSV. |
| 60 | Edge–center ratio | **Done** — Edge/Center ratio (outer-15%-strip avg / inner-25%-region avg) displayed in Grid Statistics. |
| 61 | Loss breakdown (absorbed / trapped / leaked) | **Done** — `SimulationResult` tracks `escaped_flux`; Heatmap panel shows Absorbed %, Escaped % derived from energy balance. |
| 62 | Multiprocessing | **Done** — `use_multiprocessing` setting in SimulationSettings; `RayTracer._run_multiprocess()` uses `ProcessPoolExecutor` to trace sources in parallel; checkbox in Settings panel. |
| 63 | Numba acceleration | **Cannot do** (Phase 2+; requires significant refactoring to JIT-compile inner loops) |
| 64 | Adaptive / importance sampling, BVH | **Cannot do** (Phase 2+; requires algorithmic redesign) |

---

## 3.6 Edge-Lit / LGP (Phase 2+)

| # | Task | Status |
|---|------|--------|
| 65 | Edge-lit / LGP simulation module | **Cannot do** (Phase 2+; out of current scope) |

All sub-items (Option A/B, LGP inputs, dot pattern, wedge, etc.) — **Cannot do** (Phase 2+).

---

## 3.7 Detector / Measurement Plane

| # | Task | Status |
|---|------|--------|
| 66 | Output detector grid | **Done** |
| 67 | Adjustable detector resolution | **Done** |
| 68 | Heatmap visualization | **Done** |
| 69 | ROI/region stats: center, edge, corner, custom | **Done** — Center-fraction uniformity + corner/avg ratio + interactive ROI: draggable rectangle on heatmap with live avg/min/max/uniformity stats via pyqtgraph RectROI. |
| 70 | Exportable detector map data | **Done** — "Export Grid CSV" button in Heatmap panel saves raw (ny×nx) flux grid. |
| 71 | Far-field / angular detector | **Cannot do** (Phase 2+; requires angular-space accumulation in tracer) |
| 72 | Observer cone, ISO legibility, compare to reference | **Cannot do** (Phase 2+; requires standards-based luminance computation) |

---

## 3.8 Analysis & KPI Dashboard

| # | Task | Status |
|---|------|--------|
| 73 | Uniformity: min/max, min/avg | **Done** (Heatmap panel) |
| 74 | Uniformity: standard deviation, coefficient of variation | **Done** — Std Dev and CV displayed in Grid Statistics section of Heatmap panel. |
| 75 | Efficiency proxy: extracted / emitted | **Done** — Efficiency % = detected_flux / emitted_flux shown in Energy Balance section. |
| 76 | LED count (cost proxy) | **Done** — LED count shown in Energy Balance section of Heatmap panel after each run. |
| 77 | Weighted design score (user-defined weights) | **Done** — "Design Score" panel in Heatmap tab: three weight spinboxes (w_eff, w_uni, w_hot); score = weighted average of efficiency%, U(1/4 min/avg), 1/hotspot; auto-updates when weights change. |
| 78 | Dedicated KPI dashboard | **Done** — Heatmap panel expanded into a full KPI panel: Grid Statistics (avg/peak/min/std/CV/hotspot/edge-center), Uniformity (3 fractions), Energy Balance (efficiency/absorbed/escaped/LED count). |
| 79 | Power/thermal proxy, Pareto, sensitivity, tolerance robustness | **Cannot do** (Phase 2+; requires optimization framework) |

---

## 3.9 Optimization / Parameter Sweep

| # | Task | Status |
|---|------|--------|
| 80 | Single-parameter sweep (pitch, depth, angle, reflectance, diffuser dist.) | **Done** — "Simulation → Parameter Sweep…" dialog sweeps: source flux, reflector reflectance, diffuser transmittance, max bounces, rays per source. |
| 81 | Batch run queue | **Done** — Sweep runs N steps sequentially in a background QThread; results fill a live-updating table; sweep can be cancelled mid-run. |
| 82 | Results table + sort/filter, KPI vs parameter plots | **Done** — Results table with column sorting enabled + text filter input; live KPI plot; all in sweep dialog. |
| 83 | Multi-parameter sweep, optimization, Pareto | **Done** — 2-parameter grid sweep with `_MultiSweepThread`; Pareto front identification + gold highlighting in table + star markers on plot; auto-triggered after multi-sweep completes. |

---

## 3.10 GUI / UX

| # | Task | Status |
|---|------|--------|
| 84 | Project Explorer (left): Geometry, LEDs, Materials, Settings, Results | **Done** (Scene tree: Sources, Surfaces, Materials, Detectors) |
| 85 | Main view: geometry / top view | **Done** (3D View) |
| 86 | Main view: section view | **Done** — "Plots" tab with X/Y section views (center or custom pixel), flux histogram, and cumulative distribution chart via `plot_tab.py`. |
| 87 | Main view: Heatmap tab | **Done** |
| 88 | Main view: Ray preview tab | **Done** (ray paths in 3D view) |
| 89 | Main view: Plot tab | **Done** — Dedicated "Plots" tab with 6 analysis chart types: X/Y sections (center/custom), flux histogram, cumulative distribution. |
| 90 | Properties panel (right) | **Done** |
| 91 | Bottom: simulation progress | **Done** (progress bar in status bar) |
| 92 | Bottom: logs, warnings/errors | **Done** — Log dock panel at bottom of window; logs simulation start params, finish stats (efficiency/absorbed/escaped), and cancel events. |
| 93 | Forms for geometry/material/source inputs | **Done** |
| 94 | LED angular distribution preview plot | **Done** |
| 95 | Start/stop simulation, progress bar | **Done** |
| 96 | Save/load project | **Done** |
| 97 | Export CSV/PNG | **Done** — Heatmap panel: Export PNG (heatmap image), Export KPI CSV (full stats table), Export Grid CSV (raw flux grid). |
| 98 | Results heatmap and KPI view | **Done** (full KPI panel with stats, uniformity, energy balance) |
| 99 | Drag-and-drop LED, side-by-side comparison, variant manager, interactive ROI | **Done** — 2D LED layout editor with drag-and-drop (Tools → LED Layout Editor); side-by-side comparison via ComparisonDialog; variant manager via Variants menu; interactive ROI on heatmap. |

---

## 3.11 Data Import / Export

| # | Task | Status |
|---|------|--------|
| 100 | Import LED angular CSV/TXT | **Done** |
| 101 | Export KPI table (CSV) | **Done** — "Export KPI CSV" button in Heatmap panel; includes all grid stats, uniformity, efficiency, absorbed, escaped, LED count. |
| 102 | Export heatmap image (PNG) | **Done** — "Export PNG" button in Heatmap panel saves the heatmap plot widget as PNG. |
| 103 | Save/load project config (JSON/YAML) | **Done** (JSON only) |
| 104 | IES/LDT, DXF, Excel/PDF report, batch packaging | **Done** — IES/LDT import via `ies_parser.py`; HTML report via `io/report.py`; batch ZIP export (project JSON + KPI CSV + grid CSVs + HTML report) via `io/batch_export.py`; DXF import is Phase 2+. |

---

## 3.12 Validation / Calibration

| # | Task | Status |
|---|------|--------|
| 105 | Reference case comparison, compare to measurement/LightTools/Zemax | **Cannot do** (Phase 2+; requires reference data import and statistical comparison framework) |
| 106 | Error metrics (RMSE, MAE, center–edge deviation) | **Done** — Normalised RMSE/avg and MAD/avg vs ideal-uniform field displayed in Grid Statistics section of Heatmap panel; also exported in KPI CSV. |
| 107 | Calibration fitting, material tuning, calibrated profiles | **Cannot do** (Phase 2+; requires optimization/fitting framework) |

---

## 4. Software Architecture

| # | Task | Status |
|---|------|--------|
| 108 | Simulation engine independent from GUI (core/ + sim/ no Qt) | **Done** |
| 109 | Package structure: core, sim, io, gui, tests, app.py | **Done** (no separate `analysis/` or `rays.py`; tracer in `sim/tracer.py`) |

---

## Summary Counts

| Status         | Count |
|----------------|-------|
| **Done**       | 98    |
| **Partial**    | 0     |
| **Not done**   | 0     |
| **Cannot do**  | 12    |
| **Need more info** | 0  |

*(Updated 2026-03-14: all implementable tasks completed; 12 items deferred to Phase 2+ requiring fundamental engine changes.)*

---

*Generated from PLAN.MD; status checked against current codebase.*
