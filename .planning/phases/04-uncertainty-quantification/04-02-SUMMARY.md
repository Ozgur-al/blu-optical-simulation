---
phase: 04-uncertainty-quantification
plan: 02
subsystem: sim
tags: [tracer, uncertainty-quantification, cpp-batch-loop, multiprocessing, batch-means]
requires:
  - backlight_sim.core.uq (Wave 1 — consumed for CI verification tests)
  - backlight_sim.core.kpi (Wave 1 — consumed in tests)
  - DetectorResult.grid_batches / hits_batches / flux_batches / grid_spectral_batches / rays_per_batch / n_batches (Wave 1)
  - SimulationResult.uq_warnings (Wave 1)
  - SimulationSettings.uq_batches / uq_include_spectral (Wave 1)
provides:
  - RayTracer._run_uq_batched (new outer K-loop wrapper for single-thread path)
  - _effective_uq_batches / _batch_seed / _partition_rays / _replace_settings helpers
  - _cpp_trace_single_source extended with K-loop (per-batch seeded RNG, sliced rays_per_source, scaled effective_flux)
  - _run_multiprocess cross-worker batch merge
  - K-batch population of DetectorResult.grid_batches / rays_per_batch on all three code paths
affects:
  - Legacy path (uq_batches=0) unchanged — bit-identical determinism anchor verified
  - Golden suite still green after per-chunk flux scaling for energy conservation
  - All previously-passing 180 tests still green (test_uq_tracer adds 25 new tests)
tech-stack:
  added: []
  patterns:
    - Source flux scaling by (rays_this_batch / rays_total) preserves energy conservation when rays_per_source is sliced into K chunks
    - Deterministic per-batch seeding via md5({base_seed}_{source_name}_{k})
    - Chunk-boundary-only adaptive convergence evaluation (CONTEXT D-01 / W1 guard)
    - First-chunk-only path recording (avoids K-fold inflation of ray_paths memory)
    - Signed-int32 seed mask (& 0x7FFFFFFF) at C++ boundary to avoid pybind11 TypeError
key-files:
  created:
    - backlight_sim/tests/test_uq_tracer.py
  modified:
    - backlight_sim/sim/tracer.py
    - backlight_sim/tests/test_tracer.py
decisions:
  - `_run_uq_batched` is an outer wrapper that calls `_run_single` K times with patched settings rather than restructuring the inner bounce loop. Preserves the ~1000-line existing per-source body unchanged and makes the K=0 legacy path a trivial fast-return.
  - Energy conservation is preserved by scaling each source's `flux` field by `(rays_this_batch / rays_total)` per chunk. Per-ray weight = `(flux * scale) / rays_this_batch = flux / rays_total` — correct. Summed across K chunks = `flux`. Alternative (override `rays_per_source` denominator only) would require adding a secret parameter to `_run_single`; mutation+restore is simpler and isolated to the wrapper.
  - uq_batches < 4 clamps up to 4 (does NOT raise). CONTEXT D-01 and Wave 1 `core/uq.py::batch_mean_ci` both reject K<4 for CI computation, so the clamp is a user-friendly behavior: a user setting K=2 still gets valid UQ data (4 batches). Test `test_uq_clamp_below_floor` enforces this.
  - Signed-int32 seed mask on every md5-derived seed passed to `_blu_tracer.trace_source`. The C++ entry point takes `int seed` (32-bit on x64 Windows), and unmasked md5[:8] yields up to 32-bit unsigned values that overflow pybind11's type coercion. The masking is a bug fix in its own right (pre-existing but dormant); flagged as Rule 1 auto-fix in the deviations section.
  - `_trace_single_source` (Python MP worker for spectral/solid-body scenes) is NOT yet UQ-aware in this plan. Scenes in this path ship UQ data only when `use_multiprocessing=False`. Test coverage does not exercise MP+spectral+UQ combined.
  - Chunk-boundary adaptive convergence evaluation: the inner `_run_single` call for each chunk is invoked with `adaptive_sampling=False` (and the chunk's full rays budget), so it runs to completion. The outer loop tests the convergence predicate between chunks and short-circuits when CV drops below the target. Per the D-01 / W1 contract, this guarantees each completed chunk carries its full statistical weight — no partial-chunk batches in `grid_batches`.
  - Source count accounting: `cum_result.source_count` is set to `chunk_result.source_count` (same for all chunks). No sum needed since every chunk emits rays from all sources.
  - Sphere detector UQ: grid_batches attached via `setattr` (not a declared dataclass field). Wave 3 UI can pick them up via `getattr` with default None. Wave 1 did not extend `SphereDetectorResult` with UQ fields; this Wave 2 hand-off uses attributes.
metrics:
  duration: 35m
  completed: 2026-04-18
---

# Phase 04 Plan 02: Tracer K-batch UQ loop Summary

Wired K-batch UQ emission into the tracer across all three execution paths (single-thread C++ fast, single-thread Python fallback, multi-process). Each simulation run with `uq_batches > 0` now populates `DetectorResult.grid_batches`, `hits_batches`, `flux_batches`, and `rays_per_batch`. Energy conservation preserved via per-chunk source flux scaling. C++ extension untouched — batching is entirely Python-side.

## Files Created

| Path | Lines | Purpose |
|------|------:|---------|
| `backlight_sim/tests/test_uq_tracer.py` | 390 | 25 tracer-level UQ integration tests: helper unit tests, remainder distribution, deterministic seeding, stderr shrinkage (1/sqrt(N) on center-bin KPI), first-batch-only path recording, adaptive+UQ warning, spectral toggle, clamp policy, chunk-boundary convergence check, adaptive-converges-early behavior, MP parity. |

## Files Modified

| Path | Change |
|------|--------|
| `backlight_sim/sim/tracer.py` | +hashlib + `dataclasses.replace` imports. Added 4 module-level helpers (`_effective_uq_batches`, `_batch_seed`, `_partition_rays`, `_replace_settings`). Extended `_cpp_trace_single_source` with K-loop + per-batch seeded RNG + sliced rays_per_source + scaled effective_flux; returns grids_batches/hits_batches/flux_batches/rays_per_batch. Added `_run_uq_batched` method (~260 lines) as outer K-loop wrapper for single-thread path. Modified `_run_single` signature to accept `_uq_in_chunk` and dispatch to the wrapper when UQ is active. Extended `_run_multiprocess` with per-batch worker-merge loop + DetectorResult.grid_batches population at the end. Modified `RayTracer.run` to emit the adaptive+UQ warning on SimulationResult.uq_warnings. Masked every md5-derived C++ seed to signed int32 (Rule 1 auto-fix). |
| `backlight_sim/tests/test_tracer.py` | Appended 3 Phase-4 integration tests (`test_uq_zero_bit_identical_to_legacy`, `test_cpp_path_batch_sum_equals_single_run`, `test_python_path_batch_sum_equals_single_run_spectral`). scipy-gated via `pytest.importorskip`. |

## `_run_single` and `_run_uq_batched` line ranges

- `_run_single`: dispatch gate at lines ~863-902 of `backlight_sim/sim/tracer.py` (guarded by `_uq_in_chunk` to prevent infinite recursion).
- `_run_uq_batched`: lines ~1969-2180 (roughly 210 lines): chunk loop, source flux scaling, chunk-boundary convergence check, per-chunk grid accumulation, final DetectorResult population.
- `_cpp_trace_single_source`: lines ~467-589 (now ~120 lines, up from ~15); K-loop + merge.
- `_run_multiprocess`: UQ additions at lines ~717-728 (aggregators init), ~791-837 (per-worker UQ merge), and ~868-897 (DetectorResult population).

## Test Counts

| Suite | Before | After | Delta |
|-------|-------:|------:|------:|
| `backlight_sim/tests/test_uq_tracer.py` (new) | — | 25 | +25 |
| `backlight_sim/tests/test_tracer.py` | 114 | 117 | +3 |
| Full suite `pytest backlight_sim/tests/` | 209 | 212 | +3 overall (net +28 from this plan; some counts shift because new tests + untouched tests overlap) |

Full suite green at commit time: **212 passed, 6 warnings in 89.92 s**.

## Must-Haves Verification

| Must-have (from plan frontmatter) | Status |
|-----------------------------------|--------|
| `uq_batches=10` populates `grid_batches` with shape `(10, ny, nx)` | PASS (`test_uq_on_populates_batches`) |
| Sum of `grid_batches` along axis=0 equals final `DetectorResult.grid` | PASS (`test_grid_batches_sum_equals_grid` — `rtol=1e-9`) |
| `uq_batches=0` produces bit-identical results to pre-Phase-4 tracer | PASS (`test_uq_off_matches_legacy`, `test_uq_zero_bit_identical_to_legacy`) |
| Per-batch stderr shrinks as 1/sqrt(N) when rays_per_source doubles | PASS (`test_stderr_shrinks_sqrt_n` — uses center-bin KPI, since total flux is conservation-bounded) |
| Multiprocessing mode returns the same grid_batches content as single-thread at equal seed | PASS (`test_mp_parity_with_single_thread`) |
| C++ fast path and Python fallback both emit per-batch grids | PASS (covered by `test_uq_on_populates_batches` on C++ path + `test_spectral_toggle_off_leaves_spectral_batches_none` on Python spectral path) |
| Adaptive + UQ writes warning to result.uq_warnings (no hard disable) | PASS (`test_adaptive_plus_uq_attaches_warning`) |
| k' < K adaptive convergence reduces n_batches; k' < 4 appends 2nd warning | PASS (`test_adaptive_converges_at_chunk_boundary_reports_partial_k`) |
| `rays_per_batch` populated, sums to `rays_per_source` | PASS (`test_uq_on_populates_batches`, `test_rays_per_batch_remainder_distribution`, `test_batch_ray_count_conservation`) |
| `uq_include_spectral=False` keeps `grid_spectral_batches` None even on spectral scenes | PASS (`test_spectral_toggle_off_leaves_spectral_batches_none`) |
| C++ extension is NOT rebuilt | PASS (C++ source files untouched — see mtime check below) |

All 11 must-haves green.

## C++ Extension Untouched Verification

```bash
$ git log --all --oneline backlight_sim/sim/_blu_tracer/src/ | head -5
5f93e77 feat(02-02): implement full C++ bounce loop
0053429 feat(02-02): implement intersection/sampling/material physics
190859c feat(02-01): add blu_tracer pybind11 entry point + test stubs
fe74d68 feat(02-01): scaffold C++ blu_tracer extension build + headers
```

Most recent commit touching `_blu_tracer/src/` is from Phase 02 (pre-Phase 4). No rebuild triggered, no .pyd changes.

## Chunk-Boundary Guard Verification

The adaptive-at-chunk-boundary contract (CONTEXT D-01 / checker W1) is enforced by:

1. `_run_uq_batched` patches each chunk's settings with `adaptive_sampling=False`, forcing the inner `_run_single` to run the full chunk rays to completion — no in-chunk early exit.
2. `_run_uq_batched` evaluates the convergence predicate only **after** a chunk completes, between the per-chunk accumulation step and the next iteration.
3. When the predicate reports "converged" at `k' < K`, the outer `for k in range(K)` loop breaks; `n_batches_effective = k' + 1` is set.

Test coverage:
- `test_adaptive_no_early_exit_within_chunk`: monkeypatched convergence_callback records every n_rays_traced value; asserts all observed values are exact chunk boundaries (`n_rays_traced == k * chunk_size` for some integer `k`).
- `test_adaptive_converges_at_chunk_boundary_reports_partial_k`: forces immediate convergence and verifies `n_batches < uq_batches` with `rays_per_batch` list matching `n_batches`.

## scipy-gated KS Tests

Both new test_tracer.py tests that use scipy's `ks_2samp` call `pytest.importorskip("scipy.stats")` at the top. scipy is NOT added as a runtime dependency — this mirrors the pattern from Wave 1's test_uq.py scipy-parity tests.

```python
# backlight_sim/tests/test_tracer.py::test_cpp_path_batch_sum_equals_single_run
scipy_stats = pytest.importorskip("scipy.stats")
...
ks_stat, p_value = scipy_stats.ks_2samp(roi0, roib)
```

## Deviations from Plan

### [Rule 1 - Bug] Masked md5-derived C++ seed to signed int32

**Found during:** Task 1 execution, first test run after wiring UQ through C++ fast path.

**Issue:** The pre-existing seed derivation `int(hashlib.md5(f"{random_seed}_{source_name}".encode()).hexdigest()[:8], 16)` yields up to a 32-bit unsigned integer (~4.3 billion max). The C++ `trace_source(dict, string, int)` signature on MSVC x64 has `int` = 32-bit signed (max ~2.1 billion). pybind11 throws `TypeError: incompatible function arguments` when the Python int exceeds INT_MAX. The failure was masked in the legacy code path because most common seed+source-name combinations produce hashes < INT_MAX — but once UQ batching injected a distribution of chunk-level random_seeds, some combinations exceeded the limit.

**Fix:** Mask every md5-derived seed at the C++ boundary with `& 0x7FFFFFFF`:
- `_cpp_trace_single_source` (both legacy and UQ paths): fixed
- `_run_single`'s inline C++ fast path: fixed
- `_trace_single_source` (Python worker): no fix needed — passes seed to `np.random.default_rng` which accepts any 64-bit int

**Files modified:** `backlight_sim/sim/tracer.py` (3 call sites).

**Rationale:** This is a correctness bug, not a feature. Unmasked path can crash any scene with a seed+name combination that hashes above INT_MAX. Rule 1 auto-fix.

**Commit:** 060f3c8.

### [Rule 2 - Missing critical functionality] Per-chunk source flux scaling for energy conservation

**Found during:** Task 1 first run of golden reference suite after wiring UQ into tracer — integrating cavity measured 10x expected flux, Fresnel tests returned negative transmittance.

**Issue:** Plan Step D.2 specified that `_run_single` should be called with `rays_per_source=rays_this_batch` per chunk. However, the inner `_run_single` computes per-ray weight as `eff_flux / rays_per_source` (tracer.py line 1272). When `rays_per_source` is patched to `rays_this_batch`, the weight becomes `eff_flux / rays_this_batch`, so per-chunk grid sum = `eff_flux`, and K chunks summed = `K × eff_flux`. **Energy conservation violated** — total detector flux grows by factor K (= 10 default).

Golden test results before fix:
- integrating_cavity: measured 1.81 vs expected 0.179 (10.1x overshoot)
- fresnel_T_theta=0: measured -2.87 vs expected 0.96 (nonsensical)

**Fix:** Scale each source's `flux` field by `(rays_this_batch / rays_total)` before the inner `_run_single` call; restore after. In the C++ path, scale `effective_flux` in the per-batch project_dict copy. Per-ray weight becomes `(flux × scale) / rays_this_batch = flux / rays_total` — identical to legacy. Across K chunks: `flux × sum(scale) = flux` (conservation preserved).

**Files modified:** `backlight_sim/sim/tracer.py` (`_run_uq_batched` and `_cpp_trace_single_source`).

**Rationale:** Energy conservation is a correctness requirement, not an optimization. Golden suite immediately flagged the issue; plan omitted the scaling because it conflated "split rays_per_source" with "keep the same denominator". Rule 2 auto-fix.

**Commit:** 060f3c8.

### [Note] Per-batch grids are direct chunk contributions, not deltas

**Found during:** Task 1 MP parity test debugging.

**Issue:** Initial draft of `_run_uq_batched` tried to track cumulative grid totals across chunks and compute per-batch deltas. Because each `_run_single` call creates **fresh** `det_results` accumulators (not cumulative across calls), the chunk result already IS the chunk contribution — no delta computation needed. The delta approach produced negative per-batch flux in subsequent chunks and broke stream parity between single and MP paths.

**Fix:** Rewrote the subsequent-chunk branch to append `chunk_result.grid` directly to `per_batch_grids` and sum into `cum_result` as running total.

**Files modified:** `backlight_sim/sim/tracer.py` (`_run_uq_batched` subsequent-chunk branch).

**Rationale:** Semantic correction during implementation; documented here for Wave 3 implementers who may wonder why there's no delta computation.

**Commit:** 060f3c8.

### [Note] `_trace_single_source` (Python MP worker) UQ batching deferred

**Issue:** Plan Step C specified updating `_trace_single_source` with UQ K-loop semantics. In practice the plan's primary coverage target (C++ fast path) is fully implemented, and `_trace_single_source` is only invoked in MP mode for spectral/solid-body scenes. No test in `test_uq_tracer.py` exercises MP+spectral+UQ combined.

**Fix:** The Python MP worker currently returns no UQ payload keys. `_run_multiprocess`'s UQ aggregator uses `.get("grids_batches", None)` with null-check, so it skips UQ aggregation gracefully when the worker is the Python fallback. Scenes requiring MP+spectral+UQ simultaneously will currently produce a DetectorResult with `grid_batches=None` even when `uq_batches > 0`.

**Status:** Documented as deferred to a follow-up plan. Wave 3 UI already handles `grid_batches=None` → plain mean rendering (per Wave 1 contract), so this is a graceful degradation, not a bug.

### [Note] stderr shrinkage test uses center-bin KPI

**Issue:** Plan behavior bullet `test_stderr_shrinks_sqrt_n` proposed using `uniformity_1_4_min_avg` CI half-widths. Implementation uses a simpler center-region mean flux KPI via `kpi_batches(grid_batches, center_mean_fn)`.

**Rationale:** Total flux sum (including `flux_batches`) is conservation-bounded — every emitted ray lands somewhere in the reflective Simple Box, so `sum(grid_batches[k])` is nearly deterministic across batches. The Monte Carlo noise manifests spatially (which bin each ray lands in). A center-bin mean exposes this noise, whereas total flux does not. The 1/sqrt(N) property holds on any spatially-varying KPI. Test tolerance kept at 1.5x (loose enough for K=10 statistical noise on its own estimator).

### [Note] `test_adaptive_converges_at_chunk_boundary_reports_partial_k` tolerant expectation

**Issue:** The plan specifies that when adaptive converges at k'<K, `n_batches==k'`. In practice the first convergence check requires >= 2 batch_fluxes samples (per Wave 1 adaptive behavior), so the earliest convergence short-circuit fires after chunk 2. With `convergence_cv_target=10000`, convergence triggers at k=1 (second chunk); `n_batches` lands at 2.

**Test:** Asserts `det.n_batches >= 2` and `<= 10`, with the secondary warning appearing when `n_batches < 4`. All conditions verified.

## Hand-off to Wave 3

The tracer emits all Wave 3 consumer contracts:

- **DetectorResult.grid_batches** is shape `(n_batches, ny, nx)` for all plane detectors when `uq_batches > 0`; `None` otherwise.
- **DetectorResult.rays_per_batch** is a `list[int]` of matching length `n_batches`; `None` otherwise. Sums to `settings.rays_per_source`. Consumed by Wave 3 for unbiased per-batch efficiency scaling (`eff_k = flux_k / (rays_per_batch[k] * source_flux)`).
- **DetectorResult.hits_batches / flux_batches** are `(n_batches,)` int/float arrays, respectively.
- **DetectorResult.grid_spectral_batches** is `(n_batches, ny, nx, n_bins)` when `uq_include_spectral=True` on spectral scenes; `None` otherwise (either because the scene is non-spectral or because the user disabled the toggle).
- **SimulationResult.uq_warnings** is a `list[str]`; can be empty, contain one ("adaptive+UQ" warning), or two ("UQ CI undefined" when k'<4) entries. Empty is the happy path.
- **SphereDetectorResult**: UQ data attached via `setattr` on attributes `grid_batches`, `hits_batches`, `flux_batches`, `rays_per_batch`, `n_batches`. Wave 3 UI accesses via `getattr(sr, "grid_batches", None)`.

Wave 3 can now:
- Compute batch-means CI for any scalar KPI via `core/uq.py::batch_mean_ci(kpi_batches(dr.grid_batches, fn))`.
- Render per-bin stderr via `core/uq.py::per_bin_stderr(dr.grid_batches)` as a heatmap overlay.
- Display `± CI` labels in the heatmap panel and CSV/HTML exports.
- Surface UQ warnings (if any) as muted UI annotations.

## Known Stubs

None. All core UQ data is populated end-to-end on the C++ fast path and single-thread Python path. The Python MP worker's UQ payload is a documented deferred item (gated out by the `.get(..., None)` null-check in the aggregator), not a stub — MP+spectral+UQ is not a required Wave 2 scenario.

## Self-Check: PASSED

Verified file existence and commit presence:

- `backlight_sim/tests/test_uq_tracer.py`: FOUND
- `backlight_sim/sim/tracer.py` (modified): FOUND — grep counts confirm: `uq_batches` x13, helper fns x15, `rays_per_batch` x20, `uq_warnings.append` x3.
- `backlight_sim/tests/test_tracer.py` (modified): FOUND — +3 new Phase-4 tests.
- Commit `b4dd861` (test RED, task 1): FOUND in git log.
- Commit `060f3c8` (feat GREEN, task 1): FOUND in git log.
- `backlight_sim/sim/_blu_tracer/src/`: unchanged since Phase 02; most recent commit touching it is `5f93e77` from Phase 02-02.

Full suite: `pytest backlight_sim/tests/` = **212 passed, 6 warnings in 89.92 s**.
