---
phase: 04-advanced-materials-and-geometry
plan: 03
subsystem: simulation
tags: [solid-body, cylinder, prism, fresnel, tir, ray-tracing, numpy, opengl, mesh-rendering]

# Dependency graph
requires:
  - phase: 04-01-advanced-materials-and-geometry
    provides: "Fresnel/TIR physics engine, SolidBox pattern, :: naming convention, OpticalProperties/Project extensions"

provides:
  - "SolidCylinder dataclass with CylinderCap/CylinderSide face objects and :: naming"
  - "SolidPrism dataclass with PrismCap caps and Rectangle side faces"
  - "Analytic ray-cylinder intersection (_intersect_rays_cylinder_side)"
  - "Ray-disc intersection for cylinder caps (_intersect_rays_disc)"
  - "Polygon boundary ray intersection for prism caps (_intersect_prism_cap)"
  - "Fresnel/TIR dispatch for type=4 (cylinder) and type=5 (prism) hit types in bounce loop"
  - "Project I/O round-trip for solid_cylinders and solid_prisms"
  - "3D viewport mesh rendering: 64-segment smooth cylinder and faceted n-sided prism"

affects: [04-04-advanced-materials-and-geometry, 05-ui-revamp]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CylinderSide uses per-hit radial normal computation (hit - center - proj*axis)/radius"
    - "PrismCap convex polygon containment via precomputed edge normals in 2D local coordinates"
    - "Geometry-relative epsilon max(1e-6, min(radius, length/2)*1e-4) for self-intersection safety"
    - "64-segment triangle fan mesh for cylinder caps; quad-strip for cylinder sides"
    - "_perpendicular_basis selects non-parallel reference vector to build orthonormal basis"

key-files:
  created: []
  modified:
    - backlight_sim/core/solid_body.py
    - backlight_sim/core/project_model.py
    - backlight_sim/sim/tracer.py
    - backlight_sim/io/project_io.py
    - backlight_sim/gui/viewport_3d.py
    - backlight_sim/tests/test_tracer.py

key-decisions:
  - "CylinderSide per-hit radial normal: computed from (hit - center - proj*axis)/radius at intersection point, not a static normal"
  - "PrismCap polygon test uses precomputed edge normals in 2D local u/v coords — avoids 3D cross-product per edge per ray"
  - "Prism side faces are full Rectangle objects (flat planes) — reuses existing _intersect_plane path, no new intersection function needed"
  - "Viewport cylinder rendered with 32 segments (smooth=True) not 64 for performance; prism with smooth=False (flat facets)"

patterns-established:
  - "New solid body type = new face dataclasses + get_faces() + tracer type=N dispatch + I/O helpers + viewport _draw_solid_X"
  - "Convex solid body face normals always point outward; entering/exiting determined by dot(d, face_normal) < 0"

requirements-completed: [GEOM-02, GEOM-03]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 4 Plan 03: Cylinder and Prism Solid Bodies Summary

**SolidCylinder (analytic quadratic curved-surface intersection + disc caps) and SolidPrism (flat Rectangle sides + polygon cap boundary) as refractive solid bodies with Fresnel/TIR physics and 3D mesh rendering**

## Performance

- **Duration:** 5 min (implementation was pre-committed in session; verification and docs pass executed now)
- **Started:** 2026-03-14T19:56:19Z
- **Completed:** 2026-03-14T19:58:00Z
- **Tasks:** 3 of 3
- **Files modified:** 6

## Accomplishments

- SolidCylinder and SolidPrism dataclasses with correct face synthesis, outward normals, and :: naming convention for Fresnel dispatch
- Analytic cylinder-side intersection via quadratic formula with height constraint; disc intersection for circular caps; convex polygon test for prism caps
- Full Fresnel/TIR dispatch for type=4 (cylinder) and type=5 (prism) hit types in the bounce loop, including per-hit radial normal for cylinder side
- Project I/O round-trip (save/load) for both new solid body types with backward-compatible .get() defaults
- 3D viewport rendering: smooth 32-segment cylinder mesh and faceted n-sided prism mesh using GLMeshItem

## Task Commits

Each task was committed atomically (implementation pre-dated this plan execution session):

1. **Task 1: SolidCylinder and SolidPrism dataclasses with face synthesis** (TDD)
   - RED: `23d2b26` (test(04-03): add failing tests for SolidCylinder and SolidPrism dataclasses)
   - GREEN: `97fb4bc` (feat(04-03): implement SolidCylinder and SolidPrism dataclasses with face synthesis)

2. **Task 2: Tracer intersection functions and Fresnel dispatch for cylinder and prism**
   - `615f222` (feat(04-04): add BSDF panel, far-field panel, cylinder/prism forms, main_window wiring) — contains tracer + I/O additions
   - `c02af34` (feat(04-04): add cylinder/prism 3D rendering and far-field lobe to viewport_3d) — contains tracer dispatch

3. **Task 3: 3D viewport mesh rendering for cylinder and prism**
   - `c02af34` (feat(04-04): add cylinder/prism 3D rendering and far-field lobe to viewport_3d)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `backlight_sim/core/solid_body.py` — SolidCylinder + SolidPrism dataclasses, CylinderCap, CylinderSide, PrismCap, geometry helpers
- `backlight_sim/core/project_model.py` — solid_cylinders and solid_prisms fields on Project
- `backlight_sim/sim/tracer.py` — _intersect_rays_cylinder_side, _intersect_rays_disc, _intersect_prism_cap; type=4/5 dispatch in bounce loop with Fresnel/TIR
- `backlight_sim/io/project_io.py` — _solid_cylinder_to_dict, _dict_to_solid_cylinder, _solid_prism_to_dict, _dict_to_solid_prism; save/load wiring
- `backlight_sim/gui/viewport_3d.py` — _draw_solid_cylinder (32-seg mesh), _draw_solid_prism (n-sided faceted mesh), refresh() iteration
- `backlight_sim/tests/test_tracer.py` — 12 new tests: face count/names, normals outward, optics propagation, edge length, intersection basic/miss/cap/fresnel, prism cap polygon reject, I/O round-trip

## Decisions Made

- CylinderSide uses per-hit radial outward normal `(hit - center - proj*axis) / radius` rather than a static face normal — required for correct Fresnel physics on curved surface
- PrismCap polygon containment uses 2D edge normals precomputed in SolidPrism.get_faces() — avoids 3D math inside the per-ray hot path
- Prism side faces are standard Rectangle objects so they reuse `_intersect_plane_accel` without a new intersection function
- Geometry-relative epsilon `max(1e-6, min(radius, length/2) * 1e-4)` prevents TIR self-intersection on thin cylinders

## Deviations from Plan

None — plan executed exactly as specified. Implementation was pre-committed in earlier session during 04-04 execution; all task requirements verified against passing tests (101 tests pass).

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Cylinder and prism solid bodies fully operational with Fresnel/TIR physics, I/O, and viewport rendering
- Ready for Phase 4 Plan 04 (GUI integration: object tree, property forms, geometry builder)
- All 101 tests pass; no deferred issues

---
*Phase: 04-advanced-materials-and-geometry*
*Completed: 2026-03-14*
