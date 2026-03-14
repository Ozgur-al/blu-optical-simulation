---
phase: 04-advanced-materials-and-geometry
verified: 2026-03-14T20:26:02Z
status: human_needed
score: 11/11 automated must-haves verified
human_verification:
  - test: "Launch app and open BSDF tab, import a CSV, verify 2D heatmap appears and clicking a theta_in row shows 1D line plot detail"
    expected: "Profile list populates, inferno-colormap heatmap renders for both Reflection and Transmission tabs, line plot updates on row click"
    why_human: "Pyqtgraph ImageItem rendering and mouse-click event propagation cannot be verified without a display"
  - test: "Add a SphereDetector, set mode to Far-field in properties panel, run a simulation, open Far-field tab and verify polar C-plane plot and KPI sidebar"
    expected: "8 C-plane checkboxes, colored curves, KPI sidebar shows peak_cd / total_lm / beam_angle / field_angle / asymmetry values after simulation"
    why_human: "End-to-end GUI simulation flow with polar plot rendering requires a running Qt application"
  - test: "Switch to 3D viewport after far-field simulation and verify intensity lobe is visible"
    expected: "Color-mapped spherical mesh appears centered on the sphere detector, with cool (blue) tones for low candela and warm (red) for peak"
    why_human: "OpenGL GLMeshItem rendering requires a running Qt application with a display"
  - test: "Add a cylinder and a prism (n_sides=3) from the scene menu, verify they appear in the Solid Bodies tree with correct face children and render in the 3D viewport"
    expected: "Cylinder shows top_cap/bottom_cap/side; prism shows cap_top/cap_bottom/side_0/side_1/side_2; both visible as meshes in viewport"
    why_human: "Object tree population and OpenGL mesh rendering require a running Qt application"
  - test: "Select a surface, open OpticalProperties form, choose a BSDF profile from the dropdown, verify manual reflectance/transmittance/haze fields become disabled"
    expected: "Manual fields grey out when a BSDF profile is selected; selecting (None) re-enables them"
    why_human: "Widget enable/disable state and QComboBox interaction requires a running Qt application"
---

# Phase 4: Advanced Materials and Geometry — Verification Report

**Phase Goal:** Users can assign measured BRDF data to surfaces, capture far-field candela distributions, and build cylindrical and prism optical elements
**Verified:** 2026-03-14T20:26:02Z
**Status:** human_needed — All 11 automated must-haves verified; 5 GUI items require human testing
**Re-verification:** No — initial verification

---

## Goal Achievement

The phase goal has three components: (1) measured BRDF/BSDF assignment, (2) far-field candela capture and IES export, (3) cylinder and prism solid bodies. All three are structurally complete in the codebase. The automated engine layer (tracer, I/O, data model) is fully verifiable; the GUI presentation layer requires human testing.

### Observable Truths — Automated Check

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can import a goniophotometer BSDF CSV and assign it to any surface | VERIFIED | `load_bsdf_csv` + `validate_bsdf` in `io/bsdf_io.py` (148 lines); `bsdf_profile_name` field on `OpticalProperties` and `Material`; BSDF dropdown in `properties_panel.py:928-976` |
| 2 | Rays reflect per the tabulated BSDF distribution instead of scalar reflectance | VERIFIED | `sample_bsdf` + `precompute_bsdf_cdfs` in `sim/sampling.py:148,228`; dispatch in `tracer.py:985-1032` (single-thread) and `tracer.py:1390-1424` (MP) overrides all scalar behavior |
| 3 | BSDF scattering conserves energy (no weight gain) | VERIFIED | `validate_bsdf` checks row sums with 1e-3 tolerance; stochastic reflect/transmit split uses `p_refl = refl_total / (refl_total + trans_total)` per theta_in bin; 11 BSDF tests pass including energy conservation |
| 4 | User can set a SphereDetector to far-field mode | VERIFIED | `SphereDetector.mode: str = "near_field"` in `core/detectors.py:73`; `SphereDetectorResult.candela_grid: np.ndarray | None = None` in `detectors.py:99` |
| 5 | Far-field detector accumulates flux by ray direction, not hit-point position | VERIFIED | `_accumulate_sphere_farfield` at `tracer.py:1665`; dispatch at `tracer.py:649` checks `sd.mode == "far_field"`; `compute_farfield_candela` at `tracer.py:1692` divides by solid angle |
| 6 | User can export the candela distribution as an IES file | VERIFIED | `export_ies`, `export_farfield_csv`, `compute_farfield_kpis` in `io/ies_parser.py:161,220,254`; import and calls in `far_field_panel.py:24-25,211-245` |
| 7 | User can create a SolidCylinder with analytic intersection and Fresnel/TIR | VERIFIED | `SolidCylinder` dataclass in `core/solid_body.py:220`; `_intersect_rays_cylinder_side` at `tracer.py:1484`, `_intersect_rays_disc` at `tracer.py:1518`; type=4 dispatch with :: naming at `tracer.py:326,341-363`; `SolidCylinder('c',[0,0,0],[0,0,1],5,10).get_faces()` returns 3 faces |
| 8 | User can create a SolidPrism with polygon cap intersection and Fresnel/TIR | VERIFIED | `SolidPrism` dataclass in `core/solid_body.py:299`; `_intersect_prism_cap` at `tracer.py:1541`; type=5 dispatch; `SolidPrism('p',[0,0,0],[0,0,1],3,5,10).get_faces()` returns 5 faces |
| 9 | Cylinder and prism render in the 3D viewport | VERIFIED | `_draw_solid_cylinder` (32-segment smooth mesh) at `viewport_3d.py:199`; `_draw_solid_prism` (n-sided faceted mesh) at `viewport_3d.py:262`; `refresh()` iterates `solid_cylinders` and `solid_prisms` at `viewport_3d.py:144-165` |
| 10 | Project save/load round-trips all Phase 4 additions | VERIFIED | `bsdf_profiles` serialized at `project_io.py:217,342,358`; `solid_cylinders`/`solid_prisms` serialized via `_solid_cylinder_to_dict`/`_solid_prism_to_dict`; SphereDetector `mode` serialized with `.get("mode", "near_field")` backward compat |
| 11 | All existing tests continue to pass (backward compatibility) | VERIFIED | `pytest backlight_sim/tests/` → 101 passed, 0 failed; includes 11 BSDF tests + 10 far-field tests + 12 cylinder/prism tests |

**Score:** 11/11 truths verified

---

## Required Artifacts

### Plan 01: BSDF Engine (BRDF-01)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/io/bsdf_io.py` | BSDF CSV import and validation | VERIFIED | 148 lines; exports `load_bsdf_csv`, `validate_bsdf`, `precompute_bsdf_cdfs` |
| `backlight_sim/sim/sampling.py` | 2D CDF BSDF sampling | VERIFIED | `sample_bsdf` at line 228, `precompute_bsdf_cdfs` at line 148 |
| `backlight_sim/sim/tracer.py` | BSDF dispatch | VERIFIED | `bsdf_cdf_cache` built at tracer init (lines 426-428); dispatch in both single-thread (985-1032) and MP (1390-1424) paths |
| `backlight_sim/core/materials.py` | `bsdf_profile_name` field | VERIFIED | `bsdf_profile_name: str = ""` on both `OpticalProperties` (line 36) and `Material` (line 67) |
| `backlight_sim/core/project_model.py` | `bsdf_profiles` dict | VERIFIED | `bsdf_profiles: dict[str, dict] = field(default_factory=dict)` at line 50 |

### Plan 02: Far-Field Detector (DET-01)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/core/detectors.py` | `SphereDetector.mode`, `SphereDetectorResult.candela_grid` | VERIFIED | `mode: str = "near_field"` at line 73; `candela_grid: np.ndarray | None = None` at line 99 |
| `backlight_sim/sim/tracer.py` | `_accumulate_sphere_farfield` | VERIFIED | Defined at line 1665; dispatched at line 649 |
| `backlight_sim/io/ies_parser.py` | `export_ies` function | VERIFIED | Defined at line 161; `export_farfield_csv` at 220; `compute_farfield_kpis` at 254 |

### Plan 03: Cylinder and Prism (GEOM-02, GEOM-03)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/core/solid_body.py` | `SolidCylinder`, `SolidPrism` | VERIFIED | `SolidCylinder` at line 220, `SolidPrism` at line 299; also `CylinderCap`, `CylinderSide`, `PrismCap` face types |
| `backlight_sim/sim/tracer.py` | `_intersect_rays_cylinder` and prism dispatch | VERIFIED | `_intersect_rays_cylinder_side` at 1484, `_intersect_rays_disc` at 1518, `_intersect_prism_cap` at 1541; type=4/5 dispatch in bounce loop |
| `backlight_sim/gui/viewport_3d.py` | `_draw_solid_cylinder` | VERIFIED | `_draw_solid_cylinder` at line 199, `_draw_solid_prism` at line 262 |

### Plan 04: GUI Integration (BRDF-01, DET-01, GEOM-02, GEOM-03)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/gui/bsdf_panel.py` | BSDF management panel (min 150 lines) | VERIFIED | 282 lines; imports `load_bsdf_csv`, `validate_bsdf`; pyqtgraph ImageItem heatmap; 1D line plot detail |
| `backlight_sim/gui/far_field_panel.py` | Far-field polar plot panel (min 200 lines) | VERIFIED | 250 lines; imports `export_ies`, `export_farfield_csv`; 8 C-plane QCheckBox toggles; KPI sidebar |
| `backlight_sim/gui/viewport_3d.py` | `_draw_farfield_lobe` | VERIFIED | Defined at line 323; reads `result.candela_grid` at line 330; cool-to-warm colormap |
| `backlight_sim/gui/properties_panel.py` | `SolidCylinderForm`, `SolidPrismForm`, BSDF dropdown | VERIFIED | `SolidCylinderForm` at line 1753, `SolidPrismForm` at line 1841; `bsdf_profile_name` read/written at lines 928-976 |
| `backlight_sim/gui/object_tree.py` | Cylinder and prism nodes | VERIFIED | Iterates `solid_cylinders` at line 71, `solid_prisms` at line 77 |
| `backlight_sim/gui/main_window.py` | `BSDFPanel` wiring | VERIFIED | `BSDFPanel` imported at line 28, instantiated at 128, added as tab at 138, `set_project` called on every project change; `_draw_farfield_lobe` called at line 886 post-simulation |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `tracer.py` | `sim/sampling.py` | `sample_bsdf()` called in bounce loop | VERIFIED | `sample_bsdf` imported at line 25; called at lines 1019, 1031, 1417, 1424 |
| `tracer.py` | `project.bsdf_profiles` | `bsdf_profile_name` lookup on OpticalProperties | VERIFIED | `getattr(mat, "bsdf_profile_name", "")` at line 985; `.get(bsdf_name, {})` pattern used — Note: PLAN specified `bsdf_profiles[` bracket syntax but `.get()` is functionally equivalent and safer |
| `project_io.py` | `core/project_model.py` | serialize/deserialize `bsdf_profiles` | VERIFIED | `project.bsdf_profiles` serialized at line 217; deserialized at lines 342,358 |
| `tracer.py` | `core/detectors.py` | `sd.mode == "far_field"` routes accumulation | VERIFIED | Exact string match at lines 649 and 920 |
| `io/ies_parser.py` | `SphereDetectorResult` | `export_ies` reads `candela_grid` | VERIFIED | `far_field_panel.py` calls `export_ies` with `candela_grid` from result at line 224 |
| `tracer.py` | `core/solid_body.py` | `solid_cylinders`/`solid_prisms` iterated in bounce loop | VERIFIED | `getattr(self.project, "solid_cylinders", [])` at line 341; `solid_prisms` at line 357 |
| `tracer.py` | Fresnel/TIR physics | `::` naming convention on cylinder/prism face names | VERIFIED | `face.name.split("::", 1)[1]` at lines 326, 347, 363, 1130; applies same Fresnel dispatch path as SolidBox |
| `viewport_3d.py` | `core/solid_body.py` | viewport iterates `solid_cylinders`/`solid_prisms` | VERIFIED | `getattr(project, "solid_cylinders", [])` at line 144; `solid_prisms` at line 156 |
| `bsdf_panel.py` | `io/bsdf_io.py` | Import CSV button calls `load_bsdf_csv` | VERIFIED | `from backlight_sim.io.bsdf_io import load_bsdf_csv, validate_bsdf` at line 21; called at line 214 |
| `far_field_panel.py` | `io/ies_parser.py` | export buttons call `export_ies`/`export_farfield_csv` | VERIFIED | Both imported at lines 24-25; called in `_do_export_ies` (line 224) and `_do_export_csv` (line 245) |
| `viewport_3d.py` | `SphereDetectorResult.candela_grid` | `_draw_farfield_lobe` reads `candela_grid` | VERIFIED | `result.candela_grid is None` guard at line 330; reads `candela_grid` for mesh construction |
| `properties_panel.py` | `core/solid_body.py` | `SolidCylinderForm`/`SolidPrismForm` read/write dataclass fields | VERIFIED | `SolidCylinder` imported at line 36; `SolidCylinderForm.load(cyl, ...)` at line 1794 |
| `main_window.py` | all GUI panels | Creates/wires `BSDFPanel`, `FarFieldPanel`, lobe refresh | VERIFIED | Both imported (lines 28-29), instantiated (128-130), tabbed (133-138), post-simulation hook at line 879-886 |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| BRDF-01 | 04-01, 04-04 | User can import tabulated BRDF data and assign to surfaces | SATISFIED | `load_bsdf_csv` + `bsdf_profile_name` field + tracer dispatch + `BSDFPanel` GUI |
| DET-01 | 04-02, 04-04 | User can add far-field angular detector, export as IES | SATISFIED | `SphereDetector.mode="far_field"` + `_accumulate_sphere_farfield` + `export_ies` + `FarFieldPanel` GUI |
| GEOM-02 | 04-03, 04-04 | User can create cylinder solid body primitives | SATISFIED | `SolidCylinder` dataclass + analytic quadratic intersection + type=4 Fresnel dispatch + `_draw_solid_cylinder` + property form |
| GEOM-03 | 04-03, 04-04 | User can create prism solid body primitives | SATISFIED | `SolidPrism` dataclass + polygon cap intersection + type=5 Fresnel dispatch + `_draw_solid_prism` + property form |

All four Phase 4 requirements are satisfied with evidence in the codebase. No orphaned or unmapped requirements found.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `gui/bsdf_panel.py` | 194 | `pass` in `except Exception:` | Info | Exception silently swallowed during theta_in click-to-select; benign UI guard, not a stub |
| `sim/tracer.py` | 874 | `pass` after `# end bounce loop` | Info | Semantic comment marker, not a stub — bounce loop body is complete above it |

No blocker anti-patterns found. Both `pass` statements are legitimate code patterns.

---

## Human Verification Required

The engine layer (tracer, data model, I/O) is fully verified by automated tests (101 passing). The GUI layer renders in Qt/OpenGL and requires a running application for visual confirmation.

### 1. BSDF Panel — Import and Heatmap

**Test:** Run `python app.py`, click the "BSDF" tab in the center panel. Import a test BSDF CSV file (4-column long-format: theta_in, theta_out, refl_intensity, trans_intensity). Switch between Reflection and Transmission tabs. Click on a row in the heatmap.
**Expected:** Profile appears in the list. An inferno-colormap 2D heatmap renders (theta_in on Y-axis, theta_out on X-axis). Clicking a heatmap row updates the 1D line plot below it with the intensity values for that theta_in slice.
**Why human:** Pyqtgraph `ImageItem` rendering and mouse-click-to-row-select event propagation cannot be verified programmatically.

### 2. Far-Field Panel — Polar Plot and KPIs

**Test:** Add a `SphereDetector`, open its properties and set mode to "Far-field". Run a quick simulation (1k rays). Open the "Far-field" tab.
**Expected:** 8 C-plane checkboxes (C0, C45, C90, C135, C180, C225, C270, C315) appear. Checking each toggles a colored polar curve. The KPI sidebar shows non-zero peak cd, total lm, beam angle, field angle, and asymmetry values.
**Why human:** Qt checkbox toggles, pyqtgraph polar plot rendering, and KPI sidebar updates require a running Qt application.

### 3. 3D Intensity Lobe in Viewport

**Test:** After running a far-field simulation (from test #2 above), switch to the 3D viewport tab.
**Expected:** A color-mapped spherical mesh appears centered on the sphere detector location. The mesh radius varies by direction (proportional to candela), with blue tones for low-candela directions and red/warm tones for the peak direction.
**Why human:** OpenGL `GLMeshItem` rendering requires a display and running Qt application.

### 4. Cylinder and Prism in Object Tree and Viewport

**Test:** Use the scene menu (or right-click) to add a Cylinder and a Prism (n_sides=3). Check the object tree under "Solid Bodies". Select each body and check the properties panel. Observe the 3D viewport.
**Expected:** Cylinder node expands to show "top_cap", "bottom_cap", "side" children. Prism node shows "cap_top", "cap_bottom", "side_0", "side_1", "side_2". Properties panel shows center/axis/radius/length/material fields (cylinder) and center/axis/n_sides/radius/length/material (prism). Both are visible as meshes in the 3D viewport.
**Why human:** Qt tree widget population and OpenGL mesh rendering require a running application.

### 5. BSDF Assignment Greys Out Manual Fields

**Test:** Select a surface, open its OpticalProperties form in the properties panel. The BSDF profile dropdown should be visible. Select a loaded BSDF profile from the dropdown.
**Expected:** The manual reflectance, transmittance, absorption, is_diffuse, and haze fields become disabled (greyed out). Selecting "(None)" re-enables them.
**Why human:** Widget `setEnabled` state change requires a running Qt application to visually confirm.

---

## Summary

Phase 4 engine layer is complete and verified:
- BSDF CSV import, 2D CDF sampling, and tracer dispatch all present, substantive, and wired (101 tests pass including 33 new Phase 4 tests)
- Far-field SphereDetector mode, direction-based accumulation, solid-angle candela normalization, and IES export all wired end-to-end
- SolidCylinder (analytic quadratic) and SolidPrism (polygon cap) with Fresnel/TIR dispatch, viewport mesh rendering, and project I/O round-trip all verified
- GUI panels (`bsdf_panel.py`, `far_field_panel.py`) are substantive (282 and 250 lines), import correct engine functions, and are wired into `main_window.py`

The 5 human verification items are standard GUI rendering/interaction checks that cannot be automated without a display. All underlying data flows are verified correct by the automated test suite.

---

_Verified: 2026-03-14T20:26:02Z_
_Verifier: Claude (gsd-verifier)_
