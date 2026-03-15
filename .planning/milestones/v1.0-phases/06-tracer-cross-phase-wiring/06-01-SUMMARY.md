---
phase: 06-tracer-cross-phase-wiring
plan: 01
subsystem: sim/tracer
tags: [multiprocessing, solid-body, cylinder, prism, fresnel, tdd]
dependency_graph:
  requires: [solid_body.SolidCylinder, solid_body.SolidPrism, _trace_single_source, _run_multiprocess]
  provides: [cylinder MP tracing, prism MP tracing, merged sb_stats for cylinders/prisms]
  affects: [backlight_sim/sim/tracer.py]
tech_stack:
  added: []
  patterns: [TDD red-green, module-level function expansion, sb_stats merge]
key_files:
  created: []
  modified:
    - backlight_sim/sim/tracer.py
    - backlight_sim/tests/test_tracer.py
decisions:
  - "_trace_single_source expands solid_cylinders/solid_prisms using getattr(project, ..., []) guard — safe if old project objects lack these attributes"
  - "Cylinder/prism sb_stats merge in _run_multiprocess uses getattr guard for solid_cylinders; solid_prisms also uses getattr — consistent with expansion pattern"
  - "No path recording in MP bounce loop for cylinder/prism (matching existing _trace_single_source design — MP has no n_rec_active)"
metrics:
  duration_seconds: 138
  completed_date: "2026-03-15"
  tasks_completed: 1
  files_modified: 2
---

# Phase 06 Plan 01: Tracer Cross-Phase Wiring Summary

Wire SolidCylinder and SolidPrism geometry into the multiprocessing tracer path, adding cylinder/prism expansion, intersection, and Fresnel dispatch to `_trace_single_source`, and fixing `_run_multiprocess` to merge cylinder/prism sb_stats.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing tests for cylinder/prism MP wiring | 405a9f0 | backlight_sim/tests/test_tracer.py |
| 1 (GREEN) | Wire cylinder/prism expansion and dispatch into MP tracer path | 7f65cb6 | backlight_sim/sim/tracer.py |

## What Was Built

**Problem:** `_trace_single_source` (the module-level function used for multiprocessing) was missing cylinder and prism geometry handling. Only `_run_single` (the single-threaded path) expanded `solid_cylinders` and `solid_prisms` into face objects and performed intersection/dispatch for them. This meant any scene with cylinders or prisms running in MP mode silently produced wrong results — rays passed through solid geometry without Fresnel physics, and sb_stats were always empty for cylinder/prism bodies.

**Fix applied in `_trace_single_source`:**
1. Added cylinder expansion block (lines after SolidBox sb_stats init): loops over `project.solid_cylinders`, builds `cyl_faces`, `cyl_face_map`, and initializes `sb_stats` per cylinder body.
2. Added prism expansion block: same pattern for `project.solid_prisms` with `prism_faces`, `prism_face_map`.
3. Added type=4 cylinder intersection loop in the bounce loop (brute-force path only, after SolidBox): uses `_intersect_rays_disc` for CylinderCap and `_intersect_rays_cylinder_side` for CylinderSide.
4. Added type=5 prism intersection loop: uses `_intersect_prism_cap` for PrismCap and `_intersect_plane_accel` for Rectangle side faces.
5. Added type=4 cylinder Fresnel/TIR dispatch: per-hit radial normal for CylinderSide, flat normal for CylinderCap, stochastic refract/reflect, sb_stats accounting.
6. Added type=5 prism Fresnel/TIR dispatch: flat normal from face, stochastic refract/reflect, sb_stats accounting.

**Fix applied in `_run_multiprocess`:**
7. Added cylinder and prism initialization loops for `merged_sb_stats`, so cylinder/prism stats from each subprocess are correctly merged into the final result.

## Verification

```
pytest backlight_sim/tests/test_tracer.py -v
106 passed in 6.68s
```

- 4 new tests added and passing
- 102 existing tests still passing — no regressions

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `backlight_sim/sim/tracer.py` modified (cyl_faces expansion, prism_faces expansion, type=4/5 intersection, type=4/5 dispatch, _run_multiprocess merge)
- [x] `backlight_sim/tests/test_tracer.py` modified (4 new tests added)
- [x] Commit 405a9f0 exists (RED tests)
- [x] Commit 7f65cb6 exists (GREEN implementation)
- [x] 106 tests pass
