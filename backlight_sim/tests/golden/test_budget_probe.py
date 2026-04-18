"""Wave 0 budget probe + SPD convention smoke check.

Emits throughput numbers (ms / 1M rays) for the C++ path and the Python
spectral path so Plans 02/03 can tune ray counts. Also verifies the
`spd="mono_*"` convention triggers the spectral dispatch gate per
tracer.py:631 and the CPP-unsupported predicate at tracer.py:251.

These tests do NOT gate the phase — they print budget numbers. Downstream
plans consume the printed numbers to size ray counts.
"""
from __future__ import annotations

import time

import numpy as np

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.sim.tracer import RayTracer, _project_uses_cpp_unsupported_features


def _make_cpp_eligible_scene(rays: int, source_spd: str = "white") -> Project:
    """Plain-Rectangle reflector box — eligible for C++ path when spd='white'."""
    materials = {
        "wall": Material(name="wall", surface_type="reflector",
                         reflectance=0.9, absorption=0.1),
    }
    surfaces = [
        Rectangle.axis_aligned("floor",      [0, 0, -5], (20, 20), 2, -1.0, "wall"),
        Rectangle.axis_aligned("wall_left",  [-10, 0, 0], (20, 10), 0, -1.0, "wall"),
        Rectangle.axis_aligned("wall_right", [10, 0, 0],  (20, 10), 0,  1.0, "wall"),
        Rectangle.axis_aligned("wall_front", [0, -10, 0], (20, 10), 1, -1.0, "wall"),
        Rectangle.axis_aligned("wall_back",  [0, 10, 0],  (20, 10), 1,  1.0, "wall"),
    ]
    detectors = [
        DetectorSurface.axis_aligned(
            "top_detector", [0, 0, 5], (20, 20), 2, 1.0, (50, 50)
        ),
    ]
    sources = [PointSource("src1", np.array([0.0, 0.0, 0.0]),
                           flux=1000.0, spd=source_spd)]
    settings = SimulationSettings(
        rays_per_source=rays, max_bounces=20, energy_threshold=0.001,
        random_seed=42, record_ray_paths=0,
    )
    return Project(
        name="budget_probe", sources=sources, surfaces=surfaces,
        materials=materials, detectors=detectors, settings=settings,
    )


def test_cpp_path_throughput(capsys):
    project = _make_cpp_eligible_scene(rays=100_000, source_spd="white")
    assert not _project_uses_cpp_unsupported_features(project), (
        "Probe scene must be CPP-eligible for C++ throughput measurement"
    )
    t0 = time.perf_counter()
    RayTracer(project).run()
    elapsed = time.perf_counter() - t0
    ms_per_1M = (elapsed / 100_000) * 1_000_000 * 1000.0
    print(f"\n[BUDGET PROBE] C++ path: {ms_per_1M:.1f} ms / 1M rays "
          f"(actual: {elapsed*1000:.1f} ms for 100k rays)")
    assert ms_per_1M > 0  # sanity


def test_python_path_throughput(capsys):
    project = _make_cpp_eligible_scene(rays=50_000, source_spd="mono_550")
    # For plain-Rectangle surfaces the tracer looks up reflectance/transmittance
    # keyed by optics_name (see tracer.py:1688-1695 + project_model.py:46).
    # SolidBox/Cylinder/Prism paths use refractive_index — not relevant here.
    project.spectral_material_data = {
        "wall": {
            "wavelength_nm": [450.0, 650.0],
            "reflectance": [0.9, 0.9],  # flat R, still triggers spectral path
            "transmittance": [0.0, 0.0],
        }
    }
    assert _project_uses_cpp_unsupported_features(project), (
        "Spectral scene must route to Python path"
    )
    t0 = time.perf_counter()
    RayTracer(project).run()
    elapsed = time.perf_counter() - t0
    ms_per_1M = (elapsed / 50_000) * 1_000_000 * 1000.0
    print(f"\n[BUDGET PROBE] Python path (spectral): {ms_per_1M:.1f} ms / 1M rays "
          f"(actual: {elapsed*1000:.1f} ms for 50k rays)")
    assert ms_per_1M > 0


def test_spd_naming_triggers_spectral():
    """Verify spd='mono_450' triggers has_spectral gate (tracer.py:631) and routes to Python."""
    project = _make_cpp_eligible_scene(rays=1000, source_spd="mono_450")
    assert _project_uses_cpp_unsupported_features(project), (
        "spd='mono_450' must count as non-white and route to Python"
    )
    # Run to verify no AttributeError / KeyError in the spectral dispatch.
    project.spectral_material_data = {
        "wall": {
            "wavelength_nm": [400.0, 700.0],
            "reflectance": [0.9, 0.9],
            "transmittance": [0.0, 0.0],
        }
    }
    RayTracer(project).run()  # must not raise


def test_spd_white_stays_on_cpp_eligible():
    """Baseline: spd='white' does NOT force Python."""
    project = _make_cpp_eligible_scene(rays=1000, source_spd="white")
    assert not _project_uses_cpp_unsupported_features(project)
