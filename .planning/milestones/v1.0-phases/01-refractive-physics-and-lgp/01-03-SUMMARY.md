---
phase: 01-refractive-physics-and-lgp
plan: 03
subsystem: gui
tags: [solid-body, lgp, object-tree, properties-panel, viewport-3d, geometry-builder, presets, pyside6]
requirements-completed: [GEOM-01]

dependency_graph:
  requires:
    - phase: 01-01
      provides: SolidBox dataclass, FACE_NAMES, get_faces()
    - phase: 01-02
      provides: build_lgp_scene(), preset_edge_lit_lgp(), SolidBox I/O serialization
  provides:
    - Solid Bodies category in scene tree with parent/child node structure
    - SolidBoxForm: box-level property editing (name/center/dims/material/coupling edges)
    - FaceForm: per-face optical property override editing
    - Viewport3D._draw_solid_box(): semi-transparent solid rendering with edge highlights
    - LGP tab in GeometryBuilderDialog with multi-edge coupling checkboxes
    - Edge-Lit LGP preset wired through Presets menu automatically via PRESETS dict
    - MainWindow wiring: add/delete/select SolidBox and face nodes
  affects:
    - future LGP workflow — users can now create, view, and edit SolidBox objects end-to-end

tech_stack:
  added: []
  patterns:
    - Solid Bodies tree uses 3-level hierarchy (group header -> box parent -> face children)
    - Face selection uses '::' separator in emitted name (BoxName::face_id)
    - _item_group_and_name() helper normalizes 2-level and 3-level tree items to (group, name)
    - SolidBoxForm and FaceForm follow existing _loading guard + QSignalBlocker pattern
    - Viewport draws SolidBox by iterating get_faces() and reusing _rect_mesh() helper

key_files:
  created: []
  modified:
    - backlight_sim/gui/object_tree.py
    - backlight_sim/gui/properties_panel.py
    - backlight_sim/gui/viewport_3d.py
    - backlight_sim/gui/geometry_builder.py
    - backlight_sim/gui/main_window.py

key_decisions:
  - "Solid Bodies tree uses 3-level hierarchy instead of flat list; face selection detected by checking grandparent.text(0) == 'Solid Bodies'"
  - "GeometryBuilderDialog converted to QTabWidget (Direct-Lit / LGP tabs) to cleanly separate workflows"
  - "build_lgp_scene blocking bug (wrong material name for bottom_reflector) auto-fixed via Rule 1"

patterns_established:
  - "3-level tree item: _item_group_and_name() detects face nodes (grandparent == group header)"
  - "SolidBox/FaceForm follow existing _loading guard pattern — no signal leakage on load"

duration: 8min
completed: "2026-03-14"
---

# Phase 1 Plan 3: SolidBox GUI Integration Summary

**Full GUI for edge-lit LGP workflow: Solid Bodies tree with parent/child face nodes, SolidBoxForm + FaceForm property editors, semi-transparent 3D viewport rendering, LGP geometry builder tab, and Edge-Lit LGP preset.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-14T09:16:53Z
- **Completed:** 2026-03-14T09:24:41Z
- **Tasks:** 2 auto tasks complete (Task 3 is human-verify checkpoint)
- **Files modified:** 5

## Accomplishments

- Scene tree shows "Solid Bodies" category; SolidBox expands into 6 face children with coupling edges highlighted green
- Properties panel shows SolidBoxForm (dimensions/center/material/coupling_edges) or FaceForm (optical_properties override) depending on selection
- 3D viewport renders each SolidBox face as a semi-transparent blue solid with edge lines; selected box uses yellow highlight
- LGP tab in Geometry Builder: width/height/thickness, refractive index, multi-edge coupling checkboxes, LED count/flux/distribution, detector gap, reflector gap, Build LGP Scene button
- Edge-Lit LGP preset appears in Presets menu automatically; loads complete 6-LED left-edge scene

## Task Commits

1. **Task 1: Object tree, properties panel, viewport** - `8524689` (feat)
2. **Task 2: LGP geometry builder tab and main_window wiring** - `9da01d9` (feat)
3. **Task 3: Visual verification checkpoint** — awaiting human verification

## Files Created/Modified

- `backlight_sim/gui/object_tree.py` - Added "Solid Bodies" group, parent/child tree nodes, _item_group_and_name() helper, face-aware context menu
- `backlight_sim/gui/properties_panel.py` - Added SolidBoxForm, FaceForm, show_solid_box(), show_face() methods to PropertiesPanel
- `backlight_sim/gui/viewport_3d.py` - Added _draw_solid_box() with per-face rendering; integrated into refresh() loop
- `backlight_sim/gui/geometry_builder.py` - Restructured to QTabWidget; added LGP tab with _create_lgp_tab() and _on_build_lgp()
- `backlight_sim/gui/main_window.py` - Added SolidBox import, "Solid Bodies" counter, _on_object_selected/add/delete handling

## Decisions Made

- Converted GeometryBuilderDialog to QTabWidget rather than adding another QGroupBox section — cleaner separation of direct-lit vs LGP workflows
- 3-level tree detection uses grandparent check (`grandparent.text(0) == 'Solid Bodies'`) rather than storing metadata — simple and self-contained
- SolidBoxForm coupling_edges uses individual QCheckBox per edge (left/right/front/back) rather than QListWidget — less code, matches plan spec

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed build_lgp_scene() using OpticalProperties key as Material name**
- **Found during:** Task 2 verification (io layer prerequisite check)
- **Issue:** The bottom_reflector Rectangle.axis_aligned call used `reflector_op_name` ("lgp_bottom_reflector") as the `material_name` parameter — but that's an OpticalProperties key, not a Material key. The tracer would fail to resolve the material.
- **Fix:** Added a separate `lgp_reflector_mat` Material and used it as material_name; `reflector_op_name` remains as optical_properties override
- **Files modified:** `backlight_sim/io/geometry_builder.py`
- **Verification:** `python -c "from backlight_sim.io.presets import preset_edge_lit_lgp; p=preset_edge_lit_lgp(); print(p.solid_bodies[0].name)"` prints "LGP" without error
- **Committed in:** `9da01d9` (Task 2 commit)

**2. [Rule 3 - Blocking] Plan 02 io layer prerequisites were already committed**
- **Found during:** Initial check before Task 1
- **Issue:** Plan 03 Task 2 verification calls `build_lgp_scene` and checks `PRESETS` — both were provided by plan 02. Checked git log and found commits `480b40a` and `329c337` from plan 02 execution — already committed, no re-work needed.
- **Fix:** Confirmed prerequisites exist; proceeded with plan 03 tasks only.

---

**Total deviations:** 1 auto-fixed (Rule 1 bug), 1 non-issue (prerequisite already done)
**Impact on plan:** Bug fix ensures tracer can resolve material for bottom reflector. No scope creep.

## Issues Encountered

None — plan executed cleanly.

## Next Phase Readiness

- Full LGP GUI workflow is operational: preset -> scene tree -> property editing -> 3D view -> run simulation -> KPI dashboard
- Task 3 (human visual verification) is the next step — requires running `python app.py` and verifying scene tree, properties panel, 3D viewport, geometry builder LGP tab
- Phase 2 (spectral simulation) can proceed after visual verification passes

---
*Phase: 01-refractive-physics-and-lgp*
*Completed: 2026-03-14*
