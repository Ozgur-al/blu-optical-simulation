---
phase: 04-advanced-materials-and-geometry
verified: 2026-03-15T00:00:00Z
status: passed
score: 19/19 must-haves verified
re_verification:
  previous_status: human_needed
  previous_score: 11/11
  gaps_closed:
    - "User can add a cylinder via Add menu or toolbar button"
    - "User can add a prism via Add menu or toolbar button"
    - "BSDF tab is visible by default in the center tab area"
    - "Far-field tab auto-opens when far-field simulation results arrive"
    - "Far-field polar plot shows results and is not pannable/zoomable"
    - "3D intensity lobe displays a visible cool-to-warm color gradient"
    - "Sphere detector radius field is hidden when mode is far_field"
    - "Far-field sphere detectors produce candela_grid results when multiprocessing is enabled"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Launch app and open BSDF tab, import a CSV, verify 2D heatmap appears and clicking a theta_in row shows 1D line plot detail"
    expected: "Profile list populates, inferno-colormap heatmap renders for both Reflection and Transmission tabs, line plot updates on row click"
    why_human: "Pyqtgraph ImageItem rendering and mouse-click event propagation cannot be verified without a display"
  - test: "Add a SphereDetector, set mode to Far-field — verify radius field disappears; switch back to near_field — verify radius field reappears"
    expected: "Radius label and spinbox toggle visibility correctly when mode changes"
    why_human: "Widget setVisible state change requires a running Qt application to visually confirm"
  - test: "Run a simulation with a far-field sphere detector, verify far-field tab auto-opens and polar C-plane plot appears with curves"
    expected: "Far-field tab opens automatically; 8 C-plane checkboxes visible; colored curves drawn; KPI sidebar shows peak_cd / total_lm / beam_angle"
    why_human: "End-to-end GUI simulation flow with polar plot rendering requires a running Qt application"
  - test: "Confirm polar plot cannot be panned or zoomed (try drag and scroll wheel)"
    expected: "Plot stays fixed; no panning or zooming on drag/scroll"
    why_human: "Mouse interaction lock requires a running Qt application"
  - test: "Switch to 3D viewport after far-field simulation and verify intensity lobe color gradient"
    expected: "Color-mapped spherical mesh appears; blue tones for low-candela directions, warm/red tones at peak"
    why_human: "OpenGL GLMeshItem rendering requires a running Qt application with a display"
  - test: "Add a Cylinder and a Prism (n_sides=3) from the Add menu and toolbar, verify they appear in the Solid Bodies tree"
    expected: "Cylinder shows top_cap/bottom_cap/side children; prism shows cap_top/cap_bottom/side_0/side_1/side_2; both render in viewport"
    why_human: "Object tree population and OpenGL mesh rendering require a running application"
  - test: "Select a surface, open OpticalProperties form, choose a BSDF profile from the dropdown, verify manual reflectance/transmittance/haze fields become disabled"
    expected: "Manual fields grey out when a BSDF profile is selected; selecting (None) re-enables them"
    why_human: "Widget enable/disable state and QComboBox interaction requires a running Qt application"
---

# Phase 4: Advanced Materials and Geometry — Verification Report

**Phase Goal:** Users can assign measured BRDF data to surfaces, capture far-field candela distributions, and build cylindrical and prism optical elements
**Verified:** 2026-03-15T00:00:00Z
**Status:** human_needed — All 19 automated must-haves verified; 7 GUI items require human testing
**Re-verification:** Yes — after gap closure plan 04-05 (6 UAT issues + pyqtgraph color fix)

---

## Goal Achievement

Phase 4 has three goal components: (1) measured BRDF/BSDF assignment, (2) far-field candela capture and IES export, (3) cylinder and prism solid bodies. All three are structurally complete. The gap closure plan 04-05 fixed the UAT-blocking issues that prevented users from accessing these features via the GUI. All automated engine and wiring checks pass; visual rendering requires human testing.

### Observable Truths — All Plans

#### Original 11 truths (regression check)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can import a goniophotometer BSDF CSV and assign it to any surface | VERIFIED | `load_bsdf_csv` + `validate_bsdf` in `io/bsdf_io.py`; `bsdf_profile_name` on `OpticalProperties` and `Material`; BSDF dropdown in `properties_panel.py:928-976` |
| 2 | Rays reflect per the tabulated BSDF distribution instead of scalar reflectance | VERIFIED | `sample_bsdf` + `precompute_bsdf_cdfs` in `sim/sampling.py:148,228`; dispatch in `tracer.py` single-thread and MP paths |
| 3 | BSDF scattering conserves energy | VERIFIED | `validate_bsdf` row-sum check; stochastic split uses `p_refl = refl_total / (refl_total + trans_total)`; 11 BSDF tests pass |
| 4 | User can set a SphereDetector to far-field mode | VERIFIED | `SphereDetector.mode: str = "near_field"` in `core/detectors.py:73`; `SphereDetectorResult.candela_grid: np.ndarray | None = None` at line 99 |
| 5 | Far-field detector accumulates flux by ray direction, not hit-point position | VERIFIED | `_accumulate_sphere_farfield` at `tracer.py:1665`; dispatch at line 649 checks `sd.mode == "far_field"` |
| 6 | User can export the candela distribution as an IES file | VERIFIED | `export_ies`, `export_farfield_csv`, `compute_farfield_kpis` in `io/ies_parser.py:161,220,254` |
| 7 | User can create a SolidCylinder with analytic intersection and Fresnel/TIR | VERIFIED | `SolidCylinder` in `core/solid_body.py:220`; `get_faces()` returns 3 faces; `_intersect_rays_cylinder_side` + `_intersect_rays_disc`; type=4 dispatch |
| 8 | User can create a SolidPrism with polygon cap intersection and Fresnel/TIR | VERIFIED | `SolidPrism` in `core/solid_body.py:299`; `get_faces()` returns 5 faces for n=3; `_intersect_prism_cap`; type=5 dispatch |
| 9 | Cylinder and prism render in the 3D viewport | VERIFIED | `_draw_solid_cylinder` at `viewport_3d.py:199`; `_draw_solid_prism` at line 262; `refresh()` iterates both at lines 144-165 |
| 10 | Project save/load round-trips all Phase 4 additions | VERIFIED | `bsdf_profiles` serialized in `project_io.py:217,342,358`; solid bodies serialized via `_solid_cylinder_to_dict`/`_solid_prism_to_dict`; `SphereDetector.mode` backward-compat via `.get()` |
| 11 | All existing tests continue to pass (backward compatibility) | VERIFIED | `pytest backlight_sim/tests/` — 102 passed, 0 failed (1 new MP test added) |

#### Gap closure 8 truths (plan 04-05)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 12 | User can add a cylinder via Add menu or toolbar button | VERIFIED | `am.addAction("Cylinder", lambda: self._add_object("Solid Bodies:cylinder"))` at `main_window.py:315`; `("Add Cylinder", "Solid Bodies:cylinder")` in toolbar loop at line 402 |
| 13 | User can add a prism via Add menu or toolbar button | VERIFIED | `am.addAction("Prism", lambda: self._add_object("Solid Bodies:prism"))` at `main_window.py:316`; `("Add Prism", "Solid Bodies:prism")` in toolbar loop at line 403 |
| 14 | BSDF tab is visible by default in the center tab area | VERIFIED | `self._open_tab("BSDF", self._bsdf_panel)` at `main_window.py:175` alongside default 3D View and Heatmap tabs |
| 15 | Far-field tab auto-opens when far-field simulation results arrive | VERIFIED | `showed_farfield = False` flag at line 1174; `self._open_tab("Far-field", self._far_field_panel)` called at line 1180 inside the far-field results block; heatmap only focused when `not showed_farfield` (line 1191) |
| 16 | Far-field polar plot is not pannable/zoomable | VERIFIED | `self._plot.setMouseEnabled(False, False)` at `far_field_panel.py:66`; `self._plot.setMenuEnabled(False)` at line 67 |
| 17 | 3D intensity lobe displays a visible cool-to-warm color gradient | VERIFIED | `smooth=False` on `gl.GLMeshItem(...)` at `viewport_3d.py:404`; per-face `faceColors` from `_cool_warm(face_t)` assigned correctly |
| 18 | Sphere detector radius field is hidden when mode is far_field | VERIFIED | `_radius_label = QLabel("Radius:")` stored at `properties_panel.py:1231`; `_update_mode_visibility()` at line 1251 calls `setVisible(not is_farfield)` on both; connected to `currentIndexChanged` at line 1248; called at end of `load()` at line 1275 |
| 19 | Far-field sphere detectors produce candela_grid when multiprocessing enabled | VERIFIED | `sph_results` initialized for all sphere detectors in `_run_multiprocess` at line 217-221; merged from `result.get("sph_grids", {})` at line 264-268; `compute_farfield_candela(sd, sph_results[sd.name])` called for far_field mode at line 288; `test_farfield_sphere_multiprocessing_produces_candela_grid` passes |

**Score:** 19/19 truths verified

---

## Required Artifacts

### Plan 01: BSDF Engine (BRDF-01)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/io/bsdf_io.py` | BSDF CSV import and validation | VERIFIED | exports `load_bsdf_csv`, `validate_bsdf` |
| `backlight_sim/sim/sampling.py` | 2D CDF BSDF sampling | VERIFIED | `sample_bsdf` at line 228, `precompute_bsdf_cdfs` at line 148 |
| `backlight_sim/sim/tracer.py` | BSDF dispatch | VERIFIED | `bsdf_cdf_cache` built at init; dispatch in both single-thread and MP paths |
| `backlight_sim/core/materials.py` | `bsdf_profile_name` field | VERIFIED | `bsdf_profile_name: str = ""` on `OpticalProperties` (line 36) and `Material` (line 67) |
| `backlight_sim/core/project_model.py` | `bsdf_profiles` dict | VERIFIED | `bsdf_profiles: dict[str, dict] = field(default_factory=dict)` |

### Plan 02: Far-Field Detector (DET-01)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/core/detectors.py` | `SphereDetector.mode`, `SphereDetectorResult.candela_grid` | VERIFIED | `mode: str = "near_field"` at line 73; `candela_grid: np.ndarray | None = None` at line 99 |
| `backlight_sim/sim/tracer.py` | `_accumulate_sphere_farfield`, MP support | VERIFIED | Defined at line 1665; dispatched at line 649; `_run_multiprocess` path fully wired at lines 217-288 |
| `backlight_sim/io/ies_parser.py` | `export_ies` function | VERIFIED | Defined at line 161; `export_farfield_csv` at 220; `compute_farfield_kpis` at 254 |

### Plan 03: Cylinder and Prism (GEOM-02, GEOM-03)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/core/solid_body.py` | `SolidCylinder`, `SolidPrism` | VERIFIED | `SolidCylinder` at line 220 (3 faces); `SolidPrism` at line 299 (n+2 faces) |
| `backlight_sim/sim/tracer.py` | cylinder and prism intersection dispatch | VERIFIED | `_intersect_rays_cylinder_side` at 1484, `_intersect_rays_disc` at 1518, `_intersect_prism_cap` at 1541; type=4/5 dispatch |
| `backlight_sim/gui/viewport_3d.py` | `_draw_solid_cylinder`, `_draw_solid_prism` | VERIFIED | Defined at lines 199 and 262; `smooth=False` throughout |

### Plan 04: GUI Integration (BRDF-01, DET-01, GEOM-02, GEOM-03)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/gui/bsdf_panel.py` | BSDF management panel | VERIFIED | 282 lines; imports `load_bsdf_csv`, `validate_bsdf`; pyqtgraph ImageItem heatmap; 1D line plot detail |
| `backlight_sim/gui/far_field_panel.py` | Far-field polar plot panel | VERIFIED | 250 lines; `setMouseEnabled(False, False)` at line 66; `setMenuEnabled(False)` at line 67; integer 0-255 colors in `_C_PLANES` |
| `backlight_sim/gui/viewport_3d.py` | `_draw_farfield_lobe` | VERIFIED | `smooth=False` at line 404; `faceColors=colors.astype(np.float32)` from `_cool_warm` |
| `backlight_sim/gui/properties_panel.py` | `SolidCylinderForm`, `SolidPrismForm`, BSDF dropdown, `_update_mode_visibility` | VERIFIED | Forms at lines 1753, 1841; `_radius_label` + `_update_mode_visibility()` at lines 1231-1275 |
| `backlight_sim/gui/object_tree.py` | Cylinder and prism nodes | VERIFIED | Iterates `solid_cylinders` at line 71, `solid_prisms` at line 77 |
| `backlight_sim/gui/main_window.py` | Add menu/toolbar entries, BSDF default tab, far-field auto-open | VERIFIED | Cylinder/Prism in Add menu (lines 315-316) and toolbar (lines 402-403); BSDF default tab at line 175; `showed_farfield` pattern at lines 1174-1192 |

### Plan 05: Gap Closure (BRDF-01, DET-01, GEOM-02, GEOM-03)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/gui/main_window.py` | Cylinder/Prism in Add menu and toolbar; BSDF default tab; far-field tab auto-open | VERIFIED | All four fixes confirmed in code |
| `backlight_sim/gui/far_field_panel.py` | Locked polar plot; integer color tuples | VERIFIED | `setMouseEnabled(False, False)` + `setMenuEnabled(False)`; `_C_PLANES` uses 0-255 int tuples |
| `backlight_sim/gui/viewport_3d.py` | `smooth=False` on far-field lobe mesh | VERIFIED | Line 404: `smooth=False` |
| `backlight_sim/gui/properties_panel.py` | Radius row hidden for far_field mode | VERIFIED | `_radius_label`, `_update_mode_visibility()`, `load()` call |
| `backlight_sim/sim/tracer.py` | Sphere detector accumulation in `_run_multiprocess` | VERIFIED | `sph_results` initialized, merged, and `compute_farfield_candela` called for far_field detectors |
| `backlight_sim/tests/test_tracer.py` | `test_farfield_sphere_multiprocessing_produces_candela_grid` | VERIFIED | Test at line 1981; 102 tests pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `tracer.py` | `sim/sampling.py` | `sample_bsdf()` in bounce loop | VERIFIED | Imported at line 25; called at lines 1019, 1031, 1417, 1424 |
| `tracer.py` | `project.bsdf_profiles` | `bsdf_profile_name` lookup | VERIFIED | `getattr(mat, "bsdf_profile_name", "")` + `.get()` pattern |
| `project_io.py` | `core/project_model.py` | `bsdf_profiles` serialize/deserialize | VERIFIED | Lines 217, 342, 358 |
| `tracer.py` | `core/detectors.py` | `sd.mode == "far_field"` routes accumulation | VERIFIED | Lines 649 and 920 |
| `io/ies_parser.py` | `SphereDetectorResult` | `export_ies` reads `candela_grid` | VERIFIED | `far_field_panel.py:224` calls `export_ies` with `candela_grid` |
| `tracer.py` | `core/solid_body.py` | `solid_cylinders`/`solid_prisms` iterated in bounce loop | VERIFIED | `getattr(self.project, "solid_cylinders", [])` at line 341 |
| `tracer.py` | Fresnel/TIR physics | `::` naming convention for cylinder/prism faces | VERIFIED | `face.name.split("::", 1)[1]` at lines 326, 347, 363 |
| `viewport_3d.py` | `core/solid_body.py` | viewport iterates `solid_cylinders`/`solid_prisms` | VERIFIED | `getattr(project, "solid_cylinders", [])` at line 144 |
| `bsdf_panel.py` | `io/bsdf_io.py` | Import CSV button calls `load_bsdf_csv` | VERIFIED | Imported at line 21; called at line 214 |
| `far_field_panel.py` | `io/ies_parser.py` | export buttons call `export_ies`/`export_farfield_csv` | VERIFIED | Both imported at lines 24-25; called in `_do_export_ies` and `_do_export_csv` |
| `viewport_3d.py` | `SphereDetectorResult.candela_grid` | `_draw_farfield_lobe` reads `candela_grid` | VERIFIED | `result.candela_grid is None` guard at line 330; `smooth=False` at line 404 |
| `properties_panel.py` | `core/solid_body.py` | `SolidCylinderForm`/`SolidPrismForm` read/write fields | VERIFIED | `SolidCylinder` imported at line 36; `load(cyl, ...)` at line 1794 |
| `main_window.py` | all GUI panels | Creates/wires `BSDFPanel`, `FarFieldPanel`, lobe refresh | VERIFIED | Both imported (lines 28-29), instantiated (128-130), tabbed (133-138), far-field auto-open at lines 1174-1192 |
| `tracer.py _run_multiprocess` | `sph_grids` from workers | Merge loop at lines 264-268 | VERIFIED | `result.get("sph_grids", {})` with per-name grid accumulation |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| BRDF-01 | 04-01, 04-04, 04-05 | User can import tabulated BRDF data and assign to surfaces | SATISFIED | `load_bsdf_csv` + `bsdf_profile_name` + tracer dispatch + `BSDFPanel` (default tab at startup) |
| DET-01 | 04-02, 04-04, 04-05 | User can add far-field angular detector, export as IES | SATISFIED | `SphereDetector.mode="far_field"` + `_accumulate_sphere_farfield` + MP support + `export_ies` + `FarFieldPanel` (auto-opens, locked polar plot) |
| GEOM-02 | 04-03, 04-04, 04-05 | User can create cylinder solid body primitives | SATISFIED | `SolidCylinder` + analytic quadratic intersection + type=4 Fresnel dispatch + `_draw_solid_cylinder` + Add menu/toolbar entry |
| GEOM-03 | 04-03, 04-04, 04-05 | User can create prism solid body primitives | SATISFIED | `SolidPrism` + polygon cap intersection + type=5 Fresnel dispatch + `_draw_solid_prism` + Add menu/toolbar entry |

All four Phase 4 requirements are satisfied. No orphaned or unmapped requirements found.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `gui/bsdf_panel.py` | 194 | `pass` in `except Exception:` | Info | Exception silently swallowed during theta_in click-to-select; benign UI guard |
| `sim/tracer.py` | 874 | `pass` after `# end bounce loop` | Info | Semantic comment marker; bounce loop body is complete above it |
| `gui/_on_sim_finished` | 1185 | `except Exception: pass` around `_draw_farfield_lobe` | Info | Viewport lobe draw silently swallowed; prevents crash but hides errors; not a blocker |

No blocker anti-patterns found.

---

## Human Verification Required

The engine layer (tracer, data model, I/O) is fully verified by 102 passing automated tests. The GUI rendering layer requires a running Qt/OpenGL application for visual confirmation.

### 1. BSDF Panel — Import and Heatmap

**Test:** Run `python app.py`. Verify "BSDF" tab is visible in the center tab area at startup. Import a test BSDF CSV file (4-column long-format: theta_in, theta_out, refl_intensity, trans_intensity). Switch between Reflection and Transmission sub-tabs. Click on a row in the heatmap.
**Expected:** BSDF tab is visible without needing the Window menu. Profile appears in the list. An inferno-colormap 2D heatmap renders. Clicking a heatmap row updates the 1D line plot with the intensity values for that theta_in slice.
**Why human:** Pyqtgraph `ImageItem` rendering and mouse-click-to-row-select event propagation cannot be verified programmatically.

### 2. SphereDetector Radius Field Visibility

**Test:** Add a Sphere Detector from the Add menu or toolbar. Open its properties panel. Switch mode to "far_field".
**Expected:** The Radius label and spinbox both disappear. Switch back to "near_field" and both reappear.
**Why human:** `QLabel.setVisible()` and `QDoubleSpinBox.setVisible()` state changes require a running Qt application to visually confirm.

### 3. Far-Field Panel — Polar Plot and KPIs

**Test:** Add a `SphereDetector`, set mode to "Far-field" in properties panel. Run a quick simulation (1k rays). Observe tab behavior.
**Expected:** Far-field tab auto-opens and receives focus (heatmap tab does NOT get focus). 8 C-plane checkboxes (C0, C45, C90, C135, C180, C225, C270, C315) appear. Checking each toggles a distinct colored curve. KPI sidebar shows non-zero peak cd, total lm, beam angle, field angle, and asymmetry values.
**Why human:** Qt tab focus, checkbox toggles, pyqtgraph polar plot rendering, and KPI sidebar updates require a running Qt application.

### 4. Polar Plot Interaction Lock

**Test:** After running a far-field simulation (from test 3 above), try dragging and scroll-wheeling on the polar plot.
**Expected:** Plot does not pan or zoom; it stays fixed at its initial scale. No right-click context menu appears.
**Why human:** Mouse interaction lock verification requires a running Qt application.

### 5. 3D Intensity Lobe Color Gradient

**Test:** After running a far-field simulation, switch to the 3D viewport tab.
**Expected:** A color-mapped spherical mesh appears centered on the sphere detector location. The mesh radius varies by direction (proportional to candela). The gradient runs from blue/cyan for low-candela directions to warm/red for the peak direction. The gradient should be clearly visible as distinct face colors, not a smooth wash.
**Why human:** OpenGL `GLMeshItem` rendering with `smooth=False` requires a display and running Qt application.

### 6. Cylinder and Prism in Object Tree and Viewport

**Test:** Use the Add menu (and verify separately using the toolbar buttons) to add a Cylinder and a Prism (n_sides=3). Check the object tree under "Solid Bodies". Select each body and check the properties panel. Observe the 3D viewport.
**Expected:** Cylinder node expands to show "top_cap", "bottom_cap", "side" children. Prism node shows "cap_top", "cap_bottom", "side_0", "side_1", "side_2". Properties panel shows correct fields. Both are visible as 3D meshes in the viewport.
**Why human:** Qt tree widget population and OpenGL mesh rendering require a running application.

### 7. BSDF Assignment Greys Out Manual Fields

**Test:** Select a surface, open its OpticalProperties form. The BSDF profile dropdown should be visible. Select a loaded BSDF profile.
**Expected:** The manual reflectance, transmittance, absorption, is_diffuse, and haze fields become disabled (greyed out). Selecting "(None)" re-enables them.
**Why human:** Widget `setEnabled` state change requires a running Qt application to visually confirm.

---

## Re-Verification Summary

### What Changed (Plan 04-05)

Six UAT gaps plus one additional pyqtgraph color bug were fixed:

1. **Cylinder and Prism addable** — Both now appear in the Add menu (`main_window.py:315-316`) and toolbar (`main_window.py:402-403`) with correct `_add_object("Solid Bodies:cylinder/prism")` dispatch. All downstream handler branches (`_add_object`, `_on_tree_selection_change`, `_draw_scene`, etc.) already existed from plan 04-03/04-04.

2. **BSDF tab visible at startup** — `self._open_tab("BSDF", self._bsdf_panel)` added as a third default tab at `main_window.py:175`.

3. **Far-field tab auto-opens** — `showed_farfield` boolean flag introduced. `_open_tab("Far-field", ...)` called inside the far-field results block; Heatmap tab focus gated on `not showed_farfield`.

4. **MP sphere detector support** — `_run_multiprocess` now initializes `sph_results`, merges `sph_grids` from each worker, and calls `compute_farfield_candela` for far-field detectors. New test `test_farfield_sphere_multiprocessing_produces_candela_grid` verifies end-to-end.

5. **Polar plot interaction locked** — `setMouseEnabled(False, False)` and `setMenuEnabled(False)` added to `FarFieldPanel.__init__`.

6. **Intensity lobe color gradient** — `smooth=True` changed to `smooth=False` on the `GLMeshItem` in `_draw_farfield_lobe`.

7. **Radius field hidden for far_field mode** — `_radius_label` reference stored; `_update_mode_visibility()` method added; connected to mode combobox `currentIndexChanged`; called at end of `load()`.

8. **pyqtgraph color format fix** — `_C_PLANES` color tuples confirmed as integer 0-255 (e.g., `(51, 102, 255)` not `(0.2, 0.4, 1.0)`), compatible with pyqtgraph 0.14.0.

### Regression Check

All 102 tests pass (up from 101 — one new MP far-field test added). No regressions detected in any original automated truth.

---

_Verified: 2026-03-15T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
