---
phase: 05-ui-rewamp
plan: 04
subsystem: ui
tags: [pyqtgraph, colormap, crosshair, collapsible-section, live-preview, simulation-thread, signals]

# Dependency graph
requires:
  - phase: 05-ui-rewamp
    provides: CollapsibleSection widget (05-03), QUndoStack (05-02)
provides:
  - Enhanced heatmap panel with colormap selector (viridis/plasma/inferno/magma/CET-L1)
  - Crosshair cursor with live pixel coordinate and flux value display
  - Collapsible KPI card sections (Grid Statistics, Uniformity, Energy Balance, Design Score)
  - Color-coded threshold labels (green/yellow/red) on uniformity, CV, hotspot, efficiency
  - Live heatmap preview during single-thread simulation (partial_result_callback)
  - Live preview disabled in MP mode with log message
affects: [future-heatmap-extensions, simulation-thread]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - partial_result_callback pattern in RayTracer.run() for live simulation preview
    - CollapsibleSection replacing QGroupBox for KPI card organization
    - _threshold_color() helper for CSS color-coded KPI labels

key-files:
  created: []
  modified:
    - backlight_sim/gui/heatmap_panel.py
    - backlight_sim/sim/tracer.py
    - backlight_sim/gui/main_window.py

key-decisions:
  - "Partial result emitted after each source completes (not at arbitrary 5% intervals) — source-granularity is natural throttle matching progress callback rhythm"
  - "grid.copy() used for partial snapshots — fast shallow numpy copy, avoids deepcopy overhead at source boundaries"
  - "Partial results contain only detector grids + energy balance (no ray_paths, sphere_detectors, solid_body_stats) — minimizes cross-thread data transfer"
  - "progress >= 0.05 guard prevents emitting partial result before any meaningful data exists"
  - "CollapsibleSection wraps a QWidget with QGridLayout (not the CollapsibleSection directly) to preserve existing grid layout structure"
  - "Crosshair hidden when mouse outside plot bounds — uses sceneBoundingRect().contains() check"

patterns-established:
  - "Threshold coloring: _threshold_color(value, green_thresh, yellow_thresh, higher_is_better) returns CSS color string"
  - "Collapsible KPI cards: CollapsibleSection wraps inner QWidget with existing QGridLayout"

requirements-completed: [UI-07, UI-08]

# Metrics
duration: 18min
completed: 2026-03-15
---

# Phase 05 Plan 04: Enhanced Heatmap and Live Preview Summary

**Heatmap panel with colormap selector, crosshair cursor, collapsible KPI cards with color-coded thresholds, and live simulation preview via partial_result_callback signal chain**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-15T22:00:00Z
- **Completed:** 2026-03-15T22:18:00Z
- **Tasks:** 2 (+ checkpoint awaiting visual verification)
- **Files modified:** 3

## Accomplishments

- Colormap selector (viridis, plasma, inferno, magma, CET-L1) added to heatmap toolbar, updating ImageItem and ColorBarItem in real-time
- Crosshair cursor (pg.InfiniteLine V+H) connected to sigMouseMoved with live pixel (x, y) and flux value display
- All four KPI sections (Grid Statistics, Uniformity, Energy Balance, Design Score) converted from QGroupBox to CollapsibleSection widgets
- Color-coded threshold labels applied to CV, hotspot ratio, edge-center ratio, uniformity, and extraction efficiency
- Live heatmap preview: RayTracer.run() accepts partial_result_callback, SimulationThread emits partial_result Signal, _on_partial_result() updates heatmap at source completion points
- ROI pen updated from cyan 'c' to teal '#00bcd4' for dark theme consistency

## Task Commits

1. **Task 1: Enhanced heatmap panel** - `8565ed3` (feat)
2. **Task 2: Live heatmap preview** - `31e2ffa` (feat)

## Files Created/Modified

- `backlight_sim/gui/heatmap_panel.py` - Colormap selector, crosshair, collapsible KPI cards, threshold colors
- `backlight_sim/sim/tracer.py` - partial_result_callback in run() and _run_single()
- `backlight_sim/gui/main_window.py` - partial_result Signal on SimulationThread, _on_partial_result() handler

## Decisions Made

- Partial result emitted after each source completes (not at arbitrary 5% intervals) — source-granularity is natural throttle matching progress callback rhythm
- grid.copy() used for partial snapshots — fast shallow numpy copy, avoids deepcopy overhead
- Partial results contain only detector grids + energy balance (no ray_paths, sphere_detectors, solid_body_stats) — minimizes cross-thread data transfer
- progress >= 0.05 guard prevents emitting partial result before any meaningful data exists
- CollapsibleSection wraps a QWidget with QGridLayout (not the CollapsibleSection directly) to preserve existing grid layout structure

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Self-Check

- [x] `backlight_sim/gui/heatmap_panel.py` modified with colormap combo, crosshair, CollapsibleSection, threshold colors
- [x] `backlight_sim/sim/tracer.py` partial_result_callback in run() and _run_single()
- [x] `backlight_sim/gui/main_window.py` partial_result signal and _on_partial_result()
- [x] Task 1 commit: 8565ed3
- [x] Task 2 commit: 31e2ffa
- [x] All 102 tests pass

## Self-Check: PASSED

All committed files verified to exist. All test suite passes (102/102). Feature verification checks (Task 1 and Task 2 automated assertions) both passed.

## Next Phase Readiness

- Enhanced heatmap is complete and ready for use
- Awaiting visual verification at checkpoint (checkpoint task 3)
- After checkpoint approval, phase 05 will be fully complete

---
*Phase: 05-ui-rewamp*
*Completed: 2026-03-15*
