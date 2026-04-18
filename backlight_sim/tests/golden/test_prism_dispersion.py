"""GOLD-05: Prism dispersion vs Snell's law at 3 wavelengths.

CLOSES the ``project_spectral_ri_testing.md`` memory flag: the solid-body
spectral n(lambda) refraction path was smoke-tested but never physically
verified. This test covers both (a) per-lambda Snell-angle accuracy AND
(b) the dispersion-detection guard
``Δθ(450 → 650) > 0.1°`` (Pitfall 3) — without (b), a silent fallback to
scalar ``refractive_index`` would produce zero dispersion and pass an
ambiguous tolerance.

Routed to the Python path via SolidPrism + ``spd='mono_*'`` (see
``tracer.py:631`` and ``tracer.py:1495``). 500k rays/lambda,
±0.25° per wavelength on total deviation.

Geometry note (Rule-4 deviation)
--------------------------------
RESEARCH.md recommended ``apex=45°, theta_in=20°`` but ``SolidPrism(n_sides=3)``
is FIXED as an equilateral triangle (apex=60°). The plan's default
``theta_in=20°`` combined with apex=60° causes TIR at the exit face for
all three BK7 wavelengths per ``snell_exit_angle``. The orchestrator
authorized a Rule-4 deviation to ``theta_in=40°`` (near min-deviation for
BK7 at apex=60°) — dispersion drops from 0.4° (planner estimate at
apex=45°) to ~1.2° (analytical at apex=60°, theta_in=40°), which is still
12× above the 0.1° memory-flag guard.

See RESEARCH.md §Case 5 + §Pitfall 3.
"""
from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.golden.builders import (
    PRISM_APEX_DEG,
    PRISM_THETA_IN_DEG,
)
from backlight_sim.golden.cases import GoldenResult
from backlight_sim.sim.tracer import (
    RayTracer,
    _project_uses_cpp_unsupported_features,
)
from backlight_sim.tests.golden.references import snell_exit_angle


_APEX_DEG = 60.0          # n_sides=3 equilateral prism — see builder enforcement
_THETA_IN_DEG = 40.0      # Rule-4 deviation — see module docstring


# Static check: the builder constants must match this module's constants.
# If a future refactor changes one without the other, this pytest-time
# import-level assert fails loudly.
assert abs(PRISM_APEX_DEG - _APEX_DEG) < 1e-9, (
    f"Builder PRISM_APEX_DEG={PRISM_APEX_DEG} differs from test "
    f"_APEX_DEG={_APEX_DEG}. Keep these in sync — Snell reference "
    f"calls in this test reuse _APEX_DEG."
)
assert abs(PRISM_THETA_IN_DEG - _THETA_IN_DEG) < 1e-9, (
    f"Builder PRISM_THETA_IN_DEG={PRISM_THETA_IN_DEG} differs from test "
    f"_THETA_IN_DEG={_THETA_IN_DEG}."
)


def _peak_direction_from_sphere(sph_result) -> np.ndarray:
    """Return a unit-direction vector for the peak bin of a far-field
    ``SphereDetectorResult``.

    Uses the raw flux grid (not ``candela_grid``) — the candela grid
    divides by ``sin(theta)`` which amplifies pole-bin noise (see the
    specular test's measure function in ``cases.py``).
    """
    grid = sph_result.grid
    peak = np.unravel_index(int(np.argmax(grid)), grid.shape)
    n_theta, n_phi = grid.shape
    theta_peak = (peak[0] + 0.5) * np.pi / n_theta
    phi_peak = (peak[1] + 0.5) * 2.0 * np.pi / n_phi
    # Far-field records ``-direction`` — so the exit direction is the
    # negation of the unit vector at (theta_peak, phi_peak).
    v = np.array([
        np.sin(theta_peak) * np.cos(phi_peak),
        np.sin(theta_peak) * np.sin(phi_peak),
        np.cos(theta_peak),
    ])
    return -v / np.linalg.norm(v)


def _total_deviation_deg(
    project, result,
) -> float:
    """Angle between source ray direction and measured exit direction."""
    sd = result.sphere_detectors["farfield"]
    d_exit = _peak_direction_from_sphere(sd)
    d_source = project.sources[0].direction
    d_source = d_source / np.linalg.norm(d_source)
    cos_dev = float(np.clip(np.dot(d_source, d_exit), -1.0, 1.0))
    return float(np.degrees(np.arccos(cos_dev)))


def _expected_deviation_deg(n: float) -> float:
    """Analytical total deviation D = theta_in + theta_out - apex."""
    theta_in = float(np.radians(_THETA_IN_DEG))
    apex = float(np.radians(_APEX_DEG))
    theta_out = snell_exit_angle(theta_in, n, apex)
    if np.isnan(theta_out):
        return float("nan")
    return float(np.degrees(theta_in + theta_out - apex))


@pytest.mark.parametrize("wavelength_nm,n_expected", [
    (450, 1.5252),
    (550, 1.5187),
    (650, 1.5145),
])
def test_prism_exit_angle_matches_snell(
    wavelength_nm, n_expected, make_prism_scene, assert_within_tolerance,
):
    rays = 500_000
    project = make_prism_scene(
        wavelength_nm=wavelength_nm,
        apex_deg=_APEX_DEG,
        theta_in_deg=_THETA_IN_DEG,
        rays=rays,
    )

    # --- Pitfall-3 preconditions (all three required for n(lambda) dispatch) ---
    assert project.sources[0].spd.startswith("mono_"), (
        "Pitfall-3 guard: source.spd must start with 'mono_' to trigger "
        "has_spectral gate (tracer.py:631)"
    )
    assert project.sources[0].spd == f"mono_{wavelength_nm}", (
        f"Pitfall-3 guard: source.spd must be f'mono_{wavelength_nm}' "
        f"(tracer.py:631 samples wavelength from this name)"
    )
    assert "bk7" in project.spectral_material_data, (
        "Pitfall-3 guard: spectral_material_data['bk7'] missing — dispatch "
        "at tracer.py:1495 would silently fall back to scalar n"
    )
    assert "refractive_index" in project.spectral_material_data["bk7"], (
        "Pitfall-3 guard: spectral_material_data['bk7']['refractive_index'] "
        "missing — dispatch at tracer.py:1496 'refractive_index in' check fails"
    )

    # Must route to the Python path (SolidPrism + mono SPD).
    assert _project_uses_cpp_unsupported_features(project), (
        "Prism scene must route to Python path (SolidPrism + mono_* spd) — "
        "the C++ extension does not implement spectral n(lambda) dispatch"
    )

    # --- Run tracer and measure total deviation ---
    result = RayTracer(project).run()
    sd = result.sphere_detectors["farfield"]
    assert sd.grid is not None and sd.grid.sum() > 0, (
        f"Sphere detector saw zero flux at lambda={wavelength_nm} — "
        "check prism geometry / source direction"
    )

    dev_measured = _total_deviation_deg(project, result)
    dev_expected = _expected_deviation_deg(n_expected)
    assert not np.isnan(dev_expected), (
        f"Reference Snell predicts TIR at lambda={wavelength_nm} "
        f"(apex={_APEX_DEG}°, theta_in={_THETA_IN_DEG}°, n={n_expected}) — "
        f"geometry unusable"
    )

    residual = abs(dev_measured - dev_expected)
    assert_within_tolerance(GoldenResult(
        name=f"prism_theta_lambda={wavelength_nm}",
        expected=dev_expected,
        measured=dev_measured,
        residual=residual,
        tolerance=0.25,
        rays=rays,
        notes=(
            f"lambda={wavelength_nm} nm, n={n_expected}, apex={_APEX_DEG}°, "
            f"theta_in={_THETA_IN_DEG}° (Rule 4 deviation); total-deviation metric"
        ),
    ))


def test_prism_dispersion_is_nonzero(make_prism_scene, assert_within_tolerance):
    """MEMORY-FLAG CLOSURE: Δθ(450 → 650) MUST be > 0.1°.

    Regression guard from RESEARCH §Pitfall 3. If the
    ``spectral_material_data`` dispatch at ``tracer.py:1495`` silently
    falls back to scalar ``refractive_index`` (key mismatch, missing
    sub-key, spd starts with 'mono' but has_spectral check is broken,
    etc.), all three wavelengths refract identically and Δθ → 0. A
    per-lambda tolerance check can still PASS with Δθ = 0 because all
    three expected angles land within 0.25° of the scalar-n prediction.
    This test explicitly rejects that failure mode.

    Closes: ``~/.claude/projects/.../memory/project_spectral_ri_testing.md``
    """
    rays = 500_000
    deviations_deg = {}
    for wavelength_nm in (450, 650):
        project = make_prism_scene(
            wavelength_nm=wavelength_nm,
            apex_deg=_APEX_DEG,
            theta_in_deg=_THETA_IN_DEG,
            rays=rays,
        )
        result = RayTracer(project).run()
        deviations_deg[wavelength_nm] = _total_deviation_deg(project, result)

    # Measured dispersion — identifier ``dispersion_deg`` and literal ``> 0.1``
    # must both be present for the grep acceptance criterion to match.
    dispersion_deg = abs(deviations_deg[450] - deviations_deg[650])

    assert dispersion_deg > 0.1, (
        f"Dispersion test FAILED — dispersion_deg = {dispersion_deg:.4f}° "
        f"<= 0.1°. This indicates the spectral_material_data dispatch at "
        f"tracer.py:1495 is NOT being exercised — all wavelengths are "
        f"refracting with the scalar refractive_index fallback. The memory "
        f"flag ``project_spectral_ri_testing.md`` is NOT closed by this "
        f"test run. Measured deviations: "
        f"dev(450)={deviations_deg[450]:.4f}°, "
        f"dev(650)={deviations_deg[650]:.4f}°."
    )

    # Pack a GoldenResult for the CLI report.
    # Analytical dispersion at apex=60°, theta_in=40° for BK7 n(450)=1.5252,
    # n(650)=1.5145 is ≈ 1.19°. Allow ±25% relative tolerance (MC stderr +
    # sphere-bin quantization at 0.5° bins).
    expected_dispersion_deg = abs(
        _expected_deviation_deg(1.5252) - _expected_deviation_deg(1.5145)
    )
    rel_residual = abs(dispersion_deg - expected_dispersion_deg) / max(
        expected_dispersion_deg, 1e-6,
    )
    assert_within_tolerance(GoldenResult(
        name="prism_dispersion_guard",
        expected=expected_dispersion_deg,
        measured=dispersion_deg,
        residual=rel_residual,
        tolerance=0.25,
        rays=rays,
        notes=(
            f"MEMORY FLAG CLOSURE — project_spectral_ri_testing.md; "
            f"dev(450)={deviations_deg[450]:.4f} deg, "
            f"dev(650)={deviations_deg[650]:.4f} deg"
        ),
    ))
