"""GOLD-01: integrating-cavity port irradiance vs analytical formula.

Scene — see ``backlight_sim.golden.builders.build_integrating_cavity_project``:
a closed cubic Lambertian cavity (rho=0.9, 2r=100mm) built from 6 Rectangle
walls with a 10x10 mm exit port on the top face, isotropic source at the
center, and a planar detector occupying the port. A dummy
``spectral_material_data`` entry forces the tracer onto the Python path so
the Lambertian reflection block is exercised.

The expected port irradiance combines direct (inverse-square) and indirect
(integrating-sphere throughput) components; see
``backlight_sim.tests.golden.references.integrating_sphere_port_irradiance``.
Tolerance ±2% relative at 500k rays seeded at GOLDEN_SEED=42.
"""
from __future__ import annotations

import numpy as np

from backlight_sim.golden.cases import GoldenResult
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.tests.golden.references import (
    integrating_sphere_port_irradiance,
)


def test_integrating_cavity_port_irradiance(make_integrating_cavity_scene,
                                            assert_within_tolerance):
    rho = 0.9
    radius = 50.0
    rays = 500_000
    project = make_integrating_cavity_scene(radius=radius, rho=rho, rays=rays)

    result = RayTracer(project).run()
    det = result.detectors["patch"]
    assert det.total_hits > 0, (
        "Patch detector saw zero hits — check geometry orientation (port on "
        "top wall facing -Z)"
    )

    patch_area = float(np.prod(project.detectors[0].size))   # 10 * 10 = 100 mm²
    E_measured = float(det.total_flux) / patch_area

    # Cube cavity inner area = 6 faces × (2r)² = 24 r²
    total_area = 24.0 * radius ** 2
    E_expected = integrating_sphere_port_irradiance(
        phi=project.sources[0].flux,
        port_area=patch_area,
        total_wall_area=total_area,
        rho=rho,
        source_to_port_distance=radius,
    )
    rel_residual = abs(E_measured - E_expected) / E_expected

    assert_within_tolerance(GoldenResult(
        name="integrating_cavity",
        expected=E_expected,
        measured=E_measured,
        residual=rel_residual,
        tolerance=0.02,       # ±2% per plan / RESEARCH § Tolerance Design
        rays=rays,
        notes=f"rho={rho}, radius={radius}, bounces={project.settings.max_bounces}",
    ))
