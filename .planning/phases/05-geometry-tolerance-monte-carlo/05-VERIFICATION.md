---
phase: 05-geometry-tolerance-monte-carlo
verified: 2026-04-19T18:30:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 5: Geometry Tolerance Monte Carlo Verification Report

**Phase Goal:** Geometry Tolerance Monte Carlo — ensemble simulations over parameter tolerances; P5/P50/P95 KPI distributions; sensitivity ranking (OAT + Sobol).
**Verified:** 2026-04-19T18:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `sim/ensemble.py` exists, fully implemented (no NotImplementedError stubs) | VERIFIED | `python -c "from backlight_sim.sim.ensemble import apply_jitter, build_mc_sample, build_oat_sample; print('OK')"` exits 0 |
| 2 | `PointSource` has `position_sigma_mm: float = 0.0` field | VERIFIED | `s.position_sigma_mm == 0.0` confirmed via Python import |
| 3 | `SimulationSettings` has `source_position_sigma_mm` and `source_position_distribution` fields | VERIFIED | Both fields confirmed with correct defaults (0.0 and "gaussian") |
| 4 | `Project` has `cavity_recipe: dict = field(default_factory=dict)` | VERIFIED | `p.cavity_recipe == {}` confirmed |
| 5 | JSON round-trip preserves all three new tolerance fields with backwards compat | VERIFIED | `project_io.py` lines 83, 207, 223, 273, 342, 370 — serialize + deserialize with `max(0.0, ...)` clamping |
| 6 | `apply_jitter()` is fully implemented (not `NotImplementedError`) | VERIFIED | All 11 ENS tests pass including ENS-01 (jitter shifts positions) and ENS-02 (no mutation) |
| 7 | `build_oat_sample()` returns k+1 items; `build_sobol_sample()` rounds N to power of 2 min 32 | VERIFIED | ENS-06 and ENS-08 PASS |
| 8 | All 11 ENS tests PASS with zero `xfail` decorators remaining | VERIFIED | `pytest backlight_sim/tests/test_ensemble.py -q`: 11 passed in 1.17s; grep confirms 2 occurrences of "xfail" are comments only (lines 3 and 57), no decorators |
| 9 | `backlight_sim/gui/ensemble_dialog.py` exists with `EnsembleDialog` (two tabs) and `_EnsembleThread` (mode field) | VERIFIED | Import succeeds; tabs "Distribution" and "Sensitivity Analysis" confirmed; `_EnsembleThread` has `__init__`, `cancel()`, `run()` |
| 10 | `properties_panel.py` has "Position Tolerance" CollapsibleSection with `_pos_sigma` spinbox; `main_window.py` has "Tolerance Ensemble..." menu item | VERIFIED | `grep` confirms "Position Tolerance" at line 391, `_pos_sigma` at lines 393/458/526; "Tolerance Ensemble..." at main_window.py line 377 |
| 11 | `gui/geometry_builder.py` `build_cavity` call has `record_recipe=True` | VERIFIED | Line 388 confirmed |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/sim/ensemble.py` | Headless ensemble engine — apply_jitter, OAT, Sobol, MC | VERIFIED | Full implementation; no PySide6 imports; all public functions implemented |
| `backlight_sim/tests/test_ensemble.py` | 11 tests, all PASS, zero xfail decorators | VERIFIED | 11 passed, 0 xfailed — xfail only appears in comment strings |
| `backlight_sim/core/sources.py` | `position_sigma_mm: float = 0.0` field | VERIFIED | Confirmed at runtime |
| `backlight_sim/core/project_model.py` | `source_position_sigma_mm`, `source_position_distribution`, `cavity_recipe` | VERIFIED | All three confirmed at runtime |
| `backlight_sim/io/project_io.py` | JSON round-trip for all tolerance fields | VERIFIED | 6 matching lines for new fields including clamping |
| `backlight_sim/io/geometry_builder.py` | `record_recipe: bool = False` param in `build_cavity` | VERIFIED | Present; `record_recipe=True` writes `project.cavity_recipe` |
| `backlight_sim/gui/ensemble_dialog.py` | `EnsembleDialog` + `_EnsembleThread` | VERIFIED | Created; two-tab layout confirmed |
| `backlight_sim/gui/properties_panel.py` | Position Tolerance section in SourceForm | VERIFIED | CollapsibleSection at line 391; spinbox wired to load/apply |
| `backlight_sim/gui/main_window.py` | "Tolerance Ensemble..." menu + `_open_ensemble_dialog` + `_on_save_ensemble_variant` | VERIFIED | All three confirmed |
| `backlight_sim/gui/geometry_builder.py` | `record_recipe=True` in `build_cavity` call | VERIFIED | Line 388 confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ensemble_dialog._EnsembleThread` | `sim/ensemble.py::build_mc_sample / build_oat_sample / build_sobol_sample` | mode dispatch in `run()` | VERIFIED | Import and dispatch confirmed |
| `ensemble_dialog.EnsembleDialog` | `core/kpi.py::compute_scalar_kpis` | `_on_dist_step_done` / `_on_sens_step_done` | VERIFIED | `compute_scalar_kpis` imported in ensemble_dialog |
| `main_window._open_ensemble_dialog` | `gui/ensemble_dialog.EnsembleDialog` | lazy import + `dlg.exec()` | VERIFIED | "Tolerance Ensemble" at line 377; `_open_ensemble_dialog` and `_on_save_ensemble_variant` present |
| `io/project_io._src_to_dict` | `PointSource.position_sigma_mm` | `"position_sigma_mm": s.position_sigma_mm` | VERIFIED | Line 83 in project_io.py |
| `gui/geometry_builder.GeometryBuilderDialog._on_accept` | `io/geometry_builder.build_cavity` | `record_recipe=True` | VERIFIED | Line 388 in gui/geometry_builder.py |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ensemble_dialog._EnsembleThread.run()` | `projects` list from `build_mc_sample` | `sim/ensemble.apply_jitter` → deep-copy with Gaussian position draw | Yes — RNG-based draws produce distinct clones | FLOWING |
| `EnsembleDialog._update_histogram` | `_dist_kpi_values` list | `compute_scalar_kpis(result)` per member step | Yes — real KPI from tracer result | FLOWING |
| `EnsembleDialog._update_oat_sensitivity_table` | `_sens_all_kpis` list | `compute_oat_sensitivity(baseline, perturbed, names, sigmas)` | Yes — real delta/sigma ratios | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `apply_jitter` + `build_mc_sample` import without error | `python -c "from backlight_sim.sim.ensemble import apply_jitter, build_mc_sample, build_oat_sample; print('OK')"` | "ensemble imports OK" | PASS |
| `PointSource.position_sigma_mm` default = 0.0 | `python -c "...s.position_sigma_mm"` | "position_sigma_mm: 0.0" | PASS |
| `Project.cavity_recipe` default = {} | `python -c "...p.cavity_recipe"` | "cavity_recipe: {}" | PASS |
| All 11 ENS tests pass | `pytest backlight_sim/tests/test_ensemble.py -q` | "11 passed in 1.17s" | PASS |
| Zero xfail decorators | `grep -c "xfail" test_ensemble.py` | 2 (both are comments, not decorators) | PASS |
| `record_recipe=True` in GUI geometry builder | `grep -n "record_recipe=True" gui/geometry_builder.py` | Line 388 | PASS |
| "Tolerance Ensemble" menu item | `grep -n "Tolerance Ensemble" main_window.py` | Line 377 | PASS |
| `EnsembleDialog` two tabs created | `dlg._tabs.count() == 2`, texts "Distribution", "Sensitivity Analysis" | Confirmed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ENS-01 | 05-01/02 | apply_jitter shifts source positions with Gaussian sigma > 0 | SATISFIED | test_apply_jitter_gaussian PASS |
| ENS-02 | 05-01/02 | apply_jitter does not mutate base project | SATISFIED | test_apply_jitter_does_not_mutate_base PASS |
| ENS-03 | 05-01/02 | cavity_recipe depth_sigma_mm > 0 rebuilds cavity geometry | SATISFIED | test_cavity_jitter_rebuilds_geometry PASS |
| ENS-04 | 05-01/02 | JSON round-trip preserves all tolerance fields | SATISFIED | test_json_roundtrip_tolerance_fields PASS |
| ENS-05 | 05-01/02 | Old JSON without tolerance fields loads with all-zero defaults | SATISFIED | test_json_backward_compat_no_tolerance_fields PASS |
| ENS-06 | 05-01/02 | build_oat_sample returns k+1 items; item 0 labeled "baseline" | SATISFIED | test_oat_sample_count_and_baseline PASS |
| ENS-07 | 05-01/02 | compute_oat_sensitivity returns 0.0 for zero-sigma params | SATISFIED | test_oat_sensitivity_zero_sigma PASS |
| ENS-08 | 05-01/02 | build_sobol_sample rounds N up to next power of 2, min 32 | SATISFIED | test_sobol_sample_count_power_of_2 PASS |
| ENS-09 | 05-01/04 | Larger sigma produces larger KPI spread across ensemble | SATISFIED | test_ensemble_spread_increases_with_sigma PASS (uses efficiency_pct, 2000 rays) |
| ENS-10 | 05-01/04 | _EnsembleThread cancel() halts run before all members complete | SATISFIED | test_ensemble_thread_cancel PASS |
| ENS-11 | 05-01/02 | flux_tolerance re-drawn per ensemble member (D-01b) | SATISFIED | test_flux_tolerance_redrawn_per_member PASS |

### Anti-Patterns Found

None. Scan performed on key phase files:
- `sim/ensemble.py`: No TODO/FIXME, no `return {}` / `return []` stubs, no PySide6 imports
- `tests/test_ensemble.py`: No remaining `@pytest.mark.xfail` decorators — 2 grep matches are comment lines only
- `gui/ensemble_dialog.py`: DoS clamp `min(max(1, n), 500)` present; `seed & 0x7FFFFFFF` mask present; `try/except` around tracer present
- `core/sources.py`: `position_sigma_mm: float = 0.0` — proper dataclass default, not mutable
- `core/project_model.py`: `cavity_recipe: dict = field(default_factory=dict)` — correct factory pattern, not shared mutable default

### Human Verification Required

None. All must-haves are verifiable programmatically and confirmed passing.

### Gaps Summary

No gaps. All 11 requirements (ENS-01 through ENS-11) are implemented and tested. All 4 waves completed:
- Wave 0 (Plan 01): TDD scaffold — 11 xfail tests + stub module
- Wave 1 (Plan 02): GREEN phase — data model fields, JSON round-trip, headless ensemble engine
- Wave 2 (Plan 03): GUI — EnsembleDialog, _EnsembleThread, SourceForm tolerance spinbox, menu wiring
- Wave 3 (Plan 04): Integration gate — record_recipe=True, xfail removal, CLAUDE.md update

Full test suite at phase close: 251 passed, 0 xfailed, 0 failed.

---

_Verified: 2026-04-19T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
