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

    def __post_init__(self):
        self.position = np.asarray(self.position, dtype=float)
        if self.direction is None:
            self.direction = np.array([0.0, 0.0, 1.0])
        else:
            self.direction = np.asarray(self.direction, dtype=float)
            norm = np.linalg.norm(self.direction)
            if norm > 0:
                self.direction = self.direction / norm
