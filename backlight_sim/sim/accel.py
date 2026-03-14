"""Numba JIT-compiled acceleration kernels for Monte Carlo ray tracing.

Provides JIT-accelerated versions of the ray-plane intersection, ray-sphere
intersection, and flux accumulation inner loops.  Falls back gracefully to
pure-Python/NumPy implementations when Numba is not installed.

Exports
-------
_NUMBA_AVAILABLE : bool
    True when Numba is installed and JIT compilation is enabled.
intersect_plane_jit(origins, directions, normal, center, u_axis, v_axis, half_w, half_h, epsilon) -> (N,) float64
intersect_sphere_jit(origins, directions, center, radius, epsilon) -> (N,) float64
accumulate_grid_jit(grid, iy, ix, weights) -> None
accumulate_sphere_jit(grid, i_theta, i_phi, weights) -> None
warmup_jit_kernels() -> bool
intersect_plane(origins, directions, normal, center, u_axis, v_axis, size) -> (N,) float64
intersect_sphere(origins, directions, center, radius) -> (N,) float64
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Try-import Numba — graceful fallback if not installed
# ---------------------------------------------------------------------------
try:
    from numba import njit as _njit
    _NUMBA_AVAILABLE: bool = True
except ImportError:
    # Provide a no-op decorator that handles both @njit and @njit(cache=True, ...)
    def _njit(*args, **kwargs):  # type: ignore[misc]
        if len(args) == 1 and callable(args[0]):
            # Used as bare @njit decorator
            return args[0]
        # Used as @njit(cache=True, ...) — return a decorator
        def _decorator(fn):
            return fn
        return _decorator
    _NUMBA_AVAILABLE: bool = False  # type: ignore[no-redef]

_EPSILON_DEFAULT = 1e-6

# ---------------------------------------------------------------------------
# JIT kernel: ray-plane intersection
# ---------------------------------------------------------------------------

@_njit(cache=True, fastmath=True)
def intersect_plane_jit(
    origins: np.ndarray,     # (N, 3) float64
    directions: np.ndarray,  # (N, 3) float64
    normal: np.ndarray,      # (3,) float64
    center: np.ndarray,      # (3,) float64
    u_axis: np.ndarray,      # (3,) float64
    v_axis: np.ndarray,      # (3,) float64
    half_w: float,
    half_h: float,
    epsilon: float,
) -> np.ndarray:             # (N,) float64, np.inf = no hit
    """JIT-compiled ray-rectangular-plane intersection.

    Explicit scalar loop over N rays — Numba compiles this to native machine
    code.  Do not use np.where / vectorised NumPy inside: let Numba optimise
    the scalar arithmetic.

    Parameters
    ----------
    origins : (N, 3)
        Ray origin positions.
    directions : (N, 3)
        Ray direction unit vectors.
    normal : (3,)
        Plane surface normal (unit vector).
    center : (3,)
        World-space center of the rectangle.
    u_axis : (3,)
        Local x-axis of the plane (unit vector).
    v_axis : (3,)
        Local y-axis of the plane (unit vector).
    half_w : float
        Half-width of the rectangle along u_axis.
    half_h : float
        Half-height of the rectangle along v_axis.
    epsilon : float
        Minimum positive t value to avoid self-intersection.

    Returns
    -------
    t_values : (N,) float64
        Parametric hit distance along ray; ``np.inf`` for misses.
    """
    n_rays = origins.shape[0]
    t_values = np.empty(n_rays, dtype=np.float64)

    # Pre-compute d_plane = dot(normal, center)
    d_plane = normal[0] * center[0] + normal[1] * center[1] + normal[2] * center[2]

    for i in range(n_rays):
        dx = directions[i, 0]
        dy = directions[i, 1]
        dz = directions[i, 2]

        # denom = dot(direction, normal)
        denom = dx * normal[0] + dy * normal[1] + dz * normal[2]

        if abs(denom) <= 1e-12:
            t_values[i] = np.inf
            continue

        ox = origins[i, 0]
        oy = origins[i, 1]
        oz = origins[i, 2]

        # t = (d_plane - dot(origin, normal)) / denom
        t = (d_plane - (ox * normal[0] + oy * normal[1] + oz * normal[2])) / denom

        if t <= epsilon:
            t_values[i] = np.inf
            continue

        # Hit point
        hx = ox + t * dx
        hy = oy + t * dy
        hz = oz + t * dz

        # Local coordinates relative to center
        lx = hx - center[0]
        ly = hy - center[1]
        lz = hz - center[2]

        # u/v projection
        u_coord = lx * u_axis[0] + ly * u_axis[1] + lz * u_axis[2]
        v_coord = lx * v_axis[0] + ly * v_axis[1] + lz * v_axis[2]

        if abs(u_coord) <= half_w and abs(v_coord) <= half_h:
            t_values[i] = t
        else:
            t_values[i] = np.inf

    return t_values


# ---------------------------------------------------------------------------
# JIT kernel: ray-sphere intersection
# ---------------------------------------------------------------------------

@_njit(cache=True, fastmath=True)
def intersect_sphere_jit(
    origins: np.ndarray,     # (N, 3) float64
    directions: np.ndarray,  # (N, 3) float64
    center: np.ndarray,      # (3,) float64
    radius: float,
    epsilon: float,
) -> np.ndarray:             # (N,) float64
    """JIT-compiled ray-sphere intersection (nearest positive root).

    Uses the quadratic formula: a*t^2 + b*t + c = 0 where:
      a = dot(d, d) (= 1 for unit vectors, kept for safety)
      b = 2 * dot(d, L)  where L = origin - center
      c = dot(L, L) - radius^2
    """
    n_rays = origins.shape[0]
    t_values = np.empty(n_rays, dtype=np.float64)
    r2 = radius * radius

    for i in range(n_rays):
        lx = origins[i, 0] - center[0]
        ly = origins[i, 1] - center[1]
        lz = origins[i, 2] - center[2]

        dx = directions[i, 0]
        dy = directions[i, 1]
        dz = directions[i, 2]

        a = dx * dx + dy * dy + dz * dz
        b = 2.0 * (dx * lx + dy * ly + dz * lz)
        c = lx * lx + ly * ly + lz * lz - r2

        disc = b * b - 4.0 * a * c
        if disc < 0.0:
            t_values[i] = np.inf
            continue

        sqrt_disc = disc ** 0.5
        inv2a = 1.0 / (2.0 * a)
        t1 = (-b - sqrt_disc) * inv2a
        t2 = (-b + sqrt_disc) * inv2a

        if t1 > epsilon:
            t_values[i] = t1
        elif t2 > epsilon:
            t_values[i] = t2
        else:
            t_values[i] = np.inf

    return t_values


# ---------------------------------------------------------------------------
# JIT kernel: flux accumulation into 2D grid (replaces np.add.at)
# ---------------------------------------------------------------------------

@_njit(cache=True)  # NOT fastmath — accumulation must be exact
def accumulate_grid_jit(
    grid: np.ndarray,       # (ny, nx) float64
    iy: np.ndarray,         # (M,) int
    ix: np.ndarray,         # (M,) int
    weights: np.ndarray,    # (M,) float64
) -> None:
    """JIT scatter-add into a 2D grid (replaces ``np.add.at``).

    NOT parallel (``parallel=True`` would introduce race conditions on
    scatter-add with repeated indices).
    """
    for k in range(len(weights)):
        grid[iy[k], ix[k]] += weights[k]


# ---------------------------------------------------------------------------
# JIT kernel: flux accumulation into sphere detector grid
# ---------------------------------------------------------------------------

@_njit(cache=True)  # NOT fastmath — accumulation must be exact
def accumulate_sphere_jit(
    grid: np.ndarray,       # (n_theta, n_phi) float64
    i_theta: np.ndarray,    # (M,) int
    i_phi: np.ndarray,      # (M,) int
    weights: np.ndarray,    # (M,) float64
) -> None:
    """JIT scatter-add into a sphere detector (theta, phi) grid."""
    for k in range(len(weights)):
        grid[i_theta[k], i_phi[k]] += weights[k]


# ---------------------------------------------------------------------------
# Warmup function — triggers eager LLVM compilation at startup
# ---------------------------------------------------------------------------

def warmup_jit_kernels() -> bool:
    """Eagerly compile all JIT kernels to avoid first-simulation delay.

    Calls each kernel with minimal dummy data (4 rays) to trigger LLVM
    compilation.  Wrapped in try/except so startup is never broken even
    if Numba is mis-installed.

    Returns
    -------
    bool
        True if warmup succeeded (or Numba was never available), False
        if Numba is available but warmup failed.
    """
    if not _NUMBA_AVAILABLE:
        return False

    try:
        rng = np.random.default_rng(0)
        n = 4

        # Dummy plane intersection
        origins_d = rng.standard_normal((n, 3)).astype(np.float64)
        dirs_d = np.tile(np.array([0.0, 0.0, 1.0]), (n, 1)).astype(np.float64)
        normal_d = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        center_d = np.array([0.0, 0.0, 5.0], dtype=np.float64)
        u_d = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        v_d = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        intersect_plane_jit(origins_d, dirs_d, normal_d, center_d, u_d, v_d,
                            10.0, 10.0, _EPSILON_DEFAULT)

        # Dummy sphere intersection
        sp_center = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        origins_sp = np.tile(np.array([0.0, 0.0, 10.0]), (n, 1)).astype(np.float64)
        dirs_sp = np.tile(np.array([0.0, 0.0, -1.0]), (n, 1)).astype(np.float64)
        intersect_sphere_jit(origins_sp, dirs_sp, sp_center, 5.0, _EPSILON_DEFAULT)

        # Dummy grid accumulation
        grid2d = np.zeros((10, 10), dtype=np.float64)
        iy_d = np.array([0, 1, 2, 3], dtype=np.intp)
        ix_d = np.array([0, 1, 2, 3], dtype=np.intp)
        wts = np.ones(n, dtype=np.float64) * 0.1
        accumulate_grid_jit(grid2d, iy_d, ix_d, wts)

        # Dummy sphere accumulation
        sph_grid = np.zeros((18, 36), dtype=np.float64)
        i_th = np.array([0, 1, 2, 3], dtype=np.intp)
        i_ph = np.array([0, 1, 2, 3], dtype=np.intp)
        accumulate_sphere_jit(sph_grid, i_th, i_ph, wts)

        return True

    except Exception:
        return False


# ---------------------------------------------------------------------------
# Wrapper functions — same signature as tracer's original functions
# ---------------------------------------------------------------------------

def intersect_plane(
    origins: np.ndarray,
    directions: np.ndarray,
    normal: np.ndarray,
    center: np.ndarray,
    u_axis: np.ndarray,
    v_axis: np.ndarray,
    size: tuple,
) -> np.ndarray:
    """Drop-in replacement for tracer._intersect_rays_plane.

    Extracts half_w / half_h from the ``size`` tuple and delegates to
    ``intersect_plane_jit``.
    """
    half_w = float(size[0]) / 2.0
    half_h = float(size[1]) / 2.0
    return intersect_plane_jit(
        np.ascontiguousarray(origins,    dtype=np.float64),
        np.ascontiguousarray(directions, dtype=np.float64),
        np.ascontiguousarray(normal,     dtype=np.float64),
        np.ascontiguousarray(center,     dtype=np.float64),
        np.ascontiguousarray(u_axis,     dtype=np.float64),
        np.ascontiguousarray(v_axis,     dtype=np.float64),
        half_w,
        half_h,
        _EPSILON_DEFAULT,
    )


def intersect_sphere(
    origins: np.ndarray,
    directions: np.ndarray,
    center: np.ndarray,
    radius: float,
) -> np.ndarray:
    """Drop-in replacement for tracer._intersect_rays_sphere."""
    return intersect_sphere_jit(
        np.ascontiguousarray(origins,    dtype=np.float64),
        np.ascontiguousarray(directions, dtype=np.float64),
        np.ascontiguousarray(center,     dtype=np.float64),
        float(radius),
        _EPSILON_DEFAULT,
    )
