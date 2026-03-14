from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class Rectangle:
    """Arbitrarily-oriented rectangle in 3D space.

    Internal representation uses two orthonormal in-plane axes so that
    tilted walls (e.g. from the geometry builder) work correctly.
    The outward normal is cross(u_axis, v_axis).
    """

    name: str
    center: np.ndarray         # (3,) world-space center
    u_axis: np.ndarray         # (3,) normalized local x-axis of the plane
    v_axis: np.ndarray         # (3,) normalized local y-axis of the plane
    size: tuple[float, float]  # (width along u, height along v)
    material_name: str = "default_reflector"
    optical_properties_name: str = ""  # if set, overrides material's optical behavior

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)
        self.u_axis = np.asarray(self.u_axis, dtype=float)
        self.v_axis = np.asarray(self.v_axis, dtype=float)
        for ax in ("u_axis", "v_axis"):
            v = getattr(self, ax)
            ln = np.linalg.norm(v)
            if ln > 0:
                setattr(self, ax, v / ln)

    @property
    def normal(self) -> np.ndarray:
        n = np.cross(self.u_axis, self.v_axis)
        ln = np.linalg.norm(n)
        return n / ln if ln > 0 else n

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def axis_aligned(
        cls,
        name: str,
        center,
        size: tuple[float, float],
        normal_axis: int,
        normal_sign: float,
        material_name: str = "default_reflector",
    ) -> "Rectangle":
        """Create an axis-aligned rectangle from the legacy normal_axis/sign API."""
        # Mappings chosen so cross(u, v) == normal_sign * e[normal_axis]
        _map = {
            (0,  1.0): ([0, 1, 0], [0,  0,  1]),
            (0, -1.0): ([0, 1, 0], [0,  0, -1]),
            (1,  1.0): ([0, 0, 1], [1,  0,  0]),
            (1, -1.0): ([0, 0, 1], [-1, 0,  0]),
            (2,  1.0): ([1, 0, 0], [0,  1,  0]),
            (2, -1.0): ([1, 0, 0], [0, -1,  0]),
        }
        u, v = _map[(int(normal_axis), float(normal_sign))]
        return cls(name, np.asarray(center, float),
                   np.array(u, float), np.array(v, float), size, material_name)

    # ------------------------------------------------------------------
    # UI helpers (approximate for tilted walls)
    # ------------------------------------------------------------------

    @property
    def dominant_normal_axis(self) -> int:
        return int(np.argmax(np.abs(self.normal)))

    @property
    def dominant_normal_sign(self) -> float:
        return float(np.sign(self.normal[self.dominant_normal_axis]))
