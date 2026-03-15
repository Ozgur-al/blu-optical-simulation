---
phase: 01-refractive-physics-and-lgp
plan: 01
subsystem: physics-engine
tags: [fresnel, snell, tir, solid-body, ray-tracing, tdd]
requirements: [LGP-02, GEOM-01]
requirements-completed: [LGP-02, GEOM-01]

dependency_graph:
  requires: []
  provides:
    - SolidBox dataclass with get_faces() and FACE_NAMES
    - _fresnel_unpolarized() helper (vectorized, TIR-correct)
    - _refract_snell() helper (vectorized Snell's law)
    - per-ray current_n tracking in tracer bounce loop
    - solid_body_stats in SimulationResult
    - solid_bodies list in Project
  affects:
    - backlight_sim/sim/tracer.py (bounce loop extended with type=3 solid face hits)
    - backlight_sim/core/project_model.py (new solid_bodies field)
    - backlight_sim/core/detectors.py (new solid_body_stats field)

tech_stack:
  added:
    - backlight_sim/core/solid_body.py (new file — SolidBox dataclass)
  patterns:
    - TDD: RED (failing tests) → GREEN (physics implementation)
    - Stochastic Russian roulette for Fresnel reflect/transmit decision
    - Geometry-relative epsilon (min(dimensions)*1e-4) for self-intersection avoidance
    - on_into/on_back normal convention for Snell + reflection math

key_files:
  created:
    - backlight_sim/core/solid_body.py
  modified:
    - backlight_sim/sim/tracer.py
    - backlight_sim/core/detectors.py
    - backlight_sim/core/project_model.py
    - backlight_sim/tests/test_tracer.py

decisions:
  - Use on_into (INTO new medium) convention for _refract_snell; internally flipped
    to n_hat (toward incoming ray) for the standard refraction formula
  - Geometry-relative epsilon computed as max(1e-6, min(box.dimensions)*1e-4)
    per STATE.md blocker to avoid TIR self-intersection in thin slabs
  - SolidBox faces identified by "::" in face name to distinguish from regular
    Rectangle surfaces — no new type needed, preserves existing surface API
  - Both _run_single() and _trace_single_source() implement identical Fresnel
    branch to maintain single/multiprocessing parity

metrics:
  duration_seconds: 458
  completed_date: "2026-03-14"
  tasks_completed: 2
  tests_before: 23
  tests_after: 39
  tests_added: 16
  files_created: 1
  files_modified: 4
---

# Phase 1 Plan 1: SolidBox and Fresnel/TIR Physics Engine Summary

**One-liner:** PMMA slab Fresnel/TIR physics with SolidBox geometry primitive, per-ray refractive index tracking, and per-face flux accounting — TDD implementation.

## What Was Built

### `backlight_sim/core/solid_body.py` (new)
`SolidBox` dataclass with `get_faces()` returning 6 axis-aligned `Rectangle` faces. Face names follow `"{box_name}::{face_id}"` pattern. Face normals point outward. `face_optics` dict allows per-face optical property overrides. `FACE_NAMES` constant defines canonical face ordering.

### `backlight_sim/sim/tracer.py` (extended)
Two new module-level physics helpers:
- `_fresnel_unpolarized(cos_theta_i, n1, n2)` — vectorized unpolarized Fresnel reflectance; handles TIR via `np.where(sin_t_sq >= 1, 1.0, R)`.
- `_refract_snell(directions, oriented_normals, n1, n2)` — vectorized Snell's law refraction; oriented_normals points INTO the new medium.

`_run_single()` modifications:
- Expands `project.solid_bodies` into `solid_faces` list before the bounce loop
- Builds `solid_face_map` (face name → box, face_id, box_n, geom_eps)
- Initializes per-ray `current_n = np.ones(n_rays)` for medium tracking
- Adds type=3 intersection pass for solid faces in the bounce loop
- Fresnel branch: determines entering/exiting by `dot(d, face_normal) < 0`; uses geometry-relative epsilon; does stochastic reflect/refract via Russian roulette; updates `current_n` only for refracted rays
- Writes `solid_body_stats` to `SimulationResult`

`_trace_single_source()` (MP path) receives identical SolidBox/Fresnel treatment; returns `sb_stats` in result dict. `_run_multiprocess()` merges per-source stats by summing face flux values.

### `backlight_sim/core/detectors.py` (extended)
`SimulationResult.solid_body_stats` field added (default empty dict). Structure: `{ box_name: { face_id: { "entering_flux": float, "exiting_flux": float } } }`.

### `backlight_sim/core/project_model.py` (extended)
`Project.solid_bodies: list[SolidBox]` field added (default empty list). `SolidBox` imported from `backlight_sim.core.solid_body`.

## Test Results

| Metric | Value |
|--------|-------|
| Tests before | 23 |
| Tests added | 16 |
| Tests after | 39 |
| All passing | Yes |

New tests cover: SolidBox geometry (face count, centers, normals, sizes, optics override, material propagation), Project/SimulationResult data model fields, Fresnel coefficients (normal incidence R≈0.04, TIR R=1.0, grazing R→1.0), Snell's law (normal incidence straight-through, oblique n1·sin_i=n2·sin_t), PMMA slab scene (non-zero detector flux, solid_body_stats populated, no self-intersection at 10k rays/100 bounces).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Snell's law normal orientation convention**
- **Found during:** Task 2 (GREEN phase — Snell tests failed)
- **Issue:** `_refract_snell` was called with `on` = face_normal for entering (pointing outward/downward) instead of `-face_normal` (pointing INTO new medium). This caused `cos_i = -dot(d, on)` to be negative (clipped to 0), producing no refraction.
- **Fix:** Renamed `on` to `on_into` (always points INTO new medium): `on_into = -face_normal` for entering, `on_into = +face_normal` for exiting. Updated `_refract_snell` formula to use `cos_i = dot(d, on_into)`. Added `on_back = -on_into` for reflection origin offset.
- **Files modified:** `backlight_sim/sim/tracer.py`
- **Commit:** 1cfa779

**2. [Rule 1 - Bug] Fixed reflection formula normal direction**
- **Found during:** Same as above (reflection formula used wrong normal)
- **Issue:** Reflection formula `d' = d - 2*(d·n)*n` requires `n` pointing toward incoming ray, but was using `on_into` (pointing away from incoming ray).
- **Fix:** Used `on_back` (= `-on_into`) in the reflection formula for both `_run_single()` and `_trace_single_source()`.
- **Files modified:** `backlight_sim/sim/tracer.py`
- **Commit:** 1cfa779 (same fix commit)

## Self-Check: PASSED

- `backlight_sim/core/solid_body.py` — FOUND
- `.planning/phases/01-refractive-physics-and-lgp/01-01-SUMMARY.md` — FOUND
- Commit `ab3a055` (test/RED phase) — FOUND
- Commit `1cfa779` (feat/GREEN phase) — FOUND
- All 39 tests pass
