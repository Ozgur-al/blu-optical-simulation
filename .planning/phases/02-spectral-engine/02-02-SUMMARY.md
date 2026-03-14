---
phase: 02-spectral-engine
plan: 02
subsystem: gui
tags: [spectral, colorimetry, cie, chromaticity, kpi, pyqtgraph, pyside6]

requires:
  - phase: 02-spectral-engine/02-01
    provides: spectral.py with get_spd_from_project, blackbody_spd, sample_wavelengths; Project.spd_profiles and Project.spectral_material_data; DetectorResult.grid_spectral

provides:
  - xyz_per_pixel, xy_per_pixel, uv_per_pixel in sim/spectral.py
  - cct_robertson (Robertson 1968 isotherm CCT estimation) in sim/spectral.py
  - compute_color_kpis returning delta-CCx/CCy/u'v'/CCT for full detector and center fractions
  - SpectralDataPanel GUI tab: SPD editor, material spectral table editor, blackbody generator, CIE 1931 chromaticity diagram with spectral locus and Planckian locus (fixed view range, filtered locus)
  - Color Uniformity KPI section in HeatmapPanel (hidden when no spectral data)
  - Click-to-inspect per-pixel SPD popup in HeatmapPanel
  - Spectral Color heatmap display mode with status feedback when no spectral data available
  - Color KPI rows in KPI CSV export
  - Color Uniformity table in HTML report

affects: [spectral-rendering, export-pipeline, cie-colorimetry]

tech-stack:
  added: []
  patterns:
    - "CIE colorimetry via matrix multiply: spectral_grid @ xyz_weights -> (ny,nx,3) XYZ in one call"
    - "Robertson 1968 CCT: convert xy to UCS u,v then find sign-change between isotherms and interpolate in reciprocal Mired space"
    - "Color Uniformity KPI section hidden by default; shown/hidden in _show_result based on grid_spectral presence"
    - "SpectralDataPanel follows AngularDistributionPanel pattern: _loading_table guard, QSignalBlocker on selector"
    - "ImageItem.mouseClickEvent override for non-modal pixel inspection dialog"
    - "Fixed plot range: setXRange/setYRange called both at init and after scatter update to prevent pyqtgraph auto-range override"
    - "_displayed flag pattern in display switcher: prevents fall-through when spectral mode is requested but unavailable"

key-files:
  created:
    - backlight_sim/gui/spectral_data_panel.py
  modified:
    - backlight_sim/sim/spectral.py
    - backlight_sim/gui/heatmap_panel.py
    - backlight_sim/gui/main_window.py
    - backlight_sim/io/report.py

key-decisions:
  - "Robertson 1968 31-isotherm table inlined directly — avoids external data files, covers 1000-3500 K with good accuracy; output clamped to [1000, 25000] K"
  - "Color Uniformity KPI section hidden by default, only shown when grid_spectral is not None — avoids layout reflow for non-spectral simulations"
  - "compute_color_kpis uses luminance-weighted mean CCT (weighted by Y) to emphasize bright pixels"
  - "Planckian locus computed on-demand in SpectralDataPanel init with 200-bin blackbody SPDs at each CCT — acceptable startup cost for visual quality"
  - "ImageItem.mouseClickEvent override (not signal) — simpler than subclassing ImageItem, works with pyqtgraph API"
  - "Chromaticity scatter subsampled to [::4, ::4] to limit points to ~625 max for 100x100 detector"
  - "Spectral locus filtered to CIE sum > 1e-3 of peak — removes 780nm region collapse to (0,0)"
  - "Fixed CIE 1931 view range [0,0.85] x [0,0.92] set both at init and after scatter update — prevents pyqtgraph auto-range override"
  - "Spectral Color status QLabel (orange italic) shown when grid_spectral is None — guides user to set non-white SPD"

patterns-established:
  - "Color KPI helpers (xyz_per_pixel, xy_per_pixel, uv_per_pixel) follow same (ny,nx,3) -> (ny,nx,2) broadcast pattern as spectral_grid_to_rgb"
  - "CSV export appends color KPI rows when grid_spectral is present — backward-compatible (rows only added when data available)"
  - "HTML report color section inside per-detector loop — each detector section conditionally includes its color table"
  - "Status QLabel below plot: orange italic text when display mode cannot produce output, with actionable guidance"

requirements-completed: [SPEC-03, SPEC-05]

duration: 24min
completed: 2026-03-14
---

# Phase 2 Plan 02: Spectral Engine GUI Summary

**CIE 1931 chromaticity diagram with fixed locus curves, Color Uniformity KPI dashboard (delta-CCx/CCy/u'v', CCT), click-to-inspect spectrum popup, Spectral Color heatmap mode with status feedback, and color KPIs in CSV/HTML exports**

## Performance

- **Duration:** ~24 min
- **Started:** 2026-03-14T10:19Z
- **Completed:** 2026-03-14
- **Tasks:** 3 (2 planned feature tasks + 1 visual-verification bug-fix task)
- **Files modified:** 5

## Accomplishments

- CIE 1931 colorimetry helpers (xyz/xy/uv per pixel, Robertson CCT, compute_color_kpis) added to sim/spectral.py
- SpectralDataPanel created with SPD editor (import/export/duplicate/blackbody/normalize), material spectral table editor, CIE 1931 chromaticity diagram (spectral locus, Planckian locus, per-pixel scatter after simulation)
- Color Uniformity KPI section added to HeatmapPanel dashboard (full detector + 1/4, 1/6, 1/10 center fractions; hidden for non-spectral simulations)
- Click-to-inspect: heatmap pixel click opens non-modal SPD popup plot
- KPI CSV export extended with 14 color uniformity rows when spectral data available
- HTML report extended with Color Uniformity table section per detector when spectral data available
- Three visual bugs fixed after user verification: locus collapse at 780nm, view range override, Spectral Color mode silent fallback

## Task Commits

1. **Task 1: CIE colorimetry helpers, SpectralDataPanel, MainWindow wiring** - `aab9e49` (feat)
2. **Task 2: Color Uniformity KPIs, click-to-inspect, export extensions** - `150c257` (feat)
3. **Task 3: Visual verification bug fixes** - `56db618` (fix)

## Files Created/Modified

- `backlight_sim/sim/spectral.py` — Added xyz_per_pixel, xy_per_pixel, uv_per_pixel, cct_robertson (Robertson 1968 31-isotherm table), compute_color_kpis
- `backlight_sim/gui/spectral_data_panel.py` (new) — SpectralDataPanel with SPD manager, material spectral tables, CIE 1931 chromaticity diagram, blackbody generator; fixed locus filtering and fixed view range
- `backlight_sim/gui/heatmap_panel.py` — Color Uniformity QGroupBox, _update_color_uniformity, _on_image_clicked, CSV export extension, spectral status label, _displayed flag control flow fix
- `backlight_sim/gui/main_window.py` — SpectralDataPanel imported and wired as 6th center tab, set_project/update_chromaticity calls in all project-load paths
- `backlight_sim/io/report.py` — Color Uniformity HTML table section per detector when grid_spectral is not None

## Decisions Made

- Robertson 1968 31-entry isotherm table inlined (covers 1000-3500 K); output clamped to [1000, 25000] K to handle extrapolation gracefully
- Color Uniformity KPI section hidden by default — avoids layout reflow when running non-spectral simulations
- compute_color_kpis luminance-weights mean CCT (by Y channel) to emphasize brighter pixels
- Chromaticity scatter uses [::4, ::4] subsampling to keep point count manageable for large detectors
- Spectral locus filtered to CIE sum > 1e-3 of peak to remove 780nm artifacts
- Fixed CIE 1931 view range enforced at init and after scatter update

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed spectral locus collapse to (0,0) at long wavelengths**
- **Found during:** Task 3 (user reported locus not visible)
- **Issue:** CIE _CIE_X/Y/Z at 780nm are all 0.0000, causing x=X/(X+Y+Z) to resolve 0/0 (guarded to (0,0)). Six long-wavelength points were plotted at (0,0), collapsing the locus tail.
- **Fix:** `valid = s > s.max() * 1e-3` filter in `_spectral_locus_xy()`. Reduced from 42 to 36 points.
- **Files modified:** backlight_sim/gui/spectral_data_panel.py
- **Verification:** `_spectral_locus_xy()` returns no (0,0) points; x range [0.008, 0.744], y range [0.000, 0.834]
- **Committed in:** 56db618

**2. [Rule 1 - Bug] Fixed CIE 1931 view range overridden by pyqtgraph auto-range**
- **Found during:** Task 3 (user reported locus not visible)
- **Issue:** pyqtgraph auto-ranges to fit all items. Adding/clearing scatter data caused view to jump to empty/incorrect range, potentially hiding static locus curves.
- **Fix:** Added explicit `setXRange(0.0, 0.85)` and `setYRange(0.0, 0.92)` at end of `_draw_static_loci()` and at end of `update_chromaticity()`.
- **Files modified:** backlight_sim/gui/spectral_data_panel.py
- **Verification:** CIE 1931 diagram always shows full horseshoe region regardless of scatter state.
- **Committed in:** 56db618

**3. [Rule 1 - Bug] Fixed Spectral Color mode silently falling back to intensity display**
- **Found during:** Task 3 (user reported Spectral Color doesn't function)
- **Issue:** When `grid_spectral is None` (source SPD = "white"), `use_spectral=False` caused silent fallback to intensity display with no feedback. Control flow also allowed spectral and RGB/intensity display to both render in edge cases.
- **Fix:** Introduced `_displayed` flag and `_spectral_status` QLabel (orange italic). When user selects "Spectral Color" with no spectral data, an actionable message is shown. Exception handling in spectral rendering path improved.
- **Files modified:** backlight_sim/gui/heatmap_panel.py
- **Verification:** White SPD shows orange label with guidance; non-white SPD shows color image with label hidden.
- **Committed in:** 56db618

---

**Total deviations:** 3 auto-fixed (all Rule 1 - Bug)
**Impact on plan:** All fixes address visual bugs discovered during verification. No scope creep. The underlying spectral data accumulation in the tracer was correct — only the visualization layer had issues.

## Issues Encountered

The user ran verification with the default "Simple Box" preset which uses "white" SPD. The `has_spectral` condition requires any source SPD != "white" to allocate `grid_spectral`. This is by design (avoids memory overhead for non-spectral simulations) but was not clearly communicated. The status label addition addresses this UX gap.

## Next Phase Readiness

- All colorimetry helpers in place; spectral GUI fully wired and verified
- 46/46 tests pass
- Phase 02 complete — ready for Phase 03 planning

---
*Phase: 02-spectral-engine*
*Completed: 2026-03-14*
