---
phase: 03-performance-acceleration
plan: 01
subsystem: simulation-engine
tags: [numba, jit, acceleration, monte-carlo, performance]
dependency_graph:
  requires: []
  provides: [JIT-intersect-plane, JIT-intersect-sphere, JIT-accumulate-grid, JIT-accumulate-sphere, warmup-jit-kernels]
  affects: [sim/tracer.py, gui/main_window.py]
tech_stack:
  added: [numba>=0.64.0 (optional)]
  patterns: [try-import guard for optional dependency, JIT kernel warmup pattern, drop-in wrapper functions]
key_files:
  created:
    - backlight_sim/sim/accel.py
  modified:
    - backlight_sim/sim/tracer.py
    - backlight_sim/gui/main_window.py
    - backlight_sim/tests/test_tracer.py
    - BluOpticalSim.spec
    - requirements.txt
decisions:
  - "No-op njit fallback handles both @njit and @njit(cache=True) calling conventions via len(args)==1 check"
  - "accumulate_*_jit uses @njit(cache=True) without fastmath to preserve exact scatter-add semantics"
  - "intersect_*_jit uses @njit(cache=True, fastmath=True) for maximum intersection throughput"
  - "Wrapper functions (intersect_plane/intersect_sphere) handle tuple→scalar conversion so JIT kernels receive primitive types only"
  - "warmup_jit_kernels() returns bool — True=compiled OK, False=Numba unavailable or warmup failed"
  - "JIT label uses addWidget (left-aligned) not addPermanentWidget to stay visually distinct from run/cancel buttons"
metrics:
  duration: 3.6 min
  completed: "2026-03-14"
  tasks_completed: 2
  files_modified: 6
  tests_total: 53
  tests_added: 7
---

# Phase 3 Plan 01: Numba JIT Acceleration Summary

**One-liner:** Numba JIT kernels for ray-plane/sphere intersection and np.add.at scatter-add with graceful NumPy fallback, status bar indicator, and PyInstaller bundling.

## What Was Built

### `backlight_sim/sim/accel.py` (new)
JIT kernel module with try-import guard:
- `_NUMBA_AVAILABLE: bool` — True when Numba is installed
- `intersect_plane_jit(origins, directions, normal, center, u_axis, v_axis, half_w, half_h, epsilon)` — `@njit(cache=True, fastmath=True)`, explicit scalar loop, returns (N,) t-values
- `intersect_sphere_jit(origins, directions, center, radius, epsilon)` — same pattern, quadratic formula
- `accumulate_grid_jit(grid, iy, ix, weights)` — `@njit(cache=True)`, replaces `np.add.at` for 2D detector grids
- `accumulate_sphere_jit(grid, i_theta, i_phi, weights)` — same for sphere detector grids
- `warmup_jit_kernels()` — eager LLVM compilation with 4-ray dummy data, returns bool
- `intersect_plane(...)` / `intersect_sphere(...)` — wrapper functions with same signature as original tracer functions

### `backlight_sim/sim/tracer.py` (modified)
- Imports from `accel.py`: `_intersect_plane_accel`, `_intersect_sphere_accel`, `accumulate_grid_jit`, `accumulate_sphere_jit`
- All `_intersect_rays_plane(...)` calls in `_run_single` and `_trace_single_source` bounce loops replaced with `_intersect_plane_accel(...)`
- All `_intersect_rays_sphere(...)` calls replaced with `_intersect_sphere_accel(...)`
- All `np.add.at(result.grid, ...)` calls in `_accumulate()`, `_accumulate_sphere()`, and MP inline path replaced with JIT equivalents
- Original `_intersect_rays_plane` / `_intersect_rays_sphere` preserved as reference implementations

### `backlight_sim/gui/main_window.py` (modified)
- `QLabel` JIT status indicator added to status bar: "JIT: Active" (green) when Numba available, "JIT: Off" (grey) otherwise
- `warmup_jit_kernels()` called in `__init__` after `_refresh_all()`; result logged to log dock

### `BluOpticalSim.spec` (modified)
- Added `numba`, `numba.core`, `numba.typed`, `numba.np`, `numba.np.ufunc`, `llvmlite`, `llvmlite.binding` to `hidden_imports`
- Added comment about `pyinstaller-hooks-contrib >= 2025.1`

### `requirements.txt` (modified)
- Added `numba>=0.64.0` as optional dependency with explanatory comment

## Tests Added (7 new, 53 total)

| Test | What it verifies |
|------|-----------------|
| `test_jit_numba_available_is_bool` | `_NUMBA_AVAILABLE` is a `bool` |
| `test_jit_warmup_runs_without_error` | `warmup_jit_kernels()` returns `bool`, no exception |
| `test_jit_intersect_plane_matches_numpy` | JIT plane vs NumPy within 1e-10 for 100 rays |
| `test_jit_intersect_sphere_matches_numpy` | JIT sphere vs NumPy within 1e-10 for 100 rays |
| `test_jit_accumulate_grid_matches_numpy` | `accumulate_grid_jit` == `np.add.at` (exact) for 500 hits |
| `test_jit_accumulate_sphere_matches_numpy` | `accumulate_sphere_jit` == `np.add.at` (exact) for 300 hits |
| `test_simulation_deterministic_with_jit` | Full simulation deterministic after dispatch change |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backlight_sim/sim/accel.py` exists | FOUND |
| `.planning/phases/03-performance-acceleration/03-01-SUMMARY.md` exists | FOUND |
| commit 922adb0 (Task 1) | FOUND |
| commit 5b93308 (Task 2) | FOUND |
| 53 tests pass | PASSED |
| No `np.add.at` in tracer.py | CONFIRMED |
| `JIT:` label in main_window.py | CONFIRMED |
| `_NUMBA_AVAILABLE` exported from accel.py | CONFIRMED |
| Original `_intersect_rays_plane` preserved | CONFIRMED |
