# Roadmap: Blu Optical Simulation — Phase 2

## Overview

Phase 2 extends a complete direct-lit Monte Carlo tracer into a full-fidelity optical simulator. The work runs in four phases driven by the dependency graph: refractive physics unlocks edge-lit LGP (the highest-value new product category), spectral integration wires existing groundwork into the tracer, performance acceleration makes large simulations viable, and advanced materials/geometry round out the physical model. Each phase delivers a coherent, verifiable capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Refractive Physics and LGP** - Snell's law, Fresnel/TIR, solid box body, and end-to-end edge-lit LGP simulation
- [ ] **Phase 2: Spectral Engine** - Per-ray wavelength, wavelength-dependent materials, spectral detector grids, CIE color display
- [ ] **Phase 3: Performance Acceleration** - Numba JIT for inner loops, BVH spatial acceleration, adaptive sampling
- [ ] **Phase 4: Advanced Materials and Geometry** - Tabulated BRDF, far-field detector, cylinder and prism solid bodies

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
**Plans**: TBD

Plans:
- [ ] 01-01: Fresnel/TIR physics module and epsilon fix
- [ ] 01-02: Solid body box primitive with per-face optical properties
- [ ] 01-03: LGP scene configuration, tracer integration, edge coupling KPI

### Phase 2: Spectral Engine
**Goal**: Engineers can run wavelength-aware simulations and see the detector result as a color image with color uniformity KPIs
**Depends on**: Phase 1
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-05
**Success Criteria** (what must be TRUE):
  1. Each simulated ray carries a wavelength sampled from the source SPD
  2. Material reflectance and transmittance values change with wavelength via user-defined tables
  3. Detector result can be viewed as an sRGB color image computed from CIE XYZ integration
  4. KPI dashboard shows delta-CCx and delta-CCy color uniformity across the detector plane
**Plans**: TBD

Plans:
- [ ] 02-01: Spectral accumulation vectorization, MP guard, per-ray wavelength wiring
- [ ] 02-02: Wavelength-dependent material properties, spectral GUI panel and color uniformity KPIs

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
- [ ] 03-01: Accumulator refactor for Numba compatibility and JIT kernel implementation
- [ ] 03-02: BVH build and traversal, adaptive sampling convergence criterion

### Phase 4: Advanced Materials and Geometry
**Goal**: Users can assign measured BRDF data to surfaces, capture far-field candela distributions, and build cylindrical and prism optical elements
**Depends on**: Phase 3
**Requirements**: BRDF-01, DET-01, GEOM-02, GEOM-03
**Success Criteria** (what must be TRUE):
  1. User can import a goniophotometer BRDF CSV and assign it to any surface; rays reflect per the tabulated distribution
  2. User can add a far-field angular detector, run a simulation, and export the candela distribution as an IES file
  3. User can create a cylinder solid body and a prism solid body as scene objects with independent face optical properties
**Plans**: TBD

Plans:
- [ ] 04-01: Tabulated BRDF import, 2D CDF importance sampling, surface assignment
- [ ] 04-02: Far-field angular detector with IES export, cylinder and prism solid body primitives

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Refractive Physics and LGP | 0/3 | Not started | - |
| 2. Spectral Engine | 0/2 | Not started | - |
| 3. Performance Acceleration | 0/2 | Not started | - |
| 4. Advanced Materials and Geometry | 0/2 | Not started | - |
