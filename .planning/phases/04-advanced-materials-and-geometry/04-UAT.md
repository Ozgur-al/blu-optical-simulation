---
status: diagnosed
phase: 04-advanced-materials-and-geometry
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md]
started: 2026-03-15T00:00:00Z
updated: 2026-03-15T00:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Add Cylinder Solid Body
expected: Scene menu has "Add Cylinder". Creates cylinder in object tree under "Solid Bodies" with top_cap/bottom_cap/side face children. 3D viewport shows a smooth cylindrical mesh.
result: issue
reported: "there is no such selection"
severity: major

### 2. Add Prism Solid Body
expected: Scene menu has "Add Prism". Creates a prism in the object tree under "Solid Bodies" with cap_top/cap_bottom and side_0..side_N face children. 3D viewport shows a faceted polygonal mesh.
result: issue
reported: "obviously dont have add prism either"
severity: major

### 3. Edit Cylinder Properties
expected: Selecting a cylinder in the object tree shows a property form with center XYZ, axis XYZ, radius, length, and material dropdown. Changing values updates the 3D viewport mesh.
result: skipped
reason: Cannot test — no way to add a cylinder (blocked by test 1)

### 4. Edit Prism Properties
expected: Selecting a prism shows a property form with center XYZ, axis XYZ, n_sides (spinbox, min 3), circumscribed_radius, length, and material dropdown. Changing n_sides changes the mesh shape (e.g., 3 = triangle, 6 = hexagon).
result: skipped
reason: Cannot test — no way to add a prism (blocked by test 2)

### 5. BSDF Panel Tab
expected: A "BSDF" tab is visible in the center tab area. Opening it shows a profile list (empty initially), with "Import CSV" and "Delete" buttons on the left side.
result: issue
reported: "no bsdf either"
severity: major

### 6. BSDF Dropdown on OpticalProperties
expected: When editing a surface's optical properties in the properties panel, there is a BSDF profile dropdown. Selecting a profile (if any exist) greys out the manual fields (reflectance, transmittance, absorption, diffuse, haze). Selecting "(None)" re-enables them.
result: issue
reported: "there is dropdown, cant approve the rest"
severity: minor

### 7. Far-Field Detector Mode
expected: When selecting a SphereDetector in the properties panel, there is a mode dropdown or selector with "Near-field" and "Far-field" options.
result: pass

### 8. Far-Field Simulation and Polar Plot
expected: After setting a SphereDetector to "Far-field" mode and running a simulation, a "Far-field" tab shows a polar plot with C-plane curve overlays (up to 8 C-planes with colored checkboxes). A KPI sidebar shows peak cd, total lm, beam angle, field angle, and asymmetry values.
result: issue
reported: "polar plot does not work it does not have any results, 3d receiver also dont have any results. live view does show blue shape in the middle of the receiver though. also polar plot is moveable zoomable, it should be fixed. also if i choose far-field receiver i should have to select a radius"
severity: major

### 9. 3D Intensity Lobe in Viewport
expected: After a far-field simulation, the 3D viewport shows a color-mapped spherical mesh (the intensity lobe) centered on the sphere detector. The mesh radius varies by direction (proportional to candela) and colors range from blue (low) to red (high).
result: issue
reported: "it does not have a gradient but it works by varying in direction"
severity: minor

### 10. Far-Field Export
expected: The far-field panel has "Export IES" and "Export CSV" buttons. Clicking each opens a save dialog and writes a file. The IES file follows IESNA LM-63 format.
result: skipped
reason: Far-field panel has no results (blocked by test 8)

### 11. Object Tree Face Selection
expected: Clicking a face child node (e.g., "top_cap" under a cylinder, or "side_0" under a prism) shows a face optical properties form where you can assign per-face coatings/overrides.
result: skipped
reason: Cannot test — no way to add cylinder/prism (blocked by tests 1-2)

### 12. Save and Load with Phase 4 Features
expected: Save a project containing a cylinder, a prism, and a far-field sphere detector. Close and reopen the project. All objects are preserved with correct properties — cylinders/prisms appear in tree and viewport, sphere detector mode is retained.
result: skipped
reason: Cannot test — no cylinders/prisms to save (blocked by tests 1-2)

## Summary

total: 12
passed: 1
issues: 6
pending: 0
skipped: 5

## Gaps

- truth: "Scene menu has 'Add Cylinder' option that creates a cylinder in the object tree and 3D viewport"
  status: failed
  reason: "User reported: there is no such selection"
  severity: major
  test: 1
  root_cause: "main_window.py toolbar quick-add buttons (lines 364-373) only list 'Add SolidBox'. Handler code for 'Solid Bodies:cylinder' exists at line 772 but no toolbar/menu entry triggers it."
  artifacts:
    - path: "backlight_sim/gui/main_window.py"
      issue: "Missing 'Add Cylinder' toolbar button entry at line 369"
  missing:
    - "Add ('Add Cylinder', 'Solid Bodies:cylinder') to quick-add toolbar buttons"
  debug_session: ""
- truth: "Scene menu has 'Add Prism' option that creates a prism in the object tree and 3D viewport"
  status: failed
  reason: "User reported: obviously dont have add prism either"
  severity: major
  test: 2
  root_cause: "Same as test 1 — main_window.py toolbar quick-add buttons missing 'Add Prism'. Handler code for 'Solid Bodies:prism' exists at line 786 but no toolbar/menu entry."
  artifacts:
    - path: "backlight_sim/gui/main_window.py"
      issue: "Missing 'Add Prism' toolbar button entry at line 369"
  missing:
    - "Add ('Add Prism', 'Solid Bodies:prism') to quick-add toolbar buttons"
  debug_session: ""
- truth: "A 'BSDF' tab is visible in the center tab area with profile list and Import CSV/Delete buttons"
  status: failed
  reason: "User reported: no bsdf either"
  severity: major
  test: 5
  root_cause: "BSDF dock is hidden by default (main_window.py lines 189-192). dock.hide() called at init. Only accessible via View > Panels > BSDF menu which user didn't discover."
  artifacts:
    - path: "backlight_sim/gui/main_window.py"
      issue: "BSDF dock hidden at startup (line 192), not auto-shown when relevant"
  missing:
    - "Remove bsdf_dock from _floating_docks set so it remains visible as a tab"
  debug_session: ""
- truth: "Far-field polar plot shows C-plane results with KPIs after simulation; 3D receiver shows results; polar plot should be fixed (not moveable/zoomable); far-field should not require radius"
  status: failed
  reason: "User reported: polar plot does not work it does not have any results, 3d receiver also dont have any results. live view does show blue shape in the middle of the receiver though. also polar plot is moveable zoomable, it should be fixed. also if i choose far-field receiver i should have to select a radius"
  severity: major
  test: 8
  root_cause: "Multiple issues: (1) Far-field dock hidden by default (line 189-192), show_result() writes data but dock never shown/raised — only heatmap dock is shown at line 1054. (2) Polar plot uses pyqtgraph PlotWidget with default mouse interaction enabled — needs setMouseEnabled(False, False). (3) SphereDetector form shows radius field for far-field mode where it's irrelevant (direction-based). (4) 3D receiver panel likely doesn't handle far-field data display."
  artifacts:
    - path: "backlight_sim/gui/main_window.py"
      issue: "Far-field dock not shown/raised after simulation (line 1044 calls show_result but doesn't show dock)"
    - path: "backlight_sim/gui/far_field_panel.py"
      issue: "PlotWidget allows mouse pan/zoom — should be fixed for polar display"
    - path: "backlight_sim/gui/properties_panel.py"
      issue: "SphereDetectorForm shows radius for far-field mode"
  missing:
    - "Show and raise far-field dock when far-field results arrive"
    - "Disable mouse interaction on polar plot (setMouseEnabled(False, False))"
    - "Hide radius field when mode is far-field in SphereDetectorForm"
  debug_session: ""
- truth: "3D intensity lobe has cool-to-warm color gradient (blue low to red high) based on candela values"
  status: failed
  reason: "User reported: it does not have a gradient but it works by varying in direction"
  severity: minor
  test: 9
  root_cause: "Colormap code in viewport_3d.py _draw_farfield_lobe (lines 378-398) is correct but GLMeshItem with smooth=True may not properly render per-face colors. Also, with a lambertian source the candela values may cluster in a narrow range making the gradient appear uniform blue."
  artifacts:
    - path: "backlight_sim/gui/viewport_3d.py"
      issue: "GLMeshItem smooth=True may interfere with faceColors rendering; consider smooth=False"
  missing:
    - "Try smooth=False on the lobe GLMeshItem for per-face color to render correctly"
  debug_session: ""
- truth: "BSDF dropdown greys out manual fields when a profile is selected and re-enables when '(None)' is selected"
  status: failed
  reason: "User reported: there is dropdown, cant approve the rest (no BSDF profiles to test grey-out behavior — blocked by test 5, no BSDF panel to import)"
  severity: minor
  test: 6
  root_cause: "Cascade of test 5 — BSDF panel dock hidden, so user cannot import profiles to test the dropdown grey-out behavior. The dropdown code itself may work correctly once profiles are importable."
  artifacts:
    - path: "backlight_sim/gui/main_window.py"
      issue: "BSDF panel hidden prevents importing profiles to test dropdown"
  missing:
    - "Fix test 5 (show BSDF dock) to unblock this test"
  debug_session: ""
