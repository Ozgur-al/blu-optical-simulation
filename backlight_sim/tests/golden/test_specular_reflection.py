"""GOLD-04: law of reflection (theta_out == theta_in), dual C++/Python sub-cases.

Scene — see ``backlight_sim.golden.builders.build_specular_mirror_project``:
a perfect specular mirror (R=1) tilted by theta_deg about the x-axis, a
narrow pencil-beam source (5° half-angle) at (0, 0, 20) aimed straight down,
and either a far-field ``SphereDetector`` (Python path) or a planar
``DetectorSurface`` placed on the reflected-ray axis (C++ path).

The two sub-cases assert the tracer's dispatch predicate explicitly in both
directions to catch Pitfall 2 from RESEARCH.md — a scene meant for the C++
path silently falling back to Python (or vice versa) would invalidate the
physics coverage both phases were meant to provide.

Tolerances:
* Far-field peak angle vs expected reflected direction: < 0.5° (0.5°/bin grid)
* Planar centroid offset converted to angular residual: < 1.0° (less precise
  than far-field because the centroid depends on detector size and bin width)
"""
from __future__ import annotations

import numpy as np

from backlight_sim.golden.cases import GoldenResult
from backlight_sim.sim.tracer import (
    RayTracer,
    _project_uses_cpp_unsupported_features,
)


def _unit_xyz(theta: float, phi: float) -> np.ndarray:
    return np.array([
        np.sin(theta) * np.cos(phi),
        np.sin(theta) * np.sin(phi),
        np.cos(theta),
    ])


def test_specular_angle_python_farfield(make_specular_mirror_scene,
                                        assert_within_tolerance):
    theta_deg = 30.0
    rays = 100_000
    project = make_specular_mirror_scene(
        theta_deg=theta_deg, rays=rays, use_farfield=True,
    )
    # SphereDetector(mode='far_field') must route to Python path
    # (see tracer.py:272). If this assertion fires the scene is eligible
    # for C++ and the far-field candela_grid will not be populated.
    assert _project_uses_cpp_unsupported_features(project), (
        "Far-field SphereDetector must force Python path — check scene builder"
    )

    result = RayTracer(project).run()
    sd = result.sphere_detectors["farfield"]
    assert sd.candela_grid is not None, (
        "candela_grid missing — far-field post-processing did not run"
    )

    # Use the raw flux grid (not candela_grid) to find the peak: candela
    # divides by sin(theta) per bin, so pole bins are amplified by up to
    # 10^6x (floor at 1e-6) and dominate on noise alone.
    grid = sd.grid
    peak = np.unravel_index(int(np.argmax(grid)), grid.shape)
    n_theta, n_phi = grid.shape
    theta_peak = (peak[0] + 0.5) * np.pi / n_theta
    phi_peak = (peak[1] + 0.5) * 2.0 * np.pi / n_phi

    # Expected reflected direction in far-field convention.
    # Mirror normal = (0, sin theta, cos theta); incoming ray = (0, 0, -1).
    # Reflected = (0, sin 2theta, cos 2theta). Far-field records -ray_dir,
    # so the sphere-grid direction at peak should equal the NEGATED reflected
    # direction: (0, -sin 2theta, -cos 2theta), giving
    #   theta_ff = arccos(-cos 2theta) = pi - 2 theta
    #   phi_ff   = arctan2(-sin 2theta, 0) = -pi/2 → 3pi/2 after wrap
    theta_exp = float(np.pi - 2.0 * np.radians(theta_deg))
    phi_exp = 1.5 * np.pi

    cos_ang = float(np.clip(
        np.dot(_unit_xyz(theta_peak, phi_peak),
               _unit_xyz(theta_exp, phi_exp)),
        -1.0, 1.0,
    ))
    residual_deg = float(np.degrees(np.arccos(cos_ang)))

    assert_within_tolerance(GoldenResult(
        name="specular_reflection_python",
        expected=theta_deg,
        measured=float(np.degrees(theta_peak)),
        residual=residual_deg,
        tolerance=0.5,
        rays=rays,
        notes="far-field SphereDetector, Python path",
    ))


def test_specular_angle_cpp_planar(make_specular_mirror_scene,
                                   assert_within_tolerance):
    theta_deg = 30.0
    rays = 100_000
    project = make_specular_mirror_scene(
        theta_deg=theta_deg, rays=rays, use_farfield=False,
    )
    # MUST route to C++ per dispatch predicate — Pitfall 2 guard. The scene
    # has no SolidBox, no non-white SPD, no far-field detector, no spectral
    # material data, no BSDF — so the predicate must return False.
    assert not _project_uses_cpp_unsupported_features(project), (
        "Planar-detector scene unexpectedly routes to Python — verify the "
        "builder did not introduce a feature on the unsupported list"
    )

    result = RayTracer(project).run()
    det = result.detectors["planar"]
    assert det.total_hits > 0, (
        "Planar detector saw zero hits — check geometry and source aim"
    )

    grid = det.grid
    total = float(grid.sum())
    assert total > 0, "Planar detector total flux is zero"

    # Centroid in normalized local (u, v) coords — each axis in [-0.5, +0.5].
    ny, nx = grid.shape
    us = (np.arange(nx) + 0.5) / nx - 0.5
    vs = (np.arange(ny) + 0.5) / ny - 0.5
    U, V = np.meshgrid(us, vs)
    u_cent = float((grid * U).sum() / total)
    v_cent = float((grid * V).sum() / total)

    det_size = project.detectors[0].size   # (u_size, v_size)
    offset_mm = float(np.hypot(u_cent * det_size[0], v_cent * det_size[1]))

    # Mirror-to-detector distance from builder (D=30 mm along reflected ray).
    distance = 30.0
    residual_deg = float(np.degrees(np.arctan2(offset_mm, distance)))

    assert_within_tolerance(GoldenResult(
        name="specular_reflection_cpp",
        expected=theta_deg,
        measured=theta_deg + residual_deg,
        residual=residual_deg,
        tolerance=1.0,
        rays=rays,
        notes="planar DetectorSurface, C++ path",
    ))
