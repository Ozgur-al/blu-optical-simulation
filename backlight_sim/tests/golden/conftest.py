"""Shared fixtures for the golden-reference suite.

Imports GoldenResult from backlight_sim.golden.cases (single source of truth).
Every fixture returns a fresh Project dataclass seeded with GOLDEN_SEED.

Scene-building logic lives in backlight_sim.golden.builders so the CLI case
registry can reuse the exact same builders without pulling the test package
onto its import path.
"""
from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.core.sources import PointSource
from backlight_sim.golden.cases import GoldenResult
from backlight_sim.golden import builders as _builders


GOLDEN_SEED = _builders.GOLDEN_SEED


# Re-exported for backwards compatibility with Wave 0 tests that imported it
# directly from conftest. Prefer the builders module going forward.
_base_project = _builders._base_project


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


# --- Scene-builder fixture wrappers ----------------------------------------
# Each fixture returns a callable that forwards to the shared builder in
# backlight_sim.golden.builders. Waves 2/3 will fill in make_fresnel_scene and
# make_prism_scene the same way.


@pytest.fixture
def make_integrating_cavity_scene():
    def _build(radius: float = 50.0, rho: float = 0.9, rays: int = 500_000) -> Project:
        return _builders.build_integrating_cavity_project(
            radius=radius, rho=rho, rays=rays,
        )
    return _build


@pytest.fixture
def make_lambertian_emitter_scene():
    def _build(rays: int = 500_000) -> Project:
        return _builders.build_lambertian_emitter_project(rays=rays)
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
        return _builders.build_specular_mirror_project(
            theta_deg=theta_deg, rays=rays, use_farfield=use_farfield,
        )
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
