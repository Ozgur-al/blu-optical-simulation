---
phase: 02-spectral-engine
plan: 01
subsystem: simulation
tags: [spectral, wavelength, spd, planck, monte-carlo, numpy]

requires:
  - phase: 01-refractive-physics
    provides: RayTracer with _bounce_surfaces, OpticalProperties, Project dataclass with solid_bodies

provides:
  - Project.spd_profiles and Project.spectral_material_data custom dict fields
  - get_spd_from_project() with project SPD lookup before built-in fallback
  - blackbody_spd() Planckian SPD generator using Planck's law
  - sample_wavelengths() with optional spd_profiles kwarg for custom profiles
  - _bounce_surfaces() per-wavelength R/T interpolation from spectral tables
  - Spectral + MP guard: warns and forces single-thread when spectral+MP enabled
  - project_io serialization of spd_profiles and spectral_material_data (backward-compatible)
  - 7 new spectral engine tests (46 total)

affects: [02-spectral-gui, future spectral rendering, IES spectral support]

tech-stack:
  added: []
  patterns:
    - "Custom SPD profiles stored in Project.spd_profiles as {name: {wavelength_nm, intensity}} dicts"
    - "Spectral material data in Project.spectral_material_data as {optics_name: {wavelength_nm, reflectance, transmittance}}"
    - "get_spd_from_project() check-custom-first pattern mirrors angular_distributions lookup"
    - "Per-wavelength R/T via np.interp in _bounce_surfaces when spectral_material_data present"
    - "MP guard pattern: check has_spectral before routing to _run_multiprocess, warn+fallback"

key-files:
  created: []
  modified:
    - backlight_sim/core/project_model.py
    - backlight_sim/sim/spectral.py
    - backlight_sim/sim/tracer.py
    - backlight_sim/io/project_io.py
    - backlight_sim/tests/test_tracer.py

key-decisions:
  - "Spectral accumulation triggered by any source with spd != 'white' (not by presence of spectral_material_data alone)"
  - "spectral_material_data test using warm_white SPD not white — spectral grid only allocated when has_spectral=True"
  - "blackbody_spd uses Planck's law with exponent clamp (0..700) to prevent overflow at short wavelengths/low CCT"
  - "MP+spectral guard uses stacklevel=2 warning so the warning points to user call site, not internal run()"
  - "get_spd_from_project is a thin wrapper — keeps get_spd() clean for internal use, adds project lookup on top"

patterns-established:
  - "SPD lookup chain: custom project profiles → built-in named SPDs → flat white fallback"
  - "Spectral material data uses same JSON dict pattern as angular_distributions for consistency"
  - "Per-ray np.interp for spectral R/T lookup — vectorized over hit_idx, no Python loops"

requirements-completed: [SPEC-01, SPEC-02, SPEC-04]

duration: 12min
completed: 2026-03-14
---

# Phase 2 Plan 01: Spectral Engine Backbone Summary

**Per-ray wavelength through the tracer with custom SPD profiles, Planckian blackbody generator, wavelength-dependent material R/T interpolation via np.interp, MP+spectral guard, and backward-compatible project JSON I/O**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-14T~10:00Z
- **Completed:** 2026-03-14
- **Tasks:** 1 (TDD: RED tests, GREEN implementation, no REFACTOR needed)
- **Files modified:** 5

## Accomplishments

- Custom SPD profiles round-trip through JSON and produce physically correct wavelength distributions when sampled
- Planckian blackbody SPD shifts peak wavelength correctly with CCT (Wien's displacement law verified in tests)
- Per-wavelength material reflectance and transmittance via np.interp enables wavelength-selective surfaces
- Spectral+MP guard prevents silent data loss when multiprocessing and spectral simulation are both enabled
- All 46 tests pass (39 original + 7 new spectral tests), zero regressions

## Task Commits

1. **Task 1: Data model, SPD lookup, blackbody generator, wavelength-dependent material interpolation** — `32639b6` (feat)

## Files Created/Modified

- `backlight_sim/core/project_model.py` — Added `spd_profiles` and `spectral_material_data` fields to `Project` dataclass
- `backlight_sim/sim/spectral.py` — Added `get_spd_from_project()`, `blackbody_spd()`, updated `sample_wavelengths()` signature
- `backlight_sim/sim/tracer.py` — MP+spectral guard in `run()`, spd_profiles passed to `sample_wavelengths`, per-wavelength R/T in `_bounce_surfaces()`
- `backlight_sim/io/project_io.py` — Serialize/deserialize `spd_profiles` and `spectral_material_data`
- `backlight_sim/tests/test_tracer.py` — 7 new spectral tests: custom SPD sampling, blackbody peak shift, wavelength-dependent material reflectance, spectral grid accumulation, I/O round-trip, custom override, MP guard warning

## Decisions Made

- **Spectral grid allocation condition**: `has_spectral = any(s.spd != "white")` — grid only allocated when at least one source has a non-white SPD. This means `test_spectral_material_reflectance_varies_per_wavelength` needed `spd="warm_white"` not `spd="white"` (corrected from initial test draft)
- **Blackbody overflow guard**: exponent clamped to [0, 700] before `exp()` to prevent inf at short wavelengths with low CCT
- **MP guard stacklevel**: `stacklevel=2` so the warning appears at the user's `RayTracer(p).run()` call, not buried in internal tracer code

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test using white SPD with spectral material data**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** `test_spectral_material_reflectance_varies_per_wavelength` used `spd="white"` which means `has_spectral=False` and `grid_spectral=None` — assertion fails
- **Fix:** Changed test to use `spd="warm_white"` as the behavior spec required
- **Files modified:** `backlight_sim/tests/test_tracer.py`
- **Verification:** Test now passes; behavioral intent preserved
- **Committed in:** `32639b6` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test logic)
**Impact on plan:** Trivial fix; behavioral intent of test fully preserved.

## Issues Encountered

None beyond the minor test SPD mismatch above.

## Next Phase Readiness

- Spectral engine backbone complete; ready for GUI integration (spectral source SPD selector, material spectral editor)
- `get_spd_from_project` and `blackbody_spd` are available for GUI panels to call
- Custom SPD profiles in `Project.spd_profiles` are already serialized to JSON
- Remaining Phase 2 concerns: GUI for viewing/editing spectral data, CIE XYZ display, spectral heatmap tab

---
*Phase: 02-spectral-engine*
*Completed: 2026-03-14*
