"""GOLD-02: Lambertian emitter angular intensity matches I0 * cos(theta).

Scene — see ``backlight_sim.golden.builders.build_lambertian_emitter_project``:
a single Lambertian point source at the origin aimed at -Z (so the cosine-law
peak aligns with the candela grid's theta=0 bin) and a single
``SphereDetector(mode="far_field")`` at the origin (forces Python path via
``_project_uses_cpp_unsupported_features`` at tracer.py:272).

Validation: peak-normalize the mean-over-azimuth candela profile, mask out
grazing angles (theta > 80°) and the back hemisphere (theta > 90°), then
compute RMS deviation from cos(theta). Tolerance: RMS < 0.03 at 500k rays
seeded at GOLDEN_SEED=42.
"""
from __future__ import annotations

import numpy as np

from backlight_sim.golden.cases import GoldenResult
from backlight_sim.sim.tracer import RayTracer


def test_lambertian_emitter_matches_cosine(make_lambertian_emitter_scene,
                                           assert_within_tolerance):
    rays = 500_000
    project = make_lambertian_emitter_scene(rays=rays)

    result = RayTracer(project).run()
    sd = result.sphere_detectors["farfield"]
    assert sd.candela_grid is not None, (
        "Far-field candela_grid is None — verify compute_farfield_candela "
        "ran (tracer.py:2934) and SphereDetector mode='far_field'"
    )

    # Mean candela across azimuth bins at each polar bin.
    profile = sd.candela_grid.mean(axis=1)   # (n_theta,)
    n_theta = profile.shape[0]
    theta_centers = (np.arange(n_theta) + 0.5) * np.pi / n_theta

    # Mask out grazing (theta > 80°) and back hemisphere (theta > 90°).
    mask = theta_centers <= np.radians(80.0)
    mask &= theta_centers <= np.pi / 2.0

    measured_masked = profile[mask]
    assert measured_masked.max() > 0, (
        "Lambertian profile is zero everywhere — check source direction=(0,0,-1) "
        "and that max_bounces>=1 so sphere-detector accumulation loop runs"
    )

    measured_norm = measured_masked / measured_masked.max()
    expected = np.cos(theta_centers[mask])
    rms = float(np.sqrt(np.mean((measured_norm - expected) ** 2)))

    assert_within_tolerance(GoldenResult(
        name="lambertian_cosine",
        expected=0.0,        # target RMS deviation from cos(theta) is zero
        measured=rms,
        residual=rms,
        tolerance=0.03,      # RESEARCH § Tolerance Design
        rays=rays,
        notes=f"n_theta={n_theta}, mask<=80°",
    ))
