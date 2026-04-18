"""Shared fixtures for the golden-reference suite.

Imports GoldenResult from backlight_sim.golden.cases (single source of truth).
Every fixture returns a fresh Project dataclass seeded with GOLDEN_SEED.
"""
from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.core.sources import PointSource
from backlight_sim.golden.cases import GoldenResult


GOLDEN_SEED = 42


@pytest.fixture
def assert_within_tolerance():
    def _check(result: GoldenResult) -> None:
        assert result.residual < result.tolerance, (
            f"{result.name}: residual={result.residual:.4g} "
            f"exceeds tolerance={result.tolerance:.4g} "
            f"(expected={result.expected:.4g}, measured={result.measured:.4g}, "
            f"rays={result.rays})"
        )
    return _check


# --- Scene-builder fixture STUBS -------------------------------------------
# Wave 0 provides signatures + minimal bodies that return a valid Project
# (so pytest --collect-only passes). Plans 02/03 replace bodies with real
# geometry. DO NOT change the signatures in downstream waves — they are the
# contract consumed by the test_*.py files.


def _base_project(name: str, rays: int, max_bounces: int = 50) -> Project:
    """Minimal Project with GOLDEN_SEED — downstream fixtures extend this."""
    project = Project(name=name)
    project.settings = SimulationSettings(
        rays_per_source=rays,
        max_bounces=max_bounces,
        energy_threshold=0.001,
        random_seed=GOLDEN_SEED,
        record_ray_paths=0,
        distance_unit="mm",
    )
    return project


@pytest.fixture
def make_integrating_cavity_scene():
    def _build(radius: float = 50.0, rho: float = 0.9, rays: int = 500_000) -> Project:
        # Plan 02 fills in: SolidBox cavity + interior Lambertian reflector +
        # small detector patch far from corners. For Wave 0, returns a
        # trivially valid project — downstream plans replace body.
        project = _base_project(f"integrating_cavity_rho{rho}", rays)
        project.sources.append(PointSource("src", np.array([0.0, 0.0, 0.0]), flux=1000.0))
        return project
    return _build


@pytest.fixture
def make_lambertian_emitter_scene():
    def _build(rays: int = 500_000) -> Project:
        project = _base_project("lambertian_emitter", rays)
        project.sources.append(
            PointSource(
                "src", np.array([0.0, 0.0, 0.0]), flux=1000.0,
                distribution="lambertian",
                direction=np.array([0.0, 0.0, 1.0]),
            )
        )
        # SphereDetector(mode="far_field") added in Plan 02.
        return project
    return _build


@pytest.fixture
def make_fresnel_scene():
    def _build(theta_deg: float = 0.0, rays: int = 200_000,
               n_glass: float = 1.5) -> Project:
        project = _base_project(f"fresnel_theta{theta_deg}", rays)
        project.sources.append(
            PointSource("src", np.array([0.0, 0.0, 10.0]), flux=1000.0,
                        direction=np.array([0.0, 0.0, -1.0]))
        )
        # Plan 03 fills in: SolidBox(glass, face_optics={"bottom": "absorber"})
        # + transmitted/reflected DetectorSurfaces. Pitfall 1 guard REQUIRED.
        return project
    return _build


@pytest.fixture
def make_specular_mirror_scene():
    def _build(theta_deg: float = 30.0, rays: int = 100_000,
               use_farfield: bool = False) -> Project:
        project = _base_project(f"specular_theta{theta_deg}_ff{use_farfield}", rays)
        project.sources.append(
            PointSource("src", np.array([0.0, 0.0, 10.0]), flux=1000.0,
                        direction=np.array([0.0, 0.0, -1.0]))
        )
        # Plan 02 fills in: tilted Rectangle reflector + planar detector (C++)
        # or SphereDetector(mode="far_field") (Python) based on use_farfield.
        return project
    return _build


@pytest.fixture
def make_prism_scene():
    def _build(wavelength_nm: int = 550, apex_deg: float = 45.0,
               theta_in_deg: float = 20.0, rays: int = 500_000) -> Project:
        project = _base_project(f"prism_lambda{wavelength_nm}", rays)
        project.sources.append(
            PointSource(
                "src", np.array([0.0, 0.0, 10.0]), flux=1000.0,
                direction=np.array([0.0, 0.0, -1.0]),
                spd=f"mono_{wavelength_nm}",  # MANDATORY — triggers has_spectral
            )
        )
        # Plan 03 fills in:
        #   - project.spectral_material_data["bk7"] = {
        #         "wavelength_nm":[450,550,650],
        #         "refractive_index":[1.5252,1.5187,1.5145]}
        #   - SolidPrism(n_sides=3, material_name="bk7", ...)
        #   - SphereDetector(mode="far_field") on exit side
        return project
    return _build
