---
phase: 04-uncertainty-quantification
verified: 2026-04-18T18:15:42Z
status: human_needed
score: 29/29 must_haves verified
plans_verified: [04-01, 04-02, 04-03]
requirements_covered: [UQ-01, UQ-02, UQ-03, UQ-04, UQ-05, UQ-06, UQ-07, UQ-08, UQ-ADAPTIVE-WARN, UQ-ADAPTIVE-WARN-UI, UQ-MP, UQ-SPECTRAL-TOGGLE, KPI-LIFT]
overrides_applied: 0
human_verification:
  - test: "Launch app, load Simple Box preset, set uq_batches=10 + adaptive_sampling=False + rays_per_source=5000, run simulation"
    expected: "Heatmap KPI labels show 'value ± half_width unit' tokens (e.g., 'avg = 87.3 ± 1.2'); legacy mean string when UQ off"
    why_human: "Rendered text in live Qt widgets — automated tests cover setText via headless Qt but visual alignment and correct decimal precision are UX-visible only in the running app"
  - test: "With the UQ run loaded, change the heatmap confidence dropdown from 95% to 90% and then 99%"
    expected: "All CI labels recompute without triggering a new simulation; 99% CIs visibly wider than 90% CIs"
    why_human: "Interactive combo-box driven re-render; automated test asserts text changes but humans confirm no tracer re-run (no progress bar, no wait, no disk I/O) and that the magnitudes move as expected"
  - test: "In the heatmap panel color-mode combo, switch to 'Per-bin relative stderr'"
    expected: "Heatmap image replaces flux map with a sigma/mean overlay; colorbar label updates to 'Relative stderr'"
    why_human: "Visual rendering of the per-bin stderr heatmap; automated setImage assertion does not confirm color scaling or that user can read the overlay"
  - test: "Navigate to the Convergence (UQ) tab; change the KPI selector combo"
    expected: "Plot shows a cumulative KPI line with a shaded CI band that narrows as cumulative rays grow; combo change rerenders for the selected KPI"
    why_human: "Visual inspection of FillBetweenItem band behavior — automated test asserts item presence but band narrowing and legibility are UX claims"
  - test: "Open Parameter Sweep dialog; run a 5-step sweep on LED flux with uq_batches=10"
    expected: "KPI trace on plot has vertical whiskers (ErrorBarItem) at each data point; results table has 3 CI columns 'eff ± Δ', 'u14 ± Δ', 'hot ± Δ' populated"
    why_human: "Visual whiskers alignment and table column readability; automated tests verify presence but not usability"
  - test: "Export HTML report from a UQ-on run and open it in a browser"
    expected: "KPI rows show '±' tokens; an embedded matplotlib errorbar chart image renders beneath the heatmap"
    why_human: "Browser rendering of base64-embedded PNG and overall report layout — tests verify HTML substrings but visual chart quality is human-judged"
  - test: "Run with adaptive_sampling=True + uq_batches=10; inspect heatmap panel after sim completes"
    expected: "Orange warning banner visible at top of panel containing 'adaptive' and (if k'<4) 'UQ CI undefined' strings"
    why_human: "Banner visibility/color/positioning is a visual UX property — automated test covers isHidden() flag only"
---

# Phase 4: Uncertainty Quantification Verification Report

**Phase Goal:** Every reported KPI (uniformity, peak luminance, efficiency, hotspot ratio, NRMSE) ships with a 95% confidence interval derived from the Monte Carlo sampling variance — so users know when results are noise-limited vs design-limited.
**Verified:** 2026-04-18T18:15:42Z
**Status:** human_needed (all automated checks pass; visual UX items remain)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Aggregated Across Plans)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | core/uq.py computes batch-mean CI half-width that shrinks as 1/sqrt(K) on synthetic iid samples | VERIFIED | `test_uq.py::test_batch_mean_ci_half_width_shrinks_as_sqrt_n` PASS |
| 2 | core/uq.py Student-t critical values match scipy within 0.001 | VERIFIED | `test_uq.py::test_student_t_critical_matches_scipy_within_1e3` PASS |
| 3 | core/kpi.py exposes uniformity_in_center, corner_ratio, edge_center_ratio, compute_scalar_kpis with identical results to old gui helpers | VERIFIED | `test_kpi.py` parity tests PASS; all 4 symbols present at `core/kpi.py:29,50,70,104` |
| 4 | core/kpi.py and core/uq.py do not import PySide6, pyqtgraph, or gui | VERIFIED | `test_core_kpi_has_no_gui_imports` + `test_core_uq_has_no_gui_imports` subprocess PASS; grep confirms no PySide6/pyqtgraph imports |
| 5 | gui/heatmap_panel.py and gui/parameter_sweep_dialog.py import KPI helpers from core.kpi | VERIFIED | `from backlight_sim.core.kpi import` at heatmap_panel.py:15 and parameter_sweep_dialog.py:21 |
| 6 | SimulationSettings has uq_batches=10 and uq_include_spectral=True fields | VERIFIED | `project_model.py:31,34` |
| 7 | DetectorResult has 6 optional UQ fields; legacy construction works | VERIFIED | `detectors.py:94-101`; contract check PASS |
| 8 | SimulationResult has uq_warnings = field(default_factory=list); legacy works | VERIFIED | `detectors.py:137`; mutable-default test PASS |
| 9 | Running tracer with uq_batches=10 populates grid_batches shape (10, ny, nx) | VERIFIED | Live run: `grid_batches.shape: (10, 100, 100), n_batches: 10` |
| 10 | Sum of grid_batches along axis=0 equals DetectorResult.grid (flux conservation) | VERIFIED | Live run `np.allclose(grid_batches.sum(axis=0), grid, rtol=1e-9)` PASS |
| 11 | uq_batches=0 produces bit-identical legacy results | VERIFIED | Live run returns grid_batches=None, n_batches=0; `test_uq_zero_bit_identical_to_legacy` PASS |
| 12 | Per-batch stderr shrinks as 1/sqrt(N) when rays_per_source doubles | VERIFIED | `test_stderr_shrinks_sqrt_n` PASS (center-bin KPI, documented deviation) |
| 13 | Multiprocessing mode returns same grid_batches content as single-thread | VERIFIED | `test_mp_parity_with_single_thread` PASS |
| 14 | C++ fast path + Python fallback both emit per-batch grids | VERIFIED | `test_uq_on_populates_batches` + `test_spectral_toggle_off_leaves_spectral_batches_none` PASS |
| 15 | adaptive_sampling=True + uq_batches>0 writes to result.uq_warnings (no hard disable) | VERIFIED | Live run returned 2 uq_warnings; `test_adaptive_plus_uq_attaches_warning` PASS |
| 16 | When adaptive converges at k'<K, n_batches=k'; if k'<4 second warning appended | VERIFIED | Live run: "UQ CI undefined: only 2 batches completed..." observed; `test_adaptive_converges_at_chunk_boundary_reports_partial_k` PASS |
| 17 | rays_per_batch populated whenever grid_batches is populated; reflects actual rays | VERIFIED | Live run: `len(rays_per_batch)=10, sum=5000`; `test_rays_per_batch_remainder_distribution` PASS |
| 18 | uq_include_spectral=False keeps grid_spectral_batches None on spectral scenes | VERIFIED | `test_spectral_toggle_off_leaves_spectral_batches_none` PASS |
| 19 | C++ extension NOT rebuilt — blu_tracer.cpp untouched | VERIFIED | SUMMARY 04-02 git log check: last `_blu_tracer/src/` commit is from Phase 02 |
| 20 | Heatmap KPI labels show 'mean ± half_width unit' when n_batches >= 4 | VERIFIED | `test_heatmap_labels_show_ci_when_n_batches_nonzero` PASS |
| 21 | Heatmap KPI labels fall back to plain mean when n_batches < 4 | VERIFIED | `test_heatmap_labels_fallback_when_legacy/_when_sub_floor` PASS |
| 22 | Confidence-level dropdown recomputes CIs without re-running simulation | VERIFIED | `test_confidence_combo_recomputes_without_rerun` PASS |
| 23 | Per-bin relative stderr overlay mode selectable in color-mode combo | VERIFIED | `test_noise_overlay_mode_renders` PASS; grep confirms "Per-bin relative stderr" in heatmap_panel.py |
| 24 | Convergence tab plots cumulative uniformity vs cumulative rays with FillBetweenItem CI band | VERIFIED | `convergence_tab.py:188` uses `pg.FillBetweenItem`; `test_convergence_tab_populate` PASS |
| 25 | Parameter sweep plot has ErrorBarItem + 3 CI table columns | VERIFIED | `parameter_sweep_dialog.py:319,515` ErrorBarItem; columns "eff ± Δ","u14 ± Δ","hot ± Δ" at lines 273-275,407,426; tests PASS |
| 26 | HTML report KPI rows show 'value ± half_width' + matplotlib errorbar chart embedded | VERIFIED | `test_report_html_contains_ci_strings` + `test_report_embeds_errorbar_chart` PASS |
| 27 | CSV exports include CI columns (mean,half_width,std,lower,upper,n_batches,conf_level) | VERIFIED | `batch_export.py:35-41` header; `test_export_kpi_csv_includes_ci_columns` + `test_batch_export_csv_has_ci_columns` PASS |
| 28 | When uq_warnings non-empty, warning banner shows in heatmap panel | VERIFIED | `test_uq_warning_banner_visible/_shows_multiple_warnings/_hidden` PASS |
| 29 | Per-batch efficiency uses rays_per_batch (not naive total/K) for unbiased CI | VERIFIED | `_per_batch_source_flux` in `core/kpi.py:150`; `test_compute_all_kpi_cis_uses_rays_per_batch` + `test_sweep_efficiency_uses_rays_per_batch` + `test_efficiency_ci_uses_rays_per_batch_not_naive_division` PASS |

**Score:** 29/29 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/core/uq.py` | batch_mean_ci, per_bin_stderr, kpi_batches, CIEstimate, student_t_critical; min 120 lines | VERIFIED | 287 lines; all 5 symbols found at lines 73, 105, 166, 213, 246 |
| `backlight_sim/core/kpi.py` | uniformity_in_center, corner_ratio, edge_center_ratio, compute_scalar_kpis; min 100 lines | VERIFIED | 265 lines; 6 public symbols + `_per_batch_source_flux` + `compute_all_kpi_cis` found at 29,50,70,104,150,182 |
| `backlight_sim/core/detectors.py` | DetectorResult with 6 UQ fields; SimulationResult with uq_warnings | VERIFIED | Fields at lines 94-101, 137 |
| `backlight_sim/core/project_model.py` | SimulationSettings extended with uq_batches + uq_include_spectral | VERIFIED | Lines 31, 34 |
| `backlight_sim/sim/tracer.py` | K-batch loop + rays_per_batch + uq_warnings.append | VERIFIED | 54 UQ-related matches; 3 uq_warnings.append callsites (lines 638, 664, 2204) |
| `backlight_sim/gui/convergence_tab.py` | ConvergenceTab QWidget + FillBetweenItem; min 120 lines | VERIFIED | 199 lines; FillBetweenItem at line 188 |
| `backlight_sim/gui/heatmap_panel.py` | CI labels + confidence dropdown + noise overlay + warning banner | VERIFIED | 46 matches for `_conf_combo/_uq_warning_label/Per-bin relative stderr/CIEstimate/batch_mean_ci/per_bin_stderr/kpi_batches/compute_all_kpi_cis` |
| `backlight_sim/gui/parameter_sweep_dialog.py` | ErrorBarItem + CI columns | VERIFIED | Lines 319, 515 ErrorBarItem; CI columns at 273-275, 407, 426 |
| `backlight_sim/io/report.py` | CI rows + errorbar chart | VERIFIED | 19 matches for `half_width/CIEstimate/compute_all_kpi_cis/errorbar/batch_mean_ci` |
| `backlight_sim/io/batch_export.py` | CI CSV columns | VERIFIED | 12 matches; full header schema visible at lines 35-41 |
| `backlight_sim/tests/test_uq.py` | CI math + Student-t + per-bin stderr tests; min 120 lines | VERIFIED | 240 lines; 21 tests |
| `backlight_sim/tests/test_kpi.py` | KPI parity tests; min 60 lines | VERIFIED | 341 lines; 18 tests |
| `backlight_sim/tests/test_uq_tracer.py` | Tracer UQ integration tests; min 150 lines | VERIFIED | 372 lines; 25 tests |
| `backlight_sim/tests/test_uq_ui.py` | UI rendering smoke tests | VERIFIED | 432 lines; 17 tests |
| `backlight_sim/tests/test_uq_exports.py` | CSV + HTML export schema tests; min 80 lines | VERIFIED | 302 lines; 8 tests |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| gui/heatmap_panel.py | core/kpi.py | `from backlight_sim.core.kpi import` | WIRED | heatmap_panel.py:15 |
| gui/parameter_sweep_dialog.py | core/kpi.py | `from backlight_sim.core.kpi import` | WIRED | parameter_sweep_dialog.py:21 |
| sim/tracer.py::_run_single | DetectorResult.grid_batches / rays_per_batch | per-chunk snapshot via `_run_uq_batched` wrapper | WIRED | `_run_uq_batched` populates grid_batches across all 3 paths; live run confirms shape (10, ny, nx) |
| sim/tracer.py::_cpp_trace_single_source | _blu_tracer.trace_source (K loop) | K sequential calls with hashed per-batch seeds | WIRED | SUMMARY 04-02: extended at lines ~467-589 (now ~120 lines) |
| sim/tracer.py::_run_multiprocess | worker result dict | workers return grids_batches + rays_per_batch | WIRED | Per-worker UQ merge at lines ~791-837; DetectorResult population at ~868-897 |
| sim/tracer.py::RayTracer.run | SimulationResult.uq_warnings | `uq_warnings.append` adaptive+UQ warning | WIRED | 3 append callsites (638, 664, 2204); live run shows 2 entries on adaptive+UQ |
| gui/heatmap_panel.py | core/uq.py::batch_mean_ci | kpi_batches + batch_mean_ci wrapped into _ci_or_none helper | WIRED | `batch_mean_ci` referenced in heatmap_panel.py; combo recompute test PASS |
| gui/main_window.py | gui/convergence_tab.py::ConvergenceTab | QTabWidget addTab "Convergence (UQ)" | WIRED | main_window.py:42 import, :162 instantiate, :292 addTab, :695 clear, :1296 update |
| io/report.py | core/uq.py | matplotlib errorbar chart + CI row rendering | WIRED | 19 refs; `test_report_embeds_errorbar_chart` PASS |
| core/kpi.py::compute_all_kpi_cis | DetectorResult.rays_per_batch | `_per_batch_source_flux` uses rays_per_batch / sum(rpb) * total_emitted_flux | WIRED | `_per_batch_source_flux` at core/kpi.py:150; `compute_all_kpi_cis` at :182 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| gui/convergence_tab.py | `det.grid_batches, det.rays_per_batch` | Tracer populates per-batch via `_run_uq_batched` / `_cpp_trace_single_source` | Yes — live run returned shape (10, 100, 100), rays_per_batch sums to rays_per_source | FLOWING |
| gui/heatmap_panel.py KPI labels | `self._cached_kpi_batches` | `_compute_all_kpi_batches(result)` applies `kpi_batches()` to `det.grid_batches` | Yes — test verifies `^\d+\.\d+ ± \d+\.\d+$` regex on label text | FLOWING |
| gui/parameter_sweep_dialog.py error bars | `self._sweep_ci_eff_full/_u14_full/_hot_full` | Per-step `batch_mean_ci` over per-result `kpi_batches(gb, ...)` using `_per_batch_source_flux` for efficiency | Yes — `test_sweep_plot_has_error_bars` PASS | FLOWING |
| io/report.py KPI rows | `kpi_ci_dict` | `compute_all_kpi_cis(result, conf_level=0.95)` → chained via `_per_batch_source_flux` and `kpi_batches` | Yes — HTML contains ≥ 3 `±` tokens on UQ run; 0 on legacy | FLOWING |
| io/batch_export.py kpi.csv | rows | `compute_all_kpi_cis` once per result; `_row(name, ci)` writes CI columns | Yes — test asserts header contains all 7 CI columns | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite green | `pytest backlight_sim/tests/` | 237 passed, 7 warnings in 91.75s | PASS |
| Import core UQ contracts | `python -c "from backlight_sim.core.uq import batch_mean_ci, per_bin_stderr, kpi_batches, CIEstimate, student_t_critical"` | Exit 0 | PASS |
| Import core KPI contracts | `python -c "from backlight_sim.core.kpi import uniformity_in_center, corner_ratio, edge_center_ratio, compute_scalar_kpis, compute_all_kpi_cis, _per_batch_source_flux"` | Exit 0 | PASS |
| SimulationSettings defaults | `SimulationSettings()` → `uq_batches=10, uq_include_spectral=True` | PASS | PASS |
| DetectorResult legacy construction | `DetectorResult('x', np.zeros((3,3)))` → `n_batches=0, grid_batches=None, rays_per_batch=None` | PASS | PASS |
| SimulationResult factory default | `SimulationResult()` → `uq_warnings == []` and not shared mutable | PASS | PASS |
| End-to-end UQ simulation | `RayTracer(p).run()` with uq_batches=10, rays=5000, adaptive=False on Simple Box | `grid_batches.shape=(10,100,100), n_batches=10, sum(rays_per_batch)=5000, np.allclose(grid_batches.sum(0), grid)=True` | PASS |
| Legacy fast path | same but uq_batches=0 | `grid_batches=None, n_batches=0, rays_per_batch=None` | PASS |
| Adaptive+UQ warning | uq_batches=10 + adaptive_sampling=True | `len(uq_warnings)=2`: "UQ CI undefined: only 2 batches..." and "Adaptive sampling and UQ are both enabled..." | PASS |
| Layering rule (core/sim/io no GUI imports) | `grep -l "from PySide6\|import PySide6\|from pyqtgraph\|import pyqtgraph\|from backlight_sim.gui" backlight_sim/core/ backlight_sim/sim/ backlight_sim/io/` | Only doc-comment mentions in core/kpi.py:6 and core/uq.py:23 (no actual imports) | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description (derived from plan+ROADMAP) | Status | Evidence |
|-------------|----------------|------------------------------------------|--------|----------|
| UQ-01 | 04-01, 04-02 | Batch-means CI math + tracer K-batch loop | SATISFIED | `core/uq.py::batch_mean_ci`; live run shows grid_batches populated |
| UQ-02 | 04-01 | Student-t critical-value table + per-bin stderr | SATISFIED | Hard-coded 51-entry table in `core/uq.py`; `per_bin_stderr` at line 213 |
| UQ-03 | 04-03 | Heatmap panel CI-aware labels + confidence dropdown | SATISFIED | `_conf_combo` + `_ci_or_none` + `compute_all_kpi_cis` consumed |
| UQ-04 | 04-03 | Convergence plot with shaded CI band | SATISFIED | `ConvergenceTab` with `FillBetweenItem` at convergence_tab.py:188 |
| UQ-05 | 04-01, 04-03 | Per-bin noise overlay in heatmap panel | SATISFIED | "Per-bin relative stderr" combo entry; `test_noise_overlay_mode_renders` PASS |
| UQ-06 | 04-03 | Parameter sweep CI bands + table columns | SATISFIED | `ErrorBarItem` + 3 CI columns in parameter_sweep_dialog.py |
| UQ-07 | 04-03 | HTML report CI + matplotlib errorbar chart | SATISFIED | report.py contains `half_width`, `errorbar`, `compute_all_kpi_cis` |
| UQ-08 | 04-03 | CSV exports (KPI CSV + batch ZIP) with CI columns | SATISFIED | batch_export.py header schema lines 35-41 |
| UQ-ADAPTIVE-WARN | 04-02 | Adaptive+UQ tracer warning (no hard disable) | SATISFIED | 3 `uq_warnings.append` callsites in tracer.py; chunk-boundary-only convergence verified |
| UQ-ADAPTIVE-WARN-UI | 04-03 | Warning banner in heatmap panel | SATISFIED | `_uq_warning_label` + `test_uq_warning_banner_visible/hidden` PASS |
| UQ-MP | 04-02 | Multiprocessing path returns per-batch data | SATISFIED | `_run_multiprocess` extended; `test_mp_parity_with_single_thread` PASS |
| UQ-SPECTRAL-TOGGLE | 04-02 | `uq_include_spectral=False` skips spectral per-batch caching | SATISFIED | `test_spectral_toggle_off_leaves_spectral_batches_none` PASS |
| KPI-LIFT | 04-01 | Lift KPI helpers from gui/ to core/kpi.py | SATISFIED | 4 symbols moved; GUI rewires confirmed at heatmap_panel.py:15, parameter_sweep_dialog.py:21 |

**All 13 requirement IDs accounted for.** No REQUIREMENTS.md exists in .planning/ — verification drew requirement descriptions from plan frontmatter + ROADMAP phase scope.

### Anti-Patterns Found

None. Scan of modified files (per SUMMARY key-files) did not surface blocking TODO/FIXME/PLACEHOLDER patterns or empty-implementation stubs. Known deferred items are documented in 04-02-SUMMARY.md (Python MP worker UQ batching deferred for MP+spectral+UQ combined scenario) — this is a graceful degradation already handled by the `.get(..., None)` null-check in the aggregator, not a stub.

### Gaps Found

None. All 29 must-haves across 3 plans are verified against the live codebase, 237 tests pass, layering rule is clean, all requirement IDs are satisfied.

### Human Verification Required

7 items (see frontmatter `human_verification` block). These are visual/interactive UX checks that headless Qt tests cannot fully cover:

1. Heatmap `±` token rendering in live app
2. Confidence dropdown recompute feels instant (no tracer rerun)
3. Per-bin stderr overlay visual legibility
4. Convergence (UQ) tab band-narrowing behavior
5. Parameter sweep ErrorBarItem whisker alignment + CI column population
6. HTML report rendering in browser (errorbar chart visibility)
7. Warning banner visual styling (orange color, positioning, multi-warning separator)

Automated test coverage proves the widgets are instantiated and hold the expected state; the items above verify that a real user can read/interact with them successfully.

### Summary

Phase 4 delivers its goal end-to-end: every reported KPI on every export surface (heatmap labels, convergence tab, sweep plot+table, HTML report, KPI CSV, batch ZIP) ships with a batch-means CI when `uq_batches > 0`. The legacy path (`uq_batches=0`) is bit-identical to pre-Phase-4 behavior and produces plain means with empty CI columns in CSV exports. The adaptive+UQ interaction is handled via chunk-boundary-only convergence evaluation plus a `uq_warnings` channel that the UI surfaces as an orange banner. Per-batch efficiency everywhere uses `_per_batch_source_flux(result, det)` so the `rays_per_source % K != 0` remainder-distribution bias (checker I5) cannot leak into CI estimates. The C++ extension was NOT modified — all batching is Python-side. Full pytest suite green at 237 passed.

---

_Verified: 2026-04-18T18:15:42Z_
_Verifier: Claude (gsd-verifier)_
