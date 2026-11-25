"""Ray direction sampling utilities for Monte Carlo simulation."""

from __future__ import annotations

import numpy as np


def sample_isotropic(n: int, rng: np.random.Generator) -> np.ndarray:
    """Sample n uniformly distributed unit vectors on the sphere.

    Returns (n, 3) array.
    """
    z = rng.uniform(-1.0, 1.0, size=n)
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
    r = np.sqrt(1.0 - z * z)
    x = r * np.cos(phi)
    y = r * np.sin(phi)
    return np.column_stack([x, y, z])


def sample_lambertian(n: int, normal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Sample n cosine-weighted directions in the hemisphere around normal.

    Uses Malley's method: sample uniform disk, project to hemisphere.
    Returns (n, 3) array of unit vectors.
    """
    normal = np.asarray(normal, dtype=float)
    normal = normal / np.linalg.norm(normal)

    # Build orthonormal basis (tangent, bitangent, normal)
    tangent, bitangent = _build_basis(normal)

    # Malley's method: uniform disk sampling then project up
    r = np.sqrt(rng.uniform(0.0, 1.0, size=n))
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
    x_local = r * np.cos(phi)
    y_local = r * np.sin(phi)
    z_local = np.sqrt(np.maximum(0.0, 1.0 - x_local * x_local - y_local * y_local))

    # Transform to world coordinates
    directions = (
        x_local[:, None] * tangent[None, :]
        + y_local[:, None] * bitangent[None, :]
        + z_local[:, None] * normal[None, :]
    )
    return directions


def sample_angular_distribution(
    n: int,
    normal: np.ndarray,
    theta_deg: np.ndarray,
    intensity: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample directions from a 1D angular distribution I(theta).

    theta_deg is polar angle in degrees around *normal*.
    """
    theta_deg = np.asarray(theta_deg, dtype=float).reshape(-1)
    intensity = np.asarray(intensity, dtype=float).reshape(-1)
    if theta_deg.size < 2 or intensity.size != theta_deg.size:
        return sample_lambertian(n, normal, rng)

    order = np.argsort(theta_deg)
    theta_deg = theta_deg[order]
    intensity = np.clip(intensity[order], 0.0, None)

    theta_rad = np.radians(theta_deg)
    grid = np.linspace(theta_rad[0], theta_rad[-1], 2048)
    interp_i = np.interp(grid, theta_rad, intensity, left=0.0, right=0.0)
    weights = interp_i * np.sin(grid)
    csum = np.cumsum(weights)
    if csum[-1] <= 0:
        return sample_lambertian(n, normal, rng)
    cdf = csum / csum[-1]

    u = rng.uniform(0.0, 1.0, size=n)
    sample_theta = np.interp(u, cdf, grid)
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)

    sin_t = np.sin(sample_theta)
    x_local = sin_t * np.cos(phi)
    y_local = sin_t * np.sin(phi)
    z_local = np.cos(sample_theta)

    normal = np.asarray(normal, dtype=float)
    ln = np.linalg.norm(normal)
    if ln <= 0:
        normal = np.array([0.0, 0.0, 1.0], dtype=float)
    else:
        normal = normal / ln
    tangent, bitangent = _build_basis(normal)
    return (
        x_local[:, None] * tangent[None, :]
        + y_local[:, None] * bitangent[None, :]
        + z_local[:, None] * normal[None, :]
    )


def sample_diffuse_reflection(n: int, normal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Sample diffuse (Lambertian) reflection directions off a surface."""
    return sample_lambertian(n, normal, rng)


def reflect_specular(directions: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Compute specular reflection of direction vectors about a normal.

    directions: (n, 3) incoming directions (pointing toward surface)
    normal: (3,) surface normal
    Returns (n, 3) reflected directions.
    """
    normal = np.asarray(normal, dtype=float)
    normal = normal / np.linalg.norm(normal)
    dot = np.dot(directions, normal)  # (n,)
    return directions - 2.0 * dot[:, None] * normal[None, :]


def scatter_haze(
    directions: np.ndarray,
    half_angle_deg: float,
    rng: np.random.Generator,
    surface_normals: np.ndarray | None = None,
) -> np.ndarray:
    """Perturb each direction within a cone of half_angle_deg.

    Uniform distribution within the cone. Returns (n, 3) unit vectors.

    surface_normals : optional (3,) or (n, 3) array of oriented normals that
        point into the hemisphere the scattered ray must stay in (i.e. the
        reflection side).  When given, any perturbed direction that ends up
        pointing into the surface (d . n <= 0) is mirrored about the surface
        plane back into the correct hemisphere.
    """
    if half_angle_deg <= 0:
        return directions
    result = _scatter_haze_cone(directions, half_angle_deg, rng)
    if surface_normals is not None:
        result = _fold_into_hemisphere(result, surface_normals)
    return result


def _fold_into_hemisphere(dirs: np.ndarray, normals: np.ndarray) -> np.ndarray:
    """Mirror directions with d . n <= 0 about the plane with normal n."""
    normals = np.asarray(normals, dtype=float)
    if normals.ndim == 1:
        normals = np.broadcast_to(normals, dirs.shape)
    dot = np.einsum("ij,ij->i", dirs, normals)
    bad = dot <= 0.0
    if bad.any():
        dirs = dirs.copy()
        # d' = d - 2 (d.n) n ; tiny push for exactly-tangent rays
        dirs[bad] = dirs[bad] - 2.0 * dot[bad, None] * normals[bad]
        still = np.einsum("ij,ij->i", dirs[bad], normals[bad]) <= 0.0
        if still.any():
            idx = np.nonzero(bad)[0][still]
            dirs[idx] = dirs[idx] + 1e-9 * normals[idx]
        dirs[bad] /= np.linalg.norm(dirs[bad], axis=1, keepdims=True)
    return dirs


def _scatter_haze_cone(directions: np.ndarray, half_angle_deg: float,
                       rng: np.random.Generator) -> np.ndarray:
    """Uniform-in-solid-angle perturbation within a cone (no hemisphere check)."""
    n = len(directions)
    max_theta = np.radians(half_angle_deg)
    # Uniform within cone: cos(theta) in [cos(max_theta), 1]
    cos_min = np.cos(max_theta)
    cos_theta = rng.uniform(cos_min, 1.0, size=n)
    sin_theta = np.sqrt(1.0 - cos_theta * cos_theta)
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)
    result = np.empty_like(directions)
    for i in range(n):
        d = directions[i]
        ln = np.linalg.norm(d)
        if ln < 1e-12:
            result[i] = d
            continue
        d = d / ln
        t, b = _build_basis(d)
        result[i] = (sin_theta[i] * np.cos(phi[i]) * t +
                      sin_theta[i] * np.sin(phi[i]) * b +
                      cos_theta[i] * d)
    return result


def bsdf_row_albedo(bsdf_profile: dict) -> tuple[np.ndarray, np.ndarray]:
    """Return per-theta_in-row (reflect, transmit) albedo of a BSDF profile.

    Uses the same sin-weighted integral over theta_out as
    ``io.bsdf_io.validate_bsdf`` (which rejects rows whose sum exceeds 1), so
    ``1 - (R + T)`` is the fraction the surface absorbs. Values are clipped to
    >= 0 and the sum is capped at 1 so the tracer can never create energy.
    """
    refl = np.maximum(np.asarray(bsdf_profile["refl_intensity"], dtype=float), 0.0)
    trans = np.maximum(np.asarray(bsdf_profile["trans_intensity"], dtype=float), 0.0)
    theta_out = np.asarray(bsdf_profile.get("theta_out", []), dtype=float)
    if refl.ndim == 2 and theta_out.ndim == 1 and theta_out.size >= 2 \
            and theta_out.size == refl.shape[1]:
        rad = np.radians(theta_out)
        weight = np.sin(rad) * np.gradient(rad)
        r_alb = (refl * weight).sum(axis=1)
        t_alb = (trans * weight).sum(axis=1)
    else:
        r_alb = refl.reshape(refl.shape[0], -1).sum(axis=1)
        t_alb = trans.reshape(trans.shape[0], -1).sum(axis=1)
    total = r_alb + t_alb
    scale = np.where(total > 1.0, 1.0 / np.maximum(total, 1e-300), 1.0)
    return r_alb * scale, t_alb * scale


def precompute_bsdf_cdfs(bsdf_profile: dict) -> dict:
    """Pre-build 2D CDF arrays from a BSDF profile for fast importance sampling.

    For each theta_in row, builds a 2048-point CDF over theta_out (sin-weighted).

    Parameters
    ----------
    bsdf_profile : dict
        Profile dict as returned by load_bsdf_csv:
        {"theta_in": [...], "theta_out": [...],
         "refl_intensity": [[...], ...], "trans_intensity": [[...], ...]}

    Returns
    -------
    dict
        {
            "theta_in":  np.ndarray (M,),
            "theta_out_grid": np.ndarray (2048,),  # fine grid for CDF inversion
            "refl_cdf":  np.ndarray (M, 2048),     # CDF per theta_in row
            "trans_cdf": np.ndarray (M, 2048),     # CDF per theta_in row
            "refl_total":  np.ndarray (M,),        # total (un-normalised) weight per row
            "trans_total": np.ndarray (M,),        # total (un-normalised) weight per row
        }
        theta_out_grid is in radians.
    """
    N_GRID = 2048

    theta_in = np.asarray(bsdf_profile["theta_in"], dtype=float)
    theta_out_deg = np.asarray(bsdf_profile["theta_out"], dtype=float)
    refl_mat = np.asarray(bsdf_profile["refl_intensity"], dtype=float)   # (M, N)
    trans_mat = np.asarray(bsdf_profile["trans_intensity"], dtype=float)  # (M, N)

    M = len(theta_in)
    theta_out_rad = np.radians(theta_out_deg)

    # Fine interpolation grid for theta_out
    to_min = theta_out_rad[0] if len(theta_out_rad) > 0 else 0.0
    to_max = theta_out_rad[-1] if len(theta_out_rad) > 0 else np.pi / 2
    grid = np.linspace(to_min, to_max, N_GRID)

    refl_cdf = np.zeros((M, N_GRID), dtype=float)
    trans_cdf = np.zeros((M, N_GRID), dtype=float)
    refl_total = np.zeros(M, dtype=float)
    trans_total = np.zeros(M, dtype=float)

    for i in range(M):
        # Interpolate intensity onto fine grid (sin-weighted for solid angle)
        r_interp = np.interp(grid, theta_out_rad, refl_mat[i], left=0.0, right=0.0)
        t_interp = np.interp(grid, theta_out_rad, trans_mat[i], left=0.0, right=0.0)
        sin_w = np.sin(grid)

        r_weights = np.maximum(r_interp, 0.0) * sin_w
        t_weights = np.maximum(t_interp, 0.0) * sin_w

        r_csum = np.cumsum(r_weights)
        t_csum = np.cumsum(t_weights)

        refl_total[i] = r_csum[-1]
        trans_total[i] = t_csum[-1]

        if refl_total[i] > 0:
            refl_cdf[i] = r_csum / refl_total[i]
        else:
            refl_cdf[i] = np.linspace(0.0, 1.0, N_GRID)  # fallback: uniform

        if trans_total[i] > 0:
            trans_cdf[i] = t_csum / trans_total[i]
        else:
            trans_cdf[i] = np.linspace(0.0, 1.0, N_GRID)  # fallback: uniform

    refl_albedo, trans_albedo = bsdf_row_albedo(bsdf_profile)

    return {
        "theta_in": theta_in,
        "theta_out_grid": grid,
        "refl_cdf": refl_cdf,
        "trans_cdf": trans_cdf,
        "refl_albedo": refl_albedo,
        "trans_albedo": trans_albedo,
        "refl_total": refl_total,
        "trans_total": trans_total,
    }


def sample_bsdf(
    n: int,
    incident_dirs: np.ndarray,
    surface_normal: np.ndarray,
    bsdf_profile: dict,
    mode: str,
    rng: np.random.Generator,
    cdfs: dict | None = None,
) -> np.ndarray:
    """Sample n scattered directions from a 2D BSDF profile.

    Parameters
    ----------
    n : int
        Number of rays to scatter.
    incident_dirs : (n, 3) array
        Incoming ray direction unit vectors (pointing TOWARD the surface).
    surface_normal : (3,) array
        Surface normal (pointing away from the surface on the side the ray arrives from).
    bsdf_profile : dict
        BSDF profile dict (from load_bsdf_csv or precompute_bsdf_cdfs).
    mode : str
        "reflect" — sampled directions in same hemisphere as surface_normal.
        "transmit" — sampled directions in opposite hemisphere.
    rng : np.random.Generator
        Random number generator.
    cdfs : dict, optional
        Pre-computed CDFs from precompute_bsdf_cdfs(). If None, they will be
        computed on-the-fly (less efficient for repeated calls).

    Returns
    -------
    (n, 3) array of unit scattered direction vectors.
    """
    surface_normal = np.asarray(surface_normal, dtype=float)
    ln = np.linalg.norm(surface_normal)
    if ln < 1e-12:
        surface_normal = np.array([0.0, 0.0, 1.0])
    else:
        surface_normal = surface_normal / ln

    incident_dirs = np.asarray(incident_dirs, dtype=float)

    # Build CDFs if not pre-computed
    if cdfs is None:
        cdfs = precompute_bsdf_cdfs(bsdf_profile)

    theta_in_vals = cdfs["theta_in"]           # (M,)
    grid = cdfs["theta_out_grid"]              # (2048,)
    cdf_mat = cdfs["refl_cdf"] if mode == "reflect" else cdfs["trans_cdf"]  # (M, 2048)

    M = len(theta_in_vals)

    # Compute theta_in per ray: angle between -d and surface_normal
    cos_i = np.clip(np.einsum("ij,j->i", -incident_dirs, surface_normal), 0.0, 1.0)
    theta_i_deg = np.degrees(np.arccos(cos_i))  # (n,)

    # Find nearest theta_in bin per ray
    bin_idx = nearest_theta_in_bin(theta_in_vals, theta_i_deg)

    # Sample theta_out via CDF inversion per ray
    u = rng.uniform(0.0, 1.0, size=n)
    sample_theta = np.empty(n, dtype=float)

    # Group rays by theta_in bin for vectorised CDF inversion
    unique_bins = np.unique(bin_idx)
    for b in unique_bins:
        ray_mask = bin_idx == b
        cdf_row = cdf_mat[b]                       # (2048,)
        u_sub = u[ray_mask]
        sample_theta[ray_mask] = np.interp(u_sub, cdf_row, grid)

    # Random azimuth
    phi = rng.uniform(0.0, 2.0 * np.pi, size=n)

    sin_t = np.sin(sample_theta)
    x_local = sin_t * np.cos(phi)
    y_local = sin_t * np.sin(phi)
    z_local = np.cos(sample_theta)

    # Build an outgoing normal for direction hemisphere
    if mode == "transmit":
        hemi_normal = -surface_normal
    else:
        hemi_normal = surface_normal

    tangent, bitangent = _build_basis(hemi_normal)
    directions = (
        x_local[:, None] * tangent[None, :]
        + y_local[:, None] * bitangent[None, :]
        + z_local[:, None] * hemi_normal[None, :]
    )

    # Normalize for safety
    norms = np.linalg.norm(directions, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return directions / norms


def nearest_theta_in_bin(theta_in_vals: np.ndarray, theta_deg: np.ndarray) -> np.ndarray:
    """Index of the nearest entry in sorted ``theta_in_vals`` for each angle.

    Ties (exact midpoint) resolve to the lower bin.
    """
    theta_in_vals = np.asarray(theta_in_vals, dtype=float)
    theta_deg = np.asarray(theta_deg, dtype=float)
    M = len(theta_in_vals)
    if M <= 1:
        return np.zeros(theta_deg.shape, dtype=int)
    hi = np.clip(np.searchsorted(theta_in_vals, theta_deg, side="left"), 1, M - 1)
    lo = hi - 1
    pick_hi = np.abs(theta_in_vals[hi] - theta_deg) < np.abs(theta_deg - theta_in_vals[lo])
    return np.where(pick_hi, hi, lo)


def _build_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build an orthonormal tangent/bitangent pair for a given normal."""
    if abs(normal[0]) < 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    else:
        ref = np.array([0.0, 1.0, 0.0])
    tangent = np.cross(normal, ref)
    tangent = tangent / np.linalg.norm(tangent)
    bitangent = np.cross(normal, tangent)
    return tangent, bitangent
