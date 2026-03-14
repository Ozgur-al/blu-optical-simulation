---
phase: 04-advanced-materials-and-geometry
plan: 05
subsystem: ui
tags: [pyqtgraph, PySide6, monte-carlo, far-field, multiprocessing, sphere-detector]

# Dependency graph
requires:
  - phase: 04-04
    provides: FarFieldPanel, BSDFPanel, SolidCylinder/Prism UI, 3D intensity lobe
provides:
  - Cylinder and Prism in Add menu and toolbar
  - BSDF tab visible by default at startup
  - Far-field tab auto-opens when far-field results arrive
  - Sphere detector support in multiprocessing tracer path with candela_grid
  - Polar plot locked (no pan/zoom/context menu)
  - 3D intensity lobe shows per-face cool-to-warm color gradient
  - SphereDetector radius field hides when mode is far_field
affects: [05-ui-rewamp]

# Tech tracking
tech-stack:
  added: []
  patterns: [showed_farfield boolean flag controls tab focus after simulation, smooth=False for per-face mesh coloring in pyqtgraph.opengl]

key-files:
  created: []
  modified:
    - backlight_sim/gui/main_window.py
    - backlight_sim/gui/far_field_panel.py
    - backlight_sim/gui/viewport_3d.py
    - backlight_sim/gui/properties_panel.py
    - backlight_sim/sim/tracer.py
    - backlight_sim/tests/test_tracer.py

key-decisions:
  - "showed_farfield boolean flag: only focus Heatmap tab when no far-field results were shown — avoids overriding the auto-opened Far-field tab"
  - "smooth=False on GLMeshItem: pyqtgraph.opengl smooth=True interpolates vertex normals overriding per-face faceColors; must be False for visible gradient"
  - "Sphere detector accumulation in _trace_single_source uses inline numpy (not _accumulate_sphere helpers) to avoid passing SphereDetectorResult objects between processes"
  - "sph_grids dict returned from _trace_single_source alongside grids — matches existing flat-detector pattern"

patterns-established:
  - "Mode-visibility pattern: store label reference, connect currentIndexChanged to _update_mode_visibility, call at end of load()"
  - "MP worker return dict extended with sph_grids key — maintains backwards compatibility if key absent via result.get()"

requirements-completed: [BRDF-01, DET-01, GEOM-02, GEOM-03]

# Metrics
duration: 20min
completed: 2026-03-14
---

# Phase 4 Plan 05: Gap Closure — UAT Fixes Summary

**Six UAT gaps closed: cylinder/prism addable via menu+toolbar, BSDF tab visible at startup, far-field tab auto-opens, sphere detector works in MP mode, polar plot locked, lobe gradient restored, radius hidden for far-field mode**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-14T21:25:00Z
- **Completed:** 2026-03-14T21:45:37Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Cylinder and Prism are now addable via the Add menu and the toolbar quick-add buttons
- BSDF tab opens by default at startup alongside 3D View and Heatmap, making it discoverable
- Far-field tab auto-opens and focuses when far-field simulation results arrive; heatmap focus only fires when no far-field results exist
- Sphere detectors now produce candela_grid results when multiprocessing is enabled (all 102 tests pass)
- Polar plot is non-interactive — setMouseEnabled(False, False) and setMenuEnabled(False) prevent accidental pan/zoom
- 3D intensity lobe shows visible blue-to-red gradient because smooth=False allows per-face faceColors to render correctly
- SphereDetectorForm hides the radius label and spinbox when mode is far_field, reappears when mode returns to near_field

## Task Commits

1. **Task 1: Fix menu/toolbar entries, BSDF visibility, and far-field tab auto-open** - `b9f08bc` (feat)
2. **Task 2: Fix sphere detector support in multiprocessing tracer path** - `c0bcff4` (feat)
3. **Task 3: Fix polar plot interaction, lobe colormap, and radius visibility** - `9cf1bd5` (feat)

## Files Created/Modified

- `backlight_sim/gui/main_window.py` — Added Cylinder/Prism to Add menu and toolbar; BSDF default tab; far-field tab auto-open with showed_farfield flag
- `backlight_sim/gui/far_field_panel.py` — setMouseEnabled(False, False) and setMenuEnabled(False) on polar plot
- `backlight_sim/gui/viewport_3d.py` — Changed smooth=True to smooth=False on far-field lobe GLMeshItem
- `backlight_sim/gui/properties_panel.py` — radius label/widget hidden when SphereDetector mode is far_field; _update_mode_visibility() method added
- `backlight_sim/sim/tracer.py` — Sphere detector intersection, accumulation, and candela merge in _run_multiprocess and _trace_single_source
- `backlight_sim/tests/test_tracer.py` — Added test_farfield_sphere_multiprocessing_produces_candela_grid

## Decisions Made

- `showed_farfield` boolean flag controls tab focus after simulation: only focus Heatmap when no far-field results shown — avoids overriding the auto-opened Far-field tab
- `smooth=False` on GLMeshItem: `smooth=True` interpolates vertex normals for OpenGL lighting, overriding `faceColors`; must be `False` for visible cool-to-warm gradient
- Sphere detector accumulation in `_trace_single_source` uses inline numpy rather than calling `_accumulate_sphere` helpers — avoids passing mutable `SphereDetectorResult` objects between processes (not picklable cleanly)
- `sph_grids` dict returned from `_trace_single_source` alongside `grids` — merging pattern mirrors existing flat detector merge; backwards-compatible via `result.get("sph_grids", {})`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 6 UAT gaps from Phase 04 testing are now closed
- Ready for human verification checkpoint: launch app.py and verify all 11 UAT checks
- Phase 05 (UI Revamp) can proceed once checkpoint is approved

---
*Phase: 04-advanced-materials-and-geometry*
*Completed: 2026-03-14*
