---
phase: 01-refractive-physics-and-lgp
plan: 02
subsystem: io-and-gui
tags: [lgp, serialization, geometry-builder, presets, kpi-dashboard]
dependency_graph:
  requires: [01-01]
  provides: [lgp-io, lgp-builder, lgp-preset, lgp-kpis]
  affects: [backlight_sim/io/project_io.py, backlight_sim/io/geometry_builder.py, backlight_sim/io/presets.py, backlight_sim/gui/heatmap_panel.py]
tech_stack:
  added: []
  patterns: [SolidBox serialization roundtrip, builder pattern for scene construction, conditional KPI display]
key_files:
  created: []
  modified:
    - backlight_sim/io/project_io.py
    - backlight_sim/io/geometry_builder.py
    - backlight_sim/io/presets.py
    - backlight_sim/gui/heatmap_panel.py
decisions:
  - "bottom_reflector surface uses optical_properties_name override rather than a new Material, keeping the lgp_bottom_reflector logic in OpticalProperties"
  - "LGP KPI rows hidden (not removed) from Energy Balance group box when no solid bodies are present, to avoid layout reflow"
  - "N/A displayed instead of 0% when coupling flux denominator is zero (no coupling stats yet)"
metrics:
  duration_min: 3
  tasks_completed: 2
  files_modified: 4
  completed_date: "2026-03-14"
---

# Phase 01 Plan 02: LGP I/O, Scene Builder, and KPI Dashboard Summary

**One-liner:** SolidBox JSON roundtrip, build_lgp_scene() edge-lit generator, Edge-Lit LGP preset, and coupling/extraction/overall efficiency KPIs in heatmap dashboard.

## What Was Built

### Task 1: SolidBox serialization + LGP scene builder + preset

**`backlight_sim/io/project_io.py`**
- Added `SolidBox` import
- `_solid_box_to_dict(b)` — serializes all SolidBox fields (name, center, dimensions, material_name, face_optics, coupling_edges) to a plain dict
- `_dict_to_solid_box(d)` — deserializes with `.get()` defaults for backward compatibility
- `project_to_dict()` now includes `"solid_bodies"` key
- `load_project()` reads `data.get("solid_bodies", [])` and passes to `Project(solid_bodies=...)`

**`backlight_sim/io/geometry_builder.py`**
- Added imports: Material, OpticalProperties, PointSource, DetectorSurface, SolidBox
- `build_lgp_scene(project, width, height, thickness, lgp_center_z, coupling_edges, led_count, led_flux, led_distribution, detector_gap, reflector_gap, material_name, refractive_index)`:
  - Creates PMMA material (refractive_index=1.49) if not present
  - Creates lgp_bottom_reflector OpticalProperties (95% reflectance, diffuse) if not present
  - Creates SolidBox with face_optics={"bottom": "lgp_bottom_reflector"}
  - Places led_count LEDs per coupling edge, evenly spaced: left/right along Y, front/back along X
  - Adds DetectorSurface above top face (detector_gap mm gap)
  - Adds bottom_reflector Rectangle below bottom face with optical_properties_name override
  - Returns the SolidBox

**`backlight_sim/io/presets.py`**
- Added `preset_edge_lit_lgp()`: 80x50x3mm, 6 left-edge LEDs, 200 bounces
- Added `"Edge-Lit LGP (80x50x3 mm)"` to PRESETS dict

### Task 2: LGP KPIs in heatmap dashboard

**`backlight_sim/gui/heatmap_panel.py`**
- Added 3 new label pairs to Energy Balance group box: Edge Coupling, Extraction Eff, Overall LGP Eff
- All 6 LGP widgets (3 key labels + 3 value labels) hidden by default via `w.hide()`
- `_show_result()` computes and shows LGP metrics when `solid_body_stats` is non-empty and `project.solid_bodies` exists:
  - **Edge Coupling Eff.** = sum(entering_flux at coupling edges) / total_emitted_flux
  - **Extraction Eff.** = detector_flux / total_coupling_flux
  - **Overall LGP Eff.** = coupling_eff × extraction_eff
- Division-by-zero guarded: displays "N/A" when denominator is zero
- `clear()` hides LGP widgets on result reset

## Verification Results

```
1. Save/load roundtrip: PASS
2. LGP preset runnable: PASS (detector flux=39.70, coupling_eff~95.7%)
3. Multi-edge (4 edges): PASS — 24 LEDs created
4. KPI data verified: left face entering flux > 0
5. Backward compat: PASS — old JSON with no solid_bodies field loads cleanly
All 39 tests pass (0 regressions)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added bottom_reflector Material fallback**
- **Found during:** Task 1 — Rectangle needs a material_name, but the plan specified using `lgp_bottom_reflector` (an OpticalProperties) as the material_name
- **Fix:** Assigned `material_name=material_name` (pmma) to the bottom_reflector Rectangle, and set `optical_properties_name = reflector_op_name` to apply the 95% reflectance optical properties override
- **Files modified:** backlight_sim/io/geometry_builder.py

None — plan executed with one minor fix for the material/optical-properties separation.

## Commits

- `480b40a` — feat(01-02): SolidBox serialization, build_lgp_scene(), Edge-Lit LGP preset
- `329c337` — feat(01-02): add edge coupling / extraction / overall LGP KPIs to heatmap dashboard

## Self-Check: PASSED
