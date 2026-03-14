from __future__ import annotations

from dataclasses import dataclass, field

from backlight_sim.core.sources import PointSource
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material, OpticalProperties
from backlight_sim.core.detectors import DetectorSurface, SphereDetector
from backlight_sim.core.solid_body import SolidBox, SolidCylinder, SolidPrism


@dataclass
class SimulationSettings:
    rays_per_source: int = 10_000
    max_bounces: int = 50
    energy_threshold: float = 0.001
    random_seed: int = 42
    distance_unit: str = "mm"
    flux_unit: str = "lm"
    angle_unit: str = "deg"
    record_ray_paths: int = 200
    use_multiprocessing: bool = False
    # Adaptive sampling: stop ray generation per source when detector CV% converges
    adaptive_sampling: bool = True
    convergence_cv_target: float = 2.0   # CV% threshold — stop when CV drops below this
    check_interval: int = 1000           # Check convergence every N rays per source


@dataclass
class Project:
    name: str = "Untitled"
    sources: list[PointSource] = field(default_factory=list)
    surfaces: list[Rectangle] = field(default_factory=list)
    materials: dict[str, Material] = field(default_factory=dict)
    optical_properties: dict[str, OpticalProperties] = field(default_factory=dict)
    detectors: list[DetectorSurface] = field(default_factory=list)
    sphere_detectors: list[SphereDetector] = field(default_factory=list)
    solid_bodies: list[SolidBox] = field(default_factory=list)
    solid_cylinders: list[SolidCylinder] = field(default_factory=list)
    solid_prisms: list[SolidPrism] = field(default_factory=list)
    # Name -> {"theta_deg": [...], "intensity": [...]}
    angular_distributions: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    # SPD profiles: { name: {"wavelength_nm": [...], "intensity": [...]} }
    spd_profiles: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    # Material spectral data: { optics_name: {"wavelength_nm": [...], "reflectance": [...], "transmittance": [...]} }
    spectral_material_data: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    # BSDF profiles: { name: {"theta_in": [...], "theta_out": [...],
    #                         "refl_intensity": [[...], ...],  # M x N (M=theta_in, N=theta_out)
    #                         "trans_intensity": [[...], ...]} }
    bsdf_profiles: dict[str, dict] = field(default_factory=dict)
    settings: SimulationSettings = field(default_factory=SimulationSettings)
