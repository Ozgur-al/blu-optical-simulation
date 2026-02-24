from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np


@dataclass
class DetectorSurface:
    """A receiver plane that accumulates light into a 2D grid."""

    name: str
    center: np.ndarray         # (3,)
    u_axis: np.ndarray         # (3,) normalized local x-axis
    v_axis: np.ndarray         # (3,) normalized local y-axis
    size: tuple[float, float]  # (width along u, height along v)
    resolution: tuple[int, int] = (100, 100)  # (nx, ny)

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

    @classmethod
    def axis_aligned(
        cls,
        name: str,
        center,
        size: tuple[float, float],
        normal_axis: int,
        normal_sign: float,
        resolution: tuple[int, int] = (100, 100),
    ) -> "DetectorSurface":
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
                   np.array(u, float), np.array(v, float), size, resolution)

    @property
    def dominant_normal_axis(self) -> int:
        return int(np.argmax(np.abs(self.normal)))

    @property
    def dominant_normal_sign(self) -> float:
        return float(np.sign(self.normal[self.dominant_normal_axis]))


@dataclass
class DetectorResult:
    """Result of a simulation for one detector."""

    detector_name: str
    grid: np.ndarray   # (ny, nx) accumulated flux per bin
    total_hits: int = 0
    total_flux: float = 0.0


@dataclass
class SimulationResult:
    """Full output returned by RayTracer.run()."""

    detectors: dict[str, DetectorResult] = field(default_factory=dict)
    ray_paths: list[list[np.ndarray]] = field(default_factory=list)
    # ray_paths: each element is a list of 3-D waypoints for one recorded ray
