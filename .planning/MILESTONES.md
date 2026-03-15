# Milestones

## v1.0 Phase 2 Full-Fidelity Simulator (Shipped: 2026-03-15)

**Phases:** 7 | **Plans:** 19 | **Requirements:** 24/24 satisfied
**Commits:** 88 | **Files touched:** 125 | **Python LOC:** 18,457
**Timeline:** 2026-03-14 → 2026-03-15 | **Tests:** 118 passing
**Git range:** `05929aa..7558e63`

**Key accomplishments:**
1. Refractive physics engine (Snell's law, Fresnel coefficients, TIR) with SolidBox geometry and edge-lit LGP simulation
2. Per-ray wavelength spectral engine with CIE XYZ colorimetry, sRGB color images, and color uniformity KPIs (delta-CCx/CCy)
3. Numba JIT acceleration (10-50x speedup), BVH spatial indexing for 50+ surface scenes, adaptive sampling with convergence targeting
4. Tabulated BSDF import with 2D CDF importance sampling, far-field angular detector with IES export, cylinder and prism solid body primitives
5. Professional dark-themed UI with toolbar, undo/redo, collapsible property sections, live heatmap preview, colormap selector, and crosshair cursor
6. Cross-phase integration: all solid bodies participate in MP/spectral/BSDF paths; tab persistence; duplicate action; chromaticity scatter

**Remaining tech debt (4 items, all by-design or deferred):**
- BVH excludes cylinder/prism faces (different intersection algorithms)
- Property edit undo not wired through SetPropertyCommand (add/delete only)
- BSDF+spectral in MP path structurally deferred (guarded)
- Live heatmap preview disabled in MP mode (by design)

---

