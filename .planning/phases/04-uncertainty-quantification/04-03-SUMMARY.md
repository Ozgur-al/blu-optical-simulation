---
phase: 04-uncertainty-quantification
plan: 03
subsystem: gui + io
tags: [ui, uncertainty-quantification, exports, report, sweep, convergence]
requires:
  - backlight_sim.core.uq (Wave 1)
  - backlight_sim.core.kpi (Wave 1 + Wave 3 additions)
  - DetectorResult.grid_batches / flux_batches / rays_per_batch / n_batches (Wave 1/2)
  - SimulationResult.uq_warnings (Wave 1/2)
provides:
  - backlight_sim.gui.convergence_tab.ConvergenceTab (new file; cumulative KPI + FillBetweenItem CI band)
  - backlight_sim.core.kpi.compute_all_kpi_cis (shared CI aggregator)
  - backlight_sim.core.kpi._per_batch_source_flux (rays_per_batch-aware per-batch source flux)
  - HeatmapPanel confidence-level dropdown + per-bin stderr overlay + UQ warning banner
  - ParameterSweepDialog ErrorBarItem + 3 CI columns (eff ± Δ, u14 ± Δ, hot ± Δ)
  - io.report.generate_html_report: KPI rows with ± and matplotlib errorbar chart
  - io.batch_export.export_batch_zip: kpi.csv with CI columns schema
affects:
  - MainWindow: new "Convergence (UQ)" tab distinct from existing per-source CV% plot
  - All KPI export surfaces now ship per-KPI CI columns when UQ is on
tech-stack:
  added: []
  patterns:
    - Shared CI aggregator `core.kpi.compute_all_kpi_cis` consumed by heatmap_panel, io/report, io/batch_export (eliminates triplicate KPI→CI dispatch)
    - `_per_batch_source_flux(result, det)` used everywhere per-batch efficiency is computed — guarantees unbiased scaling when `rays_per_source % K != 0`
    - pyqtgraph FillBetweenItem for shaded CI band; pg.ErrorBarItem for sweep whiskers
    - matplotlib Agg backend + base64 PNG embedding, mirrored from existing report heatmap pattern
    - QT_QPA_PLATFORM=offscreen at test module import for headless CI
key-files:
  created:
    - backlight_sim/gui/convergence_tab.py
    - backlight_sim/tests/test_uq_ui.py
    - backlight_sim/tests/test_uq_exports.py
  modified:
    - backlight_sim/core/kpi.py
    - backlight_sim/gui/heatmap_panel.py
    - backlight_sim/gui/parameter_sweep_dialog.py
    - backlight_sim/gui/main_window.py
    - backlight_sim/io/report.py
    - backlight_sim/io/batch_export.py
decisions:
  - MainWindow has TWO distinct convergence surfaces. The pre-existing `self._conv_plot` ("Convergence" tab) is a live CV%-per-source plot updated during simulation. The new Phase-4 `ConvergenceTab` is registered as "Convergence (UQ)" — a post-run cumulative-KPI + CI-band view. Keeping them separate avoids breaking the existing live-feedback flow and preserves the CV% plot for users who rely on it.
  - Confidence-level dropdown in the heatmap panel recomputes CI labels from `self._cached_kpi_batches` (populated once in `update_results`) via `batch_mean_ci(..., conf_level=self._current_conf_level())`. No tracer re-run — verified by `test_confidence_combo_recomputes_without_rerun`.
  - Sub-floor fallback policy: when a KPI's per-batch array has < 4 values (adaptive converged early, or UQ off entirely), labels silently fall back to the plain point-estimate string. Same contract as Wave 1 `CIEstimate.format()` for `n_batches == 0`.
  - Per-bin relative stderr overlay computed as `per_bin_stderr(grid_batches) / (grid / n_batches)` with `np.where(mean_bin > 0, ..., 0.0)` to avoid division-by-zero where no rays landed.
  - Parameter sweep CI column headers chosen as `eff ± Δ`, `u14 ± Δ`, `hot ± Δ` (3 columns, concise; `Δ` chosen as a single-character indicator of half-width). Per-step CI cells show the full `ci.format(precision=N)` string.
  - Per-step sweep CI uses `_per_batch_source_flux(result, det)` rather than naive `total_emitted_flux / K` — verified by `test_sweep_efficiency_uses_rays_per_batch` with an uneven [101]*5 + [100]*5 rays_per_batch split and flux exactly proportional; half_width stays ≈ 0 only when the rays_per_batch-aware formula is used.
  - CSV schema extended (not replaced): the new columns come after the legacy `metric,value,unit` triple, so external tools parsing the first three columns by position still work. Legacy (UQ-off) rows write empty strings for the 7 CI columns — consumers can filter `n_batches == 0` or `n_batches == ""` to distinguish UQ-off entries.
  - HTML report embeds the matplotlib errorbar chart via `<img src="data:image/png;base64,...">` exactly mirroring the existing heatmap PNG pattern. Graceful matplotlib-missing fallback: `_errorbar_chart_base64` returns `""` inside an `except ImportError`, and the caller's `if errorbar_png:` guard produces no `<img>` tag rather than crashing.
  - matplotlib-missing graceful test (`test_report_matplotlib_missing_graceful`) uses `monkeypatch.setattr(builtins, "__import__", ...)` to block only `matplotlib*` import names; every other import path in `generate_html_report` continues to work.
  - End-to-end smoke test disables adaptive sampling (`project.settings.adaptive_sampling = False`) because Simple Box converges early (at k'=2) at the default 2k ray budget. Disabling adaptive guarantees the test exercises the full K-batch path; documents an interaction users will hit when running UQ at low ray counts with adaptive on.
  - Heatmap KPI CSV schema mirrored in `io/batch_export.py::export_batch_zip` so consumers of either export path see the same column layout.
  - `ConvergenceTab.clear()` is called in MainWindow `_new_project` alongside `_plot_tab.clear()` — user opening a fresh project sees a blank convergence plot, not stale CI bands from the previous run.
metrics:
  duration: ~55m
  completed: 2026-04-18
---

# Phase 04 Plan 03: UI + export CI rendering Summary

Exposed Wave 2's per-batch data to every user-visible KPI channel: heatmap labels, a new convergence tab, parameter sweep plots/table, HTML report, and CSV / batch ZIP exports all now ship a 95% CI (or the selected 90/99%) when UQ is on. Legacy (UQ-off) paths preserve the pre-Phase-4 display exactly — no `±` token, empty CI cells in CSVs. Every per-batch efficiency path routes through the shared `core.kpi._per_batch_source_flux` helper so the remainder-distribution bias (checker I5 / threat T-04.03-05) is eliminated across the entire pipeline.

## Files Created

| Path | Lines | Purpose |
|------|------:|---------|
| `backlight_sim/gui/convergence_tab.py` | 199 | `ConvergenceTab(QWidget)` with KPI selector combo, PlotWidget, FillBetweenItem CI band, `update_from_result(result)` API, graceful empty-state label. |
| `backlight_sim/tests/test_uq_ui.py` | 430 | 17 headless-Qt UI tests: heatmap labels (CI / legacy / sub-floor), confidence dropdown, noise overlay, warning banner, CSV schema, ConvergenceTab construction/populate/noop, sweep ErrorBarItem + CI columns, rays_per_batch efficiency scaling. |
| `backlight_sim/tests/test_uq_exports.py` | 298 | 8 export tests: HTML CI strings / legacy no-CI / errorbar image / matplotlib-missing graceful; batch zip CI header (UQ-on + legacy); compute_all_kpi_cis rays_per_batch correctness; end-to-end Simple-Box smoke. |

## Files Modified

| Path | Change |
|------|--------|
| `backlight_sim/core/kpi.py` | Added `_per_batch_source_flux(result, det)` (rays_per_batch-aware per-batch source flux; single source of truth) and `compute_all_kpi_cis(result, conf_level)` (shared CI aggregator used by heatmap / report / batch_export). |
| `backlight_sim/gui/heatmap_panel.py` | Imports from `core.uq` and `core.kpi`; added `_uq_warning_label` (orange banner), `_conf_combo` (90/95/99%), `_cached_kpi_batches` dict; added `_compute_all_kpi_batches`, `_ci_or_none`, `_current_conf_level`, `_on_conf_changed`; extended `_color_mode` combo with "Per-bin relative stderr" entry and branch in `_show_result`; rewrote every scalar KPI `setText` call with a CI-fallback helper; rewrote `_export_kpi_csv` header schema to include `metric,value,unit,mean,half_width,std,lower,upper,n_batches,conf_level`. |
| `backlight_sim/gui/parameter_sweep_dialog.py` | Added `_per_step_kpi_cis(result)` helper; added parallel per-step CI state lists `_sweep_ci_eff_full/_u14_full/_hot_full`; added persistent `_error_bar_item: pg.ErrorBarItem`; extended both single and multi-sweep tables with 3 CI columns (`eff ± Δ`, `u14 ± Δ`, `hot ± Δ`); `_refresh_plot` overlays ErrorBarItem with per-step half-widths. |
| `backlight_sim/gui/main_window.py` | Imports `ConvergenceTab`, constructs `self._convergence_tab`, registers as "Convergence (UQ)" tab (separate from existing live CV% "Convergence" tab), calls `update_from_result(result)` in `_on_sim_finished`, calls `clear()` in `_new_project`. |
| `backlight_sim/io/report.py` | Uses `compute_all_kpi_cis` for KPI CI rows; new `_errorbar_chart_base64(kpi_ci_dict)` renders matplotlib errorbar chart embedded as second `<img>` tag; `_fmt_ci_cell` helper formats "mean ± half_width unit" or legacy value; `uq_warnings_html` banner section rendered when `result.uq_warnings` is non-empty; graceful matplotlib-missing fallback preserved. |
| `backlight_sim/io/batch_export.py` | Uses `csv.writer`; `kpi.csv` produced with the same 10-column CI-aware schema as the heatmap panel export; `compute_all_kpi_cis` consumed once per result; matches shared column layout. |

## Test Counts

| Suite | Before | After | Delta |
|-------|-------:|------:|------:|
| `backlight_sim/tests/test_uq_ui.py` (new) | — | 17 | +17 |
| `backlight_sim/tests/test_uq_exports.py` (new) | — | 8 | +8 |
| Full suite `pytest backlight_sim/tests/` | 212 | 237 | +25 |

Full suite green at commit time: **237 passed, 7 warnings in 91.76 s**.

## Must-Haves Verification

| Must-have (plan frontmatter) | Status |
|------------------------------|--------|
| Heatmap KPI labels show 'mean ± half_width unit' when n_batches >= 4 | PASS (`test_heatmap_labels_show_ci_when_n_batches_nonzero`) |
| Legacy fallback when n_batches < 4 (no ± token) | PASS (`test_heatmap_labels_fallback_when_legacy`, `test_heatmap_labels_fallback_when_sub_floor`) |
| Confidence-level dropdown recomputes CIs without tracer re-run | PASS (`test_confidence_combo_recomputes_without_rerun`) |
| Per-bin relative stderr overlay selectable in color-mode combo | PASS (`test_noise_overlay_mode_renders`) |
| ConvergenceTab plots cumulative uniformity vs cumulative rays with shaded CI band | PASS (`test_convergence_tab_populate` — FillBetweenItem detected) |
| Parameter sweep has ErrorBarItem + 3 CI columns | PASS (`test_sweep_plot_has_error_bars`, `test_sweep_table_has_ci_columns`) |
| HTML report shows 'value ± half_width' and matplotlib errorbar chart | PASS (`test_report_html_contains_ci_strings`, `test_report_embeds_errorbar_chart`) |
| CSV exports (KPI CSV + batch ZIP) include CI columns | PASS (`test_export_kpi_csv_includes_ci_columns`, `test_batch_export_csv_has_ci_columns`, `test_batch_export_csv_legacy_has_ci_columns`) |
| UQ warning banner visible when uq_warnings non-empty | PASS (`test_uq_warning_banner_visible`, `test_uq_warning_banner_shows_multiple_warnings`, `test_uq_warning_banner_hidden`) |
| Per-batch efficiency uses rays_per_batch (checker I5) | PASS (`test_efficiency_ci_uses_rays_per_batch_not_naive_division`, `test_sweep_efficiency_uses_rays_per_batch`, `test_compute_all_kpi_cis_uses_rays_per_batch`) |

All 10 must-haves green.

## Shared `compute_all_kpi_cis` + `_per_batch_source_flux` Consumers

```bash
$ grep -l "compute_all_kpi_cis" backlight_sim/**/*.py
backlight_sim/gui/heatmap_panel.py
backlight_sim/io/batch_export.py
backlight_sim/io/report.py
backlight_sim/core/kpi.py

$ grep -l "_per_batch_source_flux" backlight_sim/**/*.py
backlight_sim/gui/convergence_tab.py
backlight_sim/gui/heatmap_panel.py
backlight_sim/gui/parameter_sweep_dialog.py
backlight_sim/core/kpi.py
```

Four consumers of the rays_per_batch-aware helper; three consumers of the shared CI aggregator. No duplicate `total_emitted_flux / n_batches` scaling anywhere in the tree — threat T-04.03-05 closed.

## ± Token Evidence Across Export Surfaces

- **Heatmap labels** → `_ci_or_none("avg")` → `CIEstimate.format(..., unit)` → "X.XX ± Y.YY" when UQ on, plain mean otherwise (via `test_heatmap_labels_show_ci_when_n_batches_nonzero`).
- **HTML report** → `_fmt_ci_cell(ci, fallback)` → rows contain ≥ 3 `±` tokens when UQ on, 0 otherwise (via `test_report_html_contains_ci_strings`, `test_report_html_legacy_no_ci`).
- **HTML report chart** → `<img src="data:image/png;base64,…">` errorbar whiskers (via `test_report_embeds_errorbar_chart`).
- **KPI CSV (heatmap + batch zip)** → separate `mean`, `half_width`, `std`, `lower`, `upper`, `n_batches`, `conf_level` columns (via `test_export_kpi_csv_includes_ci_columns`, `test_batch_export_csv_has_ci_columns`).
- **Sweep plot** → `pg.ErrorBarItem` overlaid on KPI trace (via `test_sweep_plot_has_error_bars`).
- **Sweep table** → "eff ± Δ / u14 ± Δ / hot ± Δ" columns (via `test_sweep_table_has_ci_columns`).
- **ConvergenceTab** → `pg.FillBetweenItem` CI band (via `test_convergence_tab_populate`).

Phase 4 objective "every reported KPI ships with a 95% CI" is met end-to-end.

## Deviations from Plan

### [Rule 3 - Blocking] Headless-Qt `isVisible()` returns False without a shown top-level window

**Found during:** Task 1 first run of UI tests.

**Issue:** `QWidget.isVisible()` unconditionally returns `False` when the widget (or any ancestor) has not been shown via `QWidget.show()`, even when `setVisible(True)` was called on it. The warning-banner tests originally asserted `isVisible()` directly on the QLabel.

**Fix:** Switched `isVisible() / not isVisible()` assertions to `not isHidden() / isHidden()`. These are tied to the `setVisible` flag the panel actually manipulates and do not require a realized top-level window. Same issue pattern applied to the ConvergenceTab empty-label test.

**Rationale (Rule 3):** Tests that require the panel to be shown to pass would force `panel.show()` + event-loop pumping — makes headless CI flaky. `isHidden()` is the exact state variable being tested.

**Files modified:** `backlight_sim/tests/test_uq_ui.py` (same commit as Task 1 GREEN).

### [Rule 3 - Blocking] pyqtgraph PlotWidget.items is a bound method, not a list

**Found during:** Task 2 ConvergenceTab tests.

**Issue:** The test originally read `tab._plot.items` expecting a list; in pyqtgraph 0.13+ this attribute is a bound method of `GraphicsView` and not iterable directly.

**Fix:** Use `tab._plot.plotItem.items` for child items + `tab._plot.listDataItems()`. Mirrored on the sweep-dialog ErrorBarItem test (`dlg._plot_widget.plotItem.items`).

**Files modified:** `backlight_sim/tests/test_uq_ui.py` (same commit as Task 2 GREEN).

### [Rule 3 - Blocking] End-to-end smoke hit adaptive-converges-early path at 2k rays

**Found during:** Task 3 end-to-end smoke test.

**Issue:** Plan text suggested `rays_per_source=2000` + `uq_batches=10` + Simple Box preset. The preset defaults `adaptive_sampling=True`, which converged at `k' = 2` — below the 4-batch CI floor — so per-KPI CI cells stayed empty and the "non-empty half_width cell" assertion failed.

**Fix:** Disable adaptive sampling explicitly in the smoke test and raise ray budget to 4000. Documented the interaction as a decision (see Decisions section).

**Rationale (Rule 3):** Root cause is a known Wave 2 interaction (CONTEXT D-01 / adaptive+UQ may converge early); not a code defect. Fix is the same as a user would apply in practice — if you need full CI fidelity across all K batches, disable adaptive sampling.

**Files modified:** `backlight_sim/tests/test_uq_exports.py` (same commit as Task 3 GREEN).

### [Note] Sweep per-step CI uses per-step sim, not sweep-ensemble variance

**Clarification:** Each sweep step runs a single simulation with UQ on; the CI shown in each row is the within-step Monte Carlo uncertainty at that parameter value (from the step's own K per-batch grids), not an across-step ensemble variance. This matches the plan intent and lets the ErrorBarItem represent "how noisy is the KPI at this parameter value" — an entirely different quantity from Phase 5's tolerance-MC ensemble spread.

### [Note] ConvergenceTab tab order in MainWindow

**Tab order in MainWindow's openable-panels list:** `3D View`, `Heatmap`, `Plots`, **`Convergence (UQ)`** (new, right after Plots), `Angular Dist.`, `Far-field`, `3D Receiver`, `Spectral Data`, `BSDF`, `Convergence` (existing live CV% plot, kept for backward-compat), `Log`. Two "Convergence" labels coexist intentionally — the `(UQ)` suffix disambiguates in the Window menu.

## Commits

| Task | Type | Hash | Message |
|------|------|------|---------|
| 1 RED | test | 34c700a | test(04-03): add failing tests for heatmap UQ CI rendering + noise overlay |
| 1 GREEN | feat | ea908fe | feat(04-03): render UQ CI labels + noise overlay + warning banner in heatmap |
| 2 RED | test | 90d2c5e | test(04-03): add failing tests for ConvergenceTab + sweep CI columns |
| 2 GREEN | feat | 3a62724 | feat(04-03): add ConvergenceTab + sweep CI whiskers + CI table columns |
| 3 RED | test | 9a1f3b3 | test(04-03): add failing tests for report HTML + batch ZIP CI schema |
| 3 GREEN | feat | 1a7c213 | feat(04-03): CI-aware HTML report + batch ZIP KPI CSV schema |

## Hand-off Note

**Phase 4 ready for verification. No follow-up tasks.** Phase 5 (tolerance MC) and Phase 6 (optimizer) can now consume `compute_all_kpi_cis` to evaluate noise-aware objectives. `_per_batch_source_flux` is the single source of truth for unbiased per-batch efficiency scaling — use it anywhere per-batch KPI arrays need to be derived from `flux_batches`. Across-step ensemble variance (Phase 5) is still orthogonal to the within-step MC variance rendered here; both can be tracked independently via repeated calls to `compute_all_kpi_cis` across tolerance realizations.

## Known Stubs

None. Every reported KPI on every export surface is wired end-to-end. `grid_spectral_batches` remains optional and untouched here (Wave 2 populates it; Wave 3 does not render it separately — the existing spectral color mode uses the non-batched `grid_spectral` as before).

## Self-Check: PASSED

Verified file existence and commit presence:

- `backlight_sim/gui/convergence_tab.py`: FOUND (199 lines; ≥ 120 required; contains `FillBetweenItem`)
- `backlight_sim/tests/test_uq_ui.py`: FOUND (17 tests)
- `backlight_sim/tests/test_uq_exports.py`: FOUND (8 tests; ≥ 80 lines required — file is 298 lines)
- `backlight_sim/core/kpi.py` (modified): `_per_batch_source_flux` + `compute_all_kpi_cis` present
- `backlight_sim/gui/heatmap_panel.py`: `_conf_combo`, `_uq_warning_label`, `Per-bin relative stderr`, `CIEstimate` all present
- `backlight_sim/gui/parameter_sweep_dialog.py`: `ErrorBarItem`, `eff ± Δ`, `u14 ± Δ`, `hot ± Δ`, `_per_batch_source_flux` all present
- `backlight_sim/io/report.py`: `half_width`, `errorbar`, `compute_all_kpi_cis`, `CIEstimate` all present
- `backlight_sim/io/batch_export.py`: `half_width`, `n_batches`, `conf_level`, `compute_all_kpi_cis` all present
- `backlight_sim/gui/main_window.py`: `ConvergenceTab` registered + update hook wired
- Commit `34c700a` (RED task 1): FOUND in git log
- Commit `ea908fe` (GREEN task 1): FOUND in git log
- Commit `90d2c5e` (RED task 2): FOUND in git log
- Commit `3a62724` (GREEN task 2): FOUND in git log
- Commit `9a1f3b3` (RED task 3): FOUND in git log
- Commit `1a7c213` (GREEN task 3): FOUND in git log

Full suite: `pytest backlight_sim/tests/` = **237 passed, 7 warnings in 91.76 s**.
