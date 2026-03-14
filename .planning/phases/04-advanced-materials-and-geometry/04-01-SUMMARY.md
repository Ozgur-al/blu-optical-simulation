---
phase: 04-advanced-materials-and-geometry
plan: 01
subsystem: simulation
tags: [bsdf, monte-carlo, sampling, materials, optical-properties]

# Dependency graph
requires:
  - phase: 03-performance-acceleration
    provides: BVH spatial acceleration, Numba JIT kernels, adaptive sampling — tracer infrastructure that BSDF dispatch is integrated into
provides:
  - BSDF CSV import (load_bsdf_csv) and energy conservation validation (validate_bsdf) in io/bsdf_io.py
  - 2D CDF importance sampling (sample_bsdf, precompute_bsdf_cdfs) in sim/sampling.py
  - bsdf_profile_name field on OpticalProperties and Material dataclasses
  - bsdf_profiles dict on Project dataclass
  - BSDF dispatch in tracer bounce loop (both single-thread and MP paths)
  - Project JSON round-trip for bsdf_profiles
affects: [04-02, 04-03, 04-04, gui-panels, properties-panel]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "2D CDF importance sampling: precompute CDFs at tracer init time keyed by profile name; invert per ray via np.interp"
    - "Long-format BSDF CSV pivot: unique theta_in/theta_out values extracted, (M, N) intensity matrix built via index maps"
    - "BSDF dispatch priority: bsdf_profile_name check runs before all scalar reflectance/transmittance/diffuse/haze logic"

key-files:
  created:
    - backlight_sim/io/bsdf_io.py
  modified:
    - backlight_sim/core/materials.py
    - backlight_sim/core/project_model.py
    - backlight_sim/sim/sampling.py
    - backlight_sim/sim/tracer.py
    - backlight_sim/tests/test_tracer.py

key-decisions:
  - "BSDF CSV requires BOTH refl_intensity and trans_intensity columns — partial BSDF rejected with ValueError"
  - "Energy conservation check uses raw row sums (not solid-angle-weighted integrals) with 1e-3 tolerance — practical check for import-time validation"
  - "precompute_bsdf_cdfs called at tracer init time, not per-bounce — avoids repeated CDF construction for large scenes"
  - "BSDF dispatch overrides ALL scalar behavior: reflectance, transmittance, is_diffuse, haze all bypassed when bsdf_profile_name is set"
  - "Reflect/transmit split uses stochastic roll: p_refl = refl_total / (refl_total + trans_total) per theta_in bin"

patterns-established:
  - "sample_bsdf accepts cdfs=None for on-the-fly use or precomputed dict for performance — same pattern as 1D angular distribution"
  - "bsdf_profiles serialized as plain nested lists in JSON (not numpy arrays) for human-readability and backward compat via .get(key, {})"

requirements-completed: [BRDF-01]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 4 Plan 01: BSDF Engine Summary

**Tabulated BSDF CSV import, 2D CDF importance sampling, and tracer dispatch replacing scalar reflectance with measured goniophotometer data**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-14T21:15:00Z
- **Completed:** 2026-03-14T21:17:00Z (initial tasks); tracer integration completed within 95e2c49
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `io/bsdf_io.py` with `load_bsdf_csv` (long-format CSV pivot into M×N matrix) and `validate_bsdf` (energy conservation check with 1e-3 tolerance)
- Added `sample_bsdf` and `precompute_bsdf_cdfs` to `sim/sampling.py` — 2D CDF inversion with per-theta_in row CDFs, reflect/transmit hemisphere selection
- Added `bsdf_profile_name: str = ""` to `OpticalProperties` and `Material` dataclasses (backward compatible)
- Added `bsdf_profiles: dict = field(default_factory=dict)` to `Project` dataclass
- Integrated BSDF dispatch into both single-thread and multiprocessing tracer bounce loops; precomputes CDFs at init; overrides all scalar optical behavior when active
- Project JSON round-trip preserves `bsdf_profiles` via `.get("bsdf_profiles", {})` backward-compat pattern
- 11 new BSDF tests added (data model, CSV import, sampling, tracer integration, I/O round-trip); all 101 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: BSDF data model, CSV import, 2D CDF sampling (TDD RED)** - `aac5099` (test)
2. **Task 1: BSDF data model, CSV import, 2D CDF sampling (TDD GREEN)** - `7db83a2` (feat)
3. **Task 2: Tracer BSDF dispatch and project I/O** - `95e2c49` (fix — included in BVH/adaptive sampling rewrite)

_Note: TDD tasks have two commits (test RED → feat GREEN). Task 2 tracer dispatch was co-committed with the BVH rewrite in 95e2c49._

## Files Created/Modified

- `backlight_sim/io/bsdf_io.py` — BSDF CSV import (`load_bsdf_csv`) and validation (`validate_bsdf`)
- `backlight_sim/sim/sampling.py` — Added `sample_bsdf` and `precompute_bsdf_cdfs` functions
- `backlight_sim/core/materials.py` — Added `bsdf_profile_name: str = ""` to `OpticalProperties` and `Material`
- `backlight_sim/core/project_model.py` — Added `bsdf_profiles: dict[str, dict] = field(default_factory=dict)` to `Project`
- `backlight_sim/sim/tracer.py` — BSDF CDF cache initialization at tracer start; BSDF dispatch in bounce loop (single-thread + MP paths)
- `backlight_sim/tests/test_tracer.py` — 11 new BSDF tests covering all success criteria

## Decisions Made

- BSDF CSV requires both `refl_intensity` and `trans_intensity` columns — user requested full BSDF, partial is rejected with `ValueError`
- Energy conservation uses raw row sum check with 1e-3 tolerance (not solid-angle-weighted integrals) — practical for import-time validation without requiring normalized data
- `precompute_bsdf_cdfs` called once at tracer init, keyed by profile name — avoids per-bounce CDF construction overhead
- BSDF dispatch bypasses ALL scalar behavior: `reflectance`, `transmittance`, `is_diffuse`, `haze` all ignored when `bsdf_profile_name` is non-empty and found in `project.bsdf_profiles`
- Stochastic reflect/transmit split: `p_refl = refl_total / (refl_total + trans_total)` per theta_in bin — energy-correct split

## Deviations from Plan

None — plan executed exactly as written. The tracer BSDF dispatch (Task 2) was implemented within the same session's BVH rewrite commit rather than a standalone commit, but the functionality matches the plan specification exactly.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- BSDF engine complete: `load_bsdf_csv` → assign `bsdf_profile_name` on `OpticalProperties` → tracer samples from tabulated data
- GUI panel for BSDF import/assignment ready to implement in Phase 4 Plan 4 (04-04)
- All 101 tests pass; backward compatibility with existing projects confirmed

---

## Self-Check: PASSED

- `backlight_sim/io/bsdf_io.py` — FOUND
- `backlight_sim/sim/sampling.py` (sample_bsdf, precompute_bsdf_cdfs) — FOUND
- `backlight_sim/core/materials.py` (bsdf_profile_name) — FOUND
- `backlight_sim/core/project_model.py` (bsdf_profiles) — FOUND
- Commit `aac5099` — FOUND
- Commit `7db83a2` — FOUND
- All 101 tests pass — VERIFIED

---
*Phase: 04-advanced-materials-and-geometry*
*Completed: 2026-03-14*
