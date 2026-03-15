---
phase: 07-ui-spectral-display-fixes
plan: 01
subsystem: ui
tags: [pyqtgraph, pyside6, qsettings, spectral, chromaticity, simulation-preview]

# Dependency graph
requires:
  - phase: 02-spectral-engine
    provides: spectral_grid_to_xyz, xy_per_pixel, spectral_bin_centers in sim/spectral.py
  - phase: 05-ui-rewamp
    provides: SpectralDataPanel, _save_layout/_restore_layout, _on_sim_finished structure

provides:
  - SpectralDataPanel.update_from_result(result) public method for chromaticity scatter cloud
  - grid_spectral in partial DetectorResult snapshots for live spectral color preview
  - QSettings tab persistence fix for Windows single-element list edge case
  - Spectral panel wired to simulation completion in _on_sim_finished

affects:
  - spectral display pipeline
  - live simulation preview
  - tab persistence

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_sim_scatter as separate item from _chroma_scatter — independent lifecycle for simulation scatter vs SPD marker"
    - "getattr(self, '_sim_scatter', None) guard — safe access before first call"
    - "luminance > threshold pixel filter before scatter plot — avoids dark-pixel noise at CIE origin"
    - "max 2000 subsampled scatter points — prevents overload on high-res detectors"
    - "isinstance(saved_tabs, str) coercion before isinstance(saved_tabs, list) — Windows QSettings single-item list edge case"

key-files:
  created: []
  modified:
    - backlight_sim/sim/tracer.py
    - backlight_sim/gui/spectral_data_panel.py
    - backlight_sim/gui/main_window.py

key-decisions:
  - "Separate _sim_scatter item (not replacing _chroma_scatter) so SPD marker and simulation cloud coexist independently"
  - "Lazy import of spectral_grid_to_xyz/spectral_bin_centers/xy_per_pixel inside update_from_result — avoids circular import risk"
  - "try/except around chromaticity computation — non-critical display enhancement should never crash app"
  - "Update first detector with grid_spectral (not all detectors) — consistent with HeatmapPanel default behavior"
  - "UI-06 duplicate action confirmed already wired (line 437) — no code change needed, validation only"

patterns-established:
  - "Pattern: Partial snapshots should copy all result arrays including grid_spectral — ensures live preview honors display mode"
  - "Pattern: Public update_from_result(result) on display panels — consistent with _heatmap.update_results, _plot_tab.update_results"

requirements-completed: [UI-02, UI-06, SPEC-03]

# Metrics
duration: 8min
completed: 2026-03-15
---

# Phase 7 Plan 01: UI + Spectral Display Fixes Summary

**QSettings tab persistence fix, per-pixel CIE chromaticity scatter cloud from grid_spectral, and live preview spectral color via partial snapshot wiring — ~30 lines across 3 files closing all Phase 7 gaps**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-15T10:36:33Z
- **Completed:** 2026-03-15T10:44:00Z
- **Tasks:** 2 (plus checkpoint)
- **Files modified:** 3

## Accomplishments
- `SpectralDataPanel.update_from_result(result)` method added — computes per-pixel CIE (x,y) from grid_spectral and plots as translucent green scatter cloud on the CIE 1931 chromaticity diagram after simulation
- `tracer.py` partial snapshot now includes `grid_spectral.copy()` when available, so live heatmap preview honors Spectral Color mode during simulation
- `_restore_layout` fixed for Windows QSettings single-element list edge case (str coercion before list check)
- `_on_sim_finished` wired to call `_spectral_panel.update_from_result(result)` for automatic chromaticity scatter update after each simulation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add spectral grid to partial snapshots and chromaticity scatter method** - `352ed02` (feat)
2. **Task 2: Fix tab persistence and wire spectral panel update** - `7bb55f5` (feat)

**Plan metadata:** _(pending final commit)_

## Files Created/Modified
- `backlight_sim/sim/tracer.py` - Added `grid_spectral=dr.grid_spectral.copy() if dr.grid_spectral is not None else None` to partial DetectorResult construction in `_run_single`
- `backlight_sim/gui/spectral_data_panel.py` - Added public `update_from_result(result)` method after `_update_chromaticity_for_spd`
- `backlight_sim/gui/main_window.py` - Added str coercion in `_restore_layout`; added `_spectral_panel.update_from_result(result)` call in `_on_sim_finished`

## Decisions Made
- Separate `_sim_scatter` item from `_chroma_scatter` so the SPD marker and simulation cloud coexist independently on the CIE diagram with separate lifecycles
- Lazy imports inside `update_from_result` for spectral functions to avoid circular import risk
- First detector with `grid_spectral` is used (not all detectors) — consistent with HeatmapPanel default behavior; aggregation is a future enhancement
- UI-06 duplicate action already wired in Phase 5 (`_connect_signals` line 437); no code change needed — confirmed by inspection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Phase 7 gap-closure fixes implemented
- Human verification checkpoint required for visual confirmation of four fixes: tab persistence, duplicate action, chromaticity scatter cloud, live spectral color preview
- After checkpoint approval, Phase 7 plan 01 is fully complete

## Self-Check: PASSED

- FOUND: backlight_sim/sim/tracer.py
- FOUND: backlight_sim/gui/spectral_data_panel.py
- FOUND: backlight_sim/gui/main_window.py
- FOUND: .planning/phases/07-ui-spectral-display-fixes/07-01-SUMMARY.md
- FOUND commit: 352ed02 (Task 1)
- FOUND commit: 7bb55f5 (Task 2)

---
*Phase: 07-ui-spectral-display-fixes*
*Completed: 2026-03-15*
