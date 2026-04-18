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
class SphereDetector:
    """A spherical receiver that accumulates light from all directions."""

    name: str
    center: np.ndarray         # (3,)
    radius: float = 10.0
    resolution: tuple[int, int] = (72, 36)  # (n_phi, n_theta) bins
    mode: str = "near_field"   # "near_field" (position-based) or "far_field" (direction-based)

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)


@dataclass
class DetectorResult:
    """Result of a simulation for one detector."""

    detector_name: str
    grid: np.ndarray   # (ny, nx) accumulated flux per bin
    total_hits: int = 0
    total_flux: float = 0.0
    grid_rgb: np.ndarray | None = None  # (ny, nx, 3) RGB flux grid, or None if mono
    grid_spectral: np.ndarray | None = None  # (ny, nx, n_bins) spectral flux, or None

    # Phase 4 UQ: per-batch snapshots populated by the tracer when
    # SimulationSettings.uq_batches > 0.  All None / 0 on the legacy path;
    # consumers must treat a None value as "no UQ data" and fall back to the
    # point-estimate grid.
    grid_batches: np.ndarray | None = None           # (K, ny, nx)
    hits_batches: np.ndarray | None = None           # (K,) int
    flux_batches: np.ndarray | None = None           # (K,) float
    grid_spectral_batches: np.ndarray | None = None  # (K, ny, nx, n_bins)
    # Actual rays emitted per batch (accounts for remainder distribution when
    # rays_per_source % K != 0); None when UQ is disabled.
    rays_per_batch: list[int] | None = None          # (K,)
    n_batches: int = 0                               # K; 0 means "no UQ data"


@dataclass
class SphereDetectorResult:
    """Result for a sphere detector — (n_theta, n_phi) grid."""

    detector_name: str
    grid: np.ndarray           # (n_theta, n_phi) accumulated flux per bin
    total_hits: int = 0
    total_flux: float = 0.0
    candela_grid: np.ndarray | None = None  # (n_theta, n_phi) candela per bin, computed for far_field


@dataclass
class SimulationResult:
    """Full output returned by RayTracer.run()."""

    detectors: dict[str, DetectorResult] = field(default_factory=dict)
    sphere_detectors: dict[str, SphereDetectorResult] = field(default_factory=dict)
    ray_paths: list = field(default_factory=list)  # list[list[np.ndarray]] for 3D visualization

    # Energy accounting
    total_emitted_flux: float = 0.0    # sum of all source flux values
    escaped_flux: float = 0.0          # flux that left geometry without hitting anything
    source_count: int = 0              # number of light sources simulated

    # Per-face flux stats for SolidBox objects.
    # Structure: { box_name: { face_id: { "entering_flux": float, "exiting_flux": float } } }
    solid_body_stats: dict = field(default_factory=dict)

    # Phase 4 UQ: tracer-populated warnings (e.g. per CONTEXT D-01 when adaptive
    # sampling and UQ are both active, the CI may be biased — the tracer appends
    # a warning here and the UI renders it as a muted annotation).  Empty list
    # when no warnings; never None.  Uses field(default_factory=list) to avoid
    # the shared-mutable-default pitfall.
    uq_warnings: list[str] = field(default_factory=list)
