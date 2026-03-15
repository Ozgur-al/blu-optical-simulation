# Roadmap: Blu Optical Simulation — Phase 2

## Overview

Phase 2 extends a complete direct-lit Monte Carlo tracer into a full-fidelity optical simulator. The work runs in four phases driven by the dependency graph: refractive physics unlocks edge-lit LGP (the highest-value new product category), spectral integration wires existing groundwork into the tracer, performance acceleration makes large simulations viable, and advanced materials/geometry round out the physical model. Each phase delivers a coherent, verifiable capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Refractive Physics and LGP** - Snell's law, Fresnel/TIR, solid box body, and end-to-end edge-lit LGP simulation (completed 2026-03-14)
- [x] **Phase 2: Spectral Engine** - Per-ray wavelength, wavelength-dependent materials, spectral detector grids, CIE color display (completed 2026-03-14)
- [x] **Phase 3: Performance Acceleration** - Numba JIT for inner loops, BVH spatial acceleration, adaptive sampling (completed 2026-03-14)
- [x] **Phase 4: Advanced Materials and Geometry** - Tabulated BRDF, far-field detector, cylinder and prism solid bodies (completed 2026-03-14)
- [x] **Phase 6: Tracer Cross-Phase Wiring** - Fix Cylinder/Prism MP dispatch, SolidBox face_optics, spectral solid body Fresnel, BSDF+spectral exclusion (completed 2026-03-15)
- [x] **Phase 7: UI + Spectral Display Fixes** - Wire duplicate action, tab state persistence, chromaticity scatter update, live preview spectral color (completed 2026-03-15)

## Phase Details

### Phase 1: Refractive Physics and LGP
**Goal**: Engineers can simulate an edge-lit LGP panel with physically accurate TIR propagation and read edge coupling efficiency from the KPI dashboard
**Depends on**: Nothing (first phase)
**Requirements**: LGP-01, LGP-02, LGP-03, GEOM-01
**Success Criteria** (what must be TRUE):
  1. User can place an LGP slab as a solid box with independent optical properties on each of its 6 faces
  2. A ray entering a dielectric face refracts per Snell's law, undergoes TIR when angle exceeds critical angle, and exits with Fresnel-correct transmission coefficient
  3. User can run an edge-lit scene (LED at slab edge, receiver above slab) and see non-zero illuminance on the detector
  4. KPI dashboard shows edge coupling efficiency (flux into LGP edge / total emitted) after each simulation
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — SolidBox dataclass + Fresnel/TIR physics engine (TDD)
- [x] 01-02-PLAN.md — Project I/O, LGP scene builder, preset, KPI dashboard
- [x] 01-03-PLAN.md — GUI: object tree, properties panel, viewport, geometry builder

### Phase 2: Spectral Engine
**Goal**: Engineers can run wavelength-aware simulations and see the detector result as a color image with color uniformity KPIs
**Depends on**: Phase 1
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-05
**Success Criteria** (what must be TRUE):
  1. Each simulated ray carries a wavelength sampled from the source SPD
  2. Material reflectance and transmittance values change with wavelength via user-defined tables
  3. Detector result can be viewed as an sRGB color image computed from CIE XYZ integration
  4. KPI dashboard shows delta-CCx and delta-CCy color uniformity across the detector plane
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Data model, custom SPD lookup, blackbody generator, wavelength-dependent material interpolation, MP spectral guard, project I/O, tests
- [x] 02-02-PLAN.md — CIE colorimetry helpers, Spectral Data GUI panel, chromaticity diagram, Color Uniformity KPIs, click-to-inspect, export extensions

### Phase 3: Performance Acceleration
**Goal**: A 1M-ray LGP simulation completes 10-50x faster than pure NumPy via Numba JIT, and large scenes use BVH acceleration
**Depends on**: Phase 2
**Requirements**: PERF-01, PERF-02, PERF-03
**Success Criteria** (what must be TRUE):
  1. Ray-surface intersection and flux accumulation inner loops are Numba JIT-compiled and fall back gracefully to NumPy if Numba is unavailable
  2. Scenes with 50+ surfaces use BVH traversal and show measurable throughput improvement over brute-force intersection
  3. Adaptive sampling halts ray generation per source automatically when detector variance drops below the configured threshold
**Plans**: TBD

Plans:
- [x] 03-01-PLAN.md — Numba JIT kernels (sim/accel.py), tracer dispatch, GUI status indicator, PyInstaller spec update
- [ ] 03-02: BVH build and traversal, adaptive sampling convergence criterion

### Phase 4: Advanced Materials and Geometry
**Goal**: Users can assign measured BRDF data to surfaces, capture far-field candela distributions, and build cylindrical and prism optical elements
**Depends on**: Phase 3
**Requirements**: BRDF-01, DET-01, GEOM-02, GEOM-03
**Success Criteria** (what must be TRUE):
  1. User can import a goniophotometer BRDF CSV and assign it to any surface; rays reflect per the tabulated distribution
  2. User can add a far-field angular detector, run a simulation, and export the candela distribution as an IES file
  3. User can create a cylinder solid body and a prism solid body as scene objects with independent face optical properties
**Plans**: 5 plans

Plans:
- [x] 04-01: Tabulated BRDF import, 2D CDF importance sampling, surface assignment
- [x] 04-02: Far-field angular detector with IES export
- [x] 04-03: SolidCylinder + SolidPrism dataclasses, analytic intersection, Fresnel/TIR dispatch, I/O, viewport mesh rendering
- [x] 04-04: GUI integration (BSDFPanel, FarFieldPanel, SolidCylinderForm/PrismForm, 3D intensity lobe, MainWindow wiring)
- [ ] 04-05-PLAN.md — Gap closure: menu/toolbar entries, BSDF visibility, far-field tab auto-open, polar plot lock, lobe gradient, radius visibility

### Phase 5: UI Revamp
**Goal**: Application has a professional dark-themed interface with dockable panels, toolbar, undo/redo, collapsible properties, enhanced heatmap with live simulation preview — matching the look and workflow of engineering tools like Blender and Fusion 360
**Depends on**: Phase 4
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08
**Success Criteria** (what must be TRUE):
  1. Application launches with dark theme and teal accent across all widgets, including pyqtgraph plots and 3D viewport
  2. All panels are dockable QDockWidgets with layout persistence via QSettings
  3. Toolbar provides quick access to common actions and one-click object creation
  4. Scene mutations (add/delete) can be undone/redone via Ctrl+Z / Ctrl+Y
  5. Properties panel uses collapsible sections and object tree shows per-type colored icons
  6. Heatmap updates live during simulation and shows selectable colormaps with KPI threshold coloring
**Plans**: 4 plans

Plans:
- [x] 05-01-PLAN.md — Dark theme (QSS + pyqtgraph config), QDockWidget layout, toolbar, QSettings persistence
- [x] 05-02-PLAN.md — Undo/redo system (QUndoStack commands, Edit menu, toolbar integration)
- [x] 05-03-PLAN.md — Collapsible properties panel (CollapsibleSection widget) + object tree icons and context menus
- [ ] 05-04-PLAN.md — Enhanced heatmap (colormap selector, crosshair, KPI cards) + live simulation preview

### Phase 6: Tracer Cross-Phase Wiring
**Goal**: All solid body geometries participate correctly in multiprocessing, spectral, and BSDF simulation paths — closing 4 integration gaps and 3 broken E2E flows
**Depends on**: Phases 1-4
**Requirements**: GEOM-02, GEOM-03, LGP-01, SPEC-04, BRDF-01
**Gap Closure:** Closes integration/flow gaps from v1.0 audit
**Success Criteria** (what must be TRUE):
  1. Cylinder and Prism solid bodies produce correct flux when `use_multiprocessing=True`
  2. SolidBox.face_optics per-face material overrides are consumed by the tracer during bounce dispatch
  3. Wavelength-dependent R/T from spectral_material_data is applied in Fresnel branches for SolidBox/Cylinder/Prism (type=3/4/5)
  4. Surfaces with both BSDF and spectral data apply wavelength-dependent R/T before BSDF scattering (no silent exclusion)
**Plans**: 2 plans

Plans:
- [ ] 06-01-PLAN.md — Cylinder/Prism MP dispatch + sb_stats merge in _trace_single_source and _run_multiprocess
- [ ] 06-02-PLAN.md — SolidBox face_optics consumption, spectral n(lambda) in Fresnel branches, BSDF+spectral composition

### Phase 7: UI + Spectral Display Fixes
**Goal**: All UI features work end-to-end (duplicate action, tab persistence) and spectral display paths are complete (chromaticity scatter, live preview color mode)
**Depends on**: Phase 5, Phase 2
**Requirements**: UI-02, UI-06, SPEC-03
**Gap Closure:** Closes requirement gaps UI-02/UI-06 and display integration gaps from v1.0 audit
**Success Criteria** (what must be TRUE):
  1. Tab state (which tabs are open, their order) persists between sessions via QSettings
  2. Right-clicking a scene object and selecting Duplicate creates a copy of that object
  3. SpectralDataPanel chromaticity scatter overlay updates after simulation completes
  4. Live heatmap preview shows spectral color mode during spectral simulations (grid_spectral included in partial results)
**Plans**: 1 plan

Plans:
- [ ] 07-01-PLAN.md — Tab persistence fix, duplicate validation, chromaticity scatter cloud, live preview spectral color

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Refractive Physics and LGP | 3/3 | Complete   | 2026-03-14 |
| 2. Spectral Engine | 2/2 | Complete   | 2026-03-14 |
| 3. Performance Acceleration | 2/2 | Complete   | 2026-03-14 |
| 4. Advanced Materials and Geometry | 5/5 | Complete   | 2026-03-14 |
| 5. UI Revamp | 4/4 | Complete   | 2026-03-14 |
| 6. Tracer Cross-Phase Wiring | 2/2 | Complete   | 2026-03-15 |
| 7. UI + Spectral Display Fixes | 1/1 | Complete   | 2026-03-15 |
