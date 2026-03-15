---
phase: 03-performance-acceleration
verified: 2026-03-14T20:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run app.py with Numba installed and check status bar"
    expected: "'JIT: Active' label visible in green text in status bar"
    why_human: "Cannot launch GUI in headless verification environment"
  - test: "Run a simulation on a 60-surface scene and observe convergence dock"
    expected: "Convergence dock appears during simulation, showing CV% curves per source dropping over batches, with a red dashed target line"
    why_human: "Live plot behaviour requires running app with interactive session"
---

# Phase 3: Performance Acceleration Verification Report

**Phase Goal:** Numba JIT for inner loops, BVH spatial acceleration, adaptive sampling
**Verified:** 2026-03-14T20:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Ray-surface intersection and accumulation inner loops run as Numba JIT-compiled native code when Numba is installed | VERIFIED | `accel.py` exports `intersect_plane_jit`, `intersect_sphere_jit`, `accumulate_grid_jit`, `accumulate_sphere_jit` all decorated `@_njit(cache=True, ...)`. `tracer.py` imports and dispatches to all four. |
| 2 | Application starts and simulations produce identical results when Numba is not installed (graceful fallback to pure NumPy) | VERIFIED | `accel.py` try-import guard: `_njit` becomes a no-op decorator if `ImportError`. Original `_intersect_rays_plane` / `_intersect_rays_sphere` preserved in `tracer.py` as reference. Test `test_jit_warmup_runs_without_error` passes regardless of Numba state. |
| 3 | Status bar shows "JIT: Active" (green) or "JIT: Off" (grey) | VERIFIED | `main_window.py` line 187: `self._jit_label = QLabel("JIT: Active" if _NUMBA_AVAILABLE else "JIT: Off")` with green/grey stylesheet. Added to `status.addWidget(self._jit_label)`. |
| 4 | First simulation runs at full JIT speed — kernels compiled eagerly at startup | VERIFIED | `main_window.py`: `warmup_jit_kernels()` called in `__init__` after `_refresh_all()`. Result logged to log dock. Warmup function calls all 5 kernel types (plane, sphere, grid accum, sphere accum, BVH traverse) with dummy 4-ray data. |
| 5 | PyInstaller executable bundles Numba and llvmlite | VERIFIED | `BluOpticalSim.spec` lines 50-56: `"numba"`, `"numba.core"`, `"numba.typed"`, `"numba.np"`, `"numba.np.ufunc"`, `"llvmlite"`, `"llvmlite.binding"` in `hidden_imports`. |
| 6 | Scenes with 50+ surfaces automatically use BVH traversal | VERIFIED | `tracer.py` line 46: `_BVH_THRESHOLD = 50`. Lines 384-390: `use_bvh = n_all_planes >= _BVH_THRESHOLD`. BVH path calls `traverse_bvh_batch(...)` in bounce loop (line 531). MP path applies identical logic (lines 1177, 1229). |
| 7 | BVH built fresh at simulation start — scene edits always produce correct results | VERIFIED | `build_bvh_flat(aabbs)` called inside `_run_single()` per-simulation, not cached. `compute_surface_aabbs` recomputes from live surface data each run. |
| 8 | Adaptive sampling is enabled by default and stops ray generation when detector CV% drops below threshold | VERIFIED | `SimulationSettings.adaptive_sampling = True` (default). Batch loop in `tracer.py` lines 459-904: emits `check_interval` rays per batch, computes `cv_pct = 1.96*std/sqrt(n_batches)/mean*100`, breaks when `cv_pct <= settings.convergence_cv_target`. |
| 9 | Users see a live variance plot with CV% per source during simulation | VERIFIED | `main_window.py`: `pg.PlotWidget` in `_conv_dock` (QDockWidget). `_on_convergence_update` appends data to per-source `PlotDataItem`. Dock shows on first data point. Red dashed target line added at simulation start (line 851). |
| 10 | Users can configure convergence threshold in SimulationSettings via quality presets | VERIFIED | `properties_panel.py` `_QUALITY_PRESETS`: Quick=5.0%, Standard=2.0%, High=1.0% CV targets. `SimSettingsForm` has `_adaptive` checkbox, `_cv_target` spinbox, `_check_interval` spinbox. All wired to `_push_to_model()`. |
| 11 | Adaptive sampling is disabled in MP mode with a logged warning | VERIFIED | `tracer.py` lines 185-192: `if _adaptive and settings.use_multiprocessing: warnings.warn(...)` and `_adaptive = False`. Test `test_adaptive_mp_guard` passes. |
| 12 | Projects saved with new adaptive fields load correctly; old projects without them use sensible defaults | VERIFIED | `project_io.py` save: writes `adaptive_sampling`, `convergence_cv_target`, `check_interval`. Load: uses `.get("adaptive_sampling", True)`, `.get("convergence_cv_target", 2.0)`, `.get("check_interval", 1000)`. Test `test_project_serialization_adaptive_fields` passes. |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/sim/accel.py` | JIT kernels + BVH + warmup | VERIFIED | 748 lines. Exports `_NUMBA_AVAILABLE`, `intersect_plane_jit`, `intersect_sphere_jit`, `accumulate_grid_jit`, `accumulate_sphere_jit`, `warmup_jit_kernels`, `intersect_plane`, `intersect_sphere`, `compute_surface_aabbs`, `build_bvh_flat`, `intersect_aabb_jit`, `traverse_bvh_jit`, `traverse_bvh_batch`. |
| `backlight_sim/sim/tracer.py` | Dispatch to JIT kernels + BVH + adaptive loop | VERIFIED | Imports from `accel.py` at line 32. `_BVH_THRESHOLD = 50`. BVH at lines 383-417 (single) and 1175-1208 (MP). Adaptive batch loop at lines 459-904. No remaining `np.add.at` calls — all replaced with `accumulate_grid_jit` / `accumulate_sphere_jit`. |
| `backlight_sim/core/project_model.py` | `SimulationSettings` with adaptive fields | VERIFIED | Lines 24-26: `adaptive_sampling: bool = True`, `convergence_cv_target: float = 2.0`, `check_interval: int = 1000`. |
| `backlight_sim/gui/main_window.py` | JIT label + warmup + convergence signal + PlotWidget dock | VERIFIED | `_jit_label` QLabel, `warmup_jit_kernels()` call, `convergence = Signal(int, int, float)` on `SimulationThread`, `_conv_plot` PlotWidget in `_conv_dock`, `_on_convergence_update` handler. |
| `backlight_sim/gui/properties_panel.py` | Adaptive checkbox + spinboxes + quality presets | VERIFIED | `_adaptive`, `_cv_target`, `_check_interval` widgets. `_QUALITY_PRESETS` with cv values. `_apply_preset` writes cv target. |
| `backlight_sim/io/project_io.py` | Serialize/deserialize adaptive fields with `.get()` fallback | VERIFIED | Save lines 201-203, load lines 330-332. |
| `backlight_sim/tests/test_tracer.py` | JIT, BVH, adaptive regression tests | VERIFIED | 101 tests total (all pass). JIT: 7 tests. BVH: 4 tests. Adaptive: 4 tests. |
| `BluOpticalSim.spec` | Numba + llvmlite hidden imports | VERIFIED | Lines 50-56 contain all required imports. |
| `requirements.txt` | `numba>=0.64.0` | VERIFIED | Line 10: `numba>=0.64.0`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `accel.py` | numba | `try: from numba import njit` with `_NUMBA_AVAILABLE` flag | WIRED | Lines 33-46 confirmed. No-op fallback handles both `@njit` and `@njit(cache=True, ...)`. |
| `tracer.py` | `accel.py` | `from backlight_sim.sim.accel import ...` at line 32; used in bounce loop | WIRED | All 5 imports present. `_intersect_plane_accel` at lines 553, 562, 592, 604, 1251, 1260, 1270. `accumulate_grid_jit` at lines 1297, 1722, 1729, 1739. `accumulate_sphere_jit` at lines 1660, 1687. `traverse_bvh_batch` at lines 531, 1230. |
| `tracer.py` | `project_model.py` | `settings.adaptive_sampling`, `settings.convergence_cv_target` read in `_run_single()` | WIRED | Lines 185, 463, 896 confirmed. |
| `main_window.py` | `accel.py` | `warmup_jit_kernels()` + `_NUMBA_AVAILABLE` import at line 35 | WIRED | Import line 35, warmup call in `__init__`, label uses `_NUMBA_AVAILABLE` at line 187. |
| `main_window.py` | `tracer.py` | `convergence_callback` passed through `SimulationThread.run()` to `tracer.run()` | WIRED | `SimulationThread.run()` calls `self.tracer.run(convergence_callback=self.convergence.emit)` at line 50. `_sim_thread.convergence.connect(self._on_convergence_update)` at line 857. |
| `main_window.py` | pyqtgraph `PlotWidget` | live variance plot updated from convergence signal | WIRED | `pg.PlotWidget()` at line 159. `_on_convergence_update` appends to `PlotDataItem` at line 932. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PERF-01 | 03-01-PLAN.md | Ray-surface intersection and accumulation inner loops are Numba JIT-compiled for 10-50x speedup | SATISFIED | `accel.py` implements `intersect_plane_jit`, `intersect_sphere_jit`, `accumulate_grid_jit`, `accumulate_sphere_jit`. `tracer.py` dispatches to all four. 7 JIT regression tests pass. REQUIREMENTS.md marks PERF-01 Complete Phase 3. |
| PERF-02 | 03-02-PLAN.md | BVH spatial acceleration is used for scenes with 50+ surfaces | SATISFIED | `build_bvh_flat` + `traverse_bvh_batch` in `accel.py`. Tracer activates BVH at `_BVH_THRESHOLD = 50`. BVH tests (`test_bvh_matches_bruteforce`, `test_bvh_simulation_same_result_as_bruteforce`) pass. REQUIREMENTS.md marks PERF-02 Complete Phase 3. |
| PERF-03 | 03-02-PLAN.md | Adaptive sampling stops ray generation per source when detector variance is below threshold | SATISFIED | Adaptive batch loop in `tracer._run_single()`. `SimulationSettings` has `adaptive_sampling=True`, `convergence_cv_target=2.0`, `check_interval=1000`. `test_adaptive_sampling_converges_early` and `test_adaptive_sampling_disabled_traces_full` pass. REQUIREMENTS.md marks PERF-03 Complete Phase 3. |

All three phase requirements are accounted for. No orphaned requirements detected — REQUIREMENTS.md traceability table maps PERF-01/02/03 exclusively to Phase 3.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | No TODO/FIXME/placeholder/stub patterns found in modified files |

Scanned: `accel.py`, `tracer.py` (imports + key sections), `main_window.py` (JIT/convergence sections), `properties_panel.py` (adaptive section), `project_io.py` (adaptive fields). No `return null`, `return {}`, `console.log`, or placeholder comments found.

### Human Verification Required

#### 1. JIT Status Bar Label (Visual)

**Test:** Launch `python app.py` with Numba installed
**Expected:** Status bar shows "JIT: Active" in green bold text
**Why human:** Cannot launch the PySide6 GUI in headless verification; must visually confirm placement and color

#### 2. Live Convergence Plot (Real-Time Behavior)

**Test:** Open app, load Simple Box preset, run simulation with adaptive sampling enabled
**Expected:** Convergence dock appears automatically at bottom of window; CV% curve(s) per source visible and descending; red dashed horizontal line marks the 2.0% target
**Why human:** Real-time plot update during simulation cannot be verified by static code inspection alone

### Gaps Summary

No gaps found. All 12 observable truths are verified by code inspection and passing tests.

The 101-test suite (all passing in 6.73s) provides regression coverage for:
- JIT kernel output parity with NumPy (7 tests)
- BVH correctness vs brute-force for 60-surface scenes (4 tests)
- Adaptive sampling early stopping and full-trace modes (4 tests)
- MP guard and project serialization round-trip (2 tests)
- Full simulation determinism and basic scene correctness (remaining 84 tests)

---

_Verified: 2026-03-14T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
