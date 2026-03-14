# Requirements: Blu Optical Simulation — Phase 2

**Defined:** 2025-07-11
**Core Value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.

## v1 Requirements

Requirements for Phase 2 release. Each maps to roadmap phases.

### Edge-Lit / LGP

- [x] **LGP-01**: User can define an LGP slab as a solid box with independent optical properties per face
- [x] **LGP-02**: Tracer computes Snell's law refraction, Fresnel reflection/transmission, and TIR at dielectric interfaces
- [x] **LGP-03**: User can see edge coupling efficiency (flux-through-edge / total-emitted) as a KPI after simulation

### Spectral Simulation

- [x] **SPEC-01**: Each ray carries a sampled wavelength and material interactions are wavelength-dependent
- [x] **SPEC-02**: Detector accumulates flux per wavelength bin into a spectral grid
- [x] **SPEC-03**: User can view detector result as a CIE XYZ / sRGB color image
- [x] **SPEC-04**: Material reflectance and transmittance can be defined as wavelength-dependent tables
- [x] **SPEC-05**: User can see color uniformity KPIs (delta-CCx, delta-CCy) after spectral simulation

### 3D Solid Geometry

- [x] **GEOM-01**: User can create a box solid body with 6 faces, each with independent optical properties
- [x] **GEOM-02**: User can create cylinder solid body primitives
- [x] **GEOM-03**: User can create prism solid body primitives

### Performance

- [x] **PERF-01**: Ray-surface intersection and accumulation inner loops are Numba JIT-compiled for 10-50x speedup
- [x] **PERF-02**: BVH spatial acceleration is used for scenes with 50+ surfaces
- [x] **PERF-03**: Adaptive sampling stops ray generation per source when detector variance is below threshold

### BRDF

- [x] **BRDF-01**: User can import tabulated BRDF data (measured goniophotometer CSV) and assign it to surfaces

### Detectors

- [x] **DET-01**: User can add a far-field angular detector that outputs candela distribution and exports as IES file

### UI / UX

- [x] **UI-01**: Application uses a dark theme with teal/cyan accent across all widgets including pyqtgraph plots and 3D viewport
- [x] **UI-02**: Left sidebar (scene tree + properties) with central tabbed panel area; panels openable from Window menu; tab state persists between sessions via QSettings
- [x] **UI-03**: Top toolbar with icon+text buttons for common actions (New, Open, Save, Run, Cancel) and quick-add buttons (LED, Surface, Detector, SolidBox)
- [x] **UI-04**: Full undo/redo system (Ctrl+Z / Ctrl+Y) using QUndoStack for all scene mutations (add, delete, property edit)
- [x] **UI-05**: Properties panel uses collapsible sections for property groups with expand/collapse arrows
- [x] **UI-06**: Object tree shows per-type colored icons and enhanced context menus with Duplicate action
- [x] **UI-07**: Heatmap panel has selectable colormaps, crosshair cursor with live pixel values, and KPI cards with color-coded thresholds (green/yellow/red)
- [x] **UI-08**: Live heatmap preview updates during simulation at 5% intervals, with auto-focus on heatmap dock after completion

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Edge-Lit / LGP

- **LGP-04**: Extraction dot pattern (per-region scatter/transmittance map on bottom face)
- **LGP-05**: Wedge LGP (tapered thickness geometry)
- **LGP-06**: LGP dot pattern design tool (density gradient calculator from target uniformity)

### Spectral

- **SPEC-06**: Wavelength-dependent refractive index (dispersion via Cauchy/Sellmeier coefficients)
- **SPEC-07**: Spectral + uniformity co-optimization in parameter sweep

### 3D Geometry

- **GEOM-04**: Triangle mesh import (STL/OBJ via trimesh)
- **GEOM-05**: CAD/DXF import for LED layouts and LGP patterns (ezdxf)

### Renderer

- **REND-01**: VTK/PyVista 3D renderer replacing pyqtgraph.opengl for CAD-quality solid body rendering

### BRDF

- **BRDF-02**: GGX microfacet BRDF model (single roughness parameter for polished/satin surfaces)

### Materials

- **MAT-01**: Temperature-dependent optical property LUTs per material

## Out of Scope

| Feature | Reason |
|---------|--------|
| Polarization state tracking (Jones/Mueller) | ~2x memory overhead, niche within BLU work; Phase 3 candidate |
| FDTD / wave optics for thin-film effects | Category confusion in a ray tracer; use dedicated tools |
| GPU/CUDA acceleration | Packaging complexity with PyInstaller; Numba CPU covers target speedup |
| Full micro-optics LGP dot simulation | Impractical compute cost; use stochastic extraction probability map |
| CAD solid modeling / history tree | Engineers already have CAD tools; import from STL/OBJ instead |
| Bayesian/Optuna optimization | Current Pareto sweep sufficient; Nelder-Mead via scipy if needed |
| STEP/IGES import | 500MB OCC dependency, fragile PyInstaller packaging |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LGP-01 | Phase 1 | Complete |
| LGP-02 | Phase 1 | Complete |
| LGP-03 | Phase 1 | Complete |
| SPEC-01 | Phase 2 | Complete |
| SPEC-02 | Phase 2 | Complete |
| SPEC-03 | Phase 2 | Complete |
| SPEC-04 | Phase 2 | Complete |
| SPEC-05 | Phase 2 | Complete |
| GEOM-01 | Phase 1 | Complete |
| GEOM-02 | Phase 4 | Complete |
| GEOM-03 | Phase 4 | Complete |
| PERF-01 | Phase 3 | Complete |
| PERF-02 | Phase 3 | Complete |
| PERF-03 | Phase 3 | Complete |
| BRDF-01 | Phase 4 | Complete |
| DET-01 | Phase 4 | Complete |
| UI-01 | Phase 5 | Complete |
| UI-02 | Phase 5 | Complete |
| UI-03 | Phase 5 | Complete |
| UI-04 | Phase 5 | Complete |
| UI-05 | Phase 5 | Complete |
| UI-06 | Phase 5 | Complete |
| UI-07 | Phase 5 | Complete |
| UI-08 | Phase 5 | Complete |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2025-07-11*
*Last updated: 2026-03-14 — Phase 5 UI requirements added*
