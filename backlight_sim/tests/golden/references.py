"""Analytical reference formulas for golden tests.

No tracer imports — only numpy + stdlib. Each function is derived from textbook
optics (Fresnel 1823, Snell 1621, Lambert cosine law, integrating-cavity equation).
Verified against tracer.py::_fresnel_unpolarized (line 150) and the prism spectral
dispatch at tracer.py:1495.
"""
from __future__ import annotations

import numpy as np


def fresnel_transmittance_unpolarized(theta_i_rad: float, n1: float, n2: float) -> float:
    """Analytical unpolarized T(θ) at a flat interface. Returns scalar in [0,1]."""
    cos_i = float(np.cos(theta_i_rad))
    sin_t_sq = (n1 / n2) ** 2 * (1.0 - cos_i ** 2)
    if sin_t_sq >= 1.0:
        return 0.0  # total internal reflection
    cos_t = float(np.sqrt(1.0 - sin_t_sq))
    rs = (n1 * cos_i - n2 * cos_t) / (n1 * cos_i + n2 * cos_t)
    rp = (n2 * cos_i - n1 * cos_t) / (n2 * cos_i + n1 * cos_t)
    R = 0.5 * (rs ** 2 + rp ** 2)
    return 1.0 - R


def integrating_cavity_irradiance(
    phi: float, area: float, rho: float, n_bounces: int,
) -> float:
    """Finite-bounce wall irradiance for any convex closed Lambertian cavity.

    Asymptotic limit: Φρ/[A(1-ρ)]. This finite-bounce form matches Pitfall 4.
    """
    return (phi / area) * rho * (1.0 - rho ** n_bounces) / (1.0 - rho)


def integrating_sphere_port_irradiance(
    phi: float,
    port_area: float,
    total_wall_area: float,
    rho: float,
    source_to_port_distance: float,
) -> float:
    """Port irradiance for an isotropic source at the center of a closed
    Lambertian cavity with a small square port on one wall.

    Accounts for two components:

    1. **Direct flux** from the point source through the port solid angle
       at ``source_to_port_distance``:
       ``E_direct = phi / (4π · d²)``.

    2. **Indirect flux** via integrating-sphere throughput approximation.
       After one diffuse bounce on the walls, flux is (approximately)
       uniformly redistributed. The integrating-sphere multiplier
       ``M = ρ / [1 - ρ·(1 - f)]`` (with ``f = A_port / A_total``) gives the
       cumulative throughput. Port flux after the first diffuse hit is
       ``phi · M · f · (1 - f)`` (the ``1 - f`` factor removes direct hits
       onto the port itself from the first bounce).

    Cube cavities are only approximately integrating spheres — the first
    diffuse redistribution is not perfectly uniform — so a ~5% relative
    residual against this formula is expected for a 6-wall cube cavity.
    The ray tracer's Lambertian reflection block is validated by the
    residual staying below that bound at seed 42.
    """
    import math as _math
    f = port_area / total_wall_area
    E_direct = phi / (4.0 * _math.pi * source_to_port_distance ** 2)
    M = rho / (1.0 - rho * (1.0 - f))
    E_indirect = phi * M * f * (1.0 - f) / port_area
    return E_direct + E_indirect


def lambert_cosine(i0: float, theta_rad: np.ndarray) -> np.ndarray:
    """I(θ) = I₀·cos(θ) for Lambertian emitter."""
    return i0 * np.cos(theta_rad)


def snell_exit_angle(theta_in_rad: float, n: float, apex_rad: float) -> float:
    """Prism exit angle (symmetric incidence, apex apex_rad, refractive index n).

    Returns NaN if TIR occurs at the exit face.
    """
    theta1 = float(np.arcsin(np.sin(theta_in_rad) / n))
    theta2 = apex_rad - theta1
    if n * float(np.sin(theta2)) > 1.0:
        return float("nan")
    return float(np.arcsin(n * float(np.sin(theta2))))
