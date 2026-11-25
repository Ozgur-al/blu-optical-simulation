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
    position_sigma_mm: float = 0.0  # per-source position jitter σ in mm (0 = use project default)
    current_mA: float = 0.0  # drive current in mA (0 = use flux directly)
    flux_per_mA: float = 0.0  # lm/mA scaling (0 = use flux directly)
    thermal_derate: float = 1.0  # thermal derating factor 0-1 (1 = no derating)
    color_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)  # LED color as (R, G, B) weights 0-1
    # Spectral power distribution: "white" | "warm_white" | "cool_white" | "mono_<nm>" | custom key
    spd: str = "white"
    # Emitting surface: a rectangle (X, Y) centred on `position`, facing
    # `direction`. Rays start uniformly over it and the angular distribution
    # is taken about its normal. (0, 0) = point emitter.
    emitter_size: tuple[float, float] = (0.0, 0.0)
    # Side emission: the 4 faces of a clear package of this height below the
    # emitting surface also emit (0 = top surface only). Rays are split over
    # the 5 faces by area (equal radiance); each face uses the same angular
    # distribution about its own outward normal.
    emitter_side_height: float = 0.0

    def emitter_axes(self) -> tuple[np.ndarray, np.ndarray]:
        """In-plane (u, v) axes of the emitting surface; (X, Y) when facing +Z."""
        d = self.direction
        ref = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.99 else np.array([0.0, 0.0, 1.0])
        u = np.cross(ref, d)
        u /= np.linalg.norm(u)
        return u, np.cross(d, u)

    def sample_origins(self, n: int, rng) -> np.ndarray:
        """(n, 3) ray start points, uniform over the emitting top surface."""
        sx, sy = (float(v) for v in self.emitter_size)
        origins = np.tile(self.position, (n, 1))
        if sx > 0 or sy > 0:
            u, v = self.emitter_axes()
            r = rng.uniform(-0.5, 0.5, size=(n, 2))
            origins = origins + np.outer(r[:, 0] * sx, u) + np.outer(r[:, 1] * sy, v)
        return origins

    def sample_emission(self, n: int, rng, directions: np.ndarray) -> np.ndarray:
        """Ray origins over all emitting faces; rotates side-face rays of
        *directions* (sampled about `direction`) in place onto their face normal."""
        origins = self.sample_origins(n, rng)
        sx, sy = (float(v) for v in self.emitter_size)
        h = float(self.emitter_side_height)
        if h <= 0 or (sx <= 0 and sy <= 0):
            return origins
        d = self.direction
        u, v = self.emitter_axes()
        # Face areas: top, +u, -u, +v, -v.
        areas = np.array([sx * sy, sy * h, sy * h, sx * h, sx * h])
        face = rng.choice(5, size=n, p=areas / areas.sum())
        r = rng.uniform(-0.5, 0.5, size=n)
        depth = rng.uniform(0.0, 1.0, size=n) * h
        for k, (normal, along, half) in enumerate(
            ((u, v, sx), (-u, v, sx), (v, u, sy), (-v, u, sy)), start=1
        ):
            m = face == k
            if not m.any():
                continue
            span = sy if k <= 2 else sx
            origins[m] = (self.position + normal * (half / 2.0)
                          + np.outer(r[m] * span, along) - np.outer(depth[m], d))
            # 90° rotation about a = d x normal maps d -> normal.
            a = np.cross(d, normal)
            dv = directions[m]
            directions[m] = np.outer(dv @ a, a) + np.cross(a, dv)
        return origins

    @property
    def effective_flux(self) -> float:
        """Compute flux after current scaling and thermal derating."""
        base = self.flux
        if self.current_mA > 0 and self.flux_per_mA > 0:
            base = self.current_mA * self.flux_per_mA
        return base * self.thermal_derate

    def __post_init__(self):
        self.position = np.asarray(self.position, dtype=float)
        self.emitter_size = (float(self.emitter_size[0]), float(self.emitter_size[1]))
        self.emitter_side_height = float(self.emitter_side_height)
        if self.direction is None:
            self.direction = np.array([0.0, 0.0, 1.0])
        else:
            self.direction = np.asarray(self.direction, dtype=float)
            norm = np.linalg.norm(self.direction)
            if norm > 0:
                self.direction = self.direction / norm
