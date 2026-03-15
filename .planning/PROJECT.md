# Blu Optical Simulation

## What This Is

A Python desktop application for optical simulation of backlight units (BLU), targeting engineers who need fast design iteration. Uses Monte Carlo ray tracing with a PySide6 GUI. Supports both direct-lit and edge-lit (LGP) configurations with full-fidelity physics: Snell's law refraction, Fresnel coefficients, TIR, wavelength-dependent materials, tabulated BSDF, and solid body geometry (box, cylinder, prism).

## Core Value

Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.

## Requirements

### Validated

- ✓ Direct-lit Monte Carlo ray tracing engine — v0 (existing)
- ✓ Rectangular cavity geometry with tilted walls — v0 (existing)
- ✓ LED grid placement with pitch/count modes — v0 (existing)
- ✓ Angular distribution import (CSV/TXT/IES/LDT) — v0 (existing)
- ✓ Material system (reflector/absorber/diffuser with reflectance, transmittance, haze) — v0 (existing)
- ✓ Planar detector with 2D grid accumulation — v0 (existing)
- ✓ Sphere detector with 3D visualization — v0 (existing)
- ✓ Full KPI dashboard (uniformity, efficiency, hotspot, edge-center, design score) — v0 (existing)
- ✓ Project save/load (JSON), variant cloning, design history — v0 (existing)
- ✓ 3D viewport (pyqtgraph.opengl) with wireframe/solid/transparent modes — v0 (existing)
- ✓ Single + multi-parameter sweep with Pareto front — v0 (existing)
- ✓ LED enable/disable, bin tolerance, current scaling, thermal derating — v0 (existing)
- ✓ Export PNG/KPI CSV/Grid CSV/HTML report/batch ZIP — v0 (existing)
- ✓ Multiprocessing via ProcessPoolExecutor — v0 (existing)
- ✓ 2D LED layout editor with drag-and-drop — v0 (existing)
- ✓ Section views, histograms, CDF analysis plots — v0 (existing)
- ✓ Interactive ROI on heatmap — v0 (existing)
- ✓ Haze/scatter proxy — v0 (existing)
- ✓ Edge-lit LGP simulation with SolidBox, Fresnel/TIR, edge coupling KPIs — v1.0
- ✓ Per-ray wavelength spectral engine with CIE colorimetry and color uniformity KPIs — v1.0
- ✓ Wavelength-dependent material tables (R/T vs wavelength) — v1.0
- ✓ Numba JIT acceleration for ray-surface intersection inner loops — v1.0
- ✓ BVH spatial acceleration for 50+ surface scenes — v1.0
- ✓ Adaptive sampling with convergence targeting — v1.0
- ✓ Tabulated BSDF import and assignment — v1.0
- ✓ Far-field angular detector with IES export — v1.0
- ✓ Cylinder and prism solid body primitives — v1.0
- ✓ Dark theme with teal accent, toolbar, collapsible properties — v1.0
- ✓ Undo/redo for add/delete operations via QUndoStack — v1.0
- ✓ Live heatmap preview during simulation — v1.0
- ✓ Colormap selector, crosshair cursor, KPI threshold coloring — v1.0
- ✓ Tab state persistence and duplicate action — v1.0

### Active

(None — define with `/gsd:new-milestone`)

### Out of Scope

- Polarization state tracking (Jones/Mueller) — ~2x memory overhead, niche within BLU work
- FDTD / wave optics for thin-film effects — category confusion in a ray tracer
- GPU/CUDA acceleration — packaging complexity with PyInstaller; Numba CPU covers target speedup
- Full micro-optics LGP dot simulation — impractical compute cost; use stochastic extraction probability map
- CAD solid modeling / history tree — engineers already have CAD tools; import from STL/OBJ instead
- STEP/IGES import — 500MB OCC dependency, fragile PyInstaller packaging

## Context

Shipped v1.0 with 18,457 LOC Python across 40+ modules.
Tech stack: PySide6, pyqtgraph (2D/3D), NumPy, Numba (optional JIT), pytest (118 tests).
Architecture: strict layer separation — `core/`, `sim/`, `io/` never import PySide6.

Known tech debt from v1.0:
- Property edit undo not wired (add/delete only)
- BVH excludes cylinder/prism faces (different intersection algorithms)
- Live preview and adaptive sampling disabled in MP mode (by design)

Potential v2 directions (from REQUIREMENTS.md v2 section):
- LGP-04/05/06: Extraction dot patterns, wedge LGP, dot pattern design tool
- SPEC-06/07: Wavelength-dependent refractive index (dispersion), spectral+uniformity co-optimization
- GEOM-04/05: Triangle mesh import (STL/OBJ), CAD/DXF import
- REND-01: VTK/PyVista 3D renderer for CAD-quality rendering
- BRDF-02: GGX microfacet BRDF model
- MAT-01: Temperature-dependent optical property LUTs

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Edge-lit before spectral | Edge-lit unlocks new product use cases; spectral improves fidelity of existing ones | ✓ Good — edge-lit LGP working, spectral built on top |
| QSplitter+QTabWidget instead of QDockWidget | Simpler, more predictable layout; user-approved deviation | ✓ Good — professional feel without docking complexity |
| Per-face optical properties via solid body abstraction | Solids (box=6 faces) need independent coatings per face | ✓ Good — face_optics dict works for LGP bottom reflector |
| Numba over GPU/CUDA | Lower complexity, works on all platforms, no driver dependencies | ✓ Good — optional dependency with graceful fallback |
| VTK renderer deferred to v2 | Binary size cost not justified; pyqtgraph.opengl sufficient for current geometry | ✓ Good — avoided 200MB+ dependency |
| Spectral+MP guard (force single-thread) | Spectral grid merging across processes is complex; ship single-thread first | ⚠️ Revisit — users with many sources pay a performance penalty |
| Adaptive sampling disabled in MP | Convergence requires centralized variance tracking | ⚠️ Revisit — could implement per-source convergence |
| SolidBox face_optics as dict, not per-face Material | Keeps material as box-level concept; face overrides via OpticalProperties | ✓ Good — clean separation of refractive index (material) from surface behavior |

## Constraints

- **Tech stack**: Must remain PySide6-based desktop app; core/sim/io must stay headless (no GUI imports)
- **Backwards compatibility**: Existing JSON project files must continue to load; use `.get(key, default)` pattern
- **Performance**: Simulation must remain interactive for quick-preview settings (~1k rays); high-quality runs can take longer
- **Dependencies**: Prefer pure-Python or well-maintained packages; avoid heavy frameworks that complicate PyInstaller builds

---
*Last updated: 2026-03-15 after v1.0 milestone*
