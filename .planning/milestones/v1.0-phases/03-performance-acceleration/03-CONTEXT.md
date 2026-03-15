# Phase 3: Performance Acceleration - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the Monte Carlo tracer 10-50x faster via Numba JIT compilation, add BVH spatial acceleration for scenes with 50+ surfaces, and implement adaptive sampling that auto-stops ray generation when detector variance converges. Pure performance — no new simulation physics or geometry types.

</domain>

<decisions>
## Implementation Decisions

### Numba dependency
- Numba is an **optional** dependency — try-import with graceful fallback to pure NumPy
- App shows a **status bar indicator** ("JIT: Active" / "JIT: Off") so users can see acceleration state at a glance
- **Eager compile at startup** — JIT kernels compile when the app launches (2-5s startup cost) so first simulation runs at full speed
- **Bundle Numba in PyInstaller exe** — users get acceleration out of the box despite larger executable size

### Adaptive sampling UX
- Convergence threshold exposed as a **SimulationSettings field** (e.g., CV% target), with quality presets (Quick/Standard/High) setting sensible defaults that users can override
- **Per-source** adaptive stopping — each source independently halts when its detector contribution converges; sources illuminating small areas stop early
- **Live variance plot** during simulation — real-time display of detector CV% dropping, so users can watch convergence
- **Enabled by default** — adaptive sampling is on for all simulations; users who want exact ray counts can disable via checkbox in SimSettings

### JIT compilation scope
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

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_intersect_rays_plane()` (tracer.py:576-616): Pure NumPy vectorized intersection — direct candidate for Numba @njit conversion
- `_intersect_rays_sphere()` (tracer.py:619-645): Pure NumPy sphere intersection — same pattern, straightforward to JIT
- `_accumulate()` / `_accumulate_sphere()`: Uses `np.add.at` for scatter-add — needs Numba-compatible replacement
- `SimulationSettings` (core/project_model.py): Already has quality-related fields — natural place for convergence_threshold and adaptive_sampling toggle
- Multiprocessing infrastructure in `_run_multiprocess()`: Already handles per-source parallel execution — adaptive stopping integrates here

### Established Patterns
- Semi-vectorized tracer: NumPy arrays for all rays per bounce, Python loop over bounces — JIT replaces the per-bounce inner work
- Progress callback pattern: `progress_callback(float)` via QThread signal — extend for convergence feedback
- Try-import pattern: Not yet used in project, but standard Python idiom for optional deps

### Integration Points
- `tracer.py` bounce loop (lines 217-303): Core loop that calls intersection/accumulation — will dispatch to JIT or NumPy versions
- `main_window.py` SimulationThread: Needs to relay convergence data for live variance plot
- `heatmap_panel.py` or new widget: Live variance plot display during simulation
- `build_exe.py`: PyInstaller spec needs Numba + llvmlite hidden imports
- Status bar in main_window.py: Add JIT status indicator

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-performance-acceleration*
*Context gathered: 2026-03-14*
