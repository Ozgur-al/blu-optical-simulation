"""Numba JIT-compiled acceleration kernels for Monte Carlo ray tracing.

Provides JIT-accelerated versions of the ray-plane intersection, ray-sphere
intersection, flux accumulation inner loops, and BVH spatial acceleration.
Falls back gracefully to pure-Python/NumPy implementations when Numba is
not installed.

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
compute_surface_aabbs(normals, centers, u_axes, v_axes, half_ws, half_hs) -> (N, 6) float64
build_bvh_flat(surface_aabbs) -> (node_bounds, node_meta, n_nodes)
intersect_aabb_jit(origin, direction, bbox_min, bbox_max) -> float
traverse_bvh_jit(origin, direction, bvh_bounds, bvh_meta, ...) -> (float, int)
traverse_bvh_batch(origins, directions, bvh_bounds, bvh_meta, ...) -> ((N,) float, (N,) int)
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

        # Dummy BVH traversal — build a 4-surface flat BVH and traverse with 4 rays
        surf_n = np.tile(np.array([0.0, 0.0, 1.0]), (4, 1)).astype(np.float64)
        surf_c = np.array([[0, 0, 1], [3, 0, 1], [0, 3, 1], [3, 3, 1]], dtype=np.float64)
        surf_u = np.tile(np.array([1.0, 0.0, 0.0]), (4, 1)).astype(np.float64)
        surf_v = np.tile(np.array([0.0, 1.0, 0.0]), (4, 1)).astype(np.float64)
        surf_hw = np.ones(4, dtype=np.float64)
        surf_hh = np.ones(4, dtype=np.float64)
        dummy_aabbs = compute_surface_aabbs(surf_n, surf_c, surf_u, surf_v, surf_hw, surf_hh)
        dummy_bounds, dummy_meta, dummy_n_nodes = build_bvh_flat(dummy_aabbs)
        dummy_origins_bvh = np.tile(np.array([0.0, 0.0, 0.0]), (4, 1)).astype(np.float64)
        dummy_dirs_bvh = np.tile(np.array([0.0, 0.0, 1.0]), (4, 1)).astype(np.float64)
        traverse_bvh_batch(
            dummy_origins_bvh, dummy_dirs_bvh,
            dummy_bounds, dummy_meta, dummy_n_nodes,
            surf_n, surf_c, surf_u, surf_v, surf_hw, surf_hh,
            _EPSILON_DEFAULT,
        )

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


# ---------------------------------------------------------------------------
# BVH: Bounding Volume Hierarchy (NumPy build + JIT traversal)
# ---------------------------------------------------------------------------

def compute_surface_aabbs(
    normals: np.ndarray,    # (N, 3) float64
    centers: np.ndarray,   # (N, 3) float64
    u_axes: np.ndarray,    # (N, 3) float64
    v_axes: np.ndarray,    # (N, 3) float64
    half_ws: np.ndarray,   # (N,) float64
    half_hs: np.ndarray,   # (N,) float64
) -> np.ndarray:           # (N, 6) float64: [xmin, xmax, ymin, ymax, zmin, zmax]
    """Compute axis-aligned bounding boxes for N rectangles.

    For each rectangle: corners = center +/- half_w*u_axis +/- half_h*v_axis.
    Take per-axis min/max across all 4 corners.

    This is a pure NumPy function — runs once per simulation start.
    """
    n = centers.shape[0]
    # 4 corners per rectangle: (±hw*u) + (±hh*v), shape (N, 4, 3)
    hw = half_ws[:, None]  # (N, 1)
    hh = half_hs[:, None]  # (N, 1)
    corners = np.stack([
        centers + hw * u_axes + hh * v_axes,
        centers + hw * u_axes - hh * v_axes,
        centers - hw * u_axes + hh * v_axes,
        centers - hw * u_axes - hh * v_axes,
    ], axis=1)  # (N, 4, 3)

    aabbs = np.empty((n, 6), dtype=np.float64)
    aabbs[:, 0] = corners[:, :, 0].min(axis=1)  # xmin
    aabbs[:, 1] = corners[:, :, 0].max(axis=1)  # xmax
    aabbs[:, 2] = corners[:, :, 1].min(axis=1)  # ymin
    aabbs[:, 3] = corners[:, :, 1].max(axis=1)  # ymax
    aabbs[:, 4] = corners[:, :, 2].min(axis=1)  # zmin
    aabbs[:, 5] = corners[:, :, 2].max(axis=1)  # zmax
    return aabbs


def build_bvh_flat(
    surface_aabbs: np.ndarray,  # (N, 6) float64
) -> tuple:
    """Build a flat (array-based) BVH tree by recursive median-split.

    Splits along the longest AABB axis of the current node's surfaces.
    When a node contains exactly 1 surface, it becomes a leaf.

    Parameters
    ----------
    surface_aabbs : (N, 6) float64
        Per-surface AABBs in [xmin, xmax, ymin, ymax, zmin, zmax] format.

    Returns
    -------
    node_bounds : (max_nodes, 6) float64
        Per-node AABB bounds (parent bounds enclose all children).
    node_meta : (max_nodes, 3) int32
        [left_child_or_surf_idx, right_child, leaf_flag]
        leaf_flag==1: leaf, left_child_or_surf_idx=surface index in original array.
        leaf_flag==0: internal, children at left_child_or_surf_idx and right_child.
    n_nodes : int
        Number of nodes actually used (tree may be smaller than max_nodes).
    """
    n = surface_aabbs.shape[0]
    if n == 0:
        empty_bounds = np.zeros((1, 6), dtype=np.float64)
        empty_meta = np.zeros((1, 3), dtype=np.int32)
        return empty_bounds, empty_meta, 0

    max_nodes = 2 * n - 1
    node_bounds = np.zeros((max_nodes, 6), dtype=np.float64)
    node_meta = np.zeros((max_nodes, 3), dtype=np.int32)

    node_count = [0]

    def _alloc_node() -> int:
        idx = node_count[0]
        node_count[0] += 1
        return idx

    def _compute_bounds(indices: np.ndarray) -> np.ndarray:
        """AABB that encloses all surfaces with given indices."""
        sub = surface_aabbs[indices]
        return np.array([
            sub[:, 0].min(), sub[:, 1].max(),
            sub[:, 2].min(), sub[:, 3].max(),
            sub[:, 4].min(), sub[:, 5].max(),
        ], dtype=np.float64)

    # Iterative build using an explicit stack
    # Stack entries: (node_idx, list_of_surf_indices)
    root_idx = _alloc_node()
    all_indices = np.arange(n, dtype=np.int32)
    node_bounds[root_idx] = _compute_bounds(all_indices)

    stack = [(root_idx, all_indices)]

    while stack:
        current_node, indices = stack.pop()

        if len(indices) == 1:
            # Leaf node
            node_meta[current_node, 0] = int(indices[0])
            node_meta[current_node, 1] = -1
            node_meta[current_node, 2] = 1  # leaf flag
            continue

        # Internal node: split along the longest axis of this node's AABB
        bounds = node_bounds[current_node]
        extents = np.array([
            bounds[1] - bounds[0],  # x extent
            bounds[3] - bounds[2],  # y extent
            bounds[5] - bounds[4],  # z extent
        ])
        split_axis = int(np.argmax(extents))  # 0=x, 1=y, 2=z

        # Surface centroids along split axis
        centroid_axis = split_axis * 2  # index into AABB: 0->xmin/xmax, 2->ymin/ymax, 4->zmin/zmax
        centroids = (surface_aabbs[indices, centroid_axis] +
                     surface_aabbs[indices, centroid_axis + 1]) * 0.5

        # Median split
        median_val = float(np.median(centroids))
        left_mask = centroids <= median_val
        right_mask = ~left_mask

        # Handle degenerate case: if all end up on one side, split evenly
        if not left_mask.any() or not right_mask.any():
            half = len(indices) // 2
            left_mask = np.zeros(len(indices), dtype=bool)
            left_mask[:half] = True
            right_mask = ~left_mask

        left_indices  = indices[left_mask]
        right_indices = indices[right_mask]

        # Allocate children
        left_node  = _alloc_node()
        right_node = _alloc_node()

        node_meta[current_node, 0] = left_node
        node_meta[current_node, 1] = right_node
        node_meta[current_node, 2] = 0  # internal

        node_bounds[left_node]  = _compute_bounds(left_indices)
        node_bounds[right_node] = _compute_bounds(right_indices)

        stack.append((left_node, left_indices))
        stack.append((right_node, right_indices))

    n_nodes = node_count[0]
    return node_bounds, node_meta, n_nodes


# ---------------------------------------------------------------------------
# JIT kernel: slab-test AABB intersection (single ray)
# ---------------------------------------------------------------------------

@_njit(cache=True, fastmath=True)
def intersect_aabb_jit(
    origin: np.ndarray,    # (3,) float64
    direction: np.ndarray, # (3,) float64
    bbox_min: np.ndarray,  # (3,) float64
    bbox_max: np.ndarray,  # (3,) float64
) -> float:
    """Slab-test AABB intersection for a single ray.

    Returns t_entry (positive) if the ray hits the AABB, or np.inf if miss.
    """
    t_min = -np.inf
    t_max = np.inf

    for i in range(3):
        d = direction[i]
        if abs(d) < 1e-12:
            # Parallel to slab
            if origin[i] < bbox_min[i] or origin[i] > bbox_max[i]:
                return np.inf
        else:
            inv_d = 1.0 / d
            t1 = (bbox_min[i] - origin[i]) * inv_d
            t2 = (bbox_max[i] - origin[i]) * inv_d
            if t1 > t2:
                t1, t2 = t2, t1
            if t1 > t_min:
                t_min = t1
            if t2 < t_max:
                t_max = t2
            if t_min > t_max:
                return np.inf

    if t_max < 0.0:
        return np.inf  # AABB is behind the ray
    return max(t_min, 0.0)


# ---------------------------------------------------------------------------
# JIT kernel: BVH traversal for a single ray
# ---------------------------------------------------------------------------

@_njit(cache=True, fastmath=True)
def traverse_bvh_jit(
    origin: np.ndarray,       # (3,) float64
    direction: np.ndarray,    # (3,) float64
    bvh_bounds: np.ndarray,   # (max_nodes, 6) float64
    bvh_meta: np.ndarray,     # (max_nodes, 3) int32
    n_nodes: int,
    surf_normals: np.ndarray, # (N, 3) float64
    surf_centers: np.ndarray, # (N, 3) float64
    surf_u: np.ndarray,       # (N, 3) float64
    surf_v: np.ndarray,       # (N, 3) float64
    surf_hw: np.ndarray,      # (N,) float64
    surf_hh: np.ndarray,      # (N,) float64
    epsilon: float,
) -> tuple:                   # (best_t: float, best_surf_idx: int)
    """Iterative BVH traversal for a single ray.

    Uses an explicit stack (max depth 64).  For each leaf node, inlines the
    ray-plane intersection math (not calling another @njit to avoid nesting).

    Returns
    -------
    best_t : float
        Parametric distance to closest hit, or np.inf if no hit.
    best_surf_idx : int
        Index of closest surface in the original array, or -1 if no hit.
    """
    best_t = np.inf
    best_surf_idx = -1

    stack = np.empty(64, dtype=np.int32)
    stack_top = 0
    stack[stack_top] = 0  # start from root node (index 0)
    stack_top += 1

    # Pre-compute AABB slab bounds for fast rejection
    # (inlining intersect_aabb_jit logic)
    while stack_top > 0:
        stack_top -= 1
        node_idx = stack[stack_top]

        if node_idx < 0 or node_idx >= n_nodes:
            continue

        # AABB test: slab method
        bounds = bvh_bounds[node_idx]
        t_node_min = -np.inf
        t_node_max = np.inf
        hit_aabb = True
        for i in range(3):
            d = direction[i]
            bmin = bounds[i * 2]
            bmax = bounds[i * 2 + 1]
            if abs(d) < 1e-12:
                if origin[i] < bmin or origin[i] > bmax:
                    hit_aabb = False
                    break
            else:
                inv_d = 1.0 / d
                t1 = (bmin - origin[i]) * inv_d
                t2 = (bmax - origin[i]) * inv_d
                if t1 > t2:
                    t1, t2 = t2, t1
                if t1 > t_node_min:
                    t_node_min = t1
                if t2 < t_node_max:
                    t_node_max = t2
                if t_node_min > t_node_max:
                    hit_aabb = False
                    break

        if not hit_aabb:
            continue
        if t_node_max < 0.0:
            continue
        # Early-out: AABB entry farther than best hit so far
        t_entry = t_node_min if t_node_min > 0.0 else 0.0
        if t_entry >= best_t:
            continue

        leaf_flag = bvh_meta[node_idx, 2]
        if leaf_flag == 1:
            # Leaf node: test the actual surface (inline plane intersection)
            surf_idx = bvh_meta[node_idx, 0]

            nx = surf_normals[surf_idx, 0]
            ny = surf_normals[surf_idx, 1]
            nz = surf_normals[surf_idx, 2]

            denom = direction[0] * nx + direction[1] * ny + direction[2] * nz
            if abs(denom) <= 1e-12:
                continue

            cx = surf_centers[surf_idx, 0]
            cy = surf_centers[surf_idx, 1]
            cz = surf_centers[surf_idx, 2]

            d_plane = nx * cx + ny * cy + nz * cz
            t = (d_plane - (origin[0] * nx + origin[1] * ny + origin[2] * nz)) / denom

            if t <= epsilon:
                continue

            hx = origin[0] + t * direction[0]
            hy = origin[1] + t * direction[1]
            hz = origin[2] + t * direction[2]

            lx = hx - cx
            ly = hy - cy
            lz = hz - cz

            ux = surf_u[surf_idx, 0]
            uy = surf_u[surf_idx, 1]
            uz = surf_u[surf_idx, 2]
            u_coord = lx * ux + ly * uy + lz * uz

            vx = surf_v[surf_idx, 0]
            vy = surf_v[surf_idx, 1]
            vz = surf_v[surf_idx, 2]
            v_coord = lx * vx + ly * vy + lz * vz

            if abs(u_coord) <= surf_hw[surf_idx] and abs(v_coord) <= surf_hh[surf_idx]:
                if t < best_t:
                    best_t = t
                    best_surf_idx = surf_idx

        else:
            # Internal node: push children
            left_child  = bvh_meta[node_idx, 0]
            right_child = bvh_meta[node_idx, 1]
            if stack_top < 62:
                stack[stack_top] = left_child
                stack_top += 1
                stack[stack_top] = right_child
                stack_top += 1

    return best_t, best_surf_idx


# ---------------------------------------------------------------------------
# JIT kernel: BVH traversal for a batch of rays
# ---------------------------------------------------------------------------

@_njit(cache=True, fastmath=True)
def traverse_bvh_batch(
    origins: np.ndarray,      # (N, 3) float64
    directions: np.ndarray,   # (N, 3) float64
    bvh_bounds: np.ndarray,   # (max_nodes, 6) float64
    bvh_meta: np.ndarray,     # (max_nodes, 3) int32
    n_nodes: int,
    surf_normals: np.ndarray, # (M, 3) float64
    surf_centers: np.ndarray, # (M, 3) float64
    surf_u: np.ndarray,       # (M, 3) float64
    surf_v: np.ndarray,       # (M, 3) float64
    surf_hw: np.ndarray,      # (M,) float64
    surf_hh: np.ndarray,      # (M,) float64
    epsilon: float,
) -> tuple:                   # ((N,) float64, (N,) int64)
    """Batch BVH traversal: call traverse_bvh_jit for each of N rays.

    Returns
    -------
    best_t : (N,) float64
    best_surf_idx : (N,) int64
    """
    n_rays = origins.shape[0]
    best_t   = np.empty(n_rays, dtype=np.float64)
    best_idx = np.empty(n_rays, dtype=np.int64)

    for i in range(n_rays):
        t, idx = traverse_bvh_jit(
            origins[i], directions[i],
            bvh_bounds, bvh_meta, n_nodes,
            surf_normals, surf_centers, surf_u, surf_v, surf_hw, surf_hh,
            epsilon,
        )
        best_t[i]   = t
        best_idx[i] = idx

    return best_t, best_idx
