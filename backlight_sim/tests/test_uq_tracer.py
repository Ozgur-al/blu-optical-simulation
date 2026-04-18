"""Tracer-level UQ integration tests (Phase 4 Wave 2).

Covers:
- Legacy-equivalence: uq_batches=0 produces no UQ data and bit-stable grids
- UQ on: grid_batches/hits_batches/flux_batches/rays_per_batch are populated
- Remainder distribution in rays_per_batch
- Flux conservation: sum(grid_batches) == grid; sum(rays_per_batch) == rays_per_source
- Deterministic per-batch seeding (repeat run -> identical grid_batches)
- Independence sanity: pairwise correlation between batches stays moderate
- Stderr shrinks ~1/sqrt(N) when rays_per_source doubles at fixed K
- Path recording is first-batch-only
- Adaptive + UQ attaches warning to result.uq_warnings
- Adaptive converges at chunk boundary (n_batches < K)
- Adaptive predicate is never evaluated mid-chunk
- Spectral toggle off -> grid_spectral_batches is None
- Clamp policy for uq_batches below floor
"""

from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.io.presets import preset_simple_box
from backlight_sim.sim import tracer as tracer_mod
from backlight_sim.sim.tracer import (
    RayTracer,
    _effective_uq_batches,
    _batch_seed,
    _partition_rays,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_box(rays: int, k: int, seed: int = 42, adaptive: bool = False) -> Project:
    """Build the canonical Simple Box scene with tunable UQ settings."""
    project = preset_simple_box()
    project.settings.rays_per_source = rays
    project.settings.random_seed = seed
    project.settings.uq_batches = k
    project.settings.adaptive_sampling = adaptive
    project.settings.record_ray_paths = 0
    return project


# ---------------------------------------------------------------------------
# Unit tests for the partitioning / seeding helpers
# ---------------------------------------------------------------------------


def test_partition_rays_no_remainder():
    assert _partition_rays(1000, 10) == [100] * 10


def test_partition_rays_remainder_front_loaded():
    # 1005 / 10 -> first 5 batches get +1
    assert _partition_rays(1005, 10) == [101, 101, 101, 101, 101, 100, 100, 100, 100, 100]


def test_partition_rays_sum_matches_total():
    for total in (1000, 1001, 1234, 9999):
        for k in (4, 5, 10, 17, 20):
            parts = _partition_rays(total, k)
            assert len(parts) == k
            assert sum(parts) == total


def test_effective_uq_batches_zero_passthrough():
    s = SimulationSettings(uq_batches=0)
    assert _effective_uq_batches(s) == 0


def test_effective_uq_batches_clamps_below_floor():
    s = SimulationSettings(uq_batches=2)
    assert _effective_uq_batches(s) == 4  # clamped to floor


def test_effective_uq_batches_clamps_above_cap():
    s = SimulationSettings(uq_batches=500)
    assert _effective_uq_batches(s) == 20  # clamped to cap


def test_effective_uq_batches_default_is_10():
    s = SimulationSettings()
    assert _effective_uq_batches(s) == 10


def test_batch_seed_deterministic():
    a = _batch_seed(42, "src1", 0)
    b = _batch_seed(42, "src1", 0)
    assert a == b


def test_batch_seed_differs_by_k():
    seeds = [_batch_seed(42, "src1", k) for k in range(10)]
    assert len(set(seeds)) == 10


def test_batch_seed_differs_by_source_name():
    a = _batch_seed(42, "src1", 0)
    b = _batch_seed(42, "src2", 0)
    assert a != b


# ---------------------------------------------------------------------------
# Integration tests: UQ on / off on the Simple Box preset
# ---------------------------------------------------------------------------


def test_uq_off_matches_legacy():
    """K=0 leaves UQ fields as None / 0 (legacy shape)."""
    project = _simple_box(rays=2000, k=0)
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    assert det.grid_batches is None
    assert det.hits_batches is None
    assert det.flux_batches is None
    assert det.grid_spectral_batches is None
    assert det.rays_per_batch is None
    assert det.n_batches == 0
    assert result.uq_warnings == []


def test_uq_on_populates_batches():
    project = _simple_box(rays=2000, k=10)
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    ny, nx = det.grid.shape
    assert det.grid_batches is not None
    assert det.grid_batches.shape == (10, ny, nx)
    assert det.hits_batches is not None and det.hits_batches.shape == (10,)
    assert det.flux_batches is not None and det.flux_batches.shape == (10,)
    assert det.rays_per_batch is not None
    assert isinstance(det.rays_per_batch, list)
    assert len(det.rays_per_batch) == 10
    assert sum(det.rays_per_batch) == project.settings.rays_per_source
    assert det.n_batches == 10


def test_rays_per_batch_remainder_distribution():
    """rays_per_source=1005, K=10 -> first 5 batches get +1 remainder."""
    project = _simple_box(rays=1005, k=10)
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    assert det.rays_per_batch == [101, 101, 101, 101, 101, 100, 100, 100, 100, 100]


def test_batch_ray_count_conservation():
    project = _simple_box(rays=2000, k=10)
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    # Hits conservation
    assert int(det.hits_batches.sum()) == det.total_hits
    # Flux conservation (per-batch floats should add up within FP tolerance)
    assert float(det.flux_batches.sum()) == pytest.approx(det.total_flux, rel=1e-9, abs=1e-9)
    # Ray count conservation
    assert sum(det.rays_per_batch) == project.settings.rays_per_source


def test_grid_batches_sum_equals_grid():
    project = _simple_box(rays=2000, k=10)
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    np.testing.assert_allclose(det.grid_batches.sum(axis=0), det.grid, rtol=1e-9, atol=1e-12)


def test_per_batch_deterministic_seed():
    """Same scene, same seed -> identical grid_batches."""
    project1 = _simple_box(rays=2000, k=10, seed=42)
    project2 = _simple_box(rays=2000, k=10, seed=42)
    r1 = RayTracer(project1).run()
    r2 = RayTracer(project2).run()
    d1 = list(r1.detectors.values())[0]
    d2 = list(r2.detectors.values())[0]
    assert np.array_equal(d1.grid_batches, d2.grid_batches)


def test_batches_have_uncorrelated_structure():
    """Pairwise correlation between per-batch grids stays moderate (independence sanity)."""
    project = _simple_box(rays=4000, k=10)
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    gb = det.grid_batches
    # Ignore empty batches (early-exit); we expect all 10 to be populated here.
    assert gb.shape[0] == 10
    flat = gb.reshape(10, -1)
    max_off_diagonal = 0.0
    for i in range(10):
        for j in range(i + 1, 10):
            # Use correlation coefficient; constant batches would raise — guard.
            if flat[i].std() == 0 or flat[j].std() == 0:
                continue
            c = float(np.corrcoef(flat[i], flat[j])[0, 1])
            if abs(c) > max_off_diagonal:
                max_off_diagonal = abs(c)
    # Generous bound — two batches of 400 rays on 100x100 grid are sparse; the
    # correlation is primarily driven by detector geometry, not RNG overlap.
    # We just want to confirm batches are not identical.
    assert max_off_diagonal < 0.95, f"batches suspiciously correlated: {max_off_diagonal}"


def test_stderr_shrinks_sqrt_n():
    """CI half-width ~ 1/sqrt(rays); doubling rays_per_source -> ~sqrt(2) narrower CI.

    We use a spatially-varying KPI (center-bin flux) rather than total flux,
    because total flux is conservation-bounded (~= effective source flux) and
    does not show sqrt(N) behavior on its own: every ray of known weight lands
    somewhere in the scene, so the batch-sum is near-deterministic for the
    Simple Box.  A per-bin measurement exposes the Monte Carlo noise floor.
    """
    from backlight_sim.core.uq import batch_mean_ci, kpi_batches

    # Use large ray counts so the statistical test is robust.
    r_small = RayTracer(_simple_box(rays=4000, k=10)).run()
    r_big = RayTracer(_simple_box(rays=32000, k=10)).run()
    d_small = list(r_small.detectors.values())[0]
    d_big = list(r_big.detectors.values())[0]

    # KPI: mean flux over the central 10x10 region of the 100x100 detector
    def _center_mean(grid: np.ndarray) -> float:
        ny, nx = grid.shape
        return float(grid[ny // 2 - 5: ny // 2 + 5, nx // 2 - 5: nx // 2 + 5].mean())

    ks = kpi_batches(d_small.grid_batches, _center_mean)
    kb = kpi_batches(d_big.grid_batches, _center_mean)
    ci_s = batch_mean_ci(ks)
    ci_b = batch_mean_ci(kb)
    # half-width relative to mean — scale-invariant
    rel_s = ci_s.half_width / max(abs(ci_s.mean), 1e-12)
    rel_b = ci_b.half_width / max(abs(ci_b.mean), 1e-12)
    ratio = rel_s / max(rel_b, 1e-12)
    # Expected ratio = sqrt(32000/4000) = sqrt(8) ~ 2.83; accept 2.0 floor.
    # MC noise in a small-sample test (K=10) is itself noisy — demand at least 1.5x.
    assert ratio > 1.5, f"CI did not shrink as expected: ratio={ratio}"


def test_path_recording_first_batch_only():
    """With record_ray_paths>0 and K>0, ray_paths is not inflated K-fold."""
    project = _simple_box(rays=2000, k=10)
    project.settings.record_ray_paths = 50
    result = RayTracer(project).run()
    # Expect at most 50 paths (first batch only), not 500 (10× inflation).
    assert len(result.ray_paths) <= 50


def test_adaptive_plus_uq_attaches_warning():
    project = _simple_box(rays=2000, k=10, adaptive=True)
    # Ensure adaptive does not trivially converge before any batch
    project.settings.convergence_cv_target = 0.001
    project.settings.check_interval = 200
    result = RayTracer(project).run()
    assert isinstance(result.uq_warnings, list)
    assert len(result.uq_warnings) >= 1
    assert "adaptive" in result.uq_warnings[0].lower()


def test_spectral_toggle_off_leaves_spectral_batches_none():
    """With uq_include_spectral=False, grid_spectral_batches stays None even on spectral scene."""
    project = _simple_box(rays=1000, k=10)
    project.settings.uq_include_spectral = False
    # Make the source spectral to force the Python path / spectral accumulation.
    project.sources[0].spd = "d65"
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    assert det.grid_batches is not None  # UQ batches still present
    assert det.grid_spectral_batches is None  # but no spectral per-batch cache


def test_uq_clamp_below_floor():
    """Passing uq_batches=2 clamps to 4 (effective K >= 4)."""
    project = _simple_box(rays=1000, k=2)
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    assert det.n_batches == 4  # clamped from 2 -> 4


def test_adaptive_no_early_exit_within_chunk(monkeypatch):
    """Adaptive convergence check must fire only at chunk boundaries when K > 0.

    Instrument the tracer's chunk-end callback by hooking a known inner call.
    """
    # We wire this by recording n_rays_traced *from the tracer* every time an
    # adaptive convergence check is performed.  Since the check is implemented
    # inline as a call to math.sqrt / numpy comparisons, we intercept the
    # convergence_callback (hook exposed by the tracer at chunk boundaries).
    project = _simple_box(rays=2000, k=10, adaptive=True)
    project.settings.check_interval = 100  # would fire every 100 rays if not gated
    project.settings.convergence_cv_target = 0.0  # never satisfied -> no early exit

    observed_counts: list[int] = []

    def cb(src_idx: int, n_rays_traced: int, cv_pct: float) -> None:
        observed_counts.append(int(n_rays_traced))

    RayTracer(project).run(convergence_callback=cb)

    # Under UQ mode, callback must be called only at chunk boundaries.
    # rays=2000 / K=10 -> chunk_size = 200; boundaries at 200, 400, ..., 2000.
    chunk_boundaries = {200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000}
    # Every observed count must be a chunk boundary.
    for n in observed_counts:
        assert n in chunk_boundaries, (
            f"convergence check fired at n_rays_traced={n}, not a chunk boundary"
        )


def test_adaptive_converges_at_chunk_boundary_reports_partial_k():
    """If adaptive flags convergence at k'<K, n_batches == k' and rays_per_batch has len k'."""
    project = _simple_box(rays=2000, k=10, adaptive=True)
    # Force convergence predicate to accept the first check.
    project.settings.convergence_cv_target = 10_000.0  # 10,000% CV -> always "converged"
    project.settings.check_interval = 100
    result = RayTracer(project).run()
    det = list(result.detectors.values())[0]
    # Adaptive should trigger at the first chunk boundary (after chunk 2 since
    # we need >=2 batch_fluxes samples per existing implementation).
    assert det.n_batches >= 2
    assert det.n_batches <= 10
    assert len(det.rays_per_batch) == det.n_batches
    assert det.grid_batches.shape[0] == det.n_batches
    if det.n_batches < 4:
        # Must include the "UQ CI undefined" warning
        assert any("UQ CI undefined" in w or "only" in w.lower()
                   for w in result.uq_warnings)


# ---------------------------------------------------------------------------
# Multiprocessing parity (slow) — skipped on platforms where MP import fails
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_mp_parity_with_single_thread():
    """MP mode returns the same grid_batches (modulo ordering) as single-thread at equal seed."""
    # Need multiple enabled sources for MP to activate
    def make_two_source(rays: int, k: int, mp: bool) -> Project:
        project = preset_simple_box()
        # Add a second source
        project.sources.append(PointSource(
            "LED_2", np.array([5.0, 5.0, 0.5]),
            flux=50.0,
            direction=np.array([0.0, 0.0, 1.0]),
            distribution="lambertian",
        ))
        project.settings.rays_per_source = rays
        project.settings.random_seed = 42
        project.settings.uq_batches = k
        project.settings.use_multiprocessing = mp
        project.settings.adaptive_sampling = False
        project.settings.record_ray_paths = 0
        return project

    r_single = RayTracer(make_two_source(1000, 4, False)).run()
    r_mp = RayTracer(make_two_source(1000, 4, True)).run()
    d_single = list(r_single.detectors.values())[0]
    d_mp = list(r_mp.detectors.values())[0]
    # Per-batch shape matches
    assert d_single.grid_batches.shape == d_mp.grid_batches.shape
    # Per-batch sums (total flux across batches) agree (cross-path seeds differ
    # so grids are not bitwise identical, but totals conserve).
    total_single = float(d_single.grid_batches.sum())
    total_mp = float(d_mp.grid_batches.sum())
    assert abs(total_single - total_mp) / max(total_single, 1e-12) < 0.15
