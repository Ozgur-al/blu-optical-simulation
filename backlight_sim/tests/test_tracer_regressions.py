"""Regression tests for tracer energy-accounting / UQ / far-field bugs.

Each test pins one defect found in the tracer bug hunt:

* UQ ``total_emitted_flux`` was 1/K of the true value.
* UQ chunk flux scaling ignored current-driven LEDs (K x overcount).
* UQ + adaptive always stopped after 2 batches and never rescaled flux.
* Legacy adaptive sampling never converged / never rescaled on early stop.
* Python path let rays pass through detectors (double counting vs C++).
* Rays alive at ``max_bounces`` were silently dropped (C++ books them as escaped).
* Far-field accumulation recorded the mirrored direction.
* UQ far-field candela / RGB grids only reflected one chunk.

The scenes are deterministic enough (every ray ends on a large detector) that
the assertions are exact up to float rounding, so they hold on both the
Python path and the C++ fast path when the extension is built.
"""
from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.core.detectors import DetectorSurface, SphereDetector, SphereDetectorResult
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.core.sources import PointSource
from backlight_sim.sim.tracer import (
    RayTracer,
    _reflect_batch,
    _spectral_bin_index,
    compute_farfield_candela,
)
from backlight_sim.sim.spectral import N_SPECTRAL_BINS, spectral_bin_centers


FLUX = 100.0


def _settings(**kw) -> SimulationSettings:
    base = dict(
        rays_per_source=8000,
        record_ray_paths=0,
        uq_batches=0,
        adaptive_sampling=False,
        use_multiprocessing=False,
        random_seed=7,
    )
    base.update(kw)
    return SimulationSettings(**base)


def _big_detector(z: float = 5.0) -> DetectorSurface:
    return DetectorSurface(
        name="D",
        center=np.array([0.0, 0.0, z]),
        u_axis=np.array([1.0, 0.0, 0.0]),
        v_axis=np.array([0.0, 1.0, 0.0]),
        size=(1.0e6, 1.0e6),
        resolution=(10, 10),
    )


def _detector_only_project(**kw) -> Project:
    """Lambertian +Z LED under a huge detector: every ray hits it once."""
    p = Project(settings=_settings(**kw))
    p.sources = [PointSource(
        name="L", position=np.array([0.0, 0.0, 0.5]), flux=FLUX,
        direction=np.array([0.0, 0.0, 1.0]), distribution="lambertian",
    )]
    p.detectors = [_big_detector()]
    return p


# ---------------------------------------------------------------------------
# UQ batching
# ---------------------------------------------------------------------------

def test_uq_total_emitted_flux_is_full_source_flux():
    r = RayTracer(_detector_only_project(uq_batches=10)).run()
    assert r.total_emitted_flux == pytest.approx(FLUX)
    d = r.detectors["D"]
    assert d.total_flux == pytest.approx(FLUX, rel=1e-9)
    assert d.n_batches == 10
    assert d.flux_batches.sum() == pytest.approx(FLUX, rel=1e-9)


def test_uq_scales_current_driven_led_flux():
    p = _detector_only_project(uq_batches=10)
    src = p.sources[0]
    src.flux = 1.0                      # ignored by effective_flux in current mode
    src.current_mA = 100.0
    src.flux_per_mA = 1.0               # effective_flux = 100
    r = RayTracer(p).run()
    assert r.total_emitted_flux == pytest.approx(FLUX)
    assert r.detectors["D"].total_flux == pytest.approx(FLUX, rel=1e-9)
    # Source objects are restored after the run
    assert src.thermal_derate == 1.0 and src.flux == 1.0


def test_uq_adaptive_needs_min_batches_and_rescales():
    # Zero-variance scene -> CV=0 -> converges as early as allowed.
    p = _detector_only_project(
        uq_batches=10, adaptive_sampling=True, convergence_cv_target=50.0,
    )
    r = RayTracer(p).run()
    d = r.detectors["D"]
    assert d.n_batches == 4, "early exit must wait for >= 4 batches"
    assert sum(d.rays_per_batch) < p.settings.rays_per_source
    # Fluxes rescaled to represent the full source flux
    assert d.total_flux == pytest.approx(FLUX, rel=1e-9)
    assert r.total_emitted_flux == pytest.approx(FLUX)
    assert d.flux_batches.sum() == pytest.approx(FLUX, rel=1e-9)
    assert d.grid.sum() == pytest.approx(FLUX, rel=1e-9)


def test_legacy_adaptive_early_stop_rescales():
    p = _detector_only_project(
        uq_batches=0, adaptive_sampling=True, convergence_cv_target=50.0,
        check_interval=1000, rays_per_source=20000,
    )
    calls = []
    r = RayTracer(p).run(convergence_callback=lambda s, n, cv: calls.append(n))
    # Stopped after the minimum of 4 batches, not after all 20
    assert calls[-1] == 4000
    assert r.detectors["D"].total_flux == pytest.approx(FLUX, rel=1e-9)
    assert r.detectors["D"].grid.sum() == pytest.approx(FLUX, rel=1e-9)


def test_uq_rgb_grid_accumulates_all_chunks():
    p = _detector_only_project(uq_batches=5)
    p.sources[0].color_rgb = (1.0, 0.5, 0.25)
    r = RayTracer(p).run()
    d = r.detectors["D"]
    assert d.grid_rgb is not None
    np.testing.assert_allclose(
        d.grid_rgb.sum(axis=(0, 1)), [FLUX, 0.5 * FLUX, 0.25 * FLUX], rtol=1e-9,
    )


# ---------------------------------------------------------------------------
# Energy accounting / detector semantics
# ---------------------------------------------------------------------------

def _detector_under_mirror_project(**kw) -> Project:
    """Detector at z=5, lossless diffuse mirror at z=10 facing it."""
    p = _detector_only_project(**kw)
    p.materials = {"mirror": Material(
        name="mirror", surface_type="reflector", reflectance=1.0,
        absorption=0.0, is_diffuse=True,
    )}
    p.surfaces = [Rectangle(
        name="M", center=np.array([0.0, 0.0, 10.0]),
        u_axis=np.array([1.0, 0.0, 0.0]), v_axis=np.array([0.0, 1.0, 0.0]),
        size=(1.0e6, 1.0e6), material_name="mirror",
    )]
    return p


def test_detector_terminates_rays_no_double_count():
    r = RayTracer(_detector_under_mirror_project()).run()
    d = r.detectors["D"]
    # Every ray hits the detector exactly once, then dies.
    assert d.total_hits <= 8000
    assert d.total_flux == pytest.approx(FLUX, rel=1e-9)
    assert d.total_flux + r.escaped_flux == pytest.approx(r.total_emitted_flux, rel=1e-9)


def test_rays_alive_at_max_bounces_count_as_escaped():
    # Two facing lossless mirrors trap every ray; with max_bounces=3 all of
    # the flux is still alive at the end and must be booked as escaped.
    p = Project(settings=_settings(max_bounces=3, energy_threshold=1e-9))
    p.sources = [PointSource(
        name="L", position=np.array([0.0, 0.0, 0.0]), flux=FLUX,
        direction=np.array([0.0, 0.0, 1.0]), distribution="isotropic",
    )]
    p.materials = {"mirror": Material(
        name="mirror", surface_type="reflector", reflectance=1.0,
        absorption=0.0, is_diffuse=False,
    )}
    for name, z in (("top", 1.0), ("bottom", -1.0)):
        p.surfaces.append(Rectangle(
            name=name, center=np.array([0.0, 0.0, z]),
            u_axis=np.array([1.0, 0.0, 0.0]), v_axis=np.array([0.0, 1.0, 0.0]),
            size=(1.0e9, 1.0e9), material_name="mirror",
        ))
    r = RayTracer(p).run()
    assert r.escaped_flux == pytest.approx(FLUX, rel=1e-6)


# ---------------------------------------------------------------------------
# Far-field
# ---------------------------------------------------------------------------

def _farfield_project(direction, **kw) -> Project:
    p = Project(settings=_settings(max_bounces=2, rays_per_source=20000, **kw))
    p.sources = [PointSource(
        name="L", position=np.array([0.0, 0.0, 0.0]), flux=FLUX,
        direction=np.asarray(direction, dtype=float), distribution="lambertian",
    )]
    p.sphere_detectors = [SphereDetector(
        name="ff", center=np.array([0.0, 0.0, 0.0]), radius=100.0,
        resolution=(36, 18), mode="far_field",
    )]
    return p


@pytest.mark.parametrize("direction, upper_expected", [
    ((0.0, 0.0, 1.0), True),
    ((0.0, 0.0, -1.0), False),
])
def test_farfield_records_outgoing_direction(direction, upper_expected):
    r = RayTracer(_farfield_project(direction)).run()
    grid = r.sphere_detectors["ff"].grid
    n_theta = grid.shape[0]
    upper = grid[: n_theta // 2].sum()
    lower = grid[n_theta // 2:].sum()
    if upper_expected:
        assert upper == pytest.approx(FLUX) and lower == 0.0
    else:
        assert lower == pytest.approx(FLUX) and upper == 0.0


def test_farfield_accumulate_direction_bin():
    from backlight_sim.sim.tracer import _accumulate_sphere_farfield
    sd = SphereDetector("sph", np.zeros(3), radius=100.0,
                        resolution=(36, 18), mode="far_field")
    res = SphereDetectorResult("sph", np.zeros((18, 36)))
    _accumulate_sphere_farfield(sd, res, np.array([[0.0, 0.0, 1.0]]), np.array([1.0]))
    assert res.grid[0].sum() == 1.0   # +Z ray -> theta=0 row


def test_uq_farfield_candela_uses_cumulative_grid():
    p = _farfield_project((0.0, 0.0, 1.0), uq_batches=5)
    r = RayTracer(p).run()
    sr = r.sphere_detectors["ff"]
    assert sr.total_flux == pytest.approx(FLUX)
    expected = SphereDetectorResult("ff", sr.grid.copy())
    compute_farfield_candela(p.sphere_detectors[0], expected)
    np.testing.assert_allclose(sr.candela_grid, expected.candela_grid)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_spectral_bin_index_maps_centers_to_their_bin():
    centers = spectral_bin_centers(N_SPECTRAL_BINS)
    np.testing.assert_array_equal(
        _spectral_bin_index(centers, N_SPECTRAL_BINS), np.arange(N_SPECTRAL_BINS),
    )
    step = centers[1] - centers[0]
    # Just below the half-way point stays in the lower bin
    np.testing.assert_array_equal(
        _spectral_bin_index(centers[:-1] + 0.49 * step, N_SPECTRAL_BINS),
        np.arange(N_SPECTRAL_BINS - 1),
    )


def test_reflect_batch_diffuse_respects_per_ray_normals():
    rng = np.random.default_rng(0)
    angles = np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False)
    normals = np.column_stack([np.cos(angles), np.sin(angles), np.zeros_like(angles)])
    dirs = -normals  # incoming rays
    out = _reflect_batch(dirs, normals, True, rng)
    assert np.all(np.einsum("ij,ij->i", out, normals) > 0.0)
