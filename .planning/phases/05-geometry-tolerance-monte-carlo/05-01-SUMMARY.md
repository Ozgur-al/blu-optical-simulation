---
phase: 05-geometry-tolerance-monte-carlo
plan: 01
subsystem: testing
tags: [pytest, tdd, monte-carlo, ensemble, tolerance, xfail]

requires:
  - phase: 04-uncertainty-quantification
    provides: compute_scalar_kpis, SimulationResult, batch-mean CI infrastructure consumed by ensemble tests

provides:
  - backlight_sim/sim/ensemble.py — headless stub module with 7 public functions (apply_jitter, build_oat_sample, compute_oat_sensitivity, build_sobol_sample, compute_sobol_sensitivity, build_mc_sample, plus internal helpers)
  - backlight_sim/tests/test_ensemble.py — 11 xfail TDD tests covering ENS-01..ENS-11

affects:
  - 05-02 (Wave 1 Green phase — implements ensemble.py against these tests)
  - 05-03 (GUI dialog that depends on _EnsembleThread)
  - 05-04 (integration / sweep)

tech-stack:
  added: []
  patterns:
    - xfail(strict=False, raises=(NotImplementedError, AttributeError, TypeError, ImportError)) for Wave 0 TDD stubs
    - Factory function _make_tolerance_scene() using conditional kwargs (getattr-safe) for fields not yet on dataclasses
    - Headless stub module pattern — sim/ module with no GUI imports, all functions raise NotImplementedError

key-files:
  created:
    - backlight_sim/sim/ensemble.py
    - backlight_sim/tests/test_ensemble.py
  modified: []

key-decisions:
  - "Phase 05 Wave 0 TDD: xfail marker uses raises=(NotImplementedError, AttributeError, TypeError, ImportError) — ImportError added beyond plan spec to handle test_ensemble_thread_cancel where ensemble_dialog module does not yet exist (ModuleNotFoundError is a subclass of ImportError)"
  - "sim/ensemble.py stub includes 7 public functions: apply_jitter, build_oat_sample, compute_oat_sensitivity, build_sobol_sample, compute_sobol_sensitivity, build_mc_sample (Wave 1 entrypoints) plus _jitter_cavity, _count_active_tolerance_params, _active_tolerance_params (private helpers)"

patterns-established:
  - "Wave 0 TDD pattern: stub raises NotImplementedError; tests xfail(strict=False); Wave 1 implements and removes markers"
  - "Factory returns Project with conditional kwargs so Wave 0 dataclasses (missing position_sigma_mm, source_position_sigma_mm) are safe to construct"

requirements-completed: [ENS-01, ENS-02, ENS-03, ENS-04, ENS-05, ENS-06, ENS-07, ENS-08, ENS-09, ENS-10, ENS-11]

duration: 6min
completed: 2026-04-19
---

# Phase 05 Plan 01: Ensemble Service TDD Scaffold (Wave 0) Summary

**Headless ensemble.py stub with 7 NotImplementedError functions + 11 xfail TDD tests (ENS-01..ENS-11) establishing the RED gate for Wave 1 implementation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-19T17:39:53Z
- **Completed:** 2026-04-19T17:46:11Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `backlight_sim/sim/ensemble.py` as a headless stub with 7 public functions all raising `NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")`
- Created `backlight_sim/tests/test_ensemble.py` with 11 test functions (ENS-01..ENS-11) all marked `@pytest.mark.xfail(strict=False)` — all collect and show XFAIL in Wave 0
- Full suite: 240 passed, 11 xfailed, 0 failed — zero regressions in existing 237+ tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Create sim/ensemble.py API stub** - `92ea15e` (feat)
2. **Task 2: Write TDD test suite (11 tests, all RED)** - `8642116` (test)

## Files Created/Modified

- `backlight_sim/sim/ensemble.py` — 7 public stub functions (apply_jitter, _jitter_cavity, _count_active_tolerance_params, _active_tolerance_params, build_oat_sample, compute_oat_sensitivity, build_sobol_sample, compute_sobol_sensitivity, build_mc_sample); no PySide6/GUI imports
- `backlight_sim/tests/test_ensemble.py` — 11 xfail tests: apply_jitter_gaussian, apply_jitter_does_not_mutate_base, cavity_jitter_rebuilds_geometry, json_roundtrip_tolerance_fields, json_backward_compat_no_tolerance_fields, oat_sample_count_and_baseline, oat_sensitivity_zero_sigma, sobol_sample_count_power_of_2, ensemble_spread_increases_with_sigma, ensemble_thread_cancel, flux_tolerance_redrawn_per_member

## Decisions Made

- `ImportError` added to the `raises` tuple of `test_ensemble_thread_cancel` beyond what the plan specified. The test imports `backlight_sim.gui.ensemble_dialog` which does not exist in Wave 0 — raising `ModuleNotFoundError` (a subclass of `ImportError`). Without this addition the test would show as `FAILED` instead of `XFAIL`, breaking the suite's exit code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added ImportError to xfail raises for test_ensemble_thread_cancel**
- **Found during:** Task 2 (TDD test suite) — post-creation run
- **Issue:** `test_ensemble_thread_cancel` imported `backlight_sim.gui.ensemble_dialog` which does not exist in Wave 0. The raised `ModuleNotFoundError` was not in the plan's `raises=(NotImplementedError, AttributeError, TypeError)` tuple, causing the test to show as `FAILED` (exit 1) rather than `XFAIL`
- **Fix:** Added `ImportError` to the raises tuple: `raises=(NotImplementedError, AttributeError, TypeError, ImportError)`
- **Files modified:** `backlight_sim/tests/test_ensemble.py`
- **Verification:** Re-run showed all 11 tests as XFAIL, suite exits 0
- **Committed in:** `8642116` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in xfail marker)
**Impact on plan:** Single-line fix essential for correct XFAIL reporting. No scope creep.

## Issues Encountered

None beyond the xfail raises tuple deviation documented above.

## Known Stubs

All 7 functions in `backlight_sim/sim/ensemble.py` are intentional stubs raising `NotImplementedError`. This is the Wave 0 TDD state — Wave 1 (05-02-PLAN.md) will implement them. These stubs are the plan's deliverable, not unfinished work.

## Next Phase Readiness

- Wave 1 (05-02-PLAN.md) can now implement `sim/ensemble.py` against these 11 tests
- Data model changes (`position_sigma_mm` on `PointSource`, `source_position_sigma_mm` on `SimulationSettings`, `cavity_recipe` on `Project`) are needed in Wave 1 to make ENS-01..ENS-05 pass
- GUI dialog `ensemble_dialog.py` is needed by Wave 1/2 to make ENS-10 pass
- No blockers

## Self-Check: PASSED

- `backlight_sim/sim/ensemble.py` — FOUND
- `backlight_sim/tests/test_ensemble.py` — FOUND
- Commit `92ea15e` — FOUND (feat(05-01): create sim/ensemble.py API stub)
- Commit `8642116` — FOUND (test(05-01): add TDD test suite for ensemble service)
- 11 tests collected, all XFAIL — VERIFIED
- Full suite 240 passed, 11 xfailed — VERIFIED

---
*Phase: 05-geometry-tolerance-monte-carlo*
*Completed: 2026-04-19*
