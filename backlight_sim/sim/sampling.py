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
