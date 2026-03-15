---
phase: 03-performance-acceleration
plan: 02
subsystem: simulation
tags: [bvh, spatial-acceleration, adaptive-sampling, convergence, monte-carlo, pyqtgraph]

requires:
  - phase: 03-01
    provides: JIT-compiled plane/sphere/accumulate kernels in accel.py, warmup_jit_kernels

provides:
  - BVH build (build_bvh_flat) + traversal (traverse_bvh_batch) in sim/accel.py
  - BVH activation at 50+ plane surfaces in tracer bounce loop
  - compute_surface_aabbs helper for AABB computation
  - Per-source adaptive sampling batch loop with CV% convergence check in tracer
  - convergence_callback parameter on RayTracer.run()
  - SimulationSettings.adaptive_sampling, convergence_cv_target, check_interval fields
  - SimulationThread.convergence Signal(int, int, float) in main_window
  - Live convergence PlotWidget (CV% per source) as dockable widget in MainWindow
  - SimSettingsForm adaptive sampling checkbox, CV target spinbox, check interval spinbox
  - Quality presets updated with convergence targets: Quick=5%, Standard=2%, High=1%
  - Backward-compatible project I/O for adaptive fields

affects: [04-advanced-materials, 05-ui-revamp]

tech-stack:
  added: []
  patterns:
    - "BVH flat array: node_bounds(max_nodes,6) + node_meta(max_nodes,3) for iterative traversal"
    - "Adaptive batch loop: emit check_interval rays, compute batch CV%, break on convergence"
    - "convergence_callback(src_idx, n_rays, cv_pct) threading protocol via Qt Signal"

key-files:
  created: []
  modified:
    - backlight_sim/sim/accel.py
    - backlight_sim/sim/tracer.py
    - backlight_sim/core/project_model.py
    - backlight_sim/gui/main_window.py
    - backlight_sim/gui/properties_panel.py
    - backlight_sim/io/project_io.py
    - backlight_sim/tests/test_tracer.py

key-decisions:
  - "BVH activation threshold = 50 total plane surfaces (surfaces + solid faces)"
  - "BVH not JIT-compiled at build time (build_bvh_flat is pure NumPy); only traverse_bvh_batch is @njit"
  - "Adaptive sampling disabled in MP mode with warning — cross-process CV coordination too complex"
  - "Convergence metric: 95% CI / mean (cv_pct = 1.96 * std / sqrt(n_batches) / mean * 100)"
  - "Cylinder/prism face intersections belong inside the bounce loop body, not outside it"

requirements-completed: [PERF-02, PERF-03]

duration: 20min
completed: 2026-03-14
---

# Phase 3 Plan 02: BVH Spatial Acceleration + Adaptive Sampling Summary

**BVH median-split traversal for 50+ surface scenes plus per-source adaptive ray batch stopping with live CV% convergence plot in Qt dock**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-14T19:10:00Z
- **Completed:** 2026-03-14T19:33:30Z
- **Tasks:** 2 (Task 1: BVH, Task 2: Adaptive sampling)
- **Files modified:** 7

## Accomplishments

- Fixed a critical indentation bug in the tracer bounce loop: cylinder/prism intersection testing and detector intersection/processing were outside the bounce loop, causing zero detector hits in all scenes without solid bodies or prisms
- BVH build (median-split, iterative stack) + JIT traversal correctly activates for 50+ plane surfaces and produces identical hits to brute-force
- Adaptive sampling batch loop emits convergence_callback(src_idx, n_rays, cv_pct) per batch and stops early when CV% falls below target; disabled in MP mode with warning
- Live convergence PlotWidget shows real-time CV% curves per source with target dashed line in Qt dock panel
- All 101 tests pass including 10 new BVH/adaptive tests

## Task Commits

1. **Task 1 + Task 2 combined fix** - `95e2c49` (fix: bounce-loop indentation + adaptive callback guard)

**Note:** Task 1 (BVH) and Task 2 (adaptive sampling, GUI, IO) were already partially implemented in prior sessions. The critical remaining work was fixing the bounce-loop indentation bug that prevented detectors from accumulating hits, and fixing the convergence_callback being called when adaptive=False.

## Files Created/Modified

- `backlight_sim/sim/tracer.py` - Fixed bounce-loop: cylinder/prism intersections and all hit processing now correctly inside `for _bounce` loop body; adaptive batch loop + convergence_callback fix
- `backlight_sim/sim/accel.py` - BVH build/traverse functions (compute_surface_aabbs, build_bvh_flat, intersect_aabb_jit, traverse_bvh_jit, traverse_bvh_batch) + warmup integration
- `backlight_sim/core/project_model.py` - adaptive_sampling, convergence_cv_target, check_interval fields in SimulationSettings
- `backlight_sim/gui/main_window.py` - convergence Signal, live PlotWidget dock, _on_convergence_update handler
- `backlight_sim/gui/properties_panel.py` - adaptive checkbox, CV target spinbox, check_interval spinbox; quality presets include cv targets
- `backlight_sim/io/project_io.py` - serialize/deserialize adaptive fields with .get() backward compatibility
- `backlight_sim/tests/test_tracer.py` - BVH correctness tests, adaptive sampling tests, MP guard test, serialization tests

## Decisions Made

- BVH threshold = 50 plane surfaces: covers multi-LED arrays with diffuser stacks while avoiding BVH overhead for simple scenes
- traverse_bvh_batch is @njit but build_bvh_flat is pure NumPy (runs once at start, O(N log N) acceptable)
- Adaptive sampling disabled in MP mode: cross-process convergence coordination would require shared memory / IPC, not worth the complexity
- Convergence metric: 1.96*std/sqrt(n_batches)/mean — 95% CI relative to mean batch flux
- Cylinder and prism intersection loops must be inside the bounce loop, same as the BVH/brute-force surface intersection code

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed critical indentation: detector/surface hit processing outside bounce loop**
- **Found during:** Task 1 verification (test_basic_simulation_produces_nonzero_heatmap failed)
- **Issue:** Cylinder/prism intersection loops and all downstream hit processing (detector accumulation, SolidBox Fresnel, surface bounce) were at the `while` loop level (outside `for _bounce`), so detectors were only tested once after all bounces completed with stale data
- **Fix:** Moved cylinder/prism intersection loops from 16-space to 20-space indentation (inside bounce loop body); also restored detector and hit-processing code to correct 20-space level
- **Files modified:** backlight_sim/sim/tracer.py
- **Verification:** All 101 tests pass; basic box, slab, cylinder, prism tests all produce non-zero detector flux
- **Committed in:** 95e2c49

**2. [Rule 1 - Bug] Fixed convergence_callback called when adaptive_sampling=False**
- **Found during:** Task 2 verification (test_adaptive_sampling_disabled_traces_full failed)
- **Issue:** The `else` branch of the adaptive convergence check ran even when `_adaptive=False`, calling convergence_callback with cv_pct=100.0 after each batch
- **Fix:** Wrapped both `if len(batch_fluxes) >= 2` and the `else` branch inside `if _adaptive:` guard
- **Files modified:** backlight_sim/sim/tracer.py
- **Verification:** test_adaptive_sampling_disabled_traces_full passes; no callbacks issued when adaptive=False
- **Committed in:** 95e2c49

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs)
**Impact on plan:** Both fixes were necessary for correctness — the first was a complete simulation failure for all scenes, the second was incorrect callback behavior.

## Issues Encountered

The indentation bug was subtle: the Python code appeared visually structured but the bounce loop body (at 20 spaces) had cylinder/prism intersection testing at 16 spaces (outside loop), which Python accepts syntactically. The bug was introduced when cylinder/prism support was added in a prior session without carefully maintaining the 20-space indentation required to stay inside the `for _bounce` loop.

## Next Phase Readiness

- BVH + adaptive sampling complete, all 101 tests pass
- Phase 3 performance acceleration is complete
- Phase 4 (Advanced Materials) and Phase 5 (UI Revamp) can proceed independently
- No blockers

---
*Phase: 03-performance-acceleration*
*Completed: 2026-03-14*
