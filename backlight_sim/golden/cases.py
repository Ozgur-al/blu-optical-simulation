"""Golden-reference case registry — shared source of truth for pytest + CLI.

Mirrors backlight_sim/io/presets.py factory/registry pattern. Each GoldenCase
carries a project factory and a measurement function; run_case() runs the tracer
and produces a GoldenResult that pytest asserts on and the CLI reports on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

from backlight_sim.core.project_model import Project


@dataclass
class GoldenResult:
    name: str
    expected: float
    measured: float
    residual: float
    tolerance: float
    rays: int
    passed: Optional[bool] = None
    notes: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class GoldenCase:
    name: str
    description: str
    build_project: Callable[[Optional[int]], Project]
    measure: Callable[[Project, Any], GoldenResult]
    default_rays: int
    expected_runtime_s: float


def run_case(
    case: GoldenCase,
    rays_override: Optional[int] = None,
    verbose: bool = False,
) -> GoldenResult:
    """Build a case's project, run the tracer, produce a GoldenResult with .passed set."""
    from backlight_sim.sim.tracer import RayTracer  # lazy — keeps import cheap
    project = case.build_project(rays_override)
    result = RayTracer(project).run()
    gr = case.measure(project, result)
    gr.passed = bool(gr.residual < gr.tolerance)
    if verbose:
        status = "PASS" if gr.passed else "FAIL"
        print(
            f"[{status}] {gr.name}: residual={gr.residual:.4g} "
            f"tol={gr.tolerance:.4g} rays={gr.rays}"
        )
    return gr


ALL_CASES: list[GoldenCase] = []


# ---------------------------------------------------------------------------
# Case registrations — Wave 1 (Plan 03-02)
# ---------------------------------------------------------------------------
# Project builders live in backlight_sim.golden.builders so both pytest
# fixtures and the CLI can reuse them without circular imports. The measure
# callables depend on references.py (analytical formulas) which lives in
# the test package — the lazy imports inside each callable keep the CLI's
# cold-start cost low and the shipped package's runtime free of test deps.


def _build_integrating_cavity(rays_override: Optional[int]) -> Project:
    from backlight_sim.golden.builders import build_integrating_cavity_project
    rays = rays_override if rays_override is not None else 500_000
    return build_integrating_cavity_project(radius=50.0, rho=0.9, rays=rays)


def _measure_integrating_cavity(project: Project, result) -> GoldenResult:
    from backlight_sim.tests.golden.references import (
        integrating_sphere_port_irradiance,
    )
    det = result.detectors["patch"]
    patch_area = float(np.prod(project.detectors[0].size))
    E_measured = float(det.total_flux) / patch_area
    # 6 walls × (2 * radius)² total inner area = 24 * radius².
    radius = 50.0
    total_area = 24.0 * radius ** 2
    E_expected = integrating_sphere_port_irradiance(
        phi=project.sources[0].flux,
        port_area=patch_area,
        total_wall_area=total_area,
        rho=0.9,
        source_to_port_distance=radius,
    )
    rel = abs(E_measured - E_expected) / E_expected
    return GoldenResult(
        name="integrating_cavity",
        expected=E_expected,
        measured=E_measured,
        residual=rel,
        tolerance=0.02,
        rays=int(project.settings.rays_per_source),
        notes=f"rho=0.9, radius={radius}, bounces={project.settings.max_bounces}",
    )


def _build_lambertian_cosine(rays_override: Optional[int]) -> Project:
    from backlight_sim.golden.builders import build_lambertian_emitter_project
    rays = rays_override if rays_override is not None else 500_000
    return build_lambertian_emitter_project(rays=rays)


def _measure_lambertian_cosine(project: Project, result) -> GoldenResult:
    sd = result.sphere_detectors["farfield"]
    profile = sd.candela_grid.mean(axis=1)
    n_theta = profile.shape[0]
    theta_centers = (np.arange(n_theta) + 0.5) * np.pi / n_theta
    # Mask: drop grazing (theta > 80°) and back hemisphere (theta > 90°).
    mask = theta_centers <= np.radians(80.0)
    mask &= theta_centers <= np.pi / 2.0
    masked = profile[mask]
    if masked.max() <= 0:
        rms = float("inf")
    else:
        meas_norm = masked / masked.max()
        expected = np.cos(theta_centers[mask])
        rms = float(np.sqrt(np.mean((meas_norm - expected) ** 2)))
    return GoldenResult(
        name="lambertian_cosine",
        expected=0.0,
        measured=rms,
        residual=rms,
        tolerance=0.03,
        rays=int(project.settings.rays_per_source),
        notes=f"n_theta={n_theta}, mask<=80°",
    )


def _build_specular_farfield(rays_override: Optional[int]) -> Project:
    from backlight_sim.golden.builders import build_specular_mirror_project
    rays = rays_override if rays_override is not None else 100_000
    return build_specular_mirror_project(
        theta_deg=30.0, rays=rays, use_farfield=True,
    )


def _measure_specular_farfield(project: Project, result) -> GoldenResult:
    sd = result.sphere_detectors["farfield"]
    # Use raw flux grid (not candela_grid) to find the peak bin — candela_grid
    # is divided by sin(theta) per bin, so pole bins dominate on noise alone.
    grid = sd.grid
    peak = np.unravel_index(int(np.argmax(grid)), grid.shape)
    n_theta, n_phi = grid.shape
    theta_peak = (peak[0] + 0.5) * np.pi / n_theta
    phi_peak = (peak[1] + 0.5) * 2.0 * np.pi / n_phi
    # Expected reflected direction (measured as -ray_direction in far-field
    # convention). For a straight-down ray at incidence theta=30° on a
    # mirror tilted by 30° about +X, the reflected ray travels at
    # (0, sin(60°), cos(60°)); its far-field-recorded direction is the
    # negation of that, giving theta_exp = 180° - 60° = 120°, phi_exp = 270°.
    theta_deg = 30.0
    theta_exp = float(np.pi - 2.0 * np.radians(theta_deg))
    phi_exp = float(1.5 * np.pi)
    # Angular separation on the unit sphere.
    def _xyz(th, ph):
        return np.array([
            np.sin(th) * np.cos(ph),
            np.sin(th) * np.sin(ph),
            np.cos(th),
        ])
    cos_ang = float(np.clip(np.dot(_xyz(theta_peak, phi_peak),
                                   _xyz(theta_exp, phi_exp)), -1.0, 1.0))
    residual_deg = float(np.degrees(np.arccos(cos_ang)))
    return GoldenResult(
        name="specular_reflection_python",
        expected=theta_deg,
        measured=float(np.degrees(theta_peak)),
        residual=residual_deg,
        tolerance=0.5,
        rays=int(project.settings.rays_per_source),
        notes="far-field SphereDetector (0.5° bins), Python path",
    )


def _build_specular_planar(rays_override: Optional[int]) -> Project:
    from backlight_sim.golden.builders import build_specular_mirror_project
    rays = rays_override if rays_override is not None else 100_000
    return build_specular_mirror_project(
        theta_deg=30.0, rays=rays, use_farfield=False,
    )


def _measure_specular_planar(project: Project, result) -> GoldenResult:
    det = result.detectors["planar"]
    grid = det.grid
    total = float(grid.sum())
    if total <= 0:
        residual_deg = float("inf")
    else:
        ny, nx = grid.shape
        us = (np.arange(nx) + 0.5) / nx - 0.5
        vs = (np.arange(ny) + 0.5) / ny - 0.5
        U, V = np.meshgrid(us, vs)
        u_cent = float((grid * U).sum() / total)
        v_cent = float((grid * V).sum() / total)
        det_size = project.detectors[0].size
        offset_mm = float(np.hypot(u_cent * det_size[0], v_cent * det_size[1]))
        # Mirror-to-detector distance (hard-coded in the builder as D=30mm).
        distance = 30.0
        residual_deg = float(np.degrees(np.arctan2(offset_mm, distance)))
    return GoldenResult(
        name="specular_reflection_cpp",
        expected=30.0,
        measured=30.0 + residual_deg,
        residual=residual_deg,
        tolerance=1.0,
        rays=int(project.settings.rays_per_source),
        notes="planar DetectorSurface, C++ path",
    )


ALL_CASES.append(GoldenCase(
    name="integrating_cavity",
    description=(
        "Integrating-cavity port irradiance vs sphere-throughput analytical "
        "formula (direct + indirect components). Tests diffuse Lambertian "
        "reflection block on the Python path."
    ),
    build_project=_build_integrating_cavity,
    measure=_measure_integrating_cavity,
    default_rays=500_000,
    expected_runtime_s=40.0,
))

ALL_CASES.append(GoldenCase(
    name="lambertian_cosine",
    description=(
        "Lambertian emitter angular intensity matches I0·cos(theta) via "
        "SphereDetector(mode='far_field') candela readout. Python path."
    ),
    build_project=_build_lambertian_cosine,
    measure=_measure_lambertian_cosine,
    default_rays=500_000,
    expected_runtime_s=15.0,
))

ALL_CASES.append(GoldenCase(
    name="specular_reflection_python",
    description=(
        "Law of reflection on a tilted specular mirror, measured via far-field "
        "sphere detector (forces Python path)."
    ),
    build_project=_build_specular_farfield,
    measure=_measure_specular_farfield,
    default_rays=100_000,
    expected_runtime_s=5.0,
))

ALL_CASES.append(GoldenCase(
    name="specular_reflection_cpp",
    description=(
        "Law of reflection on a tilted specular mirror, measured via planar "
        "detector (no unsupported features → routes to C++ path)."
    ),
    build_project=_build_specular_planar,
    measure=_measure_specular_planar,
    default_rays=100_000,
    expected_runtime_s=3.0,
))
