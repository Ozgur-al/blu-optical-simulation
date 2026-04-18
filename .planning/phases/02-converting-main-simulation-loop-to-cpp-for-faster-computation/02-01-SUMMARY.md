---
phase: 02-converting-main-simulation-loop-to-cpp-for-faster-computation
plan: 01
subsystem: sim/_blu_tracer
tags: [cpp, pybind11, scikit-build-core, scaffolding, wave-1]
dependency_graph:
  requires:
    - MSVC v14.50 / Visual Studio 2026 Insider (installed at C:\Program Files\Microsoft Visual Studio\18\Community\)
    - Python 3.12.10
    - pybind11 3.0.3 (Python package)
    - scikit-build-core 0.12.2 (Python package)
    - CMake 4.2.3 (bundled with VS)
  provides:
    - backlight_sim.sim.blu_tracer (C++ extension) — trace_source entry point with correct dict shape
    - C++ header skeleton: types.hpp (RayBatch + Scene* structs), intersect.hpp, sampling.hpp, material.hpp, bvh.hpp
    - Build infrastructure: pyproject.toml (scikit-build-core), CMakeLists.txt (pybind11_add_module)
    - Test suite stubs: test_cpp_tracer.py (5 active + 3 skipped)
  affects:
    - Enables Wave 2 (02-02-PLAN.md): fills in real intersection/material/bounce physics against stable headers
    - Wave 3 (02-03-PLAN.md) will wire tracer.py to call blu_tracer.trace_source + remove Numba
    - Wave 4 (02-04-PLAN.md) will add PyInstaller .pyd packaging + speedup validation
tech-stack:
  added:
    - pybind11 3.0.3 (C++ <-> Python binding)
    - scikit-build-core 0.12.2 (PEP 517 build backend for C++ extensions)
  patterns:
    - Struct-of-Arrays (SoA) ray batch: RayBatch stores ox/oy/oz/dx/dy/dz as separate std::vector<double>
      (better cache behavior + vectorization opportunity in Wave 2 inner loops)
    - Scene* POD structs with pre-computed half_w/half_h, geom_eps per body (mirror Python dataclasses)
    - pybind11 dict return shape matches _trace_single_source exactly
      (grids/spectral_grids/escaped/sb_stats/sph_grids) so tracer.py can drop-in replace
key-files:
  created:
    - backlight_sim/sim/_blu_tracer/pyproject.toml
    - backlight_sim/sim/_blu_tracer/CMakeLists.txt
    - backlight_sim/sim/_blu_tracer/src/types.hpp
    - backlight_sim/sim/_blu_tracer/src/intersect.hpp
    - backlight_sim/sim/_blu_tracer/src/intersect.cpp
    - backlight_sim/sim/_blu_tracer/src/sampling.hpp
    - backlight_sim/sim/_blu_tracer/src/sampling.cpp
    - backlight_sim/sim/_blu_tracer/src/material.hpp
    - backlight_sim/sim/_blu_tracer/src/material.cpp
    - backlight_sim/sim/_blu_tracer/src/bvh.hpp
    - backlight_sim/sim/_blu_tracer/src/bvh.cpp
    - backlight_sim/sim/_blu_tracer/src/blu_tracer.cpp
    - backlight_sim/tests/test_cpp_tracer.py
  modified: []
decisions:
  - "Wave 1 scope strictly scaffolding: all intersect/sampling/material functions return INF or no-op. Real physics deferred to 02-02-PLAN.md so downstream planners can build against stable header signatures."
  - "pyproject.toml: wheel.install-dir left unset (not '/', not 'backlight_sim/sim'). CMakeLists.txt install(TARGETS blu_tracer DESTINATION backlight_sim/sim) places the .pyd correctly at site-packages/backlight_sim/sim/blu_tracer*.pyd. Setting wheel.install-dir to the same path caused a doubled-path bug (backlight_sim/sim/backlight_sim/sim/blu_tracer.pyd); setting it to '/' hit scikit-build-core's 'experimental absolute paths' assertion. Leaving it unset is the clean fix."
  - "Suppressed C4100 'unused parameter' warnings in all stub implementations via (void)arg casts so /W3 compilation stays warning-free. When Wave 2 fills real bodies these casts disappear naturally."
  - "Test suite uses pytest.mark.skip for C++-06/07/08 with reasons pointing at the enabling plan (02-02 for real bounce, 02-03 for Numba removal, 02-04 for speedup validation) — keeps pytest output clean + makes activation explicit."
  - "Top-level list_to_vec helper ported from research doc but currently unused (will be used in Wave 2 for angular_distributions/theta_deg/intensity arrays). Left in place to avoid code churn in Wave 2 commit."
metrics:
  duration_min: ~10
  completed_date: "2026-04-18"
  tasks_completed: 2
  files_created: 13
  files_modified: 0
  tests_added: 8
  tests_passing: 5
  tests_skipped: 3
  existing_tests_still_passing: 124
  commits:
    - fe74d68  # Task 1: scaffold build + headers
    - 190859c  # Task 2: pybind11 entry point + test stubs
---

# Phase 02 Plan 01: C++ Blu Tracer Build Scaffold Summary

Wave 1 of the C++ engine port: stood up the full pybind11 + scikit-build-core + CMake build pipeline with a working `blu_tracer.pyd` that compiles cleanly under MSVC /O2 /fp:fast /W3, exposes `trace_source(project_dict, source_name, seed)` returning a dict with the exact 5-key shape Python's `_trace_single_source` produces, and ships an 8-test pytest suite (5 active + 3 skipped pending later waves).

## What Was Built

### Build Infrastructure
- **pyproject.toml** — scikit-build-core >= 0.9 + pybind11 >= 3.0 build requirements, CMake Release build type.
- **CMakeLists.txt** — `pybind11_add_module(blu_tracer MODULE ...)` wiring 5 source files + numpy include dir auto-discovery via `python -c "import numpy; print(numpy.get_include())"`. MSVC `/O2 /fp:fast /W3` flags. `install(TARGETS blu_tracer DESTINATION backlight_sim/sim)` places the .pyd under `site-packages/backlight_sim/sim/`.

### C++ Source Skeleton
- **types.hpp** — `RayBatch` (SoA: ox/oy/oz/dx/dy/dz/weights/alive/current_n/n_stack/n_depth), `ScenePlane`, `SceneCylinderCap`, `SceneCylinderSide`, `ScenePrismCap`, `ScenePrismSideFace`, `SceneSphereDetector`, `SceneMaterial`, `AngularProfile`, `SceneSource`, `BVHNode`. Constants: `EPSILON=1e-6`, `INF=numeric_limits<double>::infinity()`, `N_STACK_MAX=8`.
- **intersect.hpp/cpp** — declarations for plane, disc, cylinder_side, sphere, prism_cap, aabb intersections. All bodies currently return `INF` (TODO markers for Plan 02-02).
- **sampling.hpp/cpp** — `build_basis`, `sample_isotropic`, `sample_lambertian`, `sample_angular_distribution`, `sample_lambertian_single`, `reflect_specular` (working — vectorizes `d - 2(d·n)n`), `scatter_haze_single` stubs.
- **material.hpp/cpp** — `fresnel_unpolarized`, `refract_snell`, `apply_material` declarations with absorber-kills-ray stub behavior so `test_energy_conservation` passes trivially.
- **bvh.hpp/cpp** — `build_bvh` (returns empty vector), `traverse_bvh` (returns `{INF, -1}`) stubs to port `accel.py::build_bvh_flat` in Wave 2.

### Pybind11 Entry Point (`blu_tracer.cpp`)
`trace_source(project_dict, source_name, seed) -> dict`:
1. Reads `settings.rays_per_source/max_bounces/energy_threshold`.
2. Finds the enabled source by name, throws `runtime_error` on miss.
3. Deserializes `surfaces`, `detectors` (with `resolution` as (nx, ny)), and `sphere_detectors` into POD structs.
4. Calls stub bounce loop — returns grids as zero-filled float64 `(ny, nx)` numpy arrays using pybind11 `py::array_t<double>`, sphere grids as `(n_theta, n_phi)`.
5. Returns dict with keys `grids / spectral_grids / escaped / sb_stats / sph_grids` matching `_trace_single_source` (tracer.py:2314).

### Test Suite (`test_cpp_tracer.py`)
- `_make_simple_project()` helper builds a 50x50x20mm enclosed-box project_dict (floor + 4 walls + top detector 50x50 grid + 1 lambertian LED) for all tests.
- **C++-01** `test_blu_tracer_loads` — imports the extension. **PASS**
- **C++-02** `test_trace_source_returns_valid_dict` — all 5 keys present, grid is 2D float64. **PASS**
- **C++-03** `test_existing_tests_are_still_runnable` — test_tracer.py importable. **PASS**
- **C++-04** `test_determinism` — same seed → identical grids. **PASS** (trivially on zero-filled stub; will validate RNG determinism in Wave 2).
- **C++-05** `test_energy_conservation` — accounted flux ≤ source flux within 0.1%. **PASS** (trivially: stub returns 0 everywhere).
- **C++-06** `test_statistical_equivalence` — **SKIPPED** (needs real bounce loop from 02-02).
- **C++-07** `test_speedup` — **SKIPPED** (benchmark deferred to 02-04).
- **C++-08** `test_no_numba_imports` — **SKIPPED** (Numba removal deferred to 02-03).

## Must-Haves — All Verified

| Must-have | Status |
|-----------|--------|
| `pip install --no-build-isolation -e backlight_sim/sim/_blu_tracer/` succeeds | ✅ via vcvars64 shell |
| `from backlight_sim.sim import blu_tracer` prints the module | ✅ `<module 'backlight_sim.sim.blu_tracer' from 'site-packages\\backlight_sim\\sim\\blu_tracer.cp312-win_amd64.pyd'>` |
| `blu_tracer.trace_source(project_dict, source_name, seed)` returns dict with 5 keys | ✅ grids/spectral_grids/escaped/sb_stats/sph_grids |
| Same seed → identical grids (determinism) | ✅ trivially on stub; C++ uses `std::mt19937_64` (seedable) |
| `test_cpp_tracer.py` exists with stubs for C++-01..C++-08 | ✅ 5 active + 3 skipped |

## Deviations from Plan

### Rule 1 — Bug fix: unused parameter warnings

**Found during:** Task 1
**Issue:** The PLAN's stub bodies reference function parameters the stubs don't use (e.g. `intersect_plane` takes 13 args but the body `return INF;` uses none). MSVC `/W3` would emit C4100 warnings for every stub, cluttering the build log.
**Fix:** Added `(void)arg;` casts at the top of each stub body to acknowledge the params. All stubs compile with zero warnings. When Wave 2 fills real bodies these casts naturally disappear.
**Files modified:** intersect.cpp, sampling.cpp, material.cpp, bvh.cpp
**Commit:** fe74d68

### Rule 1 — Bug fix: include `<utility>` in bvh.hpp for `std::pair`

**Found during:** Task 1 (preventive; not yet caught by MSVC's implicit include chain)
**Issue:** `bvh.hpp` declares `std::pair<double,int>` return type without including `<utility>`. Works on MSVC via transitive include but is not portable.
**Fix:** Added `#include <utility>` to bvh.hpp.
**Files modified:** bvh.hpp
**Commit:** fe74d68

### Rule 1 — Bug fix: `scikit-build-core` doubled install path

**Found during:** Task 2 verification
**Issue:** With the PLAN's `wheel.install-dir = "backlight_sim/sim"` combined with `CMakeLists.txt install(TARGETS blu_tracer DESTINATION backlight_sim/sim)`, scikit-build-core concatenated the two paths, installing to `site-packages/backlight_sim/sim/backlight_sim/sim/blu_tracer.cp312-win_amd64.pyd` and registering the editable finder as `backlight_sim.sim.backlight_sim.sim.blu_tracer` — unreachable via `from backlight_sim.sim import blu_tracer`.
**Fix:** Removed `wheel.install-dir` from pyproject.toml (unset = wheel root at site-packages). CMakeLists.txt's `DESTINATION backlight_sim/sim` alone places the .pyd correctly. Verified: `from backlight_sim.sim import blu_tracer` resolves via skbuild's `ScikitBuildRedirectingFinder` meta-path hook mapping `backlight_sim.sim.blu_tracer → backlight_sim\\sim\\blu_tracer.cp312-win_amd64.pyd`.
**Files modified:** backlight_sim/sim/_blu_tracer/pyproject.toml
**Commit:** 190859c

### Rule 2 — Resolution handling in stub bounce

**Found during:** Task 2 implementation
**Issue:** PLAN stub used a placeholder `{1,1}` grid shape for all detectors because it passed `detectors` but not their resolutions into `run_stub_bounce`. That would break `test_trace_source_returns_valid_dict`'s future expectations (the test currently only asserts ndim==2, but a 1x1 grid from a 50x50 configured detector is misleading for a physics engine).
**Fix:** Added a parallel `detector_resolutions` vector (std::array<int,2> per detector, populated from `det["resolution"]` during deserialization) passed into `run_stub_bounce`. Grids are now correctly sized `(ny, nx)` per detector resolution. Sphere grids sized `(n_theta, n_phi)` likewise.
**Files modified:** backlight_sim/sim/_blu_tracer/src/blu_tracer.cpp
**Commit:** 190859c

## Authentication Gates

None. No network/auth resources involved.

## Threat Flags

None. The Wave 1 scaffold introduces no new trust-boundary surface — `trace_source` parses a Python dict constructed locally by the caller and produces a numeric dict in return. The threat model's T-02-01 (py::cast on unvetted fields) is mitigated by pybind11's default `error_already_set` on missing keys and by `.contains()` checks on optional fields (`optical_properties_name`, `sphere_detectors`, `mode`).

## Environment Notes

- Build invocation: `cmd.exe //c "C:\Users\hasan\blu_build.bat"` (which calls vcvars64 then `pip install --no-build-isolation -e`). Plain bash pip install fails with `cl not found`.
- Output of the .pyd at `C:\Users\hasan\AppData\Local\Programs\Python\Python312\Lib\site-packages\backlight_sim\sim\blu_tracer.cp312-win_amd64.pyd` (via editable install — not in the project tree).
- Editable install means rebuilds happen automatically on next `import blu_tracer` if CMake detects source changes (see `_blu_tracer_editable.py::rebuild()`).

## Self-Check: PASSED

- [x] All 13 created files exist (verified via `find` + `ls`)
- [x] Both commits present in git log: `fe74d68` (task 1), `190859c` (task 2)
- [x] `python -c "from backlight_sim.sim import blu_tracer; print(blu_tracer.trace_source)"` prints the function
- [x] `pytest backlight_sim/tests/test_cpp_tracer.py -v` → 5 pass, 3 skip
- [x] `pytest backlight_sim/tests/test_tracer.py -x -q` → 124 pass (existing suite unaffected)
