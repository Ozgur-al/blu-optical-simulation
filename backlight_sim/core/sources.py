from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class PointSource:
    """A point light source in 3D space."""

    name: str
    position: np.ndarray  # (3,)
    flux: float = 100.0  # total emitted power (arbitrary units)
    direction: np.ndarray = None  # (3,) forward direction for lambertian
    distribution: str = "isotropic"  # "isotropic" or "lambertian"
    enabled: bool = True  # when False the tracer skips this source
    flux_tolerance: float = 0.0  # ±% bin tolerance (e.g. 10 = ±10%)
    current_mA: float = 0.0  # drive current in mA (0 = use flux directly)
    flux_per_mA: float = 0.0  # lm/mA scaling (0 = use flux directly)
    thermal_derate: float = 1.0  # thermal derating factor 0-1 (1 = no derating)
    color_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)  # LED color as (R, G, B) weights 0-1
    # Spectral power distribution: "white" | "warm_white" | "cool_white" | "mono_<nm>" | custom key
    spd: str = "white"

    @property
    def effective_flux(self) -> float:
        """Compute flux after current scaling and thermal derating."""
        base = self.flux
        if self.current_mA > 0 and self.flux_per_mA > 0:
            base = self.current_mA * self.flux_per_mA
        return base * self.thermal_derate

    def __post_init__(self):
        self.position = np.asarray(self.position, dtype=float)
        if self.direction is None:
            self.direction = np.array([0.0, 0.0, 1.0])
        else:
            self.direction = np.asarray(self.direction, dtype=float)
            norm = np.linalg.norm(self.direction)
            if norm > 0:
                self.direction = self.direction / norm
