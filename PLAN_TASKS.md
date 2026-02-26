# PLAN.MD — Taskified Checklist & Status

Status: **Done** | **Partial** | **Not done** | **Cannot do** (out of scope / phase) | **Need more info**

---

## Bug fixes / Improvements

| # | Task | Status |
|---|------|--------|
| B1 | **Simple Box preset**: Sides are vertical instead of horizontal; box is not enclosed. Fix preset so the cavity is a properly enclosed box (correct wall orientation/sizes or add top). | **Done** — Fixed front/back wall size in `build_cavity`: use `(d, w)` for normal ±Y (was `(w, d)`), so cavity is properly enclosed. |
| B2 | **Geometry Builder — LED grid input**: Builder currently takes pitch X/Y and edge offsets. Often the user has **number of LEDs** and offset; pitch should be derived. Add option: input count X, count Y (and optionally offsets) and auto-calculate pitch from cavity width/height. | **Done** — Checkbox “Specify number of LEDs (auto pitch)” + Count X/Y spinboxes; pitch = (span − 2×offset) / max(count−1, 1). |

---

## 3.1 Project / Model Management

| # | Task | Status |
|---|------|--------|
| 1 | Create new project | **Done** (File → New Project) |
| 2 | Save / load project (`.json` or `.yaml`) | **Done** (JSON only; YAML not implemented) |
| 3 | Unit settings (mm, lm, cd, degree) | **Partial** (`distance_unit` in settings; lm/cd/degree not explicit) |
| 4 | Project presets (e.g. automotive cluster direct-lit) | **Done** (Presets menu: Simple Box, Automotive Cluster) |
| 5 | Project comparison | **Not done** |
| 6 | Variant cloning (A/B design comparison) | **Not done** |
| 7 | Design history snapshots | **Not done** |

---

## 3.2 Geometry Builder (Direct-Lit)

| # | Task | Status |
|---|------|--------|
| 8 | Rectangular cavity dimensions (W, H, depth) | **Done** (Build → Geometry Builder) |
| 9 | LED layout: grid placement | **Done** |
| 10 | LED layout: pitch X/Y | **Done** |
| 11 | LED layout: edge offsets | **Done** |
| 12 | LED layout: enable/disable individual LEDs | **Not done** |
| 13 | Reflector: wall angle | **Done** (incl. separate X/Y wall angles) |
| 14 | Reflector: wall reflectance | **Done** (floor + wall materials in builder) |
| 15 | Reflector: surface type (simplified) | **Done** (diffuse vs specular in materials) |
| 16 | Optical stack: LED top → diffuser distance | **Partial** (z_offset for LEDs; no explicit “diffuser distance” in builder) |
| 17 | Optical stack: additional film placeholder distances | **Not done** |
| 18 | Surface material assignment (reflective / absorptive / transmissive) | **Done** (materials + floor/wall assignment) |
| 19 | Non-rectangular geometry | **Not done** |
| 20 | Mixed LED zones/groups | **Not done** |
| 21 | Mechanical obstacles (bosses, FPC, shields) | **Not done** |
| 22 | CAD/DXF outline import | **Not done** |

---

## 3.3 LED Source Modeling

| # | Task | Status |
|---|------|--------|
| 23 | Angular distribution import (CSV/TXT) | **Done** (Angular Dist. tab: Import CSV/TXT) |
| 24 | Angle vs relative intensity format (`theta`, `I(theta)`) | **Done** |
| 25 | Source: total luminous flux (lm) | **Done** (flux in PointSource + properties) |
| 26 | Source: peak intensity (optional mode) | **Not done** |
| 27 | Source: position / orientation / tilt | **Done** (position + direction; rotation in Surface form) |
| 28 | Normalization: normalize to peak | **Not done** |
| 29 | Normalization: normalize to total flux | **Not done** |
| 30 | Normalization: normalize to 1.0 | **Not done** |
| 31 | IES / LDT import | **Not done** |
| 32 | LED bin/tolerance variation | **Not done** |
| 33 | Current-dependent flux scaling | **Not done** |
| 34 | Thermal derating | **Not done** |
| 35 | Color / spectral support | **Not done** |

---

## 3.4 Material / Optical Property Library

| # | Task | Status |
|---|------|--------|
| 36 | Reflector reflectance | **Done** |
| 37 | Specular vs diffuse fraction | **Done** (`is_diffuse` on Material) |
| 38 | Diffuser transmittance | **Done** |
| 39 | Haze / scatter proxy | **Not done** |
| 40 | Plate absorption | **Done** (`absorption` on Material) |
| 41 | Refractive index (for later TIR) | **Not done** |
| 42 | Spectral properties | **Not done** |
| 43 | BRDF tables / measured reflectance | **Not done** |
| 44 | Temperature dependence | **Not done** |

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
| 55 | Quality presets (Quick / Standard / High) | **Not done** (only raw numeric settings) |
| 56 | Output heatmap (relative irradiance / pseudo-luminance) | **Done** (Heatmap tab) |
| 57 | Total extracted energy / efficiency proxy | **Partial** (total_flux; no explicit “efficiency” ratio UI) |
| 58 | Uniformity metrics | **Done** (min/avg, min/max for center fractions) |
| 59 | Hotspot indicators | **Not done** |
| 60 | Edge–center ratio | **Not done** |
| 61 | Loss breakdown (absorbed / trapped / leaked) | **Not done** |
| 62 | Multiprocessing | **Not done** |
| 63 | Numba acceleration | **Not done** |
| 64 | Adaptive / importance sampling, BVH | **Not done** |

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
| 69 | ROI/region stats: center, edge, corner, custom | **Partial** (center-fraction uniformity only; no explicit ROI/corner/edge) |
| 70 | Exportable detector map data | **Not done** (data in memory only; no export in GUI) |
| 71 | Far-field / angular detector | **Not done** |
| 72 | Observer cone, ISO legibility, compare to reference | **Not done** |

---

## 3.8 Analysis & KPI Dashboard

| # | Task | Status |
|---|------|--------|
| 73 | Uniformity: min/max, min/avg | **Done** (Heatmap panel) |
| 74 | Uniformity: standard deviation, coefficient of variation | **Not done** |
| 75 | Efficiency proxy: extracted / emitted | **Partial** (total_flux available; no dashboard ratio) |
| 76 | LED count (cost proxy) | **Partial** (trivial from tree; not in KPI view) |
| 77 | Weighted design score (user-defined weights) | **Not done** |
| 78 | Dedicated KPI dashboard | **Not done** (stats only in Heatmap panel) |
| 79 | Power/thermal proxy, Pareto, sensitivity, tolerance robustness | **Not done** |

---

## 3.9 Optimization / Parameter Sweep

| # | Task | Status |
|---|------|--------|
| 80 | Single-parameter sweep (pitch, depth, angle, reflectance, diffuser dist.) | **Not done** |
| 81 | Batch run queue | **Not done** |
| 82 | Results table + sort/filter, KPI vs parameter plots | **Not done** |
| 83 | Multi-parameter sweep, optimization, Pareto | **Not done** |

---

## 3.10 GUI / UX

| # | Task | Status |
|---|------|--------|
| 84 | Project Explorer (left): Geometry, LEDs, Materials, Settings, Results | **Done** (Scene tree: Sources, Surfaces, Materials, Detectors) |
| 85 | Main view: geometry / top view | **Done** (3D View) |
| 86 | Main view: section view | **Not done** (only 3D; no dedicated section cut) |
| 87 | Main view: Heatmap tab | **Done** |
| 88 | Main view: Ray preview tab | **Done** (ray paths in 3D view) |
| 89 | Main view: Plot tab | **Partial** (angular dist. plot in Angular Dist. tab) |
| 90 | Properties panel (right) | **Done** |
| 91 | Bottom: simulation progress | **Done** (progress bar in status bar) |
| 92 | Bottom: logs, warnings/errors | **Not done** |
| 93 | Forms for geometry/material/source inputs | **Done** |
| 94 | LED angular distribution preview plot | **Done** |
| 95 | Start/stop simulation, progress bar | **Done** |
| 96 | Save/load project | **Done** |
| 97 | Export CSV/PNG | **Partial** (angular dist. Export CSV only; no heatmap/KPI export) |
| 98 | Results heatmap and KPI view | **Done** (heatmap + basic stats) |
| 99 | Drag-and-drop LED, side-by-side comparison, variant manager, interactive ROI | **Not done** |

---

## 3.11 Data Import / Export

| # | Task | Status |
|---|------|--------|
| 100 | Import LED angular CSV/TXT | **Done** |
| 101 | Export KPI table (CSV) | **Not done** |
| 102 | Export heatmap image (PNG) | **Not done** |
| 103 | Save/load project config (JSON/YAML) | **Done** (JSON only) |
| 104 | IES/LDT, DXF, Excel/PDF report, batch packaging | **Not done** |

---

## 3.12 Validation / Calibration

| # | Task | Status |
|---|------|--------|
| 105 | Reference case comparison, compare to measurement/LightTools/Zemax | **Not done** |
| 106 | Error metrics (RMSE, MAE, center–edge deviation) | **Not done** |
| 107 | Calibration fitting, material tuning, calibrated profiles | **Not done** |

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
| **Done**       | 54    |
| **Partial**    | 12    |
| **Not done**   | 44    |
| **Cannot do**  | 1     |
| **Need more info** | 0  |

*(B1 and B2 marked Done. Includes 2 bug-fix / improvement items.)*

---

*Generated from PLAN.MD; status checked against current codebase.*
