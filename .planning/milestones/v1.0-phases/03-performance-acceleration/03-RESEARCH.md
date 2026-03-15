# Phase 3: Performance Acceleration - Research

**Researched:** 2026-03-14
**Domain:** Numba JIT compilation, BVH spatial acceleration, adaptive Monte Carlo sampling
**Confidence:** HIGH (stack: HIGH, architecture: HIGH, pitfalls: HIGH)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Numba dependency:**
- Numba is an **optional** dependency — try-import with graceful fallback to pure NumPy
- App shows a **status bar indicator** ("JIT: Active" / "JIT: Off") so users can see acceleration state at a glance
- **Eager compile at startup** — JIT kernels compile when the app launches (2-5s startup cost) so first simulation runs at full speed
- **Bundle Numba in PyInstaller exe** — users get acceleration out of the box despite larger executable size

**Adaptive sampling UX:**
- Convergence threshold exposed as a **SimulationSettings field** (e.g., CV% target), with quality presets (Quick/Standard/High) setting sensible defaults that users can override
- **Per-source** adaptive stopping — each source independently halts when its detector contribution converges; sources illuminating small areas stop early
- **Live variance plot** during simulation — real-time display of detector CV% dropping, so users can watch convergence
- **Enabled by default** — adaptive sampling is on for all simulations; users who want exact ray counts can disable via checkbox in SimSettings

**JIT compilation scope:**
- JIT-compile **intersection + accumulation** only: `_intersect_rays_plane`, `_intersect_rays_sphere`, `_accumulate`, `_accumulate_sphere`
- Sampling and reflection functions stay pure NumPy (already well-vectorized)
- JIT kernels live in a **separate module** (`sim/numba_kernels.py` or `sim/accel.py`) — tracer.py imports JIT versions if Numba available, else uses local NumPy versions
- **BVH traversal is also Numba JIT-compiled** — build in NumPy (runs once), traversal kernels in Numba for per-ray-per-bounce performance
- **BVH built on-demand at simulation start** when scene has 50+ surfaces — no overhead during scene editing

### Claude's Discretion
- Exact BVH tree structure (binary, 4-wide, etc.)
- Convergence metric details (which CV variant, check frequency)
- Status bar indicator design and placement
- Numba decorator options (@njit vs @jit, cache=True, etc.)
- Live variance plot widget choice and layout

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERF-01 | Ray-surface intersection and accumulation inner loops are Numba JIT-compiled for 10-50x speedup | Numba 0.64.0 supports Python 3.12 + NumPy 2.x; `@njit(cache=True, fastmath=True)` on `_intersect_rays_plane`, `_intersect_rays_sphere`, `_accumulate`, `_accumulate_sphere`; `np.add.at` replaced with explicit for-loop (Numba-native); eager warmup at startup |
| PERF-02 | BVH spatial acceleration is used for scenes with 50+ surfaces | Binary AABB BVH, flat array representation (max 2N-1 nodes), build in NumPy once per simulation start, Numba-JIT traversal; activated when `len(all_surfaces) >= 50` |
| PERF-03 | Adaptive sampling stops ray generation per source when detector variance is below threshold | I = 1.96 × (σ/√n) ≤ maxTolerance × μ; check every `check_interval` rays (suggested 1000); per-source convergence tracked against `SimulationSettings.convergence_cv_target`; live plot via QThread signal to PlotWidget |
</phase_requirements>

---

## Summary

Phase 3 accelerates the Monte Carlo tracer through three independent but coordinated strategies. Numba 0.64.0 (the current stable release as of Feb 2026) supports Python 3.12 and NumPy 2.x and can deliver 10–50x speedup by JIT-compiling the innermost per-bounce work: `_intersect_rays_plane`, `_intersect_rays_sphere`, and the accumulation functions. The critical blocker already noted in STATE.md — `np.add.at` is not supported inside Numba nopython mode — is resolved by replacing scatter-add with an explicit indexed for-loop, which Numba handles natively and compiles to equivalent speed.

BVH acceleration addresses scenes with 50+ surfaces (LGP faces, diffuser stacks, multi-LED arrays). A binary AABB BVH stored as a flat NumPy array (at most 2N−1 nodes) is built once per simulation start and traversed with a JIT-compiled, stack-based loop. The build cost is O(N log N) and runs in pure NumPy; only the traversal (called per-ray per-bounce) needs to be JIT-compiled. For the target scene sizes (50–200 surfaces), a simple median-split or midpoint-split BVH is sufficient — SAH construction adds negligible accuracy gain at this scale.

Adaptive sampling uses the standard Berkeley CS184 I-statistic: I = 1.96 × σ/√n, stopping each source when I ≤ cv_target × μ (a relative convergence test on detector total flux). Checks occur every N rays (not every ray) to amortize the variance computation. The live variance plot is a pyqtgraph `PlotWidget` embedded in the simulation progress area, updated via the existing QThread `progress` signal extended with convergence data.

**Primary recommendation:** Implement in module order: (1) `sim/accel.py` with JIT kernels + BVH, (2) extend `SimulationSettings` with adaptive fields, (3) update `tracer.py` dispatch logic, (4) add GUI status bar indicator and live variance widget.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numba | 0.64.0 | JIT-compile Python functions to native machine code via LLVM | Only Python JIT compiler with genuine NumPy array support; designed exactly for this use case |
| llvmlite | 0.44.x | LLVM bindings (numba dependency, installed automatically) | Bundled with numba; no direct API needed |
| numpy | 2.4.2 (already installed) | BVH array storage, fallback compute path | Already in project; BVH build entirely in NumPy |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyinstaller-hooks-contrib | latest (2025.x) | Auto-handles Numba/llvmlite hidden imports in PyInstaller | Required when bundling Numba into exe; replaces manual hidden import list |
| pyqtgraph PlotWidget | already installed | Live variance convergence plot | Real-time plot of CV% vs rays for each source during simulation |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Numba @njit | Cython | Cython requires .pyx files and a C compiler at install time; Numba is pure Python install |
| Numba @njit | cupy / CUDA | CUDA excluded by project scope (packaging complexity) |
| Binary BVH | 4-wide BVH (QBVH) | QBVH is faster but significantly more complex to implement; not needed for N<200 |
| Median-split BVH build | SAH BVH build | SAH gives 10–20% better tree quality; overkill for N<200 flat rectangles |
| Detector CV% check | per-pixel variance | Per-pixel convergence (rendering-style) is complex; total-flux CV is simpler and correct for uniformity |

**Installation:**
```bash
pip install numba
pip install --upgrade pyinstaller-hooks-contrib
```

---

## Architecture Patterns

### Recommended Project Structure

```
backlight_sim/
├── sim/
│   ├── tracer.py              # Unchanged API; dispatch to JIT or NumPy
│   ├── accel.py               # NEW: JIT kernels + BVH build/traverse + try-import guard
│   └── sampling.py            # Unchanged (stays pure NumPy)
├── core/
│   └── project_model.py       # Add convergence_cv_target, adaptive_sampling, check_interval
└── gui/
    └── main_window.py         # Status bar JIT label, convergence signal, live plot widget
```

### Pattern 1: Try-Import with Eager Warmup

**What:** Import Numba conditionally at module load time; fall back to NumPy versions; trigger eager compilation at app startup by calling JIT functions with dummy arrays.
**When to use:** All JIT kernel dispatch.

```python
# sim/accel.py
try:
    from numba import njit
    _NUMBA = True
except ImportError:
    _NUMBA = False
    def njit(*args, **kwargs):          # no-op decorator
        def decorator(fn):
            return fn
        return decorator

@njit(cache=True, fastmath=True)
def _intersect_plane_jit(
    origins: np.ndarray,       # (N, 3) float64
    directions: np.ndarray,    # (N, 3) float64
    normal: np.ndarray,        # (3,)
    center: np.ndarray,        # (3,)
    u_axis: np.ndarray,        # (3,)
    v_axis: np.ndarray,        # (3,)
    half_w: float,
    half_h: float,
    epsilon: float,
) -> np.ndarray:               # (N,) float64 t-values
    n_rays = origins.shape[0]
    result = np.empty(n_rays)
    for i in range(n_rays):
        ...                    # explicit scalar loop — Numba compiles to native
    return result


def warmup_jit_kernels():
    """Call once at app startup to trigger LLVM compilation."""
    dummy_o = np.zeros((4, 3), dtype=np.float64)
    dummy_d = np.ones((4, 3), dtype=np.float64)
    dummy_n = np.array([0.0, 0.0, 1.0])
    dummy_c = np.zeros(3)
    _intersect_plane_jit(dummy_o, dummy_d, dummy_n, dummy_c, dummy_n, dummy_n, 1.0, 1.0, 1e-6)
    # ... call other JIT functions
```

### Pattern 2: Scatter-Add Replacement (np.add.at → for-loop)

**What:** `np.add.at` is not supported in Numba nopython mode. Replace with an explicit indexed for-loop, which Numba compiles to equivalent native scatter-add.
**When to use:** `_accumulate` and `_accumulate_sphere` inside JIT scope.

```python
# BEFORE (NumPy version, not JIT-able):
np.add.at(grid, (iy, ix), hit_weights)

# AFTER (Numba-compatible):
@njit(cache=True)
def _accumulate_jit(grid, iy, ix, weights):
    for k in range(weights.shape[0]):
        grid[iy[k], ix[k]] += weights[k]
```

Note: When `_accumulate_jit` runs single-threaded (default `@njit` without `parallel=True`), there is no race condition. Do NOT use `parallel=True` for accumulation — scatter-add with `prange` causes races.

### Pattern 3: Flat-Array Binary BVH

**What:** Axis-aligned bounding box (AABB) BVH stored as two parallel NumPy arrays: node bounds and node metadata. Leaf nodes store a surface index; internal nodes store child offsets.
**When to use:** When `len(all_surfaces) >= 50` at simulation start.

BVH node structure (flat arrays, not a Python tree):
```python
# bvh_bounds: (max_nodes, 6) float64  — [xmin, xmax, ymin, ymax, zmin, zmax]
# bvh_meta:   (max_nodes, 3) int32    — [left_child, right_child_or_surface_idx, tri_count]
# tri_count == 0 → internal node (left_child, right_child are node indices)
# tri_count == 1 → leaf node (left_child field = surface index in all_surfaces)
max_nodes = 2 * n_surfaces - 1

def build_bvh(surface_centers, surface_bounds):
    """Build in pure NumPy, O(N log N) median-split."""
    ...

@njit(cache=True, fastmath=True)
def traverse_bvh(
    origin, direction,
    bvh_bounds, bvh_meta,
    surf_normals, surf_centers, surf_u, surf_v, surf_hw, surf_hh,
    epsilon,
):
    """Iterative stack traversal — no Python recursion."""
    stack = np.empty(64, dtype=np.int32)   # max depth
    stack_top = 0
    stack[stack_top] = 0   # root
    best_t = np.inf
    best_surf = -1
    while stack_top >= 0:
        node_idx = stack[stack_top]
        stack_top -= 1
        # AABB slab test ...
        tri_count = bvh_meta[node_idx, 2]
        if tri_count == 1:
            si = bvh_meta[node_idx, 0]
            t = _intersect_plane_scalar(origin, direction, ...)
            if t < best_t:
                best_t = t
                best_surf = si
        else:
            # push children
            stack_top += 1; stack[stack_top] = bvh_meta[node_idx, 0]
            stack_top += 1; stack[stack_top] = bvh_meta[node_idx, 1]
    return best_t, best_surf
```

### Pattern 4: Per-Source Adaptive Stopping

**What:** Track cumulative flux and squared flux per detector per source. After every `check_interval` rays, compute I = 1.96 × σ/√n. Stop when I ≤ cv_target × μ for the total detector flux.
**When to use:** When `settings.adaptive_sampling` is True.

```python
# In the per-source emit loop:
flux_sum = 0.0
flux_sq_sum = 0.0
n_rays_traced = 0
batch_size = settings.check_interval   # e.g., 1000

while not converged and n_rays_traced < settings.rays_per_source:
    n_batch = min(batch_size, settings.rays_per_source - n_rays_traced)
    batch_flux = _trace_batch(source, n_batch)   # returns total flux this batch
    flux_sum += batch_flux
    flux_sq_sum += batch_flux ** 2
    n_rays_traced += n_batch

    if n_rays_traced >= 2 * check_interval:      # need ≥2 samples for variance
        mean = flux_sum / n_rays_traced
        variance = max(0.0, flux_sq_sum / n_rays_traced - mean ** 2)
        std = variance ** 0.5
        I = 1.96 * std / (n_rays_traced ** 0.5)
        cv_actual = I / max(mean, 1e-12)
        converged = cv_actual <= settings.convergence_cv_target / 100.0

    # Emit convergence signal for live plot
    if convergence_callback:
        convergence_callback(src_idx, n_rays_traced, cv_actual)
```

### Pattern 5: Live Variance Plot via QThread Signal

**What:** Extend `SimulationThread` to emit a second signal carrying convergence data. Wire it to a `pyqtgraph.PlotWidget` that updates each source's CV% curve.

```python
class SimulationThread(QThread):
    progress     = Signal(float)
    convergence  = Signal(int, int, float)   # NEW: (src_idx, n_rays, cv_pct)
    finished_sim = Signal(object)

    def run(self):
        result = self.tracer.run(
            progress_callback=self.progress.emit,
            convergence_callback=self.convergence.emit,   # NEW
        )
        self.finished_sim.emit(result)
```

In `MainWindow`, connect `convergence` signal to a callback that calls `plot_widget.setData(...)` — safe from the GUI thread.

### Anti-Patterns to Avoid

- **JIT-compiling sampling functions:** `sample_lambertian`, `sample_angular_distribution` use NumPy broadcasting that is already near-optimal; JIT adds compilation overhead with no gain. Stay pure NumPy for sampling.
- **Using `parallel=True` for accumulation:** Race condition on scatter-add. Only use `parallel=True` on embarrassingly parallel loops where no shared array is written by multiple threads.
- **Calling `warmup_jit_kernels()` in a QThread:** First JIT compilation must happen on the main thread before the first `RayTracer.run()` call, or the first simulation will stall while LLVM compiles.
- **Building BVH inside the Python bounce loop:** BVH must be built once before the bounce loop starts. Rebuilding per-bounce wastes all acceleration benefit.
- **Checking convergence every ray:** The variance estimate is unstable with few samples. Only check every `check_interval` (≥500) rays. The check itself is O(1) — the issue is premature termination from noisy variance.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLVM JIT | Custom C extension | numba @njit | Numba handles type inference, LLVM IR generation, caching, Python integration |
| Scatter-add thread safety | Custom atomic | Serial @njit for-loop | Serial JIT is correct and fast; no threading needed for per-source accumulation |
| PyInstaller hidden imports for Numba | Manual `--hidden-import` list | `pyinstaller-hooks-contrib` | Auto-resolved since pyinstaller-hooks-contrib 2025.1; manual list is fragile |
| Variance statistics | Custom Welford | Running sum + sum-of-squares | Simple batch estimator: var = E[x²] − E[x]² is sufficient; Welford is overkill here |

**Key insight:** The scatter-add problem (np.add.at → Numba) is the only non-trivial migration; everything else is decorator application. Do not over-engineer the BVH for N < 200 surfaces.

---

## Common Pitfalls

### Pitfall 1: np.add.at Is Silently Unsupported in Numba
**What goes wrong:** `@njit` on a function containing `np.add.at` will raise a `numba.core.errors.TypingError` at compilation time (or fall back to object mode with no speedup if `@jit` is used instead).
**Why it happens:** `np.add.at` is a NumPy ufunc unbuffered operation with no Numba equivalent in nopython mode.
**How to avoid:** Replace every `np.add.at(arr, idx, val)` with a scalar for-loop `for k in range(len(val)): arr[idx[k]] += val[k]`. Numba compiles this to native atomic-safe scatter.
**Warning signs:** No error during decoration; error appears at first JIT-call. Always smoke-test the JIT path with a small scene.

### Pitfall 2: NumPy 2.x Compatibility Window
**What goes wrong:** Numba 0.64.0 supports NumPy < 2.5. The project currently has NumPy 2.4.2, which is within range, but a future `pip install --upgrade numpy` could break Numba if NumPy 2.5 ships before Numba 0.65.
**Why it happens:** Numba pins its NumPy upper bound to the version it was tested against.
**How to avoid:** Pin `numba==0.64.0` in `requirements.txt` and note the NumPy upper bound. Use `try/except ImportError` in `accel.py` so a NumPy upgrade doesn't break the app — it just disables JIT.
**Warning signs:** `ImportError: Numba needs NumPy X or less. Got NumPy Y.` at import time.

### Pitfall 3: JIT Warmup Must Happen Before First Simulation
**What goes wrong:** If warmup is deferred to first `RayTracer.run()`, the UI freezes for 2–5 seconds on the first simulation run. With `cache=True`, this only happens once ever (after that, cached LLVM IR is loaded), but the first-ever user experience is broken.
**Why it happens:** Numba compiles on first call with new argument types. `cache=True` saves the compiled kernel to `__pycache__`, so subsequent app restarts skip compilation.
**How to avoid:** Call `warmup_jit_kernels()` during `MainWindow.__init__` (before the event loop) or in a startup splash. Log "JIT kernels compiled" to the log dock.
**Warning signs:** First simulation takes 5× longer than subsequent ones.

### Pitfall 4: BVH Stale After Scene Edit
**What goes wrong:** If the BVH is cached on the `RayTracer` instance and the user edits a surface between runs, the old BVH is used, producing wrong results.
**Why it happens:** BVH is built from surface center/bounds data; any surface edit invalidates it.
**How to avoid:** Build the BVH inside `RayTracer.run()` or `RayTracer.__init__()` — never cache it across simulation calls. The build cost (O(N log N), NumPy, N ≤ 200) is <1 ms.
**Warning signs:** Ray hit patterns differ between runs when scene is unchanged between runs (hard to detect).

### Pitfall 5: PyInstaller Needs pyinstaller-hooks-contrib Update
**What goes wrong:** Numba 0.61+ uses a `_RedirectSubpackage` mechanism that PyInstaller's static analysis cannot detect. Without updated hooks, the bundled exe fails with `ModuleNotFoundError: numba.core.types.old_scalars`.
**Why it happens:** Numba's internal module redirection is dynamic; static analysis misses it.
**How to avoid:** `pip install --upgrade pyinstaller-hooks-contrib` (≥2025.1). Also add `llvmlite` binary to the spec: llvmlite ships `llvmlite.dll` (Windows) that must be bundled.
**Warning signs:** Exe works in dev but crashes at startup on clean machines.

### Pitfall 6: Adaptive Sampling Breaks with Multiprocessing
**What goes wrong:** Per-source convergence tracking requires per-source state. In multiprocessing mode, each source runs in a separate `ProcessPoolExecutor` worker. Convergence callbacks can't cross process boundaries.
**Why it happens:** Python callbacks are not picklable.
**How to avoid:** Disable adaptive sampling in multiprocessing mode (similar to the existing spectral+MP guard). Log a warning to the log dock. Add a guard in `_run_multiprocess` before delegating to workers.
**Warning signs:** `AttributeError` or silent hang when both `use_multiprocessing=True` and `adaptive_sampling=True`.

---

## Code Examples

Verified patterns from official sources and project codebase inspection:

### @njit with cache and fastmath (Numba official docs)
```python
# Source: https://numba.readthedocs.io/en/stable/user/jit.html
from numba import njit
import numpy as np

@njit(cache=True, fastmath=True)
def intersect_plane_scalar(ox, oy, oz, dx, dy, dz,
                            nx, ny, nz, cx, cy, cz,
                            ux, uy, uz, vx, vy, vz,
                            hw, hh, epsilon):
    """Single ray against single plane. Called inside BVH traversal loop."""
    denom = dx * nx + dy * ny + dz * nz
    if abs(denom) < 1e-12:
        return np.inf
    d_plane = nx * cx + ny * cy + nz * cz
    t = (d_plane - (ox * nx + oy * ny + oz * nz)) / denom
    if t <= epsilon:
        return np.inf
    hx = ox + dx * t - cx
    hy = oy + dy * t - cy
    hz = oz + dz * t - cz
    u = hx * ux + hy * uy + hz * uz
    v = hx * vx + hy * vy + hz * vz
    if abs(u) <= hw and abs(v) <= hh:
        return t
    return np.inf
```

### Flat BVH Node Array (no external library)
```python
# Source: research synthesis from https://jacco.ompf2.com/2022/04/13/how-to-build-a-bvh-part-1-basics/
import numpy as np

def build_bvh_flat(surface_aabbs):
    """
    surface_aabbs: (N, 6) float64 — [xmin, xmax, ymin, ymax, zmin, zmax]
    Returns:
      node_bounds: (2N-1, 6) float64
      node_meta:   (2N-1, 3) int32  — [left_or_surf_idx, right_child, is_leaf]
    """
    N = len(surface_aabbs)
    max_nodes = 2 * N - 1
    node_bounds = np.zeros((max_nodes, 6), dtype=np.float64)
    node_meta   = np.zeros((max_nodes, 3), dtype=np.int32)
    # Recursive build using a stack of (node_idx, surface_indices)
    # ... median split along longest AABB axis
    return node_bounds, node_meta
```

### Adaptive Convergence Check
```python
# Source: Berkeley CS184 adaptive sampling algorithm (https://cs184.eecs.berkeley.edu/sp21/docs/proj3-1-part-5)
def check_convergence(flux_sum, flux_sq_sum, n_rays, cv_target):
    """
    Returns (converged: bool, cv_actual: float).
    cv_target: fractional (e.g., 0.02 for 2%)
    """
    if n_rays < 2:
        return False, 1.0
    mean = flux_sum / n_rays
    if mean < 1e-12:
        return True, 0.0   # no flux — trivially converged
    variance = max(0.0, flux_sq_sum / n_rays - mean * mean)
    std = variance ** 0.5
    I = 1.96 * std / (n_rays ** 0.5)
    cv_actual = I / mean
    return cv_actual <= cv_target, cv_actual
```

### Try-Import Guard (canonical Python pattern)
```python
# sim/accel.py — top of file
try:
    from numba import njit as _njit
    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False
    def _njit(*args, **kwargs):
        """No-op decorator when Numba is not installed."""
        def wrapper(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]   # called as @_njit without arguments
        return wrapper
```

### PyInstaller Spec Update for Numba
```python
# BluOpticalSim.spec — additions required
hidden_imports = [
    # ... existing imports ...
    # Numba (hooks-contrib handles the old_* redirects automatically)
    "numba",
    "numba.core",
    "numba.typed",
    "llvmlite",
]

binaries = [
    # llvmlite ships a DLL that PyInstaller won't find automatically
    # Path varies by Python env — use glob to locate
]
# NOTE: ensure pyinstaller-hooks-contrib >= 2025.1 is installed;
# it handles numba's _RedirectSubpackage modules automatically.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@jit(nopython=True)` | `@njit` (same since 0.59) | Numba 0.59 (Jan 2024) | Simpler syntax; no behavior change |
| `@jit` with object mode fallback | `@njit` (nopython=True default) | Numba 0.59 | Guarantees compiled native code; no silent slowdown |
| Separate hidden imports list for Numba in PyInstaller | `pyinstaller-hooks-contrib` ≥ 2025.1 | Jan 2025 | Eliminates 13+ manual hidden imports; `old_*` modules resolved automatically |
| Single fixed rays_per_source | Adaptive stopping with CV threshold | This phase | Reduces over-sampling for easy sources; similar final accuracy with fewer rays |

**Deprecated/outdated:**
- Manual Numba hidden imports: Replaced by `pyinstaller-hooks-contrib` 2025.1 hooks. Don't add `numba.core.types.old_scalars` etc. manually.
- `@jit(nopython=False)` (object mode): Never use — produces no speedup and silently falls back.

---

## Open Questions

1. **NumPy 2.4.2 vs Numba 0.64.0 compatibility**
   - What we know: Numba 0.64.0 supports NumPy up to <2.5 (per official install docs, Feb 2026)
   - What's unclear: NumPy 2.5 release timeline; could break Numba at next `pip upgrade`
   - Recommendation: Pin `numba==0.64.0` and `numpy>=2.0,<2.5` in requirements.txt until Numba 0.65 is released

2. **llvmlite.dll bundling path in PyInstaller spec**
   - What we know: llvmlite ships a native DLL that must be explicitly added to `binaries` in the spec
   - What's unclear: Exact path varies by environment; `pyinstaller-hooks-contrib` may handle it but not confirmed for 0.64.0
   - Recommendation: Wave 0 task should verify DLL bundling on a clean Windows install; add explicit binaries fallback in spec

3. **Adaptive sampling + spectral mode interaction**
   - What we know: Spectral mode accumulates per-wavelength bins; the adaptive convergence check is on total detector flux
   - What's unclear: Whether total-flux convergence is sufficient for spectral accuracy or if per-bin CV should be checked
   - Recommendation: Use total-flux convergence as the primary criterion; document as known limitation; spectral+adaptive requires more rays for color accuracy

4. **BVH benefit threshold**
   - What we know: BVH is activated at 50+ surfaces; typical LGP scene has 6 box faces + 5 walls + 1 diffuser + 1 detector ≈ 13 surfaces
   - What's unclear: At what surface count does BVH traversal overhead exceed naive loop benefit on the current codebase
   - Recommendation: Implement with configurable threshold (default 50); benchmark after implementation

---

## Validation Architecture

*Note: `workflow.nyquist_validation` is not set in `.planning/config.json` (key absent). Treating as false — skipping formal validation architecture section. Existing pytest infrastructure covers regression testing.*

**Test command (existing):** `pytest backlight_sim/tests/test_tracer.py`

**Phase 3 test strategy:**
- Existing 20 tests must still pass after JIT integration (regression gate)
- Add tests: JIT-path produces same results as NumPy-path (within tolerance) for a fixed-seed scene
- Add tests: Adaptive sampling converges to same detector flux as fixed-ray-count run (within 5%)
- BVH correctness: BVH traversal hits same surfaces as naive loop for a 60-surface scene

---

## Sources

### Primary (HIGH confidence)
- [Numba Install Docs (Feb 2026)](https://numba.readthedocs.io/en/stable/user/installing.html) — version 0.64.0, Python/NumPy compatibility matrix
- [Numba JIT Docs](https://numba.readthedocs.io/en/stable/user/jit.html) — @njit, cache=True, eager compilation, @jit vs @njit equivalence since 0.59
- [Numba Performance Tips](https://numba.readthedocs.io/en/stable/user/performance-tips.html) — fastmath, parallel=True, loop vs vectorized equivalence
- [Numba Parallel Docs](https://numba.readthedocs.io/en/stable/user/parallel.html) — supported reductions, race condition warnings for scatter-add with prange
- [Numba Supported NumPy features](https://numba.readthedocs.io/en/stable/reference/numpysupported.html) — confirms np.add.at NOT supported in nopython mode
- [PyPI numba 0.64.0](https://pypi.org/project/numba/) — latest stable version, Python wheel availability
- [Berkeley CS184 Adaptive Sampling](https://cs184.eecs.berkeley.edu/sp21/docs/proj3-1-part-5) — I-statistic formula, convergence algorithm
- [BVH Part 1: Basics (Jacco)](https://jacco.ompf2.com/2022/04/13/how-to-build-a-bvh-part-1-basics/) — flat array BVH structure, node encoding, dual-purpose leftFirst/triCount

### Secondary (MEDIUM confidence)
- [GitHub numba/numba issue #9844](https://github.com/numba/numba/issues/9844) — PyInstaller hidden import issue with Numba 0.61+; resolved by pyinstaller-hooks-contrib 2025.1
- [pyinstaller-hooks-contrib resolution](https://github.com/numba/numba/issues/9844) — confirmed auto-resolution in hooks-contrib 2025.1

### Tertiary (LOW confidence)
- WebSearch results on BVH SAH vs median-split for small N — community consensus, not official benchmark
- WebSearch results on pyqtgraph real-time PlotWidget update patterns — community tutorials

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Numba 0.64.0 verified via official install page (Feb 2026); np.add.at unsupport verified via NumPy supported features page
- Architecture: HIGH — try-import pattern well-established; BVH flat-array structure from authoritative source (Jacco BVH series); adaptive sampling I-statistic from CS184 course
- Pitfalls: HIGH — np.add.at unsupport verified; PyInstaller hook resolution verified from GitHub issue; NumPy version window verified from install docs

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (30 days — NumPy/Numba compatibility is stable; PyInstaller hooks resolved)
