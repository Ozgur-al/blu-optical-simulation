---
phase: 02-spectral-engine
verified: 2026-03-14T14:31:24Z
status: human_needed
score: 11/11 must-haves verified (automated)
human_verification:
  - test: "Launch app, load a preset, change source SPD to warm_white, run simulation, then switch heatmap to Spectral Color mode"
    expected: "A color image appears in the heatmap panel — not a gray intensity map. The Color Uniformity KPI section becomes visible with numeric delta-CCx, delta-CCy, delta-u', delta-v', CCT avg and CCT range values."
    why_human: "Requires PySide6 rendering — cannot be verified headlessly. Color correctness and KPI visibility depend on pyqtgraph ImageItem display."
  - test: "In the Spectral Data tab, click Blackbody button, enter CCT 5000, confirm dialog"
    expected: "A new 'blackbody_5000K' entry appears in the SPD selector and the SPD plot shows a smooth Planckian curve peaking in the green-yellow region (~550 nm)."
    why_human: "Requires GUI interaction and visual inspection of the chart."
  - test: "After a spectral simulation, click a single heatmap pixel"
    expected: "A non-modal popup appears with a pyqtgraph plot of wavelength (nm) on the x-axis and flux on the y-axis, titled 'Pixel (col, row) Spectrum'."
    why_human: "Mouse event wiring on ImageItem.mouseClickEvent cannot be exercised in headless mode."
  - test: "After a spectral simulation, check the Spectral Data tab chromaticity diagram"
    expected: "The CIE 1931 horseshoe spectral locus and Planckian locus curves are visible. Yellow scatter points appear inside the horseshoe representing per-pixel chromaticity. The view stays fixed to approximately [0.0, 0.85] x [0.0, 0.92]."
    why_human: "Visual geometry of pyqtgraph PlotWidget; auto-range override bug was fixed but must be confirmed by eye."
  - test: "Export KPI CSV after a spectral simulation, open the file"
    expected: "Rows for delta_ccx, delta_ccy, delta_uprime, delta_vprime, cct_avg_K, cct_range_K, and prefixed center-fraction variants (e.g. center_1_4_delta_ccx) are present."
    why_human: "File open and row inspection is straightforward but requires a running app to produce the simulation result."
  - test: "Export HTML Report after a spectral simulation, open in browser"
    expected: "A 'Color Uniformity' section appears in the report with a table showing delta-CC and delta-u'v' values for Full, Center 1/4, Center 1/6, and Center 1/10 regions."
    why_human: "HTML output depends on a live SimulationResult with grid_spectral populated."
---

# Phase 2: Spectral Engine Verification Report

**Phase Goal:** Engineers can run wavelength-aware simulations and see the detector result as a color image with color uniformity KPIs
**Verified:** 2026-03-14T14:31:24Z
**Status:** human_needed — all automated checks pass; 6 items require GUI/visual confirmation
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Rays carry wavelength sampled from custom project SPDs, not just built-in names | VERIFIED | `sample_wavelengths()` calls `get_spd_from_project(spd_name, spd_profiles)` in tracer; test_custom_spd_profile_used_in_sampling passes |
| 2  | Material reflectance and transmittance vary per-wavelength via np.interp lookup into spectral tables | VERIFIED | `_bounce_surfaces()` uses `np.interp(ray_wl, ...)` when `spectral_material_data` is present; test_spectral_material_reflectance_varies_per_wavelength passes |
| 3  | Spectral grid is accumulated in single-thread path (MP guard forces single-thread for spectral) | VERIFIED | `has_spectral` guard in `run()` warns and routes to `_run_single`; `grid_spectral` allocated and accumulated via `np.add.at`; test_spectral_mp_guard_falls_back_to_single_thread passes |
| 4  | Projects with spd_profiles and spectral_material_data round-trip through JSON save/load | VERIFIED | `project_to_dict()` serializes both fields; `load_project()` reads with `.get(..., {})`; test_spd_profiles_project_io_roundtrip passes; live I/O check confirms match |
| 5  | User can manage SPD profiles and material spectral tables in a dedicated Spectral Data tab | VERIFIED (automated) | `SpectralDataPanel` (725 lines) exists with SPD selector, table editor, blackbody generator, material spectral table; `MainWindow` adds it as 6th tab "Spectral Data" |
| 6  | User can generate a blackbody SPD by entering a CCT value | VERIFIED (automated) | `blackbody_spd()` exists in spectral.py; `_on_blackbody()` in SpectralDataPanel calls it and writes to `project.spd_profiles`; blackbody peak shift verified programmatically |
| 7  | User can toggle the heatmap to show a true-color sRGB image computed from spectral data | VERIFIED (automated) | `_color_mode` QComboBox with "Spectral Color" mode exists; `spectral_grid_to_rgb()` call wired; `_spectral_status` QLabel shown when grid_spectral is None | NEEDS HUMAN visual |
| 8  | User can see CIE 1931 chromaticity diagram with per-pixel scatter points after spectral simulation | VERIFIED (automated) | `_chroma_scatter` ScatterPlotItem; `_draw_static_loci()` draws spectral locus + Planckian locus; `update_chromaticity()` called from `_on_sim_finished()` | NEEDS HUMAN visual |
| 9  | User can click a heatmap pixel to see its spectral power distribution as a line plot | VERIFIED (automated) | `_img.mouseClickEvent = self._on_image_clicked` wired; `_on_image_clicked()` extracts `grid_spectral[row, col, :]` and creates popup PlotWidget | NEEDS HUMAN interaction |
| 10 | KPI dashboard shows delta-CCx, delta-CCy, delta-u'v', and CCT color uniformity metrics | VERIFIED (automated) | `_update_color_uniformity()` in HeatmapPanel calls `compute_color_kpis()`; `_color_uni_labels` dict populates Full + center fractions; `compute_color_kpis()` returns all required keys | NEEDS HUMAN visual |
| 11 | Color KPIs appear in CSV export and HTML report | VERIFIED (automated) | KPI CSV export path appends color rows when `grid_spectral is not None`; `report.py` generates Color Uniformity HTML table when `grid_spectral is not None` | NEEDS HUMAN for live run |

**Score:** 11/11 truths verified (automated evidence); 6 truths additionally require human visual/interactive confirmation

---

## Required Artifacts

### Plan 02-01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/core/project_model.py` | Project.spd_profiles and Project.spectral_material_data dict fields | VERIFIED | Both fields present as `dict[str, dict[str, list[float]]]` with `field(default_factory=dict)` |
| `backlight_sim/sim/spectral.py` | get_spd_from_project(), blackbody_spd(), updated sample_wavelengths with spd_profiles param | VERIFIED | All three functions present and substantive (559 lines total); `sample_wavelengths` accepts `spd_profiles=None` kwarg |
| `backlight_sim/sim/tracer.py` | Wavelength-dependent material lookup in _bounce_surfaces, MP spectral grid merge, spectral+MP guard | VERIFIED | `_bounce_surfaces()` accepts `wavelengths` and `spectral_material_data`; `has_spectral` guard in `run()`; `grid_spectral` accumulated via `np.add.at` |
| `backlight_sim/io/project_io.py` | Serialization of spd_profiles and spectral_material_data | VERIFIED | Both fields serialized in `project_to_dict()` and deserialized with `.get(..., {})` in `load_project()` |
| `backlight_sim/tests/test_tracer.py` | Spectral simulation tests | VERIFIED | 9 spectral tests collected and passing (test_spectral_tracing, test_custom_spd_profile_used_in_sampling, test_blackbody_spd_peak_shifts_with_cct, test_spectral_material_reflectance_varies_per_wavelength, test_spectral_grid_accumulated_for_non_white_spd, test_spd_profiles_project_io_roundtrip, test_get_spd_from_project_custom_overrides_builtin, test_spectral_mp_guard_falls_back_to_single_thread, test_spectral_rgb_conversion) |

### Plan 02-02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/gui/spectral_data_panel.py` | Combined Spectral Data tab, min 200 lines | VERIFIED | 725 lines; SpectralDataPanel with SPD editor, material spectral table editor, blackbody generator, chromaticity diagram, `spectral_data_changed` signal, `set_project()`, `update_chromaticity()` |
| `backlight_sim/sim/spectral.py` | xyz_per_pixel, xy_per_pixel, uv_per_pixel, cct_robertson, compute_color_kpis | VERIFIED | All five functions present and return correct shapes; `compute_color_kpis()` returns full + center_1_4 + center_1_6 + center_1_10 sub-dicts |
| `backlight_sim/gui/heatmap_panel.py` | Color Uniformity KPI section, click-to-inspect per-pixel spectrum popup | VERIFIED | `_color_uni_box` QGroupBox; `_update_color_uniformity()` calls `compute_color_kpis`; `_on_image_clicked` wired to `_img.mouseClickEvent` |
| `backlight_sim/gui/main_window.py` | SpectralDataPanel wired into main window tab bar | VERIFIED | Imported, instantiated as `self._spectral_panel`, added as tab "Spectral Data", `set_project()` called in all 5 project-load paths, `update_chromaticity()` called in `_on_sim_finished()` |
| `backlight_sim/io/report.py` | Color KPIs in HTML report | VERIFIED | `generate_html_report()` calls `compute_color_kpis()` when `grid_spectral is not None`; renders HTML table with `<h3>Color Uniformity</h3>` |

---

## Key Link Verification

### Plan 02-01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `sim/tracer.py` | `sim/spectral.py` | `sample_wavelengths(n, spd, rng, spd_profiles=...)` | WIRED | Import present; `spd_profiles=self.project.spd_profiles or None` passed at call site |
| `sim/tracer.py` | `core/project_model.py` | `project.spectral_material_data` lookup in `_bounce_surfaces` | WIRED | `spectral_material_data=self.project.spectral_material_data or None` passed into `_bounce_surfaces()`; field consumed via `.get(optics_name)` |
| `io/project_io.py` | `core/project_model.py` | serialize/deserialize `spd_profiles` and `spectral_material_data` | WIRED | Both fields read and written symmetrically; round-trip verified by test and live check |

### Plan 02-02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `gui/spectral_data_panel.py` | `core/project_model.py` | reads/writes `project.spd_profiles` and `project.spectral_material_data` | WIRED | Multiple write sites: `_on_blackbody`, `_on_import_spd`, `_on_table_edited`; `set_project()` reads both |
| `gui/heatmap_panel.py` | `sim/spectral.py` | calls `compute_color_kpis()` for delta-CCx/CCy/u'v'/CCT | WIRED | Import inside `_update_color_uniformity()` and CSV export path; returns dict consumed and displayed |
| `gui/main_window.py` | `gui/spectral_data_panel.py` | `addTab SpectralDataPanel`, `spectral_data_changed` signal | WIRED | `SpectralDataPanel` imported; tab added; `spectral_data_changed.connect(self._mark_dirty)` connected; `update_chromaticity(result)` called in `_on_sim_finished()` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SPEC-01 | 02-01 | Each ray carries a sampled wavelength and material interactions are wavelength-dependent | SATISFIED | `wavelengths` array allocated per source when `has_spectral`; per-wavelength R/T via `np.interp` in `_bounce_surfaces`; 9 spectral tests pass |
| SPEC-02 | 02-01 | Detector accumulates flux per wavelength bin into a spectral grid | SATISFIED | `grid_spectral (ny, nx, n_bins)` allocated in `DetectorResult`; `np.add.at(result.grid_spectral[:,:,b], ...)` in `_accumulate()`; `test_spectral_grid_accumulated_for_non_white_spd` passes |
| SPEC-03 | 02-02 | User can view detector result as a CIE XYZ / sRGB color image | SATISFIED (automated) | `spectral_grid_to_rgb()` converts spectral grid to sRGB via CIE XYZ matrix; "Spectral Color" mode wired in HeatmapPanel; NEEDS HUMAN visual confirmation |
| SPEC-04 | 02-01 | Material reflectance and transmittance can be defined as wavelength-dependent tables | SATISFIED | `Project.spectral_material_data` stores per-material wavelength-indexed R/T tables; `_bounce_surfaces` interpolates with `np.interp`; `test_spectral_material_reflectance_varies_per_wavelength` passes |
| SPEC-05 | 02-02 | User can see color uniformity KPIs (delta-CCx, delta-CCy) after spectral simulation | SATISFIED (automated) | `compute_color_kpis()` returns delta_ccx/delta_ccy/delta_uprime/delta_vprime/cct_avg/cct_range for full detector and center fractions; `_update_color_uniformity()` in HeatmapPanel; NEEDS HUMAN visual confirmation |

No orphaned requirements — all 5 SPEC requirements appear in plan frontmatter and are accounted for in code.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backlight_sim/sim/spectral.py` | 346 | `# placeholder sentinel` comment in `_ROBERTSON_TABLE` | Info | Data table comment only — not a code stub. The sentinel row is intentional (boundary condition for Robertson CCT). No impact on functionality. |

No blockers or warnings found. All other files are fully implemented.

---

## Test Results

- **Total tests:** 46 (46 passed, 0 failed)
- **Spectral tests (new):** 9 passed — `test_spectral_tracing`, `test_spectral_rgb_conversion`, `test_custom_spd_profile_used_in_sampling`, `test_blackbody_spd_peak_shifts_with_cct`, `test_spectral_material_reflectance_varies_per_wavelength`, `test_spectral_grid_accumulated_for_non_white_spd`, `test_spd_profiles_project_io_roundtrip`, `test_get_spd_from_project_custom_overrides_builtin`, `test_spectral_mp_guard_falls_back_to_single_thread`
- **Regressions:** 0

---

## Human Verification Required

### 1. Spectral Color Heatmap Mode

**Test:** Launch `python app.py`, load Presets > Simple Box. In Source properties, change SPD from "white" to "warm_white". Run simulation. In the Heatmap tab, open the color mode dropdown and select "Spectral Color".
**Expected:** A colored (non-gray) image replaces the intensity heatmap. The image should show warm-tinted colors consistent with the warm_white phosphor + blue-peak SPD.
**Why human:** Requires PySide6 rendering and visual color judgment — `spectral_grid_to_rgb()` is verified mathematically but the display pipeline (ImageItem RGBA, transpose, flip) must be confirmed visually.

### 2. Blackbody SPD Generator

**Test:** In the Spectral Data tab, click "Blackbody" button, enter CCT = 5000, press OK.
**Expected:** A new "blackbody_5000K" entry appears in the SPD dropdown. The SPD plot shows a smooth bell curve peaking around 550-560 nm (green-yellow region for 5000 K).
**Why human:** GUI dialog interaction and chart rendering cannot be exercised headlessly.

### 3. Click-to-Inspect Per-Pixel Spectrum

**Test:** After a spectral simulation (warm_white or cool_white SPD), click a pixel on the heatmap.
**Expected:** A non-modal popup window opens with a pyqtgraph plot, x-axis labeled in nm (380-780), y-axis showing flux, and title "Pixel (col, row) Spectrum".
**Why human:** `mouseClickEvent` override on `ImageItem` must be confirmed to fire correctly with real Qt event loop.

### 4. CIE 1931 Chromaticity Diagram

**Test:** After a spectral simulation, switch to the Spectral Data tab and observe the chromaticity diagram.
**Expected:** The CIE horseshoe spectral locus is visible as a curve. The Planckian (blackbody) locus appears as a second curve inside the horseshoe. Yellow scatter points appear representing per-pixel chromaticity. The view remains fixed to approximately x:[0, 0.85], y:[0, 0.92] even after the scatter is added.
**Why human:** Visual geometry of pyqtgraph PlotWidget; locus filtering and fixed view range bugs were fixed (56db618) but must be confirmed by eye.

### 5. Color Uniformity KPI Section

**Test:** After a spectral simulation, scroll down in the Heatmap KPI dashboard.
**Expected:** A "Color Uniformity" group box is visible with rows for Full, Center 1/4, Center 1/6, Center 1/10, and columns for delta-CCx, delta-CCy, delta-u', delta-v', CCT avg, CCT range. Values should be non-zero numeric strings.
**Why human:** QGroupBox visibility and QLabel population depends on the Qt layout and live result propagation.

### 6. CSV and HTML Report Color KPIs

**Test:** After a spectral simulation, click Export KPI CSV and Export HTML Report.
**Expected:** KPI CSV contains rows starting with `delta_ccx`, `delta_ccy`, `delta_uprime`, `delta_vprime`, `cct_avg_K`, `cct_range_K`. HTML report contains a "Color Uniformity" section with a formatted table.
**Why human:** Requires a running app with a live spectral SimulationResult to trigger the export code paths that check `grid_spectral is not None`.

---

## Summary

Phase 2 (Spectral Engine) is fully implemented at the code level. All 11 must-have truths are backed by concrete, wired, substantive artifacts. All 46 tests pass with zero regressions. All 5 SPEC requirements (SPEC-01 through SPEC-05) are satisfied by the implementation.

The `human_needed` status reflects that SPEC-03 and SPEC-05 involve GUI rendering, interactive events, and visual outputs that require a running Qt application to confirm. The code paths are correctly wired — the automated evidence strongly indicates everything works. Human verification is a final visual/interactive sanity check, not a suspected failure.

The only deviation from an ideal pure `passed` status is the inherent limitation of headless verification for PySide6 GUI components.

---

_Verified: 2026-03-14T14:31:24Z_
_Verifier: Claude (gsd-verifier)_
