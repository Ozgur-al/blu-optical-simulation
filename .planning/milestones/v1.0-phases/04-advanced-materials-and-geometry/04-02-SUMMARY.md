---
phase: 04-advanced-materials-and-geometry
plan: 02
subsystem: sim/io
tags: [far-field, IES, photometry, sphere-detector, candela]
dependency_graph:
  requires: [04-01]
  provides: [DET-01]
  affects: [backlight_sim/core/detectors.py, backlight_sim/sim/tracer.py, backlight_sim/io/ies_parser.py, backlight_sim/io/project_io.py]
tech_stack:
  added: []
  patterns: [solid-angle-normalization, direction-based-binning, IES-LM63-2002-format]
key_files:
  created: []
  modified:
    - backlight_sim/core/detectors.py
    - backlight_sim/sim/tracer.py
    - backlight_sim/io/ies_parser.py
    - backlight_sim/io/project_io.py
    - backlight_sim/tests/test_tracer.py
decisions:
  - "Far-field accumulation negates ray direction (outgoing from luminaire = -ray_dir)"
  - "Beam/field angle uses 2*half_angle convention for standard cone angle measurement"
  - "compute_farfield_candela floors sin(theta) at 1e-6 to prevent division-by-zero at poles"
  - "mode field serialized with .get('mode', 'near_field') for backward compatibility"
metrics:
  duration: 5 min
  completed: "2026-03-14"
  tasks_completed: 2
  files_modified: 5
---

# Phase 4 Plan 02: Far-Field Angular Detector Summary

**One-liner:** Far-field sphere detector with direction-based accumulation, solid-angle candela normalization, and IESNA LM-63-2002 IES export.

## What Was Built

### Task 1: Far-field mode on SphereDetector (TDD)

**SphereDetector** (`core/detectors.py`):
- Added `mode: str = "near_field"` field. Valid values: `"near_field"` (position-based, existing behavior) and `"far_field"` (direction-based binning).

**SphereDetectorResult** (`core/detectors.py`):
- Added `candela_grid: np.ndarray | None = None` field. Populated post-simulation for far_field detectors.

**`_accumulate_sphere_farfield()`** (`sim/tracer.py`):
- Bins by ray direction at intersection, negated to get outgoing direction from luminaire region.
- Same theta/phi binning formula as `_accumulate_sphere`.

**`compute_farfield_candela()`** (`sim/tracer.py`):
- `solid_angle_per_bin = (pi/n_theta) * (2*pi/n_phi) * sin(theta_center)`
- `sin(theta_center)` floored at `1e-6` to avoid division-by-zero at poles.
- `candela_grid = grid / solid_angle_per_bin[:, None]`

**Tracer dispatch** (`sim/tracer.py`):
- Bounce loop checks `sd.mode`: routes to `_accumulate_sphere_farfield` or `_accumulate_sphere`.
- After bounce loop: calls `compute_farfield_candela` for all far_field detectors.

**Serialization** (`io/project_io.py`):
- `_sph_det_to_dict`: serializes `mode`.
- `_dict_to_sph_det`: loads with `.get("mode", "near_field")` for backward compatibility.

### Task 2: IES export and far-field KPI helpers

**`export_ies()`** (`io/ies_parser.py`):
- Writes IESNA LM-63-2002 format with standard header blocks.
- Photometric data: vertical angles, horizontal angles, one row per C-plane.
- Round-trip compatible: re-readable by `load_ies()`.

**`export_farfield_csv()`** (`io/ies_parser.py`):
- Long-format CSV: columns `theta_deg, phi_deg, candela`, one row per bin.

**`compute_farfield_kpis()`** (`io/ies_parser.py`):
- `peak_cd`: max candela value.
- `total_lm`: sum of `candela * solid_angle` over all bins.
- `beam_angle`: 2 × half-angle where avg candela >= 50% of peak.
- `field_angle`: 2 × half-angle where avg candela >= 10% of peak.
- `asymmetry`: max candela ratio between opposing C-plane pairs (C0/C180, C90/C270).

## Test Coverage

10 new tests added covering:
- `test_sphere_detector_defaults_to_near_field` — mode default
- `test_sphere_detector_result_candela_grid_default_none` — candela_grid default
- `test_farfield_accumulation_uses_ray_direction` — same direction → same bin
- `test_farfield_candela_computation_solid_angle_normalization` — math correctness
- `test_farfield_candela_no_division_by_zero_at_poles` — no inf/nan
- `test_sphere_detector_mode_backward_compat_serialization` — old JSON compat
- `test_farfield_simulation_end_to_end` — full simulation produces candela_grid
- `test_export_ies_roundtrip` — IES file re-readable by load_ies
- `test_export_farfield_csv_row_count` — correct row count
- `test_farfield_kpis_lambertian_beam_angle` — ~120 deg for Lambertian pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Beam angle formula produced half expected value**
- **Found during:** Task 2, test_farfield_kpis_lambertian_beam_angle
- **Issue:** Initial implementation computed `above[-1] - above[0]` which gave the span of the above-threshold theta range (59° for Lambertian). The convention for beam angle is `2 × half_angle` (full cone angle).
- **Fix:** Changed to `beam_angle = above_50[-1] * 2.0` and `field_angle = above_10[-1] * 2.0`.
- **Files modified:** `backlight_sim/io/ies_parser.py`
- **Commit:** 86cd46d

### Deferred Items

Pre-existing test failures from other plans (04-03 SolidCylinder/SolidPrism, 04-04 BSDF) documented in `deferred-items.md`. Not introduced by this plan.

## Commits

- `6877fb2`: feat(04-02): add far-field mode to SphereDetector with direction-based accumulation
- `86cd46d`: feat(04-02): add export_ies, export_farfield_csv, compute_farfield_kpis to ies_parser

## Self-Check: PASSED

All files verified present. All commits verified in git log.
- FOUND: backlight_sim/core/detectors.py
- FOUND: backlight_sim/sim/tracer.py
- FOUND: backlight_sim/io/ies_parser.py
- FOUND: backlight_sim/io/project_io.py
- FOUND: commit 6877fb2
- FOUND: commit 86cd46d
