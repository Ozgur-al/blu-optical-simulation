"""Spectral utilities — SPD sampling, CIE XYZ color matching."""

from __future__ import annotations

import numpy as np

# Visible wavelength range (nm)
LAMBDA_MIN = 380.0
LAMBDA_MAX = 780.0
N_SPECTRAL_BINS = 40  # default spectral resolution (10 nm bins)


# -----------------------------------------------------------------------
# CIE 1931 2-degree observer, sampled at 10 nm intervals (380–780 nm)
# Compact inline table to avoid external data files.
# -----------------------------------------------------------------------

_CIE_LAMBDA = np.arange(380, 790, 10, dtype=float)  # 41 points

_CIE_X = np.array([
    0.0014, 0.0042, 0.0143, 0.0435, 0.1344, 0.2839, 0.3483, 0.3362,
    0.2908, 0.1954, 0.0956, 0.0320, 0.0049, 0.0093, 0.0633, 0.1655,
    0.2904, 0.4334, 0.5945, 0.7621, 0.9163, 1.0263, 1.0622, 1.0026,
    0.8544, 0.6424, 0.4479, 0.2835, 0.1649, 0.0874, 0.0468, 0.0227,
    0.0114, 0.0058, 0.0029, 0.0014, 0.0007, 0.0003, 0.0002, 0.0001,
    0.0000,
], dtype=float)

_CIE_Y = np.array([
    0.0000, 0.0001, 0.0004, 0.0012, 0.0040, 0.0116, 0.0230, 0.0380,
    0.0600, 0.0910, 0.1390, 0.2080, 0.3230, 0.5030, 0.7100, 0.8620,
    0.9540, 0.9950, 0.9950, 0.9520, 0.8700, 0.7570, 0.6310, 0.5030,
    0.3810, 0.2650, 0.1750, 0.1070, 0.0610, 0.0320, 0.0170, 0.0082,
    0.0041, 0.0021, 0.0010, 0.0005, 0.0003, 0.0001, 0.0001, 0.0000,
    0.0000,
], dtype=float)

_CIE_Z = np.array([
    0.0065, 0.0201, 0.0679, 0.2074, 0.6456, 1.3856, 1.7471, 1.7721,
    1.6692, 1.2876, 0.8130, 0.4652, 0.2720, 0.1582, 0.0782, 0.0422,
    0.0203, 0.0087, 0.0039, 0.0021, 0.0017, 0.0011, 0.0008, 0.0003,
    0.0002, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000,
    0.0000,
], dtype=float)


# -----------------------------------------------------------------------
# Built-in SPDs
# -----------------------------------------------------------------------

def _spd_flat() -> tuple[np.ndarray, np.ndarray]:
    """Uniform (equal-energy white) SPD."""
    lam = np.linspace(LAMBDA_MIN, LAMBDA_MAX, N_SPECTRAL_BINS)
    return lam, np.ones_like(lam)


def _spd_warm_white() -> tuple[np.ndarray, np.ndarray]:
    """Approximate warm white LED (3000 K phosphor + blue peak)."""
    lam = np.linspace(LAMBDA_MIN, LAMBDA_MAX, N_SPECTRAL_BINS)
    # Blue peak ~450 nm + broad phosphor hump ~580 nm
    blue = np.exp(-0.5 * ((lam - 450) / 15) ** 2) * 0.6
    phosphor = np.exp(-0.5 * ((lam - 580) / 60) ** 2)
    spd = blue + phosphor
    return lam, spd / spd.max()


def _spd_cool_white() -> tuple[np.ndarray, np.ndarray]:
    """Approximate cool white LED (6500 K phosphor + blue peak)."""
    lam = np.linspace(LAMBDA_MIN, LAMBDA_MAX, N_SPECTRAL_BINS)
    blue = np.exp(-0.5 * ((lam - 455) / 12) ** 2) * 1.0
    phosphor = np.exp(-0.5 * ((lam - 555) / 55) ** 2) * 0.7
    spd = blue + phosphor
    return lam, spd / spd.max()


def _spd_mono(wavelength_nm: float) -> tuple[np.ndarray, np.ndarray]:
    """Monochromatic source at a single wavelength."""
    lam = np.linspace(LAMBDA_MIN, LAMBDA_MAX, N_SPECTRAL_BINS)
    spd = np.exp(-0.5 * ((lam - wavelength_nm) / 3.0) ** 2)
    return lam, spd / max(spd.max(), 1e-12)


BUILTIN_SPDS = {
    "white": _spd_flat,
    "warm_white": _spd_warm_white,
    "cool_white": _spd_cool_white,
}


def get_spd(name: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (wavelengths_nm, relative_intensity) for a named SPD.

    Supports: "white", "warm_white", "cool_white", "mono_<nm>".
    """
    if name in BUILTIN_SPDS:
        return BUILTIN_SPDS[name]()
    if name.startswith("mono_"):
        try:
            wl = float(name[5:])
            return _spd_mono(wl)
        except ValueError:
            pass
    # Fallback to flat white
    return _spd_flat()


def get_spd_from_project(
    name: str, spd_profiles: dict | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Return (wavelengths_nm, relative_intensity) for a named SPD.

    Checks ``spd_profiles`` dict first, then falls back to ``get_spd(name)``
    (built-in SPDs: "white", "warm_white", "cool_white", "mono_<nm>").

    Parameters
    ----------
    name : str
        SPD name.
    spd_profiles : dict or None
        Project-level custom SPD table.  Format::

            { "<name>": {"wavelength_nm": [...], "intensity": [...]} }
    """
    if spd_profiles:
        entry = spd_profiles.get(name)
        if entry is not None:
            wl = np.asarray(entry["wavelength_nm"], dtype=float)
            intensity = np.asarray(entry["intensity"], dtype=float)
            return wl, intensity
    return get_spd(name)


def blackbody_spd(
    cct_K: float, n_bins: int = N_SPECTRAL_BINS
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a Planckian (blackbody) SPD at the given color temperature.

    Uses Planck's law: B(lambda, T) ~ lambda^-5 / (exp(hc / lambda*k*T) - 1).
    The result is normalized so that peak intensity = 1.

    Parameters
    ----------
    cct_K : float
        Color temperature in Kelvin (e.g., 3000 for warm white, 6500 for cool white).
    n_bins : int
        Number of spectral bins (default N_SPECTRAL_BINS = 40).

    Returns
    -------
    wavelengths_nm : np.ndarray of shape (n_bins,)
    intensity : np.ndarray of shape (n_bins,), normalized to peak = 1
    """
    lam = np.linspace(LAMBDA_MIN, LAMBDA_MAX, n_bins)
    lam_m = lam * 1e-9  # convert nm to metres
    # Physical constants
    h = 6.626e-34   # Planck's constant (J·s)
    c = 2.998e8     # speed of light (m/s)
    k = 1.381e-23   # Boltzmann constant (J/K)

    exponent = (h * c) / (lam_m * k * cct_K)
    # Clamp to avoid overflow in exp for very short wavelengths / low T
    exponent = np.clip(exponent, 0.0, 700.0)
    spd = lam_m ** -5 / (np.exp(exponent) - 1.0 + 1e-300)

    peak = spd.max()
    if peak > 0:
        spd = spd / peak
    return lam, spd


# -----------------------------------------------------------------------
# Wavelength sampling
# -----------------------------------------------------------------------

def sample_wavelengths(
    n: int,
    spd_name: str,
    rng: np.random.Generator,
    spd_profiles: dict | None = None,
) -> np.ndarray:
    """Sample n wavelengths according to the source SPD.

    Parameters
    ----------
    n : int
        Number of wavelengths to sample.
    spd_name : str
        Name of the SPD (built-in or custom key).
    rng : np.random.Generator
        Random number generator.
    spd_profiles : dict or None
        Optional project-level custom SPD profiles; checked before built-ins.

    Returns
    -------
    np.ndarray of shape (n,) — wavelengths in nm.
    """
    lam, intensity = get_spd_from_project(spd_name, spd_profiles)
    # Build CDF
    cdf = np.cumsum(intensity)
    cdf = cdf / cdf[-1]
    # Invert CDF
    u = rng.uniform(size=n)
    return np.interp(u, cdf, lam)


# -----------------------------------------------------------------------
# CIE XYZ <-> sRGB conversion
# -----------------------------------------------------------------------

def wavelength_to_xyz(wavelength_nm: float) -> np.ndarray:
    """Convert a single wavelength to CIE XYZ (interpolated)."""
    x = np.interp(wavelength_nm, _CIE_LAMBDA, _CIE_X)
    y = np.interp(wavelength_nm, _CIE_LAMBDA, _CIE_Y)
    z = np.interp(wavelength_nm, _CIE_LAMBDA, _CIE_Z)
    return np.array([x, y, z])


def spectral_grid_to_rgb(spectral_grid: np.ndarray, wavelengths: np.ndarray) -> np.ndarray:
    """Convert a spectral grid (ny, nx, n_bins) to RGB image (ny, nx, 3).

    spectral_grid: accumulated flux per bin per pixel
    wavelengths: (n_bins,) center wavelengths in nm
    """
    ny, nx, n_bins = spectral_grid.shape

    # Compute XYZ weights for each bin
    xyz_weights = np.zeros((n_bins, 3), dtype=float)
    for i, wl in enumerate(wavelengths):
        xyz_weights[i] = wavelength_to_xyz(wl)

    # Integrate: (ny, nx, 3) = spectral_grid @ xyz_weights
    xyz_img = spectral_grid @ xyz_weights  # (ny, nx, 3)

    # XYZ to linear sRGB
    # sRGB D65 matrix
    m = np.array([
        [ 3.2406, -1.5372, -0.4986],
        [-0.9689,  1.8758,  0.0415],
        [ 0.0557, -0.2040,  1.0570],
    ], dtype=float)
    rgb_lin = xyz_img @ m.T

    # Normalize to [0, 1]
    mx = rgb_lin.max()
    if mx > 0:
        rgb_lin = rgb_lin / mx

    # Gamma correction (sRGB)
    rgb_lin = np.clip(rgb_lin, 0, 1)
    rgb = np.where(rgb_lin <= 0.0031308,
                   12.92 * rgb_lin,
                   1.055 * np.power(rgb_lin, 1.0 / 2.4) - 0.055)

    return np.clip(rgb, 0, 1).astype(np.float32)


def spectral_bin_centers(n_bins: int = N_SPECTRAL_BINS) -> np.ndarray:
    """Return center wavelengths for spectral bins."""
    return np.linspace(LAMBDA_MIN, LAMBDA_MAX, n_bins)
