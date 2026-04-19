---
phase: 05-geometry-tolerance-monte-carlo
plan: 04
subsystem: integration
tags: [ensemble, integration-gate, xfail-removal, gui, testing, docs]

requires:
  - phase: 05-geometry-tolerance-monte-carlo
    plan: 03
    provides: EnsembleDialog + _EnsembleThread; Position Tolerance in SourceForm; Tolerance Ensemble menu wired

provides:
  - backlight_sim/tests/test_ensemble.py — all 11 ENS tests passing, zero xfail markers
  - backlight_sim/gui/geometry_builder.py — build_cavity call writes cavity_recipe via record_recipe=True
  - CLAUDE.md — Phase 5 pre-commit gate documented

affects:
  - Phase 6 (inverse design optimizer) — can now rely on full ENS test coverage as regression gate

tech-stack:
  added: []
  patterns:
    - efficiency_pct KPI for ensemble spread test (uniformity_1_4_min_avg always 0 at low ray counts in 100x100 grid)

key-files:
  created: []
  modified:
    - backlight_sim/gui/geometry_builder.py
    - backlight_sim/tests/test_ensemble.py
    - CLAUDE.md

key-decisions:
  - "ENS-09 uses efficiency_pct (not uniformity_1_4_min_avg) because the Simple Box 100x100 detector grid has empty bins at 500-2000 rays, making uniformity always 0; efficiency_pct is sensitive to LED position jitter and yields clean nonzero spread"
  - "rays_per_source in ENS-09 increased 500→2000 for reliable nonzero efficiency_pct variance across 15 members with sigma=2.0"

metrics:
  duration: 6min
  completed: 2026-04-19
  tasks: 2
  files_modified: 3
---

# Phase 05 Plan 04: Integration Gate Summary

**Phase 5 integration gate: record_recipe=True wired in GUI geometry builder; all 11 ENS tests pass with no xfail markers; full suite 251 passed**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-19T18:15:20Z
- **Completed:** 2026-04-19T18:21:07Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `backlight_sim/gui/geometry_builder.py`: added `record_recipe=True` to `build_cavity()` call in `GeometryBuilderDialog._on_accept()` — project.cavity_recipe is now written whenever the user runs the geometry builder dialog, enabling the Phase 5 ensemble cavity-jitter path (ENS-03)
- `backlight_sim/tests/test_ensemble.py`: removed both remaining `@pytest.mark.xfail` decorators (ENS-09, ENS-10); fixed ENS-09 KPI from `uniformity_1_4_min_avg` to `efficiency_pct` (see deviation below); updated module docstring to reflect Phase 5 Wave 4 completion
- `CLAUDE.md`: added Phase 5 ensemble test commands to Commands section; added Phase 5 pre-commit gate note to Development Conventions section

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire record_recipe=True in GUI geometry builder | `489e2d9` | gui/geometry_builder.py |
| 2 | Remove xfail markers; fix ENS-09 KPI; update CLAUDE.md | `56adbc7` | tests/test_ensemble.py, CLAUDE.md |

## Files Modified

- `backlight_sim/gui/geometry_builder.py` — `record_recipe=True` added to `build_cavity()` call
- `backlight_sim/tests/test_ensemble.py` — xfail markers removed; ENS-09 fixed; docstring updated
- `CLAUDE.md` — Phase 5 commands + pre-commit gate documented

## Decisions Made

- `efficiency_pct` chosen as ENS-09 spread KPI: `uniformity_1_4_min_avg` is a min/avg ratio over the center 1/4 region. The Simple Box preset uses a 100×100 detector grid; at 500–5000 rays the center region contains empty bins (zero flux), so the ratio is always 0 regardless of LED position jitter. `efficiency_pct` (total detector flux / source flux × 100%) is sensitive to LED displacement — a displaced LED sends more rays toward the cavity wall vs. the detector aperture, producing measurable variance across members.
- `rays_per_source` in ENS-09 increased from 500 to 2000 for reliable nonzero variance; at 500 rays even `efficiency_pct` returned 0 variance at sigma=0 (acceptable) but also near-0 at sigma=2 for some seeds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ENS-09 used wrong KPI for spread measurement**
- **Found during:** Task 2 — after removing xfail, ENS-09 failed with `AssertionError: Expected sigma=2 spread (0.0000) > sigma=0 spread (0.0000)`
- **Issue:** `uniformity_1_4_min_avg` always returns 0.0 for the Simple Box preset at ≤10k rays because the 100×100 detector grid has empty bins in the center 1/4 region (center min = 0, so min/avg = 0). This is a KPI calculation correctness issue, not a simulation bug.
- **Fix:** Changed KPI key to `efficiency_pct` which is non-zero and varies with LED position jitter; increased `rays_per_source` from 500 to 2000 for reliable signal-to-noise across 15 members.
- **Files modified:** `backlight_sim/tests/test_ensemble.py`
- **Commit:** `56adbc7`

---

**Total deviations:** 1 auto-fixed (Rule 1 — wrong KPI causing ENS-09 always-zero spread)
**Impact on plan:** The fix produces a stronger, more meaningful test: efficiency_pct directly measures how much LED position jitter affects light collection, which is the physical quantity of interest in ensemble tolerance analysis.

## Known Stubs

None — all Phase 5 functionality is fully implemented and tested.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The `record_recipe=True` addition writes only user-supplied GUI spinbox values (no external data).

## Self-Check: PASSED

- `backlight_sim/gui/geometry_builder.py` — FOUND, contains `record_recipe=True` at line 388
- `backlight_sim/tests/test_ensemble.py` — FOUND, zero `@pytest.mark.xfail` decorators, 11 tests
- `CLAUDE.md` — FOUND, contains `pytest backlight_sim/tests/test_ensemble.py` (3 occurrences) and `Phase 5` pre-commit gate note
- Commit `489e2d9` — Task 1
- Commit `56adbc7` — Task 2
- `pytest backlight_sim/tests/test_ensemble.py -q`: 11 passed, 0 xfailed, 0 failed — VERIFIED
- `pytest backlight_sim/tests/ -q`: 251 passed, 7 warnings — VERIFIED (no regressions)

---
*Phase: 05-geometry-tolerance-monte-carlo*
*Completed: 2026-04-19*
