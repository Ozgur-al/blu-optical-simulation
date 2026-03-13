# Codebase Concerns

**Analysis Date:** 2025-03-14

## Tech Debt

**Diffuse reflection batch approximation:**
- Issue: When many rays with different oriented normals hit a diffuse surface, the tracer uses a "majority normal approximation" for n > 32 rays, applying a single Lambertian sample to all rays.
- Files: `backlight_sim/sim/tracer.py` lines 543–559 (`_reflect_batch()` function)
- Impact: Diffuse reflection accuracy degradation at high ray counts per bounce. Incorrect scattering direction for rays not aligned with majority normal.
- Fix approach: Replace with true per-ray diffuse reflection loop (trade accuracy for performance), or implement a grouping strategy that clusters rays by normal orientation.

**Multiprocessing mode disables ray path visualization:**
- Issue: When `use_multiprocessing=True`, ray paths are not recorded (see `tracer.py` line 48). Path recording is disabled entirely in multiprocessing mode because each source runs in a separate process and collecting path data across process boundaries is non-trivial.
- Files: `backlight_sim/sim/tracer.py` lines 45–49 (condition check), line 105 (n_record = 0 in MP mode)
- Impact: Users cannot visualize ray paths when using multiprocessing for faster simulations. Design trade-off limits debugging capability.
- Fix approach: Implement inter-process communication to collect first-N paths from each worker, or record paths in single-threaded mode only and warn user.

**Hardcoded epsilon value for ray offset:**
- Issue: All ray-surface intersections use a fixed `_EPSILON = 1e-6` to offset ray origins after bounces. This value is not configurable and may be too small for some geometries or too large for others.
- Files: `backlight_sim/sim/tracer.py` line 29
- Impact: Risk of self-intersection artifacts (rays re-hitting same surface) or missed intersections for very small/large scale models. No user control.
- Fix approach: Make epsilon configurable in `SimulationSettings`, or scale adaptively based on scene bounds.

**Spectral wavelength sampling fallback is silent:**
- Issue: When a source has `spd` set to an unknown value (e.g., user typo like "warm_whit"), `get_spd()` silently falls back to white, and sampling proceeds.
- Files: `backlight_sim/sim/spectral.py` lines 99–105
- Impact: User may not realize their custom SPD was not loaded; silent failure masks configuration errors.
- Fix approach: Log warning or raise exception on invalid SPD name; validate at load time.

**No input validation for geometry axes:**
- Issue: `Rectangle` and `DetectorSurface` assume u_axis and v_axis are orthonormal. If a user loads a corrupted project file or modifies data directly, non-orthogonal axes will cause incorrect binning and intersection calculations.
- Files: `backlight_sim/core/geometry.py` lines 24–32 (normalization only, no orthogonality check)
- Impact: Silent numerical errors in ray binning and intersection math if axes drift out of orthogonality.
- Fix approach: Add `__post_init__()` assertions that u_axis ⊥ v_axis and both are unit vectors; raise on load.

**No range checks for simulation parameters:**
- Issue: `SimulationSettings` fields (rays_per_source, max_bounces, energy_threshold) accept any float/int without validation. Pathological values like 0 rays, negative bounces, or energy_threshold > 1 are not caught.
- Files: `backlight_sim/core/project_model.py` lines 12–21
- Impact: Simulation produces silent failures or misleading results with invalid parameters. No error feedback at load time.
- Fix approach: Add dataclass validators (e.g., via `__post_init__()` or custom descriptor) to enforce ranges: rays_per_source >= 1, max_bounces >= 1, 0 < energy_threshold <= 1.

---

## Known Bugs

**Euler angle extraction may fail for gimbal-lock edge cases:**
- Symptoms: When rotating a surface/detector to certain orientations (Ry ≈ ±90°), the Euler angle decomposition may produce ambiguous results or numerical instability.
- Files: `backlight_sim/gui/properties_panel.py` lines 58–69 (`_euler_xyz_from_matrix()`)
- Trigger: Rotate surface to a vertical orientation (e.g., Ry = 90°), then read back the rotation angles in properties panel.
- Workaround: Avoid exact gimbal-lock angles; use small offset (e.g., 89.9°).

**Spectral grid accumulation has dimension mismatch in edge case:**
- Symptoms: If `wavelengths` is None but `spec_centers` is not (or vice versa), the spectral accumulation logic skips, and spectral grids remain zeros.
- Files: `backlight_sim/sim/tracer.py` lines 682–689 (`_accumulate()` function)
- Trigger: Enable spectral mode (has_spectral=True) but source has spd="white" (no wavelengths sampled).
- Workaround: Ensure all sources have non-white SPD if spectral mode is enabled.

**Angular distribution CDF inversion may extrapolate beyond theta range:**
- Symptoms: If a custom angular distribution has theta_deg = [0, 45, 90] and user loads an IES file with data only out to 60°, CDF inversion for uniform random samples may extrapolate, producing erratic sampling beyond 90°.
- Files: `backlight_sim/sim/sampling.py` (CDF inversion via numpy.interp uses edge values)
- Trigger: Load custom angular distribution with limited theta range, then run simulation.
- Workaround: Ensure angular distributions cover full 0–90° range (pad with zeros if needed).

---

## Security Considerations

**No JSON schema validation on project load:**
- Risk: Malformed or malicious `.json` project files could contain unexpected field types (e.g., string instead of float) or missing fields, leading to crashes or incorrect behavior during load.
- Files: `backlight_sim/io/project_io.py` lines 229–256 (`load_project()`)
- Current mitigation: `.get(key, default)` fallbacks provide some protection; dataclass construction validates types.
- Recommendations: Add explicit type checking and schema validation (e.g., via `jsonschema` library) before deserializing; log warnings for missing/unexpected fields.

**Environment configuration not validated:**
- Risk: `.env` files or environment variables are not validated for correctness or safe ranges (though this app has minimal external configuration).
- Files: `.env` not currently used (if it exists, it's ignored in code)
- Recommendations: Document expected env var format if configuration is added; use a validation library.

**No bounds checking on detector resolution:**
- Risk: A user could create a detector with resolution=(100000, 100000), causing memory exhaustion or slow allocation.
- Files: `backlight_sim/core/detectors.py` line 88 (no check in DetectorSurface.__init__())
- Current mitigation: GUI spinboxes have reasonable max values (up to 1000).
- Recommendations: Add validation in dataclass to cap resolution (e.g., max 2048×2048).

---

## Performance Bottlenecks

**Ray–surface intersection is O(surfaces × rays):**
- Problem: For each bounce, every active ray is tested against every surface and detector. With 10k rays, 50 surfaces, and 50 bounces, this is millions of intersection tests.
- Files: `backlight_sim/sim/tracer.py` lines 218–239 (nested loop over surfaces/detectors)
- Cause: Brute-force spatial search; no acceleration structure (BVH, KD-tree).
- Improvement path: Implement bounding volume hierarchy (BVH) or spatial grid to cull non-intersecting surfaces; Phase 2+ feature.

**Progress callback overhead in tight loop:**
- Problem: Progress callback is emitted every source (line 296), which may trigger Qt signal processing overhead. With 100 sources and slow callbacks, simulation may stall.
- Files: `backlight_sim/sim/tracer.py` line 296
- Cause: Callback not rate-limited; called once per source regardless of frequency.
- Improvement path: Throttle progress updates (e.g., emit every 5 sources or 500ms wall-clock time).

**Spectral accumulation loop over bins is slow:**
- Problem: For each spectral bin, a separate `np.add.at()` call is made, introducing Python loop overhead.
- Files: `backlight_sim/sim/tracer.py` lines 686–689 (loop over n_bins)
- Cause: Vectorization not fully exploited; per-bin accumulation instead of vectorized binning.
- Improvement path: Pre-bin wavelengths once per bounce, then vectorized accumulation; use `np.add.at()` with pre-computed indices.

**Deep copy of entire project on each sweep step:**
- Problem: Parameter sweep creates a `copy.deepcopy(base_project)` for every step (100+ steps × full project = expensive).
- Files: `backlight_sim/gui/parameter_sweep_dialog.py` line 90
- Cause: Ensures isolation; avoids state mutation bugs.
- Improvement path: Implement shallow copy strategy with mutation rollback, or create lightweight parameter-only copies.

---

## Fragile Areas

**Properties panel state synchronization:**
- Files: `backlight_sim/gui/properties_panel.py` (entire file, ~1000 lines)
- Why fragile: Panel uses many `_loading` guards and `blockSignals()` calls to prevent value leakage during updates. Any new field added to a data model must be wired into the form, and signal order matters. Easy to introduce feedback loops or missed updates.
- Safe modification: Always use `_loading` guard for form value changes; test with object tree selection changes and direct property edits.
- Test coverage: No dedicated unit tests for properties panel synchronization; coverage gap.

**Multiprocessing seed derivation:**
- Files: `backlight_sim/sim/tracer.py` lines 391–394 (`_trace_single_source()`)
- Why fragile: Seed derived via MD5 hash of source name + base seed. If source naming changes or hash collisions occur (unlikely but possible), reproducibility breaks silently.
- Safe modification: Use deterministic hash only; document seed derivation. Consider explicit per-source seed array instead.
- Test coverage: No test for multiprocessing determinism; should add.

**Euler angle rotation round-tripping:**
- Files: `backlight_sim/gui/properties_panel.py` lines 47–92 (rotation matrix ↔ Euler conversions)
- Why fragile: Round-trip conversions between rotation matrix and Euler angles can accumulate error. Gimbal-lock edge cases not handled gracefully.
- Safe modification: Validate that rotation matrices are orthonormal before extraction; add unit tests for round-trip error.
- Test coverage: No test for rotation round-tripping; only visual inspection in GUI.

**Angular distribution interpolation for non-standard theta ranges:**
- Files: `backlight_sim/sim/sampling.py` (CDF inversion)
- Why fragile: `sample_angular_distribution()` builds a CDF from user-supplied theta values. If theta is non-uniform (e.g., [0, 10, 90]) or sparse, interpolation may produce unexpected results.
- Safe modification: Validate theta_deg is sorted and covers expected range; add warning for sparse/irregular distributions.
- Test coverage: Tests exist for basic sampling (test_custom_angular_distribution_sampling_points_forward) but not for edge cases.

---

## Scaling Limits

**Ray path recording memory grows linearly with rays:**
- Current capacity: Storing first N=200 rays × up to 50 bounces = 10k path points per source.
- Limit: At 100 sources × 10k points × 3 floats = ~12 MB per result. Multiple results in history → memory creep (capped at 20 history entries = ~240 MB).
- Scaling path: Implement streaming visualization or GPU-side path rendering; limit ray path recording to a max memory budget.

**Detector grid resolution is squared:**
- Current capacity: 1000×1000 detector = 1 million values per detector = ~8 MB float64. With 5 detectors + RGB + spectral: ~120 MB per result.
- Limit: Memory exhaustion or swap if user requests 4000×4000 detector (128 MB per detector).
- Scaling path: Implement sparse grid representation or out-of-core accumulation.

**Simulation history capped at 20 snapshots:**
- Current capacity: 20 projects × ~500 KB/project (typical) = 10 MB.
- Limit: Soft cap; no auto-cleanup. User must manually "Clear History" to reclaim memory.
- Scaling path: Implement LRU eviction or compression; offer configurable cap.

---

## Dependencies at Risk

**NumPy version compatibility:**
- Risk: Code uses `np.random.default_rng()` (NumPy 1.19+) and assumes float64 array math. Older NumPy versions will break silently.
- Files: `backlight_sim/sim/tracer.py`, `backlight_sim/sim/sampling.py`, throughout codebase
- Impact: Incompatible with NumPy < 1.19.
- Migration plan: Document minimum NumPy version in `requirements.txt`; consider pinning (e.g., `numpy>=1.19,<2.0`).

**PySide6 breaking changes in major releases:**
- Risk: Signal/slot APIs and widget construction may change in PySide6 v7+. Current code targets PySide6 v6.x.
- Files: All `backlight_sim/gui/*.py` files
- Impact: Potential breakage on Qt library upgrade.
- Migration plan: Test against latest PySide6 nightly; pin version in requirements.txt (e.g., `PySide6>=6.0,<7.0`).

**pyqtgraph undocumented internals:**
- Risk: Heatmap rendering relies on `ImageItem`, `ColorBarItem`, and `RectROI` APIs that are relatively stable but not officially versioned.
- Files: `backlight_sim/gui/heatmap_panel.py` lines 105–122
- Impact: GUI may break if pyqtgraph major version changes.
- Migration plan: Pin pyqtgraph version; monitor upstream releases.

**IES/LDT file format parsing is fragile:**
- Risk: Parser assumes specific line/column formats per IESNA LM-63 spec. Malformed files may cause IndexError or ValueError without informative error messages.
- Files: `backlight_sim/io/ies_parser.py` lines 29–128
- Impact: Silent failure or cryptic error when parsing non-compliant IES/LDT files.
- Migration plan: Implement more robust line-by-line parsing with detailed error reporting.

---

## Missing Critical Features

**No undo/redo system:**
- Problem: User changes (e.g., surface rotation, material edit) are applied immediately without undo. Design history snapshots are coarse-grained (full project) and manual.
- Blocks: Rapid design iteration; risky to make changes without saving.
- Path: Implement command pattern with undo/redo stack; integrate with design history.

**No live simulation preview during parameter editing:**
- Problem: User must click "Run Simulation" after every change. No real-time feedback.
- Blocks: Fast design exploration; users can't see impact of parameter changes in real-time.
- Path: Implement progressive/streaming simulation with low-resolution live preview; show KPI updates as rays accumulate.

**No constraint/validation UI for geometry:**
- Problem: Geometry builder accepts arbitrary dimensions without checking physical feasibility (e.g., 0-depth cavity, negative offsets).
- Blocks: Users can create invalid scenes that fail silently.
- Path: Add real-time validation UI with warnings/errors for invalid configurations.

---

## Test Coverage Gaps

**Multiprocessing simulation is not tested:**
- What's not tested: `_run_multiprocess()` and `_trace_single_source()` code paths; determinism with multiprocessing.
- Files: `backlight_sim/sim/tracer.py` lines 53–96, 386–540
- Risk: Multiprocessing mode could silently produce incorrect results (e.g., seed derivation bug, lost detector grid merges).
- Priority: High — multiprocessing is user-facing feature.

**Spectral simulation is not tested:**
- What's not tested: `has_spectral=True` path; wavelength sampling and binning; spectral-to-RGB conversion.
- Files: `backlight_sim/sim/tracer.py` lines 107–124, 182–186, 682–689; `backlight_sim/sim/spectral.py` all
- Risk: Spectral features added to tracer but no tests verify correctness.
- Priority: Medium — spectral is Phase 2+ feature, not fully implemented.

**Geometry builder is not tested:**
- What's not tested: `build_cavity()`, `build_led_grid()`, `build_optical_stack()` functions; tilted wall corner cases.
- Files: `backlight_sim/io/geometry_builder.py`
- Risk: Geometry changes (wall angles, LED pitch auto-calculation) are not validated by tests.
- Priority: Medium — GUI tests are manual; pure logic should have unit tests.

**Properties panel round-tripping:**
- What's not tested: Reading/writing properties via panel; rotation angle round-trip; signal blocking logic.
- Files: `backlight_sim/gui/properties_panel.py` (all)
- Risk: Panel state corruption (e.g., form not updating after selection change, signal feedback loops).
- Priority: Medium — GUI tests are hard; consider integration tests for critical paths.

**Error handling paths:**
- What's not tested: Load corrupted JSON, load IES with invalid format, empty project simulation, zero flux.
- Files: `backlight_sim/io/project_io.py`, `backlight_sim/io/ies_parser.py`
- Risk: Error conditions fail with unhelpful messages or crash.
- Priority: Low — some happy-path tests exist; error paths are defensive.

---

*Concerns audit: 2025-03-14*
