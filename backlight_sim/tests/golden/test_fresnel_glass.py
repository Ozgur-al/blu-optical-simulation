"""GOLD-03: Fresnel transmittance at an air->glass interface.

Parametrized over 5 incidence angles {0, 30, 45, 60, 80} degrees. Scene is
a single SolidBox glass slab with ``face_optics={"bottom": "absorber"}`` so
any ray that refracts into the glass and reaches the bottom face is killed
there — this is the Pitfall-1 mitigation from 03-RESEARCH.md Case 3.

Measurement topology is REFLECTED-FLUX: a planar detector is placed along
the mirror-reflected direction from the top face. T is computed as

    T_measured = 1.0 - reflected_flux / source_flux

This routes via the SolidBox Fresnel dispatch at ``tracer.py:1242``; the
scene is forced onto the Python path by ``solid_bodies`` being non-empty
(see ``_project_uses_cpp_unsupported_features`` at tracer.py:264).

200k rays per angle, +/-0.02 absolute tolerance per RESEARCH Tolerance
Design (6-13x MC standard error).
"""
from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.golden.cases import GoldenResult
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.sim.sampling import sample_angular_distribution
from backlight_sim.tests.golden.references import fresnel_transmittance_unpolarized


_TOLERANCE = 0.02
_RAYS = 200_000


def _pencil_mean_incidence_deg(theta_deg: float) -> float:
    """Smoke probe: draw 10k rays from the same pencil distribution the
    builder installs (``theta_deg=[0, 1], intensity=[1, 0]``), aim them
    along the builder's source direction, and return the mean angle
    between drawn rays and the top face normal (+z).

    Guards the 2-point CDF sampler (Warning #4): if the ``intensity=[1, 0]``
    sampler silently collapses to ``theta=0``, the Fresnel tests would
    measure normal incidence at every angle and all still pass within
    +/-0.02 because T(0) is a single value. This probe fails loudly before
    the expensive 200k-ray run.
    """
    theta_rad = float(np.radians(theta_deg))
    # Same source direction the builder produces for this theta.
    src_dir = np.array([0.0, float(np.sin(theta_rad)), -float(np.cos(theta_rad))])
    src_dir = src_dir / np.linalg.norm(src_dir)

    rng = np.random.default_rng(42)
    dirs = sample_angular_distribution(
        n=10_000,
        normal=src_dir,
        theta_deg=np.array([0.0, 1.0]),
        intensity=np.array([1.0, 0.0]),
        rng=rng,
    )
    # Top face normal is +z; incidence angle = arccos(|d . n|) where d is
    # the ray direction (heading toward the surface). For d tilted downward
    # by theta, cos(incidence) = |d_z| so angle = arccos(|d_z|).
    incidence = np.degrees(np.arccos(np.clip(np.abs(dirs[:, 2]), 0.0, 1.0)))
    return float(np.mean(incidence))


@pytest.mark.parametrize("theta_deg", [0, 30, 45, 60, 80])
def test_fresnel_transmittance_matches_analytic(
    theta_deg, make_fresnel_scene, assert_within_tolerance,
):
    # --- Pencil-distribution smoke probe (Warning #4 guard) ---
    # Must use the identifier `mean_incidence` and the literal `< 2.0`.
    mean_incidence = _pencil_mean_incidence_deg(theta_deg)
    assert abs(mean_incidence - theta_deg) < 2.0, (
        f"Pencil distribution collapsed: mean_incidence={mean_incidence:.3f} deg "
        f"differs from target {theta_deg} deg by >= 2.0 deg. The 2-point CDF "
        f"sampler (intensity=[1.0, 0.0]) may have silently collapsed to theta=0 "
        f"- all Fresnel angles would otherwise measure normal incidence and "
        f"still pass within +/-0.02 because T(0) is a single value."
    )

    # --- Build scene and verify pitfall-1 guard on the SolidBox ---
    project = make_fresnel_scene(theta_deg=theta_deg, rays=_RAYS, n_glass=1.5)
    slab = project.solid_bodies[0]
    assert getattr(slab, "face_optics", None), (
        "Pitfall-1 guard missing: SolidBox must carry face_optics override "
        "on one face to kill the second interface (else T_measured = T(theta_i) "
        "* T(theta_t) ~ T^2)."
    )
    face_optics = slab.face_optics or {}
    assert "absorber" in face_optics.values(), (
        "Pitfall-1 guard missing: face_optics must map one face to 'absorber'."
    )
    # The override key must resolve against project.optical_properties.
    op = project.optical_properties.get("absorber")
    assert op is not None and op.surface_type == "absorber", (
        "Pitfall-1 guard broken: project.optical_properties['absorber'] must "
        "exist with surface_type='absorber' (tracer.py:1163 dispatch)."
    )

    # --- Run tracer and measure transmittance via reflected-flux topology ---
    result = RayTracer(project).run()
    reflected_flux = float(result.detectors["reflected"].total_flux)
    source_flux = float(project.sources[0].flux)
    assert source_flux > 0.0
    R_measured = reflected_flux / source_flux
    T_measured = 1.0 - R_measured
    T_expected = float(
        fresnel_transmittance_unpolarized(float(np.radians(theta_deg)), 1.0, 1.5)
    )

    assert_within_tolerance(GoldenResult(
        name=f"fresnel_T_theta={theta_deg}",
        expected=T_expected,
        measured=T_measured,
        residual=abs(T_measured - T_expected),
        tolerance=_TOLERANCE,
        rays=_RAYS,
        notes=(
            f"air->glass n=1.5, reflected-flux topology, single interface "
            f"(face_optics bottom=absorber)"
        ),
    ))
