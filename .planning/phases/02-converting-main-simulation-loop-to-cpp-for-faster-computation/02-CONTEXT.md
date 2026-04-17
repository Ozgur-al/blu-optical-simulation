# Phase 2: Converting Main Simulation Loop to C++ — Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite the core Monte Carlo ray tracing engine in C++ and expose it to Python via pybind11, achieving significant speedup on CPU-bound simulation workloads. The Python/PySide6 front-end and `RayTracer.run()` API surface remain unchanged. Scope ends at the simulation engine — no GUI changes, no new features.

</domain>

<decisions>
## Implementation Decisions

### Binding Strategy
- **D-01:** Use **pybind11** for the Python-C++ binding layer. Industry standard, first-class NumPy array support, good PyInstaller community support. Build via setup.py or CMake extension.

### Scope of C++ Port
- **D-02:** Port the **full per-source bounce loop** to C++: emit ray batch, bounce loop (intersect all surfaces/detectors, material dispatch, reflection/refraction/absorption, grid accumulation). The complete inner engine runs in C++.
- **D-03:** Python remains the orchestration shell: it calls `RayTracer.run()` which delegates to the C++ extension and gets back a `SimulationResult`. The `RayTracer` class and public API are unchanged.
- **D-04:** Multiprocessing (ProcessPoolExecutor) orchestration stays in Python — C++ handles single-source trace runs. Each process worker calls the C++ extension.

### Numba Relationship
- **D-05:** **Remove Numba entirely.** The C++ extension supersedes all Numba-accelerated code in `sim/accel.py`. No dual-maintenance — C++ is the single acceleration layer.
- **D-06:** `sim/accel.py` and the `_NUMBA_AVAILABLE` guard are deleted. Any Numba imports removed throughout `sim/tracer.py`.

### Build & Distribution
- **D-07:** Ship a **pre-compiled `.pyd` (Windows)** checked into the repo or attached to the GitHub release. PyInstaller bundles it as a standard binary dependency (same as numpy).
- **D-08:** Developers building from source need MSVC once; end users get the pre-compiled binary. This preserves the Phase 1 goal of running on admin-locked work computers without build tools.
- **D-09:** If the `.pyd` fails to load at runtime, **crash with a clear error message** — no silent Python fallback. The C++ extension is mandatory; instruct users how to rebuild if needed.

### Performance Expectation
- **D-10:** Target 3–8x speedup over the current Numba-accelerated baseline for typical scenes; larger gains for dense multi-bounce workloads. Expected speedup comes from eliminating the Python for-loop overhead, per-bounce array bookkeeping, and material dispatch branching.

### Claude's Discretion
- C++ internal data layout (SoA vs AoS for ray batches)
- CMake vs setup.py build system choice
- C++ standard version (C++17 acceptable)
- Memory management strategy (shared numpy buffers vs copy-in/copy-out)
- Exact error message wording on missing `.pyd`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Simulation Engine (to be ported)
- `backlight_sim/sim/tracer.py` — Current Python engine (2428 lines); all methods here are candidates for C++ port. Key: `RayTracer.run()`, `_run_single()`, `_bounce_surfaces()`, `_trace_single_source()`, `_intersect_rays_plane()`, `_reflect_batch()`.
- `backlight_sim/sim/sampling.py` — Ray sampling utilities (337 lines); likely ported alongside tracer or kept in Python if not on critical path.
- `backlight_sim/sim/accel.py` — Existing Numba acceleration; to be **deleted** after C++ port.

### Core Data Models (must match in C++ structs)
- `backlight_sim/core/geometry.py` — `Rectangle` dataclass (u_axis/v_axis/size/center/material_name)
- `backlight_sim/core/materials.py` — `Material` dataclass (surface_type, reflectance, transmittance, is_diffuse, haze)
- `backlight_sim/core/sources.py` — `PointSource` (position, flux, direction, distribution, enabled, effective_flux)
- `backlight_sim/core/detectors.py` — `DetectorSurface`, `DetectorResult`, `SimulationResult`, `SphereDetector`
- `backlight_sim/core/solid_body.py` — `SolidCylinder`, `SolidPrism`, `CylinderCap`, `CylinderSide`, `PrismCap`
- `backlight_sim/core/project_model.py` — `Project` + `SimulationSettings`

### Build & Distribution
- `build_exe.py` — PyInstaller build script; will need updating to include the C++ `.pyd`
- `BluOpticalSim.spec` — PyInstaller spec; needs `binaries` or `datas` entry for the `.pyd`
- `requirements.txt` — Add `pybind11` as a build dependency

### Tests (correctness validation baseline)
- `backlight_sim/tests/test_tracer.py` — 20 existing tests; C++ port must pass all of these

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sim/accel.py` — Numba JIT implementations of intersection math; these are the reference implementations to port to C++. Contains: `intersect_plane`, `intersect_sphere`, `accumulate_grid_jit`, `accumulate_sphere_jit`, `build_bvh_flat`, `traverse_bvh_batch`.
- `sim/sampling.py` — Sampling functions (isotropic, Lambertian, angular distribution CDF inversion, haze scatter, BSDF). Port to C++ or keep in Python depending on profiling.

### Established Patterns
- **Layer separation**: `core/`, `sim/`, `io/` never import PySide6. The C++ extension fits entirely in `sim/`.
- **NumPy interface**: All ray data flows as NumPy arrays (origins, directions, weights). pybind11 buffer protocol maps these to Eigen or raw C arrays without copy.
- **Optional acceleration pattern**: `_NUMBA_AVAILABLE` guard in `accel.py` — the C++ extension replaces this pattern (mandatory, not optional, so guard is removed).
- **Multiprocessing**: `_trace_single_source` is the per-process unit dispatched by `ProcessPoolExecutor`. This function signature is the natural C++ extension boundary.
- **`SimulationResult` dataclass** — the output container that Python unpacks; C++ must fill this or an equivalent transferable dict.

### Integration Points
- `sim/tracer.py` `_run_single()` — imports and calls Numba-accelerated functions; these import calls become C++ extension calls instead.
- `build_exe.py` / `BluOpticalSim.spec` — PyInstaller pipeline; needs to discover and bundle the `.pyd`.
- `backlight_sim/tests/test_tracer.py` — golden test baseline; all 20 tests must pass after port.

</code_context>

<specifics>
## Specific Ideas

- The C++ extension should expose a single entry point like `blu_tracer.trace_source(project_dict, source_name, seed)` returning a dict that Python unpacks into `SimulationResult`. This keeps the boundary clean.
- Aim to keep the `RayTracer` Python class as a thin shell that serializes `Project` to a dict, calls the C++ extension per source, and reassembles `SimulationResult`.

</specifics>

<deferred>
## Deferred Ideas

- CUDA/GPU acceleration — explicitly out of scope (packaging complexity)
- Spectral engine port to C++ — only bounce loop is scoped; spectral binning stays Python for now
- ARM/macOS builds of the `.pyd` — Windows-only target for this phase

</deferred>

---

*Phase: 02-converting-main-simulation-loop-to-cpp-for-faster-computation*
*Context gathered: 2026-04-17*
