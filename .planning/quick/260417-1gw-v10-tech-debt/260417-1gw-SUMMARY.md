---
phase: quick-260417-1gw
plan: 01
status: complete
requirements-completed:
  - BatchForm property edits undoable via QUndoStack (Ctrl+Z reverts batch flux/dist/position changes)
  - Spectral simulation runs in MP mode without single-thread fallback
  - Spectral grids from multiple sources merged correctly in MP mode
  - Live heatmap partial previews emitted after each MP source completes
  - BVH broad-phase now covers cylinder/prism AABBs; narrow-phase intersectors unchanged
commits:
  - 1ff8ca7
  - 4eaf878
  - 3cc1193
  - 65fdf7c
  - 60509dc
tests-added: 6
tests-total: 124
---

# Quick Task 260417-1gw Summary

**Task:** Fix v1.0 tech debts — BatchForm undo, Spectral+MP guard, BVH cylinder/prism, live heatmap in MP  
**Date:** 2026-04-17  
**Status:** Complete

## What Was Done

### Task 1 — BatchForm undo wiring (commit 1ff8ca7)

`properties_panel.py`:
- Added `self._batchform` to `PropertiesPanel.set_undo_stack` forms list
- `BatchForm._apply_sources` and `_apply_surfaces` now call `_push_or_apply_changes` per object, routing through `SetPropertyCommand` when the undo stack is wired
- Fallback to direct mutation preserved when undo stack is absent (safe for test/headless contexts)

### Task 2 — Spectral + MP guard lifted (commits 4eaf878, 3cc1193)

`tracer.py`:
- Removed the `has_spectral and settings.use_multiprocessing` guard that forced single-thread
- `_run_multiprocess` accepts `has_spectral`, `n_spec_bins`, and `partial_result_callback`
- `_trace_single_source` (MP worker) now samples wavelengths via `sample_wavelengths()` and accumulates `grid_spectral` per detector
- `_run_multiprocess` merges `spectral_grids` from each worker return dict
- `partial_result_callback` called after each source future merges — live heatmap updates during MP runs

### Task 3 — BVH cylinder/prism broad-phase (commits 65fdf7c, 60509dc)

`tracer.py`:
- Added `_aabb_ray_candidates()` helper: slab-test AABB pre-filter for a batch of rays
- CylinderCap, CylinderSide, and PrismFace AABBs computed conservatively and added to BVH index
- Cylinder/prism brute-force loops now use AABB candidate set when BVH is active (skipping clear misses)
- Narrow-phase intersectors (disc, cylinder side, polygon) unchanged
- `_BVH_THRESHOLD` count now includes cyl+prism face contributions

## Test Results

| Before | After |
|--------|-------|
| 118 passing | 124 passing (+6 new) |

New tests: `test_spectral_mp_runs_without_fallback`, `test_spectral_mp_produces_nonzero_spectral_grid`, `test_spectral_mp_grid_spectral_shape`, `test_bvh_cylinder_broad_phase`, `test_bvh_prism_broad_phase`, `test_bvh_cylinder_prism_no_regression`

## Tech Debt Resolved

All 4 items from v1.0-MILESTONE-AUDIT.md are now closed:
- ✅ Property edit undo wired through SetPropertyCommand (BatchForm)
- ✅ Spectral+MP guard lifted
- ✅ BVH excludes cylinder/prism — fixed (broad-phase now covers them)
- ✅ Live heatmap preview in MP mode enabled via partial_result_callback
