"""Tests for the Monte Carlo ray tracer."""

import numpy as np
import pytest

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.sim.sampling import sample_angular_distribution


def _make_box_scene(
    rays_per_source=5000,
    wall_reflectance=0.9,
    wall_type="reflector",
    source_flux=1000.0,
) -> Project:
    materials = {
        "wall": Material(name="wall", surface_type=wall_type,
                         reflectance=wall_reflectance, absorption=1.0-wall_reflectance),
    }
    surfaces = [
        Rectangle.axis_aligned("floor",      [0, 0, -5], (20, 20), 2, -1.0, "wall"),
        Rectangle.axis_aligned("wall_left",  [-10, 0, 0], (20, 10), 0, -1.0, "wall"),
        Rectangle.axis_aligned("wall_right", [10, 0, 0],  (20, 10), 0,  1.0, "wall"),
        Rectangle.axis_aligned("wall_front", [0, -10, 0], (20, 10), 1, -1.0, "wall"),
        Rectangle.axis_aligned("wall_back",  [0, 10, 0],  (20, 10), 1,  1.0, "wall"),
    ]
    detectors = [
        DetectorSurface.axis_aligned("top_detector", [0, 0, 5], (20, 20), 2, 1.0, (50, 50)),
    ]
    sources = [PointSource("src1", np.array([0.0, 0.0, 0.0]), flux=source_flux)]
    settings = SimulationSettings(rays_per_source=rays_per_source, max_bounces=50,
                                  energy_threshold=0.001, random_seed=42, record_ray_paths=10)
    return Project(name="test_box", sources=sources, surfaces=surfaces,
                   materials=materials, detectors=detectors, settings=settings)


def test_basic_simulation_produces_nonzero_heatmap():
    result = RayTracer(_make_box_scene()).run()
    det = result.detectors["top_detector"]
    assert det.total_hits > 0
    assert det.total_flux > 0
    assert det.grid.sum() > 0
    assert det.grid.shape == (50, 50)


def test_zero_flux_produces_zero_results():
    result = RayTracer(_make_box_scene(source_flux=0.0)).run()
    det = result.detectors["top_detector"]
    assert det.total_flux == 0.0
    assert det.grid.sum() == 0.0


def test_absorber_walls_fewer_hits_than_reflector():
    res_absorb  = RayTracer(_make_box_scene(wall_type="absorber",  rays_per_source=10000)).run()
    res_reflect = RayTracer(_make_box_scene(wall_reflectance=0.9,  rays_per_source=10000)).run()
    assert res_absorb.detectors["top_detector"].total_flux < res_reflect.detectors["top_detector"].total_flux
    assert res_absorb.detectors["top_detector"].total_hits > 0


def test_deterministic_with_same_seed():
    r1 = RayTracer(_make_box_scene()).run()
    r2 = RayTracer(_make_box_scene()).run()
    np.testing.assert_array_equal(r1.detectors["top_detector"].grid, r2.detectors["top_detector"].grid)


def test_progress_callback_called():
    calls = []
    RayTracer(_make_box_scene()).run(progress_callback=lambda p: calls.append(p))
    assert len(calls) > 0
    assert calls[-1] == pytest.approx(1.0)


def test_ray_paths_recorded():
    result = RayTracer(_make_box_scene(rays_per_source=500)).run()
    assert len(result.ray_paths) > 0
    assert all(len(p) >= 1 for p in result.ray_paths)


def test_custom_angular_distribution_sampling_points_forward():
    rng = np.random.default_rng(7)
    dirs = sample_angular_distribution(
        20000,
        np.array([0.0, 0.0, 1.0]),
        np.array([0.0, 90.0]),
        np.array([1.0, 0.0]),
        rng,
    )
    assert dirs.shape == (20000, 3)
    assert float(dirs[:, 2].mean()) > 0.5


def test_tracer_supports_custom_angular_distribution_name():
    project = _make_box_scene(rays_per_source=4000)
    project.sources[0].distribution = "led_curve"
    project.angular_distributions["led_curve"] = {
        "theta_deg": [0.0, 30.0, 60.0, 90.0],
        "intensity": [1.0, 0.9, 0.3, 0.0],
    }
    result = RayTracer(project).run()
    det = result.detectors["top_detector"]
    assert det.total_hits > 0
