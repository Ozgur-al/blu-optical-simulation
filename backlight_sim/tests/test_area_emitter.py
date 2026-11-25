"""LED emitting surface: rays start uniformly over a rectangle facing `direction`."""

import numpy as np
import pytest

from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project
from backlight_sim.core.sources import PointSource
from backlight_sim.io.project_io import load_project, save_project
import backlight_sim.sim.tracer as tracer_mod
from backlight_sim.sim.tracer import RayTracer


def test_sample_origins_cover_rectangle_facing_direction():
    src = PointSource("led", [1.0, 2.0, 3.0], direction=[0, 0, 1], emitter_size=(4.0, 2.0))
    o = src.sample_origins(20000, np.random.default_rng(0))
    assert np.allclose(o[:, 2], 3.0)
    assert o[:, 0].min() >= -1.0 and o[:, 0].max() <= 3.0
    assert o[:, 1].min() >= 1.0 and o[:, 1].max() <= 3.0
    assert np.ptp(o[:, 0]) == pytest.approx(4.0, abs=0.01)

    side = PointSource("side", [0, 0, 0], direction=[1, 0, 0], emitter_size=(2.0, 2.0))
    o = side.sample_origins(1000, np.random.default_rng(0))
    assert np.allclose(o[:, 0], 0.0)  # surface lies in the plane normal to +X


def test_point_emitter_unchanged():
    src = PointSource("led", [1.0, 2.0, 3.0])
    assert np.allclose(src.sample_origins(5, np.random.default_rng(0)), [1.0, 2.0, 3.0])


def _footprint_scene() -> Project:
    """20x20 Lambertian emitter 0.01 above a 40x40 detector-sized receiver."""
    p = Project()
    p.sources.append(PointSource("led", [0, 0, 0], direction=[0, 0, 1],
                                 distribution="lambertian", emitter_size=(20.0, 10.0)))
    p.detectors.append(DetectorSurface.axis_aligned("det", [0, 0, 0.01], (40.0, 40.0), 2, 1.0, (40, 40)))
    p.settings.rays_per_source = 20000
    p.settings.max_bounces = 2
    p.settings.record_ray_paths = 0
    return p


def _lit_extent(grid: np.ndarray) -> tuple[int, int]:
    ys, xs = np.nonzero(grid > grid.max() * 0.05)
    return xs.max() - xs.min() + 1, ys.max() - ys.min() + 1


@pytest.mark.parametrize("force_python", [False, True])
def test_detector_sees_emitter_footprint(monkeypatch, force_python):
    if force_python:
        monkeypatch.setattr(tracer_mod, "_project_uses_cpp_unsupported_features", lambda p: True)
    grid = RayTracer(_footprint_scene()).run().detectors["det"].grid
    w, h = _lit_extent(grid)
    # 1 mm bins: lit area matches the 20 x 10 emitter, not a point.
    assert 19 <= w <= 21
    assert 9 <= h <= 11


def test_emitter_size_round_trips(tmp_path):
    p = Project()
    p.sources.append(PointSource("led", [0, 0, 0], emitter_size=(1.5, 0.8)))
    save_project(p, tmp_path / "p.json")
    assert load_project(tmp_path / "p.json").sources[0].emitter_size == (1.5, 0.8)
