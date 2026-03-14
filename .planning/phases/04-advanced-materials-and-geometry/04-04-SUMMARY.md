---
phase: 04-advanced-materials-and-geometry
plan: 04
subsystem: gui
tags: [bsdf, far-field, polar-plot, cylinder, prism, opengl, pyqtgraph, properties-panel, object-tree]

# Dependency graph
requires:
  - phase: 04-01-advanced-materials-and-geometry
    provides: "BSDF io (load_bsdf_csv, validate_bsdf), OpticalProperties.bsdf_profile_name, bsdf_profiles on Project"
  - phase: 04-02-advanced-materials-and-geometry
    provides: "SphereDetector.mode, SphereDetectorResult.candela_grid, export_ies, export_farfield_csv, compute_farfield_kpis"
  - phase: 04-03-advanced-materials-and-geometry
    provides: "SolidCylinder, SolidPrism dataclasses, solid_cylinders/solid_prisms on Project, 3D viewport cylinder/prism mesh rendering"

provides:
  - "BSDFPanel: profile list with Import CSV + Delete, 2D heatmap (reflection/transmission tabs, inferno colormap), 1D line plot for selected theta_in row"
  - "FarFieldPanel: multi-slice C-plane polar plot (8 C-planes with per-plane color), KPI sidebar (peak cd/total lm/beam angle/field angle/asymmetry), IES and CSV export"
  - "SolidCylinderForm and SolidPrismForm property editors following SolidBoxForm pattern"
  - "BSDF profile dropdown on OpticalPropertiesForm with grey-out of manual fields when BSDF active"
  - "PropertiesPanel show_solid_cylinder/show_solid_prism methods"
  - "Object tree: cylinder nodes with top_cap/bottom_cap/side children; prism nodes with cap_top/cap_bottom/side_N children"
  - "_draw_farfield_lobe in Viewport3D: color-mapped spherical mesh, radius proportional to candela, cool-to-warm colormap"
  - "clear_farfield_lobe in Viewport3D: removes previous lobe GLMeshItem"
  - "MainWindow: BSDF panel tab + far-field panel tab; add/delete Cylinder/Prism; post-simulation lobe refresh"

affects: [05-ui-revamp]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BSDFPanel: QListWidget + QTabWidget (Reflection/Transmission) + pyqtgraph ImageItem heatmaps + 1D PlotWidget for row detail"
    - "FarFieldPanel: pyqtgraph PlotWidget with aspect-locked polar display, C-plane QCheckBox per plane, QFormLayout KPI sidebar"
    - "Cool-to-warm colormap via np.interp with 5 keypoints [blue -> cyan -> green -> yellow -> red]"
    - "BSDF dropdown: setEnabled(False) on manual_fields list when BSDF profile selected"
    - "SolidCylinder/PrismForm follows SolidBoxForm pattern: _loading guard + QSignalBlocker on all spinboxes"

key-files:
  created:
    - backlight_sim/gui/bsdf_panel.py
    - backlight_sim/gui/far_field_panel.py
  modified:
    - backlight_sim/gui/properties_panel.py
    - backlight_sim/gui/object_tree.py
    - backlight_sim/gui/main_window.py
    - backlight_sim/gui/viewport_3d.py
    - backlight_sim/io/project_io.py

key-decisions:
  - "FarFieldPanel polar plot: aspect ratio locked to 1:1; polar display uses (I*sin(theta), I*cos(theta)) with mirrored negative half"
  - "BSDF delete guard checks op.bsdf_profile_name across all optical_properties before allowing delete"
  - "Far-field lobe cleared before each refresh via clear_farfield_lobe() to avoid duplicate meshes"
  - "Object tree cylinders/prisms placed under existing Solid Bodies group (not Surfaces) — architecturally correct for volumetric objects"

patterns-established:
  - "New tab panels: QWidget created in _setup_ui, wired via signal in _connect_signals, refreshed in _on_sim_finished"
  - "Per-face solid body tree nodes stored with UserRole tuple (body_type, body_name) for type-safe selection dispatch"

requirements-completed: [BRDF-01, DET-01, GEOM-02, GEOM-03]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 4 Plan 04: GUI Panels for BSDF, Far-field, and Solid Bodies Summary

**BSDFPanel (import/heatmap/line-plot), FarFieldPanel (polar C-plane plot/KPIs/export), OpticalProperties BSDF dropdown, SolidCylinderForm/SolidPrismForm, 3D intensity lobe rendering, and full MainWindow wiring**

## Performance

- **Duration:** 5 min (implementation was pre-committed; verification and docs executed now)
- **Started:** 2026-03-14T20:01:35Z
- **Completed:** 2026-03-14T20:06:00Z
- **Tasks:** 2 of 3 (Task 3 is human-verify checkpoint)
- **Files modified:** 7

## Accomplishments

- BSDFPanel: profile list with Import CSV (validates energy conservation, warns if violated) and Delete (with reference check), 2D heatmap tabs for Reflection/Transmission using pyqtgraph ImageItem + inferno colormap, 1D line plot for selected theta_in row (click-to-select)
- FarFieldPanel: 8 C-plane polar plot overlays with per-plane QCheckBox toggles and distinct colors, KPI sidebar (peak cd, total lm, beam angle, field angle, asymmetry via compute_farfield_kpis), Export IES + Export CSV buttons
- OpticalPropertiesForm: BSDF profile QComboBox, manual fields disabled when BSDF active, bsdf_profile_name written to OpticalProperties
- SolidCylinderForm and SolidPrismForm following SolidBoxForm pattern with load/apply and changed Signal
- Viewport3D _draw_farfield_lobe: spherical mesh with radius proportional to candela, cool-to-warm colormap (blue -> cyan -> green -> yellow -> red), clear_farfield_lobe removes previous item
- Object tree: cylinder with top_cap/bottom_cap/side children; prism with cap_top/cap_bottom/side_N children under Solid Bodies
- MainWindow: BSDF and Far-field panel tabs, cylinder/prism add/delete actions, post-simulation lobe refresh triggered for far-field sphere detectors

## Task Commits

Implementation was pre-committed from prior session:

1. **Task 1: BSDF panel and OpticalProperties BSDF dropdown** - `615f222` (feat)
   - BSDFPanel (bsdf_panel.py), SolidCylinderForm + SolidPrismForm + BSDF dropdown (properties_panel.py)
   - Object tree cylinder/prism entries (object_tree.py), main_window wiring (main_window.py)

2. **Task 2: Far-field polar plot panel, 3D intensity lobe, and viewport wiring** - `c02af34` (feat)
   - FarFieldPanel (far_field_panel.py), _draw_farfield_lobe + clear_farfield_lobe (viewport_3d.py)

3. **Task 3: Human verify checkpoint** — AWAITING human verification

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `backlight_sim/gui/bsdf_panel.py` — BSDFPanel with import/delete, heatmap tabs, 1D row detail plot
- `backlight_sim/gui/far_field_panel.py` — FarFieldPanel with 8 C-plane polar plot, KPI sidebar, IES/CSV export
- `backlight_sim/gui/properties_panel.py` — SolidCylinderForm, SolidPrismForm, BSDF dropdown on OpticalPropertiesForm, PropertiesPanel show_* methods
- `backlight_sim/gui/object_tree.py` — cylinder/prism nodes with face children in Solid Bodies group
- `backlight_sim/gui/main_window.py` — panel tabs, add/delete cylinder/prism, _on_bsdf_changed, post-sim lobe refresh
- `backlight_sim/gui/viewport_3d.py` — _draw_farfield_lobe (spherical candela mesh), clear_farfield_lobe, cylinder/prism refresh iteration
- `backlight_sim/io/project_io.py` — solid_cylinders/solid_prisms/bsdf_profiles serialization

## Decisions Made

- FarFieldPanel uses aspect-locked PlotWidget with polar display `(I*sin(theta), I*cos(theta))` mirrored to negative half — matches standard goniophotometer convention
- BSDF delete guard checks all optical_properties for bsdf_profile_name references before allowing delete — prevents dangling references
- Far-field lobe cleared before each refresh to avoid mesh accumulation across multiple simulation runs
- Cylinder and prism placed under "Solid Bodies" group (not "Surfaces") — volumetric refractive objects need the Solid Bodies group with face-children pattern

## Deviations from Plan

None — plan executed exactly as specified. All implementations follow the patterns from the plan's interfaces section.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All Phase 4 GUI panels complete: BSDF management, far-field photometric analysis, 3D intensity lobe, cylinder/prism property editing
- Phase 4 requirements BRDF-01, DET-01, GEOM-02, GEOM-03 satisfied
- Ready for Phase 5 (UI revamp) after human verification of this checkpoint
- Application imports verified clean: all gui modules import without error

---
*Phase: 04-advanced-materials-and-geometry*
*Completed: 2026-03-14*
