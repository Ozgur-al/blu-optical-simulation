# Phase 2: C++ Simulation Engine — Research

**Researched:** 2026-04-18
**Domain:** pybind11, C++ ray-tracing port, Windows MSVC build, PyInstaller bundling
**Confidence:** HIGH (primary claims verified via Context7 / official docs / npm registry)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** pybind11 binding layer (not ctypes). Industry standard, first-class NumPy array support.
- **D-02:** Port **full per-source bounce loop** to C++: emit ray batch, bounce loop (intersect all surfaces/detectors, material dispatch, reflection/refraction/absorption, grid accumulation). The complete inner engine runs in C++.
- **D-03:** Python remains orchestration shell; `RayTracer.run()` API surface unchanged.
- **D-04:** Multiprocessing (ProcessPoolExecutor) orchestration stays in Python — C++ handles single-source trace runs.
- **D-05/D-06:** Remove Numba entirely. `sim/accel.py` and all `_NUMBA_AVAILABLE` guards are deleted. C++ is the single acceleration layer.
- **D-07:** Ship a pre-compiled `.pyd` (Windows). Checked into repo or attached to GitHub release. PyInstaller bundles it.
- **D-08:** Developers building from source need MSVC once; end users get the pre-compiled binary.
- **D-09:** If `.pyd` fails to load at runtime, **crash with a clear error** — no silent Python fallback.
- **D-10:** Target 3–8x speedup over current Numba-accelerated baseline.

### Claude's Discretion

- C++ internal data layout (SoA vs AoS for ray batches)
- CMake vs setup.py build system choice
- C++ standard version (C++17 acceptable)
- Memory management strategy (shared numpy buffers vs copy-in/copy-out)
- Exact error message wording on missing `.pyd`

### Deferred Ideas (OUT OF SCOPE)

- CUDA/GPU acceleration — packaging complexity
- Spectral engine port to C++ — spectral binning stays Python for now
- ARM/macOS builds of the `.pyd` — Windows-only target for this phase
</user_constraints>

---

## Summary

The core simulation bottleneck is the Python bounce loop in `_run_single` and `_trace_single_source` — a nested `for _bounce in range(max_bounces)` that calls out to NumPy and Numba-accelerated intersection kernels but still carries heavy Python dispatch overhead on every bounce. Eliminating the Python loop and replacing it with a C++ compiled kernel is the highest-leverage optimization available.

The build ecosystem has converged around **scikit-build-core + CMake + pybind11** as the modern standard for shipping compiled Python extensions. For this project's specific constraint (single Windows target, pre-compiled binary shipped to non-developer users), the recommended path is: write C++ in `backlight_sim/sim/blu_tracer/`, build once on a developer machine with MSVC 2022, check the `.pyd` into the repo, and teach PyInstaller to include it via the `binaries=[]` list in `BluOpticalSim.spec`.

The main complexity is faithfully porting all geometry types (Rectangle/DetectorSurface plane, CylinderCap disc, CylinderSide quadratic, PrismCap polygon), material dispatch, and the Fresnel/TIR physics path — the intersection math is well-understood but the number of code paths is large. A conservative data layout (SoA for the hot intersection loop, copy-in/copy-out for material dispatch) is the pragmatic choice for correctness and developer velocity given no SIMD libraries are in scope.

**Primary recommendation:** Use scikit-build-core + CMake for the build system, SoA layout (separate `origins_x/y/z`, `directions_x/y/z`, `weights` arrays) for the hot intersection loop, copy-in/copy-out for NumPy data transfer, and C++17 with MSVC 2022 `/O2 /fp:fast`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ray emit (sample directions) | C++ extension | — | On the critical path; sampling inside the loop |
| Plane intersection (Rectangle, DetectorSurface, solid box faces) | C++ extension | — | Most common hit type; hot loop |
| Disc intersection (CylinderCap) | C++ extension | — | Same plane math, radial clip instead of rect clip |
| Cylinder side intersection (CylinderSide) | C++ extension | — | Quadratic formula; bounded by axis range |
| Prism cap intersection (PrismCap) | C++ extension | — | Plane hit + polygon containment test |
| Material dispatch (reflector/absorber/diffuser/Fresnel) | C++ extension | — | Per-bounce, branchy, benefits from C++ speed |
| Fresnel / TIR physics | C++ extension | — | Float math, vectorized per-ray stochastic roll |
| Grid accumulation (scatter-add) | C++ extension | — | Replaces `accumulate_grid_jit` |
| Sphere detector accumulation | C++ extension | — | Replaces `accumulate_sphere_jit` |
| BVH construction and traversal | C++ extension | — | Port from `accel.py`; only engaged when n_planes >= 50 |
| Spectral wavelength sampling | Python (stay) | — | Deferred per D-02 context; wavelengths not flow into C++ bounce loop |
| Spectral grid accumulation (grid_spectral) | Python (stay) | — | Deferred per CONTEXT.md |
| Multiprocessing orchestration (ProcessPoolExecutor) | Python | — | D-04; one C++ call per process worker |
| Project serialization to dict | Python | — | Python RayTracer serializes Project before calling C++ |
| SimulationResult assembly | Python | — | RayTracer reassembles from dict returned by C++ |
| Ray path recording | Python (stay) or C++ optional | — | Low-priority; used only for visualization |

---

## Standard Stack

### Core Build Stack
| Library / Tool | Version | Purpose | Why Standard |
|---------------|---------|---------|--------------|
| pybind11 | 3.0.3 | Python-C++ binding layer | Industry standard; first-class `array_t`; C++17 support; best PyInstaller community support |
| scikit-build-core | 0.12.2 | CMake-driven Python package build backend | Official pybind team recommendation; replaces deprecated cmake_example setup.py approach |
| CMake | 3.18+ | C++ build orchestration | Required by scikit-build-core; CMake 3.15+ is the minimum |
| MSVC (Visual Studio 2022 Build Tools) | 19.x | C++ compiler for Windows | Only supported compiler for CPython .pyd on Windows; MSVC 2019+ recommended |
| numpy | 2.4.2 (installed) | Buffer protocol; return array | Already a project dependency; pybind11 3.x removed `PYBIND11_NUMPY_1_ONLY` — requires NumPy 2 compat |

[VERIFIED: pip index versions pybind11, scikit-build-core]
[VERIFIED: pybind11==3.0.3 is current latest — pip registry 2026-04-18]
[VERIFIED: scikit-build-core==0.12.2 is current latest — pip registry 2026-04-18]
[CITED: https://github.com/pybind/scikit_build_example — official pybind team example]

### Optional Supporting Tools
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ninja | latest | Fast parallel C++ build backend for CMake | Significantly faster than MSBuild for incremental builds; `pip install ninja` |
| cmake | pip-installable | CMake binary for build-time | Install via `pip install cmake` to avoid system CMake version conflicts |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scikit-build-core + CMake | `setup.py` + `pybind11.setup_helpers` | setup.py approach is deprecated and harder to maintain; cmake_example repo is archived in favor of scikit_build_example |
| scikit-build-core + CMake | nanobind | nanobind is newer and faster at startup but has less ecosystem adoption; pybind11 has more PyInstaller community knowledge |
| pybind11 | ctypes + manual ABI | No C++ STL types; manual lifetime management; rejected by D-01 |
| copy-in/copy-out | zero-copy shared buffer | Zero-copy requires extra care about buffer lifetimes in MP mode (each process has its own memory space anyway); copy-in is simpler and safe |

**Installation (build-time, developer only):**
```bash
pip install pybind11 scikit-build-core cmake ninja
# Then build the extension:
pip install --no-build-isolation -e .
```

---

## Architecture Patterns

### System Architecture Diagram

```
Python: RayTracer.run()
    │
    ├── serialize Project → project_dict (Python dict of lists/floats)
    │
    ├── for each enabled source:
    │       │
    │       └── [ProcessPoolExecutor or direct call]
    │               │
    │               └── blu_tracer.trace_source(project_dict, source_name, seed)
    │                       │
    │                       └── C++ extension (blu_tracer.pyd)
    │                               │
    │                               ├── deserialize project_dict → C++ structs
    │                               ├── emit ray batch (C++ sampling)
    │                               ├── bounce loop (C++ scalar loop over max_bounces):
    │                               │       ├── BVH or brute-force intersection
    │                               │       │       (plane/disc/cylinder/prism cap)
    │                               │       ├── material dispatch
    │                               │       │       (absorb/reflect/diffuse/Fresnel)
    │                               │       ├── grid accumulate (scatter-add)
    │                               │       └── energy threshold cull
    │                               └── return result_dict
    │                                       (grids, hits, flux, escaped, sb_stats)
    │
    └── merge result dicts → SimulationResult (Python dataclass)
```

### Recommended Project Structure
```
backlight_sim/
└── sim/
    ├── tracer.py              # Thin Python shell; unchanged API
    ├── sampling.py            # Keep in Python (not on critical path for C++ phase)
    ├── spectral.py            # Keep in Python (deferred per CONTEXT.md)
    ├── accel.py               # DELETE after C++ port validates
    └── _blu_tracer/           # C++ extension source
        ├── CMakeLists.txt
        ├── pyproject.toml     # scikit-build-core build spec
        ├── src/
        │   ├── blu_tracer.cpp          # pybind11 module entry point + trace_source()
        │   ├── intersect.hpp/cpp       # plane/disc/cylinder/prism intersection
        │   ├── material.hpp/cpp        # material dispatch, Fresnel, sampling
        │   ├── bvh.hpp/cpp             # BVH build and traversal (ported from accel.py)
        │   ├── sampling.hpp/cpp        # C++ CDF inversion, Lambertian, isotropic
        │   └── types.hpp               # RayBatch SoA struct, SceneSurface structs
        └── blu_tracer.cpXX-win_amd64.pyd   # pre-compiled binary (checked in)
```

### Pattern 1: pybind11 array_t Zero-Copy Read Access
**What:** Pass NumPy arrays from Python to C++ without copying by using `py::array_t<double>` with `request()` to get a raw pointer.
**When to use:** Any time the C++ function needs to read data from a Python-owned NumPy array (e.g., grid arrays passed back from previous Python accumulation steps).
```cpp
// Source: pybind11 official docs / numpy.h
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
namespace py = pybind11;

// Accept a C-contiguous double array; no copy made
double sum_array(py::array_t<double, py::array::c_style | py::array::forcecast> arr) {
    py::buffer_info buf = arr.request();
    double *ptr = static_cast<double *>(buf.ptr);
    double total = 0.0;
    for (ssize_t i = 0; i < buf.size; ++i) total += ptr[i];
    return total;
}

// Mutable (write) access via unchecked proxy — no bounds checking, fast
void scale_array(py::array_t<double> arr, double factor) {
    auto r = arr.mutable_unchecked<1>();
    for (py::ssize_t i = 0; i < r.shape(0); ++i) r(i) *= factor;
}
```
[CITED: pybind11 NumPy documentation — pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html]

### Pattern 2: SoA Layout for the Ray Batch
**What:** Store all `N` rays as separate arrays per field rather than an array of ray structs. This is preferred for the intersection loop where only position and direction are needed simultaneously.
**When to use:** The hot intersection loop — each surface test reads origins_x/y/z, directions_x/y/z, and writes t_values; SoA keeps these reads cache-line contiguous.
```cpp
// Source: [ASSUMED] — standard HPC ray tracing SoA idiom
struct RayBatch {
    std::vector<double> ox, oy, oz;   // origins (SoA)
    std::vector<double> dx, dy, dz;   // directions (SoA)
    std::vector<double> weights;
    std::vector<bool>   alive;
    std::vector<double> current_n;    // per-ray refractive index
    // n_stack and n_depth for Fresnel/TIR: small arrays per ray
    std::vector<std::array<double, 8>> n_stack;
    std::vector<int>    n_depth;
    int n;
};
```
[ASSUMED] — SoA is the idiomatic layout for CPU ray tracing; confirmed by Monte Carlo SIMD literature showing SoA enables SIMD auto-vectorization.

### Pattern 3: Single Entry Point — `trace_source`
**What:** Expose exactly one function from the C++ module. Python serializes the `Project` to a plain dict of scalars/lists; C++ deserializes it, runs the full bounce loop, and returns a plain dict.
**When to use:** Always — this is the agreed interface from D-02/D-03.
```cpp
// Source: CONTEXT.md decision D-02
py::dict trace_source(
    py::dict project_dict,   // serialized Project
    std::string source_name,
    int seed
);

PYBIND11_MODULE(blu_tracer, m) {
    m.doc() = "BluOpticalSim C++ ray tracer core";
    m.def("trace_source", &trace_source,
          py::arg("project_dict"), py::arg("source_name"), py::arg("seed"),
          "Trace all rays from one source and return detector grids.");
}
```

### Pattern 4: Mandatory .pyd Load with Clear Error (D-09)
**What:** `sim/tracer.py` imports `blu_tracer` at module level and raises immediately on failure — no fallback.
**When to use:** Module import in `tracer.py`.
```python
# In backlight_sim/sim/tracer.py (replaces accel.py import block)
try:
    from backlight_sim.sim import blu_tracer as _blu_tracer
except ImportError as e:
    raise RuntimeError(
        "blu_tracer C++ extension failed to load. "
        "The pre-compiled blu_tracer.pyd is missing or incompatible with your Python version. "
        f"Details: {e}\n"
        "To rebuild from source, run: pip install --no-build-isolation -e . "
        "(requires MSVC 2022 Build Tools and CMake)."
    ) from e
```

### Pattern 5: PyInstaller .pyd Bundling
**What:** Tell PyInstaller to include the `.pyd` via the `binaries` list in the spec file.
**When to use:** `BluOpticalSim.spec` update — the `.pyd` is a DLL-type binary, not a Python module, so `binaries=` is the correct key (not `datas=`).
```python
# In BluOpticalSim.spec
binaries = [
    # (source_path, dest_dir_within_bundle)
    ("backlight_sim/sim/blu_tracer*.pyd", "backlight_sim/sim"),
]
```
[CITED: PyInstaller spec-files docs — pyinstaller.org/en/stable/spec-files.html]
[VERIFIED: binaries= is for DLL/pyd type files; datas= is for data-only files]

### Anti-Patterns to Avoid
- **Optional C++ with Python fallback:** Rejected by D-09. A working Numba fallback was acceptable for Numba (graceful degradation); for C++ it is mandatory. Silent fallbacks hide build failures.
- **Returning NumPy arrays from C++ owned by C++ memory:** pybind11 `py::array_t` constructor that takes ownership is subtle; prefer returning Python `py::dict` containing `py::array_t` built from C++ `std::vector<double>` — pybind11 copies the data once on return, which is fine (result is returned only once per source).
- **Using `np.add.at` equivalent in C++ (non-atomic scatter-add):** The scatter-add into the grid is single-threaded per source (D-04); no atomics needed. A plain `grid[iy*nx + ix] += weight` loop is correct and fast.
- **Mixing C++ standard and Python NumPy RNG sequences:** C++ will use its own `std::mt19937_64` seeded from the `seed` parameter. The Python `rng` is no longer consumed inside the C++ kernel. This breaks exact bitwise reproducibility vs the old Python path but produces statistically equivalent results — this is expected and correct.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Python-C++ binding | Raw CPython API (Py_BuildValue etc.) | pybind11 | CPython API is brittle, versioned, and requires manual reference counting; pybind11 handles all of that |
| NumPy buffer access | Manual `PyArray_DATA` / `PyObject*` | `py::array_t<T>` + `request()` or `unchecked<N>()` | Automatic type checking, shape validation, contiguity enforcement |
| Build system (Windows .pyd) | Manual `cl.exe` invocation scripts | scikit-build-core + CMake | CMake handles MSVC toolchain discovery, include paths, Python extension linking, `.pyd` naming |
| C++ random number generation | Hand-rolled LCG | `std::mt19937_64` (C++11 STL) | Tested, reproducible, thread-safe seed isolation |
| CDF inversion for angular distribution | Custom interpolation | `std::lower_bound` on precomputed CDF array | `lower_bound` is O(log N) and already in STL |

**Key insight:** The hardest hand-rolled thing in this domain is correct `.pyd` naming on Windows — CMake's `pybind11_add_module()` handles the platform-specific suffix (`.cpXX-win_amd64.pyd`) automatically.

---

## Intersection Algorithms in C++

### Plane (Rectangle, DetectorSurface, SolidBox faces, SolidPrism side faces)
This is the most common intersection — directly port `intersect_plane_jit` from `accel.py`.

```cpp
// Port of accel.py::intersect_plane_jit — [VERIFIED from accel.py source read]
// d_plane = dot(normal, center)  (precomputed per surface)
// denom = dot(d, normal)
// t = (d_plane - dot(o, normal)) / denom
// check |u_coord| <= half_w AND |v_coord| <= half_h
inline double intersect_plane(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double nx, double ny, double nz,
    double d_plane,
    double ux, double uy, double uz,   // u_axis
    double vx, double vy, double vz,   // v_axis
    double half_w, double half_h,
    double epsilon
) {
    double denom = dx*nx + dy*ny + dz*nz;
    if (std::abs(denom) <= 1e-12) return std::numeric_limits<double>::infinity();
    double t = (d_plane - (ox*nx + oy*ny + oz*nz)) / denom;
    if (t <= epsilon) return std::numeric_limits<double>::infinity();
    double hx = ox + t*dx - cx, hy = oy + t*dy - cy, hz = oz + t*dz - cz;
    // u/v projection
    if (std::abs(hx*ux + hy*uy + hz*uz) > half_w) return std::numeric_limits<double>::infinity();
    if (std::abs(hx*vx + hy*vy + hz*vz) > half_h) return std::numeric_limits<double>::infinity();
    return t;
}
```
[VERIFIED: ported from `accel.py` intersect_plane_jit, lines 54-146]

### Disc (CylinderCap)
Plane intersection restricted to circular region: `r2 = u_coord^2 + v_coord^2 <= radius^2`.
```cpp
// Plane hit test, then:
double u_c = hx*ux + hy*uy + hz*uz;
double v_c = hx*vx + hy*vy + hz*vz;
if (u_c*u_c + v_c*v_c > radius*radius) return inf;
```

### Cylinder Side (CylinderSide)
Quadratic ray-infinite-cylinder intersection, bounded by `|proj_along_axis| <= half_length`.
[CITED: pbr-book.org/3ed-2018/Shapes/Cylinders — reference implementation]
```cpp
// Project ray onto plane perpendicular to cylinder axis
// a = dot(d_perp, d_perp), b = 2*dot(d_perp, o_perp), c = dot(o_perp,o_perp) - r^2
// disc = b^2 - 4ac; pick smallest positive t
// Then check: |dot(hit_point - center, axis)| <= half_length
```

### Prism Cap (PrismCap)
Plane intersection, then polygon containment test (half-plane test against precomputed edge normals — already in `PrismCap.edge_normals_2d`). Port the Python polygon containment logic that's currently implicit in the Python tracer.
[VERIFIED: PrismCap has `vertices_2d`, `edge_normals_2d` precomputed — solid_body.py]

---

## Spectral Engine Interaction (What Stays Python)

The CONTEXT.md defers spectral to Python. This means:

1. **`wavelengths` array is NOT passed to `trace_source()`** — the C++ bounce loop has no per-ray wavelength.
2. **Spectral grid accumulation (`grid_spectral`)** is skipped in C++; the C++ `trace_source()` only fills the monochromatic flux grid.
3. **Spectral `n(lambda)` for SolidBox/Cylinder materials** — the wavelength-dependent refractive index lookup (`spectral_material_data`) is not ported; C++ uses the scalar `refractive_index` from the Material.
4. **Practical effect:** When `has_spectral = True`, the Python tracer must still call `_run_single` (the old path) rather than `trace_source`. This is an acceptable temporary restriction — documented in the error message and the updated `RayTracer.run()` logic.

**Spectral + MP guard is preserved:** Currently `has_spectral AND use_multiprocessing` forces single-thread with a warning. After the C++ port, the guard becomes `has_spectral` alone (because the C++ path doesn't handle spectral). Non-spectral scenes get the full C++ speedup.

[VERIFIED: tracer.py line 195-203 — spectral+MP guard already exists]

---

## Build Setup: scikit-build-core + CMake

### Minimal `pyproject.toml` for the Extension
```toml
# backlight_sim/sim/_blu_tracer/pyproject.toml
[build-system]
requires = ["scikit-build-core>=0.9", "pybind11>=2.13"]
build-backend = "scikit_build_core.build"

[project]
name = "blu_tracer"
version = "0.1.0"
```
[CITED: scikit-build-core getting-started docs; scikit_build_example official pybind team repo]

### Minimal `CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.18)
project(blu_tracer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

# NumPy include path
execute_process(
    COMMAND "${Python_EXECUTABLE}" -c "import numpy; print(numpy.get_include())"
    OUTPUT_VARIABLE NUMPY_INCLUDE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

pybind11_add_module(blu_tracer MODULE
    src/blu_tracer.cpp
    src/intersect.cpp
    src/material.cpp
    src/sampling.cpp
    src/bvh.cpp
)

target_include_directories(blu_tracer PRIVATE src ${NUMPY_INCLUDE_DIR})

# MSVC-specific: fast math, full optimization
if(MSVC)
    target_compile_options(blu_tracer PRIVATE /O2 /fp:fast /W3)
endif()

install(TARGETS blu_tracer DESTINATION backlight_sim/sim)
```
[CITED: pybind11 cmake helpers docs; scikit-build-core getting started]

### MSVC Requirements
- **Minimum:** MSVC 2019 (v16.x)
- **Recommended:** MSVC 2022 Build Tools (v17.x) — freely downloadable without full VS IDE
- **Install:** Download "Build Tools for Visual Studio 2022" from visualstudio.microsoft.com/downloads/ → select "Desktop development with C++" workload
- **No IDE required:** `cl.exe` from the command line (via "Developer Command Prompt for VS 2022") is sufficient
- **Python 3.12 compatibility:** MSVC 2022 is actively tested with CPython 3.12 by the pybind11 CI [CITED: pybind11 changelog/releases]
- **Checked-in `.pyd`:** The compiled `.pyd` filename encodes the Python ABI tag, e.g. `blu_tracer.cp312-win_amd64.pyd`. If users have a different CPython minor version, the pre-compiled binary won't load — they must rebuild (the crash error message D-09 explains this).

[VERIFIED: pybind11 MSVC minimum is 2017, 2019+ strongly recommended — pybind11 releases discussion]

### Building the `.pyd`
```bash
# One-time developer setup (in the _blu_tracer/ subdirectory)
pip install scikit-build-core pybind11 cmake ninja

# Build the extension (produces .pyd in site-packages or in-place)
pip install --no-build-isolation -e backlight_sim/sim/_blu_tracer/

# Or: build and place .pyd in the source tree for git commit
python -m scikit_build_core.build --wheel
# Then unzip the wheel and copy the .pyd to backlight_sim/sim/
```

---

## PyInstaller Bundling

The `.pyd` is a Windows DLL-type file, not a Python `.py` file. PyInstaller auto-discovers `.pyd` files that are imported at analysis time. Because `tracer.py` imports `blu_tracer` at module level (per D-09 pattern), PyInstaller's Analysis phase will find it automatically via `hiddenimports` or direct import tracing — **no explicit `binaries=` entry is needed IF the .pyd is importable during analysis**.

However, to be safe and explicit (especially if the `.pyd` is in a non-standard location), add it to `binaries`:

```python
# BluOpticalSim.spec
binaries = [
    # Glob matches the ABI-tagged filename automatically
    ("backlight_sim/sim/blu_tracer*.pyd", "backlight_sim/sim"),
]
```

**Key finding:** The current spec has `binaries=[]` (empty). The `numba` entries are all in `hiddenimports`. For pybind11 .pyd files, there is no equivalent of `pyinstaller-hooks-contrib` needed — pybind11 .pyd files are standard Python extension modules (DLLs) with no extra runtime dependencies beyond MSVC runtime DLLs (which PyInstaller already bundles on Windows).

**Remove from spec:** Delete all `numba`, `numba.core`, `numba.typed`, `numba.np`, `llvmlite`, `llvmlite.binding` entries from `hidden_imports` (D-05/D-06).

[CITED: PyInstaller spec-files docs — pyinstaller.org/en/stable/spec-files.html]
[ASSUMED: pybind11 .pyd files need no special hooks — based on the absence of hooks in pyinstaller-hooks-contrib for pybind11 (no equivalent of the numba hook)]

---

## Memory Management Strategy

**Recommended: Copy-in / copy-out**

The `trace_source()` function receives the `project_dict` (Python dict), deserializes it into C++ structs, runs the full bounce loop internally, and returns a plain dict containing numpy arrays built from `std::vector<double>`.

Rationale:
- In multiprocessing mode (D-04), each subprocess has its own memory space — zero-copy across processes is impossible regardless.
- The project dict is small relative to the ray batch (few surfaces; the rays are the large allocation). Copying 20 surface structs is negligible.
- The result grids (detector grids) are copied once on return; this is O(detector_resolution) not O(n_rays).
- Zero-copy of the grid arrays back to Python is possible via `py::array_t` that wraps a `std::vector<double>` — but this requires the vector to outlive the Python array, which means it must be heap-allocated and owned by the Python object. This is manageable but adds complexity. **For Wave 0, copy-out is correct and simple.**

**Ray arrays:** The ray batch (`origins`, `directions`, `weights`) is allocated entirely inside C++ for the duration of `trace_source()`. No Python NumPy arrays are passed in for rays — C++ creates them from scratch using the source's position and distribution.

---

## Common Pitfalls

### Pitfall 1: ABI Tag Mismatch for Pre-Compiled .pyd
**What goes wrong:** Developer builds with Python 3.11; user has Python 3.12. The `.pyd` file is named `blu_tracer.cp311-win_amd64.pyd`; Python 3.12 won't load it and raises `ImportError`.
**Why it happens:** The Python stable ABI (limited API, `.pyd` without version tag) is not the default for pybind11; by default pybind11 links against the full CPython ABI which is version-specific.
**How to avoid:** Target Python 3.12 specifically (the installed version is 3.12.10). Document in CLAUDE.md and a `BUILD.md` that the pre-compiled binary is for Python 3.12. OR explore `Py_LIMITED_API` / stable ABI (`pybind11_add_module(... NO_EXTRAS)` + CMake stable ABI flags) — but this is complex and not standard. For this project, naming the binary explicitly and maintaining it per Python version is simpler.
**Warning signs:** The D-09 crash error will report the exact ImportError including the filename.

### Pitfall 2: NumPy 2.x Compatibility — pybind11 3.x Required
**What goes wrong:** Using pybind11 < 2.12 with NumPy 2.x raises `AttributeError: module 'numpy' has no attribute 'bool'` or similar deprecation errors because old pybind11 used `numpy.bool` (removed in NumPy 2.0).
**Why it happens:** NumPy 2.0 removed several deprecated type aliases. pybind11 3.0 removes `PYBIND11_NUMPY_1_ONLY` and fully supports NumPy 2.x.
**How to avoid:** Use pybind11 3.0.3 (the current latest, installed on this machine as verified). Require `pybind11>=3.0` in `pyproject.toml`.
**Warning signs:** Errors at import time mentioning `numpy.bool`, `numpy.int`, etc.
[VERIFIED: pybind11 3.0.3 is latest — pip registry; NumPy 2.4.2 is installed]

### Pitfall 3: Self-Intersection Epsilon
**What goes wrong:** After a bounce, the new ray origin is offset by `1e-6 * normal`. If C++ uses a slightly different epsilon than Python (e.g., float32 vs float64), rays immediately re-intersect the same surface.
**Why it happens:** The existing Python code uses `_EPSILON = 1e-6` (float64). The Numba JIT `intersect_plane_jit` also uses `epsilon=1e-6`. The C++ port must use the same value and the same `t > epsilon` (strict inequality, not `>=`).
**How to avoid:** Define `constexpr double EPSILON = 1e-6;` in `types.hpp` and use it consistently.
[VERIFIED: tracer.py line 43 `_EPSILON = 1e-6`; accel.py line 48 `_EPSILON_DEFAULT = 1e-6`]

### Pitfall 4: Scatter-Add Race Condition (Not an Issue in Single-Thread)
**What goes wrong:** Using `std::atomic` for grid accumulation causes performance regression; not using it in a parallel context causes data races.
**Why it happens:** Confusion about thread model. The C++ `trace_source()` handles exactly one source at a time (D-04 — MP stays in Python). The scatter-add loop inside `trace_source()` is single-threaded. No atomics needed.
**How to avoid:** Plain `grid[iy * nx + ix] += weight;` in a single-threaded loop. If future phases add intra-source threading, revisit.

### Pitfall 5: Per-Ray Python Loop in `_bounce_surfaces`
**What goes wrong:** There are per-ray Python loops inside `_bounce_surfaces` for path recording (`for local_i, global_i in enumerate(hit_idx): paths[global_i].append(...)`). If these are ported to C++, path recording requires special treatment.
**Why it happens:** Path recording is only done for the first `n_record` rays of the first batch; it is not on the critical performance path.
**How to avoid:** For Wave 0 of the C++ port, **do not port path recording to C++**. The `trace_source()` call in MP mode already disables path recording. For single-thread mode, either (a) keep path recording in Python by running the first few rays through the old Python path, or (b) have C++ return optional path waypoints as a list of lists. Option (a) is simpler.

### Pitfall 6: prism_cap Containment Test
**What goes wrong:** Forgetting to port the polygon containment test for PrismCap — falling back to infinite-plane hit, which causes phantom hits on extended prism plane regions.
**Why it happens:** `PrismCap` uses half-plane tests against precomputed edge normals. This is non-trivial and easy to overlook.
**How to avoid:** Explicitly test PrismCap intersection in C++ unit tests using a known regular hexagon.

### Pitfall 7: pybind11 Module Name Must Match Filename
**What goes wrong:** `PYBIND11_MODULE(foo, m)` with the compiled file named `bar.pyd` — Python import fails silently or with confusing errors.
**Why it happens:** The module name in `PYBIND11_MODULE()` must exactly match the Python import name (and thus the filename without the platform suffix).
**How to avoid:** Use `blu_tracer` as both the CMake target name and the `PYBIND11_MODULE` macro argument. CMake will produce `blu_tracer.cpXX-win_amd64.pyd`.

---

## C++ Data Layout Recommendation (Claude's Discretion)

**Recommendation: SoA for the hot inner loop; per-ray state as parallel vectors.**

The primary bottleneck is the intersection loop where all N rays are tested against each surface. With SoA, `origins_x[i]`, `origins_y[i]`, `origins_z[i]` for ray `i` are in three separate arrays — the compiler can auto-vectorize the inner loop over surfaces for each coordinate component.

```cpp
// Hot intersection kernel: iterate over rays for a given surface
for (int i = 0; i < n_active; ++i) {
    double ox = batch.ox[active[i]], oy = batch.oy[active[i]], oz = batch.oz[active[i]];
    double dx = batch.dx[active[i]], dy = batch.dy[active[i]], dz = batch.dz[active[i]];
    double t = intersect_plane(ox, oy, oz, dx, dy, dz, ...);
    if (t < best_t[i]) { best_t[i] = t; best_surf[i] = si; }
}
```

The active-ray indexing (`active[i]` — the surviving ray index) introduces gather operations which hurt SIMD. A more advanced approach is "compaction" (repack live rays into contiguous arrays each bounce) but this adds implementation complexity. **For Wave 0, use SoA without compaction.** The speedup from eliminating Python loop overhead alone will achieve the 3–8x target.

[VERIFIED: SoA provides better SIMD cache performance than AoS for per-ray inner loops — algorithmica.org/hpc/cpu-cache/aos-soa/; HN discussion on RT cores and AoS]

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.0+ (already installed) |
| Config file | none — run from repo root |
| Quick run command | `pytest backlight_sim/tests/test_tracer.py -x -q` |
| Full suite command | `pytest backlight_sim/tests/ -q` |

### Strategy: Statistical Equivalence, Not Bitwise

The C++ extension uses its own `std::mt19937_64` RNG seeded independently from the Python `np.random.Generator`. Bitwise identical results to the Python/Numba path are **not possible and not required**. Instead, validate:

1. **All 20 existing tests pass** with the C++ path enabled. The tests use large ray counts (5000–10000) and check physics invariants (not exact values), so stochastic variance is not a problem.
2. **New determinism test:** `trace_source(project_dict, name, seed=42)` called twice must return bit-identical grids (C++ is deterministic given the same seed).
3. **Energy conservation test:** `total_emitted_flux ≈ escaped_flux + sum(detector_flux) + absorbed_flux` within 0.1% for a fully enclosed scene.
4. **Geometry regression test:** For a simple box scene (axis-aligned surfaces only, no solid bodies), the C++ result grid must agree with the Python Numba result to within 5% relative error per pixel (Monte Carlo noise tolerance) when both use 100,000 rays and the same scene.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| C++-01 | `.pyd` loads without error | smoke | `python -c "from backlight_sim.sim import blu_tracer"` | Wave 0 |
| C++-02 | `trace_source` returns valid dict with grids | unit | `pytest tests/test_cpp_tracer.py::test_trace_source_returns_valid_dict` | Wave 0 (new) |
| C++-03 | All 20 existing tracer tests pass | regression | `pytest backlight_sim/tests/test_tracer.py -q` | ✅ exists |
| C++-04 | C++ result deterministic with same seed | unit | `pytest tests/test_cpp_tracer.py::test_determinism` | Wave 0 (new) |
| C++-05 | Energy balance within 0.1% | physics | `pytest tests/test_cpp_tracer.py::test_energy_conservation` | Wave 0 (new) |
| C++-06 | Simple box: C++ vs Python within 5% | regression | `pytest tests/test_cpp_tracer.py::test_statistical_equivalence` | Wave 0 (new) |
| C++-07 | 3–8x speedup over Python baseline | perf | `pytest tests/test_cpp_tracer.py::test_speedup -s` | Wave 0 (new) |
| C++-08 | Numba entirely absent from imports | regression | `pytest tests/test_cpp_tracer.py::test_no_numba_imports` | Wave 0 (new) |

### Sampling Rate
- **Per task commit:** `pytest backlight_sim/tests/test_tracer.py -x -q` (existing tests, ~30 seconds)
- **Per wave merge:** `pytest backlight_sim/tests/ -q` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backlight_sim/tests/test_cpp_tracer.py` — new file covering C++-01 through C++-08
- [ ] `backlight_sim/sim/_blu_tracer/` directory — does not exist yet (create in Wave 0)
- [ ] `blu_tracer.cp312-win_amd64.pyd` — built by Wave 0 build task, checked into repo

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Build + runtime | ✓ | 3.12.10 | — |
| numpy | pybind11 NumPy headers | ✓ | 2.4.2 | — |
| pybind11 | Build | ✗ | — | `pip install pybind11` |
| scikit-build-core | Build backend | ✗ | — | `pip install scikit-build-core` |
| cmake | Build | ✗ | — | `pip install cmake` |
| ninja | Build (faster) | ✗ | — | Falls back to MSBuild; `pip install ninja` recommended |
| MSVC (cl.exe / Build Tools 2022) | C++ compilation | UNKNOWN | — | Must install; no fallback |
| numba | Runtime (to be deleted) | ✓ | installed | N/A — being removed |

**Missing dependencies with no fallback:**
- MSVC Build Tools 2022: Must be installed by the developer before building. Download from visualstudio.microsoft.com/downloads/ → "Build Tools for Visual Studio 2022" → "Desktop development with C++" workload.

**Missing dependencies with fallback:**
- pybind11, scikit-build-core, cmake, ninja: All installable via `pip install`. A Wave 0 task should document and automate this with `pip install -r requirements-dev.txt`.

**MSVC availability is UNKNOWN** — `vswhere.exe` could not be probed from the bash shell in this environment. The developer must verify MSVC is installed before starting Wave 1 build tasks.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pybind11 cmake_example` (setup.py + CMake) | `scikit_build_example` (scikit-build-core + CMake) | 2023–2024 | cmake_example is being archived; new projects should use scikit-build-core |
| `PYBIND11_NUMPY_1_ONLY` option | Removed in pybind11 3.0 | pybind11 3.0.0 (2025) | Must use NumPy 2-compatible array access; `numpy.bool` etc. removed |
| Numba JIT as the acceleration layer | C++ via pybind11 | This phase | Numba had ~10s warmup, CIL size overhead; C++ has zero warmup, smaller binary |
| Python per-bounce for-loop | C++ inner loop | This phase | Python GIL overhead and boxing per iteration eliminated |

**Deprecated/outdated:**
- `sim/accel.py`: Entire file deleted post-port (D-05/D-06)
- `_NUMBA_AVAILABLE` guard pattern: Deleted; replaced by mandatory import
- `numba` in `requirements.txt`: Removed
- numba/llvmlite entries in `BluOpticalSim.spec` hiddenimports: Removed

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | pybind11 .pyd files need no special PyInstaller hooks (unlike numba which needed `pyinstaller-hooks-contrib`) | PyInstaller Bundling | If wrong: need to write a custom hook or add explicit hidden_imports for pybind11 runtime dependencies |
| A2 | SoA without active-ray compaction will achieve 3–8x speedup over Numba baseline | Architecture / Performance | If wrong: may need compaction or manual SIMD to hit target; or target is adjusted |
| A3 | Path recording can remain in Python for Wave 0 (skip porting path waypoint collection to C++) | Don't port path recording | If wrong: the GUI visualization breaks; requires C++ to return ray paths as a list-of-lists |
| A4 | `std::mt19937_64` seeded from `seed` parameter produces statistically valid distributions for the test suite's physics invariant checks | Validation | If wrong: specific test assertions about uniformity or energy balance may fail even with correct code |
| A5 | MSVC 2022 Build Tools are freely available and installable without full Visual Studio IDE on the developer machine | Environment Availability | If wrong: developer must install full VS IDE; or use a GitHub Actions MSVC runner to build the .pyd |

---

## Open Questions (RESOLVED)

1. **MSVC Availability on Developer Machine**
   - What we know: Python 3.12 is installed; no MSVC was detected via the bash shell probe.
   - What's unclear: Whether MSVC Build Tools are already installed (vswhere.exe probe failed due to shell path issues).
   - Recommendation: Developer should run `where cl` from a "Developer Command Prompt for VS 2022" before starting Wave 1. If absent, install Build Tools (~6GB download) before implementation begins.
   - **RESOLVED:** Developer must verify by running `where cl` in a 'Developer Command Prompt for VS 2022' before starting Wave 1. This is documented as a Wave 1 pre-condition in plan 02-01 Task 1. End users do not need MSVC — they receive the pre-compiled .pyd.

2. **Python Version Lock for Pre-Compiled .pyd**
   - What we know: Python 3.12.10 is installed; `.pyd` is ABI-tagged to CPython minor version.
   - What's unclear: Will any end users or CI environments have Python 3.11 or 3.13? If so, the pre-compiled `.pyd` won't work for them.
   - Recommendation: Document Python 3.12 as the supported version in CLAUDE.md. The D-09 crash error message tells users to rebuild from source if needed.
   - **RESOLVED:** The .pyd filename `blu_tracer.cp312-win_amd64.pyd` encodes Python 3.12. Plan 02-04 updates CLAUDE.md to document that rebuilding requires Python 3.12 + MSVC 2022. D-09 hard crash catches version mismatches at runtime.

3. **BVH Port Complexity**
   - What we know: `accel.py` has a full flat BVH build + traversal (build_bvh_flat, traverse_bvh_batch). It's used only when `n_planes >= 50`.
   - What's unclear: Whether the BVH port should be in Wave 0 (required for correctness on large scenes) or Wave 1 (after brute-force path works).
   - Recommendation: Port BVH in Wave 1 after the brute-force path passes all 20 tests. Use `_BVH_THRESHOLD = 9999` temporarily to disable BVH while testing brute-force.
   - **RESOLVED:** BVH is deferred from this phase (brute-force only with BVH_THRESHOLD=9999). An explicit deferred decision is noted in plan 02-02. Production scenes with 50+ surfaces will run slower until BVH is ported in a future phase.

4. **Spectral Scenes Path**
   - What we know: When `has_spectral=True`, the tracer must NOT call `trace_source()` and must fall back to the old Python `_run_single`.
   - What's unclear: Whether `_run_single` should be kept indefinitely or deprecated after spectral C++ port in a future phase.
   - Recommendation: Keep `_run_single` for spectral scenes. Add a docstring warning that it is the legacy path. This is clean and matches CONTEXT.md.
   - **RESOLVED:** When `project_dict['settings']['spectral_mode']` is True, the C++ extension returns early (or the Python orchestrator detects this and routes to the existing Python path). CONTEXT.md explicitly states spectral binning stays Python for this phase.

---

## Sources

### Primary (HIGH confidence)
- `backlight_sim/sim/tracer.py` — all intersection patterns, bounce loop structure, material dispatch, spectral guard [VERIFIED: full file read]
- `backlight_sim/sim/accel.py` — JIT kernel signatures to port; BVH structure [VERIFIED: full file read]
- `backlight_sim/sim/sampling.py` — sampling function signatures [VERIFIED: full file read]
- `backlight_sim/core/solid_body.py` — CylinderCap, CylinderSide, PrismCap geometry [VERIFIED: full file read]
- `backlight_sim/tests/test_tracer.py` — existing test baseline [VERIFIED: full file read]
- `BluOpticalSim.spec` — existing PyInstaller spec structure [VERIFIED: full file read]
- pip registry — pybind11 3.0.3 (latest), scikit-build-core 0.12.2 (latest), numpy 2.4.2 [VERIFIED: `pip index versions` commands]
- python runtime — Python 3.12.10 x64, numpy 2.4.2 confirmed installed [VERIFIED: `python --version`, `python -c "import numpy"` commands]

### Secondary (MEDIUM confidence)
- [pybind11 NumPy buffer protocol docs](https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html) — array_t, unchecked, mutable_unchecked
- [pybind11 compiling docs](https://pybind11.readthedocs.io/en/stable/compiling.html) — build systems, MSVC support
- [pybind11 scikit_build_example](https://github.com/pybind/scikit_build_example) — official minimal example
- [pybind11 3.0.0 changelog](https://iscinumpy.dev/post/pybind11-3-0-0/) — NumPy 2.x compatibility
- [PyInstaller spec-files docs](https://pyinstaller.org/en/stable/spec-files.html) — binaries= vs datas=
- [PBR Book — Cylinders](https://www.pbr-book.org/3ed-2018/Shapes/Cylinders) — ray-cylinder intersection reference
- [Algorithmica HPC — AoS and SoA](https://en.algorithmica.org/hpc/cpu-cache/aos-soa/) — SoA cache performance rationale
- [Lorenzo Rovigatti — pybind11 + scikit-build-core tutorial](https://www.roma1.infn.it/~rovigatl/posts/pybind_cmake/) — complete pyproject.toml and CMakeLists.txt example

### Tertiary (LOW confidence — assumptions flagged above)
- PyInstaller + pybind11 .pyd community experience — no hooks needed [ASSUMED A1]

---

## Metadata

**Confidence breakdown:**
- Standard stack (pybind11, scikit-build-core, CMake): HIGH — verified via pip registry; official pybind team recommendation
- Intersection algorithms (plane, disc, cylinder, prism cap): HIGH — verified from accel.py and solid_body.py source + PBR book citation
- Build system (pyproject.toml, CMakeLists.txt): MEDIUM — based on official examples and tutorial; exact MSVC availability on developer machine unconfirmed
- PyInstaller bundling: MEDIUM — standard .pyd bundling; pybind11-specific behavior ASSUMED (A1)
- Performance (SoA, 3–8x target): MEDIUM — SoA benefit confirmed by literature; actual speedup depends on MSVC compiler output

**Research date:** 2026-04-18
**Valid until:** 2026-07-18 (90 days — pybind11/scikit-build-core are stable; NumPy 2 compat is the only fast-moving factor, already addressed)
