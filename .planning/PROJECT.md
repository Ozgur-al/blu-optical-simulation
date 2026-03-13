# Blu Optical Simulation — Phase 2

## What This Is

A Python desktop application for optical simulation of backlight units (BLU), targeting engineers who need fast design iteration. Uses Monte Carlo ray tracing with a PySide6 GUI. Phase 2 extends the engine from a direct-lit-only tool with simplified physics to a full-fidelity optical simulator supporting edge-lit/LGP, spectral wavelength simulation, refractive optics, 3D solid body geometry, and high-performance computation.

## Core Value

Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.

## Requirements

### Validated

- ✓ Direct-lit Monte Carlo ray tracing engine — existing
- ✓ Rectangular cavity geometry with tilted walls — existing
- ✓ LED grid placement with pitch/count modes — existing
- ✓ Angular distribution import (CSV/TXT/IES/LDT) — existing
- ✓ Material system (reflector/absorber/diffuser with reflectance, transmittance, haze) — existing
- ✓ Planar detector with 2D grid accumulation — existing
- ✓ Sphere detector with 3D visualization — existing (partial)
- ✓ Full KPI dashboard (uniformity, efficiency, hotspot, edge-center, design score) — existing
- ✓ Project save/load (JSON), variant cloning, design history — existing
- ✓ 3D viewport (pyqtgraph.opengl) with wireframe/solid/transparent modes — existing
- ✓ Single + multi-parameter sweep with Pareto front — existing
- ✓ LED enable/disable, bin tolerance, current scaling, thermal derating — existing
- ✓ Export PNG/KPI CSV/Grid CSV/HTML report/batch ZIP — existing
- ✓ Spectral utilities (CIE observer, SPD sampling, XYZ→RGB) — existing (sim/spectral.py, not yet integrated into tracer)
- ✓ Optical properties per-surface override (OpticalProperties separate from Material) — existing (partial)
- ✓ Multiprocessing via ProcessPoolExecutor — existing
- ✓ 2D LED layout editor with drag-and-drop — existing
- ✓ Section views, histograms, CDF analysis plots — existing
- ✓ Interactive ROI on heatmap — existing
- ✓ Haze/scatter proxy — existing

### Active

- [ ] Edge-lit / LGP simulation engine (coupling, propagation, TIR extraction, dot pattern)
- [ ] Spectral wavelength-based simulation integrated into tracer (per-ray wavelength, spectral detector grids)
- [ ] Refractive index and TIR (Snell's law, Fresnel equations in tracer)
- [ ] BRDF / measured reflectance data support
- [ ] Per-face optical properties on solid bodies (6 faces per solid, each with independent optical properties)
- [ ] 3D solid body geometry primitives (box, cylinder, prism — not just rectangles)
- [ ] Better 3D renderer (VTK/pyvistaqt replacing pyqtgraph.opengl for CAD-quality rendering)
- [ ] Non-rectangular geometry support
- [ ] CAD/DXF import
- [ ] Numba JIT acceleration for ray tracing inner loops
- [ ] Adaptive sampling / BVH spatial acceleration
- [ ] Far-field / angular detector
- [ ] Temperature-dependent material properties
- [ ] Constraint-based Pareto optimization

### Out of Scope

- Polarization-based models — extremely niche, adds major complexity with little practical benefit for BLU
- Multi-edge LGP injection optimization — defer to Phase 3 after basic edge-lit works
- Bayesian/Optuna optimization — premature; Pareto sweep sufficient for now
- Mobile/web interface — desktop-only tool

## Context

This is a mature Phase 1 codebase: 98 of 110 originally planned tasks are complete. The 12 deferred items form the core of Phase 2. The architecture is clean with strict layer separation (core/sim/io never import PySide6). Existing partial work includes:

- `sim/spectral.py`: CIE 1931 observer, SPD sampling, XYZ→sRGB conversion — groundwork for spectral engine
- `gui/receiver_3d.py`: Sphere detector 3D visualization widget — partially integrated
- `core/materials.py`: `OpticalProperties` dataclass already exists alongside `Material` — per-surface override pattern started

The priority order for Phase 2 is:
1. **Edge-lit / LGP** — unlocks a new product category
2. **Physical fidelity** — spectral, refractive, BRDF, per-face materials, solid bodies, better 3D renderer
3. **Performance** — Numba, adaptive sampling, BVH — make it fast enough for production workloads

## Constraints

- **Tech stack**: Must remain PySide6-based desktop app; core/sim/io must stay headless (no GUI imports)
- **Backwards compatibility**: Existing JSON project files must continue to load; use `.get(key, default)` pattern
- **Performance**: Simulation must remain interactive for quick-preview settings (~1k rays); high-quality runs can take longer
- **Dependencies**: Prefer pure-Python or well-maintained packages; avoid heavy frameworks that complicate PyInstaller builds

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Edge-lit before spectral | Edge-lit unlocks new product use cases; spectral improves fidelity of existing ones | — Pending |
| VTK/pyvistaqt for 3D renderer | pyqtgraph.opengl is limited for solid body rendering; VTK is industry standard for scientific viz | — Pending |
| Per-face optical properties via solid body abstraction | Solids (box=6 faces) need independent coatings per face; current Rectangle has single material | — Pending |
| Numba over GPU/CUDA | Lower complexity, works on all platforms, no driver dependencies | — Pending |

---
*Last updated: 2025-07-11 after initialization*
