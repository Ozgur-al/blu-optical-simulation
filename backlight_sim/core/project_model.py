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
    # Uncertainty quantification (Phase 4).
    # K per-source batches for batch-means CI; 0 disables UQ (legacy fast path /
    # back-compat).  Tracer (Wave 2) clamps to [4, 20] at runtime; DoS mitigation
    # for T-04.01-02 in the threat register.
    uq_batches: int = 10
    # Cache per-batch spectral grids so spectral KPIs can report CIs.  Users on
    # memory-tight scenes can disable to skip the K×(ny,nx,n_bins) allocation.
    uq_include_spectral: bool = True
    # Phase 5 — ensemble tolerance defaults
    source_position_sigma_mm: float = 0.0       # project-level isotropic σ in mm for all LEDs
    source_position_distribution: str = "gaussian"  # "gaussian" | "uniform"


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
    # Phase 5 — cavity build recipe for ensemble realization (empty dict = no cavity tolerances)
    # Schema: {"width": float, "height": float, "depth": float,
    #          "wall_angle_x_deg": float, "wall_angle_y_deg": float,
    #          "floor_material": str, "wall_material": str,
    #          "depth_sigma_mm": float, "wall_angle_x_sigma_deg": float,
    #          "wall_angle_y_sigma_deg": float,
    #          "depth_distribution": str, "wall_angle_distribution": str}
    cavity_recipe: dict = field(default_factory=dict)
