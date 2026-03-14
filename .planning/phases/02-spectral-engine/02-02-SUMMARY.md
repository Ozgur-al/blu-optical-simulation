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
  - SpectralDataPanel GUI tab: SPD editor, material spectral table editor, blackbody generator, CIE 1931 chromaticity diagram with spectral locus and Planckian locus
  - Color Uniformity KPI section in HeatmapPanel (hidden when no spectral data)
  - Click-to-inspect per-pixel SPD popup in HeatmapPanel
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

patterns-established:
  - "Color KPI helpers (xyz_per_pixel, xy_per_pixel, uv_per_pixel) follow same (ny,nx,3) -> (ny,nx,2) broadcast pattern as spectral_grid_to_rgb"
  - "CSV export appends color KPI rows when grid_spectral is present — backward-compatible (rows only added when data available)"
  - "HTML report color section inside per-detector loop — each detector section conditionally includes its color table"

requirements-completed: [SPEC-03, SPEC-05]

duration: 7min
completed: 2026-03-14
---

# Phase 2 Plan 02: Spectral Engine GUI Summary

**CIE 1931 colorimetry KPI suite (delta-CCx/CCy/u'v'/CCT), SpectralDataPanel with SPD editor and chromaticity diagram, click-to-inspect per-pixel spectrum, and color uniformity in heatmap dashboard and reports**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-14T~10:19Z
- **Completed:** 2026-03-14
- **Tasks:** 2 auto-tasks complete, 1 checkpoint pending human verification
- **Files modified:** 5

## Accomplishments

- CIE 1931 colorimetry helpers (xyz/xy/uv per pixel, Robertson CCT, compute_color_kpis) added to sim/spectral.py
- SpectralDataPanel created with SPD editor (import/export/duplicate/blackbody/normalize), material spectral table editor, CIE 1931 chromaticity diagram (spectral locus, Planckian locus, per-pixel scatter after simulation)
- Color Uniformity KPI section added to HeatmapPanel dashboard (full detector + 1/4, 1/6, 1/10 center fractions; hidden for non-spectral simulations)
- Click-to-inspect: heatmap pixel click opens non-modal SPD popup plot
- KPI CSV export extended with 14 color uniformity rows when spectral data available
- HTML report extended with Color Uniformity table section per detector when spectral data available

## Task Commits

1. **Task 1: CIE colorimetry helpers, SpectralDataPanel, MainWindow wiring** - `aab9e49` (feat)
2. **Task 2: Color Uniformity KPIs, click-to-inspect, export extensions** - `150c257` (feat)
3. **Task 3: Human visual verification** - PENDING CHECKPOINT

## Files Created/Modified

- `backlight_sim/sim/spectral.py` — Added xyz_per_pixel, xy_per_pixel, uv_per_pixel, cct_robertson (Robertson 1968 31-isotherm table), compute_color_kpis
- `backlight_sim/gui/spectral_data_panel.py` (new) — SpectralDataPanel with SPD manager, material spectral tables, CIE 1931 chromaticity diagram, blackbody generator
- `backlight_sim/gui/heatmap_panel.py` — Color Uniformity QGroupBox, _update_color_uniformity, _on_image_clicked, CSV export extension
- `backlight_sim/gui/main_window.py` — SpectralDataPanel imported and wired as 6th center tab, set_project/update_chromaticity calls in all project-load paths
- `backlight_sim/io/report.py` — Color Uniformity HTML table section per detector when grid_spectral is not None

## Decisions Made

- Robertson 1968 31-entry isotherm table inlined (covers 1000–3500 K); output clamped to [1000, 25000] K to handle extrapolation gracefully
- Color Uniformity KPI section hidden by default — avoids layout reflow when running non-spectral simulations
- compute_color_kpis luminance-weights mean CCT (by Y channel) to emphasize brighter pixels
- Chromaticity scatter uses [::4, ::4] subsampling to keep point count manageable for large detectors

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- All colorimetry helpers in place; spectral GUI fully wired
- Human verification (Task 3 checkpoint) required before marking plan complete
- After checkpoint approval: ready for Phase 2 Plan 03 (if exists) or Phase 3 planning

---
*Phase: 02-spectral-engine*
*Completed: 2026-03-14*
