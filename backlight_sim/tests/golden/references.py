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
