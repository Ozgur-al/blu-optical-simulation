# Backlight Optical Simulation Tool (Python) — Product Plan & Feature List

## 1. Project Vision

A Python-based desktop application for backlight unit optical simulation and design iteration, focused on **engineering usefulness** from early prototype to advanced internal tool.

The software should support:

- **Direct-lit backlight simulation** (first priority)
- **Edge-lit / LGP simulation** (later phases)
- LED angular distribution import
- Optical/material parameter editing
- Ray-based simulation (Monte Carlo / simplified models)
- Output heatmap + engineering KPI analysis
- Layout optimization and parameter sweeps
- GUI-based workflow for fast iteration

---

## 2. Design Philosophy

Start with **useful approximations** for engineering decisions, then improve physical fidelity over time.

### Early focus (useful now)
- LED layout / pitch / count
- Cavity depth
- Reflector wall angle
- Uniformity trend
- Relative efficiency trend
- Hotspot risk
- Cost proxy (LED count)

### Later focus (higher fidelity)
- More realistic diffuser/scattering behavior
- Better reflector surface models
- Edge-lit LGP TIR/extraction simulation
- Calibration against measurement or LightTools/Zemax reference

---

## 3. Core Product Features

## 3.1 Project / Model Management

### Must-have
- Create new project
- Save / load project (`.json` or `.yaml`)
- Unit settings (mm, lm, cd, degree)
- Project presets (e.g., automotive cluster direct-lit)

### Nice-to-have (later)
- Project comparison
- Variant cloning (A/B design comparison)
- Design history snapshots

---

## 3.2 Geometry Builder (Direct-Lit First)

### Must-have
- Rectangular cavity dimensions (W, H, depth)
- LED layout generator:
  - Grid placement
  - Pitch X/Y
  - Edge offsets
  - Enable/disable LEDs
- Reflector parameters:
  - Wall angle
  - Wall reflectance
  - Surface type (simplified)
- Optical stack spacing:
  - LED top → diffuser distance
  - Additional film placeholder distances
- Surface material assignment (reflective / absorptive / transmissive)

### Nice-to-have (later)
- Non-rectangular geometry
- Mixed LED zones/groups
- Mechanical obstacles (bosses, FPC, shields)
- CAD/DXF outline import

---

## 3.3 LED Source Modeling

### Must-have
- **Angular distribution import (CSV/TXT)**
- Support angle vs relative intensity format (e.g., `theta`, `I(theta)`)
- Source parameters:
  - Total luminous flux (lm)
  - Peak intensity (optional mode)
  - Position / orientation / tilt
- Normalization modes:
  - Normalize to peak
  - Normalize to total flux
  - Normalize to 1.0

### Nice-to-have (later)
- IES / LDT import
- LED bin/tolerance variation
- Current-dependent flux scaling
- Thermal derating
- Color / spectral support

---

## 3.4 Material / Optical Property Library

### Must-have
Editable material database with simplified properties:
- Reflector reflectance
- Specular vs diffuse fraction
- Diffuser transmittance
- Haze / scatter proxy
- Plate absorption
- Refractive index (for later TIR checks)

### Nice-to-have (later)
- Spectral properties
- BRDF tables / measured reflectance data
- Temperature dependence
- Polarization-related models (if ever needed)

---

## 3.5 Simulation Engine (Direct-Lit MVP)

## MVP Method: Monte Carlo Ray Tracing (Simplified)

### Core behavior
- Emit rays from each LED according to angular distribution
- Intersect with cavity surfaces
- Reflect / absorb by material properties
- Continue propagation until:
  - Output plane hit
  - Absorbed
  - Max bounce count reached
  - Energy below threshold
- Accumulate energy on detector plane grid

### Must-have simulation controls
- Rays per LED
- Max bounces
- Energy threshold / Russian roulette
- Random seed (repeatable runs)
- Detector resolution (e.g., 100×100, 300×300)
- Quality presets:
  - Quick preview
  - Standard
  - High quality

### Must-have outputs
- Output heatmap (relative irradiance / pseudo-luminance)
- Total extracted energy / efficiency proxy
- Uniformity metrics
- Hotspot indicators
- Edge-center ratio
- Loss breakdown (absorbed / trapped / leaked)

### Nice-to-have (later)
- Multiprocessing
- Numba acceleration
- Adaptive sampling
- Importance sampling
- Better geometric acceleration (BVH, etc.)

---

## 3.6 Edge-Lit / LGP Simulation Module (Phase 2+)

## Progressive Implementation Strategy

### Option A — Fast Engineering Approximation (first edge-lit version)
Model LGP as a guided slab using statistical extraction:
- Coupling efficiency into LGP
- Propagation attenuation
- Extraction probability map / function
- Sidewall reflection/loss
- Output accumulation

### Option B — Monte Carlo Slab Ray Model (later)
- Rays injected into LGP with angular distribution
- Top/bottom surface hit checks
- Per-hit extraction probability decision
- If not extracted, continue via TIR/specular reflection
- Sidewall loss/reflection
- Bulk absorption

### Must-have edge-lit inputs
- LGP size (W, H, thickness)
- LED strip count/placement
- Coupling efficiency / coupling surface behavior
- Refractive index
- Absorption coefficient
- Sidewall reflectance
- Extraction map / parameterized extraction function

### Nice-to-have (later)
- Dot pattern generator
- Wedge LGP geometry
- Multi-edge injection
- Extraction optimization
- Prism film approximation

---

## 3.7 Detector / Measurement Plane System

### Must-have
- Output detector grid
- Adjustable detector resolution
- Heatmap visualization
- ROI/region statistics:
  - Center
  - Edge
  - Corner
  - Custom areas
- Exportable detector map data

### Nice-to-have (later)
- Far-field / angular detector
- Observer cone metrics
- ISO-style legibility region masks
- Compare detector maps against target/reference

---

## 3.8 Analysis & KPI Dashboard

### Must-have KPIs
- Uniformity:
  - `min / max`
  - `min / avg`
  - Standard deviation
  - Coefficient of variation
- Efficiency proxy:
  - Extracted / emitted
- LED count (cost proxy)
- Weighted design score (user-defined weights)

### Nice-to-have (later)
- Power / thermal proxy
- Brightness vs cost Pareto plot
- Sensitivity analysis
- Tolerance robustness (Monte Carlo over parameter variation)

---

## 3.9 Optimization / Parameter Sweep Tools

### Must-have (Phase 2)
- Single-parameter sweep runner:
  - LED pitch
  - Cavity depth
  - Reflector angle
  - Reflectance
  - Diffuser distance
- Batch run queue
- Results table + sorting/filtering
- KPI vs parameter plots

### Nice-to-have (later)
- Multi-parameter sweep
- Constraint-based optimization
- Bayesian optimization / Optuna
- Pareto front analysis

---

## 3.10 GUI / UX (Python Desktop)

## Recommended Stack
- **PySide6** (Qt for Python)
- **PyQtGraph** (fast heatmap/plot display)
- **Matplotlib** (optional export plots)

### Proposed GUI layout
1. **Project Explorer (left panel)**
   - Geometry
   - LEDs
   - Materials
   - Simulation settings
   - Results

2. **Main View (center)**
   - Geometry top view
   - Section view
   - Heatmap tab
   - Ray preview tab
   - Plot tab

3. **Properties Panel (right)**
   - Editable parameters for selected item

4. **Bottom Panel**
   - Simulation progress
   - Logs
   - Warnings/errors

### Must-have GUI features
- Forms for geometry/material/source inputs
- LED angular distribution preview plot
- Start/stop simulation
- Progress bar
- Save/load project
- Export CSV/PNG
- Results heatmap and KPI view

### Nice-to-have (later)
- Drag-and-drop LED placement
- Side-by-side result comparison
- Variant manager
- Interactive ROI selection

---

## 3.11 Data Import / Export

### Must-have
- Import LED angular CSV/TXT
- Export KPI table (CSV)
- Export heatmap image (PNG)
- Save/load project config (JSON/YAML)

### Nice-to-have (later)
- IES/LDT support
- DXF import
- Excel report export
- PDF report generation
- Batch result packaging

---

## 3.12 Validation / Calibration (Trust Building)

### Must-have (later, but important)
- Reference case comparison mode
- Compare simulation output map with:
  - Measured luminance map
  - LightTools/Zemax result
- Error metrics:
  - RMSE
  - MAE
  - Center-edge deviation

### Nice-to-have (later)
- Calibration fitting tool
- Material preset tuning per optical stack
- “Calibrated model profiles” for common stack types

---

## 4. Software Architecture (Modular)

Keep simulation engine independent from GUI.

## Suggested package structure

```text
backlight_sim/
├── core/
│   ├── geometry.py
│   ├── materials.py
│   ├── sources.py
│   ├── rays.py
│   ├── detectors.py
│   └── project_model.py
├── sim/
│   ├── directlit_engine.py
│   ├── edgelit_engine.py
│   └── sampling.py
├── analysis/
│   ├── kpis.py
│   ├── plots.py
│   └── sweeps.py
├── io/
│   ├── angular_import.py
│   ├── project_io.py
│   └── export.py
├── gui/
│   ├── main_window.py
│   ├── panels/
│   └── widgets/
├── tests/
│   ├── test_sampling.py
│   ├── test_intersections.py
│   └── test_regression_cases.py
└── app.py