# Phase 2: Converting Main Simulation Loop to C++ — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 02-converting-main-simulation-loop-to-cpp-for-faster-computation
**Areas discussed:** Binding strategy, Scope of C++ port, Numba relationship, Build & distribution

---

## Binding Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| pybind11 | Modern C++11, first-class NumPy support, widely adopted, good PyInstaller community support | ✓ |
| ctypes / cffi | Zero extra C++ dependencies, manual ABI management, painful for complex numpy array exchange | |
| Cython | .pyx files, good for wrapping existing C++, less ergonomic for new C++ code | |

**User's choice:** pybind11 (recommended)
**Notes:** User also asked about expected performance improvement and wanted a recommendation upfront. Addressed: 3–8x speedup over current Numba baseline expected, from eliminating Python bounce loop overhead and per-bounce dispatch.

---

## Scope of C++ Port

| Option | Description | Selected |
|--------|-------------|----------|
| Full bounce loop | Full per-source ray batch: emit, bounce, intersect, material dispatch, accumulate | ✓ |
| Inner loops only (surgical) | Only intersection math + BVH; Python still orchestrates bounce. Minimal gain over current Numba baseline | |
| Full engine rewrite | Multiprocessing, convergence, progress callbacks all in C++. Maximum gain, highest risk | |

**User's choice:** Full bounce loop (recommended)
**Notes:** Python stays as orchestration shell calling `RayTracer.run()`; multiprocessing stays in Python.

---

## Numba Relationship

| Option | Description | Selected |
|--------|-------------|----------|
| Replace Numba entirely | C++ supersedes sim/accel.py; remove Numba dependency; single acceleration layer | ✓ |
| Keep Numba as fallback | C++ primary, Numba fallback if .pyd missing; three-layer complexity | |

**User's choice:** Replace Numba entirely (recommended)
**Notes:** `sim/accel.py` and `_NUMBA_AVAILABLE` guard deleted after C++ port.

---

## Build & Distribution

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-compiled .pyd in repo | Build once, check in or attach to GitHub release; PyInstaller bundles it | ✓ |
| Build at install time | pip install triggers C++ compilation; requires MSVC on user's machine; violates Phase 1 goal | |
| Pure Python fallback | Keep Python tracer alongside C++; doubles maintenance burden | |

**User's choice:** Pre-compiled .pyd in repo (recommended)

### Runtime Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Crash with clear error message | .pyd is mandatory; show how to rebuild if missing | ✓ |
| Fall back to pure Python silently | Auto-degrade to slower Python tracer | |

**User's choice:** Crash with clear error message

---

## Claude's Discretion

- C++ internal data layout (SoA vs AoS for ray batches)
- CMake vs setup.py build system
- C++ standard version
- Memory management (shared numpy buffers vs copy-in/copy-out)
- Error message wording on missing .pyd

## Deferred Ideas

- CUDA/GPU acceleration — out of scope
- Spectral engine in C++ — only bounce loop scoped for this phase
- ARM/macOS builds — Windows-only target
