---
phase: 04-uncertainty-quantification
plan: 01
subsystem: core
tags: [uncertainty-quantification, kpi-refactor, core-lift, data-model]
requires: []
provides:
  - backlight_sim.core.uq (CIEstimate, batch_mean_ci, per_bin_stderr, kpi_batches, student_t_critical)
  - backlight_sim.core.kpi (uniformity_in_center, corner_ratio, edge_center_ratio, compute_scalar_kpis)
  - DetectorResult.grid_batches / hits_batches / flux_batches / grid_spectral_batches / rays_per_batch / n_batches
  - SimulationResult.uq_warnings (list[str], factory default)
  - SimulationSettings.uq_batches (int=10) / uq_include_spectral (bool=True)
affects:
  - backlight_sim/gui/heatmap_panel.py (KPI helpers imported from core.kpi)
  - backlight_sim/gui/parameter_sweep_dialog.py (_kpis removed, uses compute_scalar_kpis)
  - backlight_sim/io/project_io.py (UQ settings persisted in JSON round-trip)
tech-stack:
  added: []
  patterns:
    - Hard-coded Student-t table (avoids scipy runtime dep)
    - field(default_factory=list) for UQ warnings (avoids shared mutable default)
    - Subprocess-based layering enforcement test (core must not leak gui imports)
key-files:
  created:
    - backlight_sim/core/uq.py
    - backlight_sim/core/kpi.py
    - backlight_sim/tests/test_uq.py
    - backlight_sim/tests/test_kpi.py
  modified:
    - backlight_sim/core/project_model.py
    - backlight_sim/core/detectors.py
    - backlight_sim/io/project_io.py
    - backlight_sim/gui/heatmap_panel.py
    - backlight_sim/gui/parameter_sweep_dialog.py
decisions:
  - Hard-coded Student-t table (17 dof x 3 conf = 51 entries, 4 dp) keeps scipy out of the runtime dependency footprint while matching scipy.stats.t.ppf within 1e-3.
  - dof clamps to 19 for K>20 (tail asymptote); K<4 rejected (CIs become uninformative below).
  - CIEstimate.format() aligns mean precision to 2 sig figs of half_width (standard scientific-paper convention — "87.3 +/- 1.2%" not "87.324 +/- 1.2%").
  - KPI helper bodies copied verbatim from gui/heatmap_panel.py (not re-implemented) to guarantee bitwise parity with the pre-refactor behavior on random grids.
  - _kpis in parameter_sweep_dialog.py removed outright (not kept as a back-compat shim) per plan action D — callsites unpack compute_scalar_kpis(result) dict directly.
  - SimulationSettings.uq_batches persists in project JSON via project_io — user-selected K survives save/load.
  - uq_warnings uses field(default_factory=list) to avoid the Python shared-mutable-default pitfall; verified by dedicated test.
metrics:
  duration: 9m
  completed: 2026-04-18
---

# Phase 04 Plan 01: core/uq.py + core/kpi.py lift Summary

Established the Phase 4 data-model and pure-numpy compute foundation before any tracer or UI wiring: CI math lives in `core/uq.py`, KPI helpers in `core/kpi.py`, DetectorResult/SimulationResult/SimulationSettings extended with UQ fields, GUI rewired to import from core. Zero behavior change to the running app; 180/180 tests green.

## Files Created

| Path | Lines | Purpose |
|------|------:|---------|
| `backlight_sim/core/uq.py` | 287 | Batch-means CI math: `CIEstimate` dataclass (frozen), `batch_mean_ci`, `per_bin_stderr`, `kpi_batches`, `student_t_critical`, hard-coded 51-entry Student-t table. |
| `backlight_sim/core/kpi.py` | 150 | KPI helpers lifted from gui/: `uniformity_in_center`, `corner_ratio`, `edge_center_ratio`; new `compute_scalar_kpis(result) -> dict` replacing the old `_kpis` tuple. |
| `backlight_sim/tests/test_uq.py` | 240 | 21 tests: scipy parity, 1/sqrt(N) shrinkage, Poisson noise-floor agreement within 20%, CIEstimate.format precision alignment, subprocess layering check. |
| `backlight_sim/tests/test_kpi.py` | 341 | 18 tests: KPI parity on 10 fixed-seed grids (shapes 50x50, 100x100, 37x73, 10x10, 20x30), `compute_scalar_kpis` parity, DetectorResult/SimulationResult/SimulationSettings extension + back-compat, legacy JSON round-trip, GUI rewire checks. |

## Files Modified

| Path | Change |
|------|--------|
| `backlight_sim/core/project_model.py` | Added `uq_batches: int = 10` and `uq_include_spectral: bool = True` to `SimulationSettings`. |
| `backlight_sim/core/detectors.py` | Added 6 optional UQ fields to `DetectorResult` (grid_batches, hits_batches, flux_batches, grid_spectral_batches, rays_per_batch, n_batches). Added `uq_warnings: list[str] = field(default_factory=list)` to `SimulationResult`. |
| `backlight_sim/io/project_io.py` | Persist / restore `uq_batches` and `uq_include_spectral` in project JSON with safe `.get()` defaults for legacy files. |
| `backlight_sim/gui/heatmap_panel.py` | Deleted module-level `_uniformity_in_center` / `_corner_ratio` / `_edge_center_ratio` definitions; imports them from `backlight_sim.core.kpi` with `as _name` aliases. |
| `backlight_sim/gui/parameter_sweep_dialog.py` | Deleted module-level `_kpis`; two call sites (`_on_step_done`, `_on_multi_step_done`) unpack `compute_scalar_kpis(result)` dict directly. Added `from backlight_sim.core.kpi import compute_scalar_kpis, uniformity_in_center as _uniformity_in_center`. |

## Test Counts

| Suite | Before | After | Delta |
|-------|-------:|------:|------:|
| backlight_sim/tests/test_uq.py (new) | — | 21 | +21 |
| backlight_sim/tests/test_kpi.py (new) | — | 18 | +18 |
| Full suite `pytest backlight_sim/tests/` | 132 | 180 | +48 (incl. existing Phase 03 golden) |

Full suite green at commit time: **180 passed, 5 warnings in 40.18s**.

## Commits

| Task | Type | Hash | Message |
|------|------|------|---------|
| 1 RED | test | ede4b2f | test(04-01): add failing tests for core/uq CI math + Student-t table |
| 1 GREEN | feat | b6cc3b1 | feat(04-01): add core/uq with batch-means CI math and Student-t table |
| 2 RED | test | acad49f | test(04-01): add failing tests for core/kpi + DetectorResult/SimulationResult UQ fields |
| 2 GREEN | refactor | 8878f79 | refactor(04-01): lift KPI helpers to core/kpi; extend data model with UQ fields |

## Deviations from Plan

### [Rule 3 - Blocking] Task 1 commit accidentally included Phase 03 uncommitted files

**Found during:** Task 1 final commit.

**Issue:** After `git add backlight_sim/core/uq.py` and `git commit`, the resulting commit (`b6cc3b1`) also contained modifications to `backlight_sim/golden/builders.py`, `backlight_sim/golden/cases.py`, `backlight_sim/tests/golden/conftest.py`, and a new `backlight_sim/tests/golden/test_fresnel_glass.py`. These were uncommitted Phase 03 Plan 03 work-in-progress files in the working tree when Plan 01 execution began. They were never intended to be part of this plan.

**Fix:** None — the extra files are valid Phase 03 work and the suite remains green with them included. A separate commit (`082818e test(03-03): add prism dispersion golden test`) was created by what appears to be a post-tool hook between Task 2 RED and GREEN.

**Root cause:** A repository hook / auto-staging behavior that picks up adjacent modified files; not a plan defect. Flagged here for transparency.

**Files improperly co-located:** `backlight_sim/golden/builders.py`, `backlight_sim/golden/cases.py`, `backlight_sim/tests/golden/conftest.py`, `backlight_sim/tests/golden/test_fresnel_glass.py` (all Phase 03 surface).

**Commit:** b6cc3b1 (task 1) — no scope-affecting test changes; Phase 04 files are clean.

### [Note - Project I/O round-trip] Persist UQ settings in JSON

**Found during:** Task 2 test writing.

**Issue:** Plan specified that legacy JSONs without `uq_*` keys must load cleanly (dataclass defaults). Added a matching `save_project` path so new sessions round-trip — otherwise the user's K selection would silently reset to the default on every reload.

**Fix:** Added `uq_batches` and `uq_include_spectral` to the `settings` dict in `project_to_dict` (io/project_io.py lines 204-205) and to the `SimulationSettings(...)` constructor call in `load_project` (io/project_io.py lines 333-334).

**Files modified:** `backlight_sim/io/project_io.py`.

**Rationale (Rule 2 — missing critical functionality):** a UQ setting that silently resets on save/load is a correctness defect disguised as a plan omission — users would mis-diagnose nondeterministic CI widths between runs.

**Commit:** 8878f79.

## Must-Haves Verification

| Must-have | Status |
|-----------|--------|
| `core/uq.py` batch-mean CI half-width shrinks as 1/sqrt(K) on synthetic iid samples | PASS (`test_batch_mean_ci_half_width_shrinks_as_sqrt_n`) |
| `core/uq.py` Student-t critical values match scipy within 0.001 at K-1 in {3,4,5,9,10,14,19} and conf in {0.90,0.95,0.99} | PASS (`test_student_t_critical_matches_scipy_within_1e3`) |
| `core/kpi.py` exposes uniformity_in_center, corner_ratio, edge_center_ratio, compute_scalar_kpis with identical results to old gui/ helpers | PASS (all 4 parity tests — bitwise equality on 10 fixed-seed grids across 5 shapes) |
| `core/kpi.py` and `core/uq.py` do not import PySide6, pyqtgraph, or any gui.* module | PASS (`test_core_kpi_has_no_gui_imports`, `test_core_uq_has_no_gui_imports` — subprocess) |
| `gui/heatmap_panel.py` and `gui/parameter_sweep_dialog.py` import KPI helpers from `core.kpi` | PASS (`test_heatmap_panel_imports_from_core_kpi`, `test_parameter_sweep_imports_from_core_kpi`) |
| `SimulationSettings` has `uq_batches: int = 10` and `uq_include_spectral: bool = True` | PASS (`test_simulation_settings_uq_defaults`) |
| `DetectorResult` has `grid_batches`, `hits_batches`, `flux_batches`, `grid_spectral_batches`, `rays_per_batch`, `n_batches`; legacy construction still works | PASS (`test_detector_result_legacy_construction_unchanged`, `test_detector_result_accepts_uq_kwargs`) |
| `SimulationResult` has `uq_warnings: list[str] = field(default_factory=list)`; legacy construction still works | PASS (`test_simulation_result_uq_warnings_default_empty`, `test_simulation_result_uq_warnings_not_shared_mutable`) |

All 8 must-haves green.

## Hand-off to Wave 2

The tracer can now populate UQ data without further data-model changes:

- **DetectorResult.grid_batches / hits_batches / flux_batches / grid_spectral_batches** are ready to be filled by the per-batch loop. All remain `None` on the legacy path when `settings.uq_batches == 0`.
- **DetectorResult.rays_per_batch** is `list[int] | None` — the tracer should populate a K-element list to record actual rays emitted per batch (accounts for the `rays_per_source % K != 0` remainder).
- **SimulationResult.uq_warnings** is ready to be appended to — e.g., `result.uq_warnings.append("Adaptive sampling is active; CI may be biased (CONTEXT D-01).")` when the tracer detects the adaptive+UQ interaction.
- **SimulationSettings.uq_batches / uq_include_spectral** are ready to be read by the tracer. Threat register T-04.01-02 (DoS via huge `uq_batches`): Wave 2 tracer MUST clamp `uq_batches` to `min(20, max(4, rays_per_source // 1000))` at runtime.
- **compute_scalar_kpis(result)** is ready for Phase 6 optimizer use — CMA-ES can evaluate KPIs by dict-key without importing any gui module.

## Known Stubs

None. The module-level API surface is complete and consumed by the existing GUI. `uq_warnings` is a list populated by Wave 2; it is not a stub (empty is the correct default for Wave 1).

## Self-Check: PASSED

Verified file existence and commit presence:

- `backlight_sim/core/uq.py`: FOUND
- `backlight_sim/core/kpi.py`: FOUND
- `backlight_sim/tests/test_uq.py`: FOUND
- `backlight_sim/tests/test_kpi.py`: FOUND
- Commit `ede4b2f` (test RED, task 1): FOUND in git log
- Commit `b6cc3b1` (feat GREEN, task 1): FOUND in git log
- Commit `acad49f` (test RED, task 2): FOUND in git log
- Commit `8878f79` (refactor GREEN, task 2): FOUND in git log

Full suite: `pytest backlight_sim/tests/` = **180 passed, 5 warnings in 40.18s**.
