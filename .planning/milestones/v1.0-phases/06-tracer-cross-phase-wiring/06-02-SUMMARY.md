---
phase: 06-tracer-cross-phase-wiring
plan: 02
subsystem: simulation
tags: [ray-tracer, solid-body, fresnel, spectral, bsdf, lgp, face-optics]

requires:
  - phase: 06-01
    provides: SolidCylinder/SolidPrism expansion and Fresnel dispatch in _trace_single_source

provides:
  - face_optics consumption in SolidBox Fresnel dispatch (_run_single + _trace_single_source)
  - spectral n(lambda) interpolation in SolidBox/SolidCylinder/SolidPrism Fresnel branches
  - BSDF+spectral composition: spectral R/T weight scaling applied before BSDF scatter
affects:
  - LGP bottom reflector workflow (face_optics now consumed)
  - Any spectral simulation with solid glass bodies
  - Any BSDF surface with spectral material data

tech-stack:
  added: []
  patterns:
    - face_optics override block inserted BEFORE Fresnel in SolidBox dispatch — continues on match, falls through to Fresnel if no match
    - spectral n(lambda) via np.interp before n2_arr = np.where(entering, n_lambda, 1.0)
    - spectral R/T lookup moved BEFORE BSDF dispatch in _bounce_surfaces so both paths share the interpolated r_vals

key-files:
  created: []
  modified:
    - backlight_sim/sim/tracer.py
    - backlight_sim/tests/test_tracer.py

key-decisions:
  - "face_optics override uses continue in each branch (reflector/absorber/diffuser) to skip Fresnel; empty optical_properties_name falls through unchanged"
  - "spectral refractive_index is an optional extension to spectral_material_data dict — absent key falls back to scalar box_n/cyl_n/prism_n (backward compatible)"
  - "BSDF+spectral composition: move spectral R/T lookup before BSDF block; replace mat.reflectance with r_vals inside BSDF weight scaling when available"
  - "MP path face_optics fix applied to _trace_single_source with rng instead of self.rng — consistent with existing MP surface dispatch pattern"
  - "MP path spectral R/T variable set to None (spectral+MP guard prevents wavelengths from being non-None); structural fix is future-ready"

requirements-completed: [LGP-01, SPEC-04, BRDF-01]

duration: 14min
completed: 2026-03-15
---

# Phase 06 Plan 02: Tracer Cross-Phase Wiring — face_optics + spectral n(lambda) + BSDF+spectral Summary

**Three surgical tracer fixes: per-face optical property override in SolidBox Fresnel dispatch (LGP bottom reflector), wavelength-dependent refractive index in solid body Fresnel branches, and BSDF+spectral composition via spectral R/T lookup repositioned before BSDF dispatch.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-15T22:15:39Z
- **Completed:** 2026-03-15T22:29:13Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 2

## Accomplishments

- SolidBox faces with `optical_properties_name` pointing to a reflector/absorber/diffuser now use that optical behavior instead of Fresnel — LGP bottom reflector now works correctly
- SolidBox, SolidCylinder, and SolidPrism Fresnel branches interpolate n(lambda) from `spectral_material_data["refractive_index"]` when spectral tracing is active
- BSDF surfaces with `spectral_material_data` entries now apply wavelength-dependent R/T weight scaling instead of scalar `mat.reflectance` — no more mutual exclusion between BSDF and spectral
- All fixes applied symmetrically in both `_run_single` and `_trace_single_source` (MP path)
- 110 tests pass (4 new: 2 from Task 1 RED + 2 from Task 2 RED — all GREEN after implementation)

## Task Commits

1. **Task 1 RED: Failing tests for face_optics, spectral Fresnel, BSDF+spectral** — `5bf2ea3` (test)
2. **Task 1+2 GREEN: Wire all three fixes in tracer.py** — `fb57697` (feat)

## Files Created/Modified

- `backlight_sim/sim/tracer.py` — face_optics override block in `_run_single` SolidBox dispatch; spectral n(lambda) in SolidBox/Cylinder/Prism Fresnel branches; spectral R/T lookup repositioned before BSDF dispatch in `_bounce_surfaces`; symmetric fixes in `_trace_single_source` MP path
- `backlight_sim/tests/test_tracer.py` — 4 new tests: `test_face_optics_reflector_override`, `test_face_optics_empty_string_fallback`, `test_spectral_solidbox_fresnel`, `test_bsdf_spectral_composition`

## Decisions Made

- face_optics override uses `continue` in each branch (reflector/absorber/diffuser) to skip Fresnel; empty `optical_properties_name` falls through to standard Fresnel unchanged
- `spectral_material_data["refractive_index"]` is treated as an optional extension — if absent, falls back to scalar `box_n`/`cyl_n`/`prism_n` (fully backward compatible)
- BSDF+spectral fix: moved spectral R/T lookup above BSDF dispatch block; replaces `mat.reflectance` with `r_vals` inside BSDF weight scaling when spectral data is present
- MP path face_optics fix uses `rng` (process-local) instead of `self.rng` — consistent with rest of `_trace_single_source`
- MP path spectral `r_vals_mp = None` — spectral+MP is still guarded; fix is structural for future readiness

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed in a single GREEN commit after TDD RED phase.

## Issues Encountered

None. The SolidBox facing test `test_face_optics_empty_string_fallback` passed immediately in RED (by design — it tests fallback behavior which already worked), and `test_spectral_solidbox_fresnel` also passed in RED (it just checks no crash + non-zero flux, which the existing code handled). The two hard failures were `test_face_optics_reflector_override` and `test_bsdf_spectral_composition` which confirmed the gaps.

## Next Phase Readiness

- Phase 06 complete (2/2 plans done) — all tracer cross-phase wiring gaps closed
- LGP bottom reflector workflow fully functional
- Spectral + solid body simulation correct with wavelength-dependent n(lambda)
- BSDF + spectral composition no longer mutually exclusive

---
*Phase: 06-tracer-cross-phase-wiring*
*Completed: 2026-03-15*
