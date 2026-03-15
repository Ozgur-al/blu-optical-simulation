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
    # Ensure wavelengths are sorted so trapezoidal CDF is monotonic
    order = np.argsort(lam)
    lam = lam[order]
    intensity = intensity[order]
    intensity = np.maximum(intensity, 0.0)
    total = intensity.sum()
    if total <= 0.0:
        # Uniform fallback for zero/negative SPDs
        return rng.uniform(lam[0], lam[-1], size=n)
    # Build CDF using trapezoidal integration (weights by wavelength spacing)
    mid = 0.5 * (intensity[:-1] + intensity[1:])
    dlam = np.diff(lam)
    cdf = np.concatenate(([0.0], np.cumsum(mid * dlam)))
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


# -----------------------------------------------------------------------
# CIE colorimetry helpers (XYZ, xy, u'v', CCT, color KPIs)
# -----------------------------------------------------------------------

def xyz_per_pixel(spectral_grid: np.ndarray, wavelengths: np.ndarray) -> np.ndarray:
    """Convert spectral grid to CIE XYZ image.

    Parameters
    ----------
    spectral_grid : np.ndarray, shape (ny, nx, n_bins)
        Accumulated spectral flux per bin per pixel.
    wavelengths : np.ndarray, shape (n_bins,)
        Center wavelength for each bin in nm.

    Returns
    -------
    np.ndarray, shape (ny, nx, 3)
        CIE XYZ image.
    """
    n_bins = len(wavelengths)
    # Build CIE XYZ weight matrix by interpolating the CMFs at each wavelength
    xyz_weights = np.zeros((n_bins, 3), dtype=float)
    for i, wl in enumerate(wavelengths):
        xyz_weights[i, 0] = np.interp(wl, _CIE_LAMBDA, _CIE_X)
        xyz_weights[i, 1] = np.interp(wl, _CIE_LAMBDA, _CIE_Y)
        xyz_weights[i, 2] = np.interp(wl, _CIE_LAMBDA, _CIE_Z)
    # Matrix multiply: (ny, nx, n_bins) @ (n_bins, 3) -> (ny, nx, 3)
    return spectral_grid @ xyz_weights


def xy_per_pixel(xyz: np.ndarray) -> np.ndarray:
    """Compute CIE 1931 (x, y) chromaticity from XYZ image.

    Parameters
    ----------
    xyz : np.ndarray, shape (ny, nx, 3)

    Returns
    -------
    np.ndarray, shape (ny, nx, 2)  — (x, y) chromaticity per pixel
    """
    s = xyz[..., 0] + xyz[..., 1] + xyz[..., 2]  # X + Y + Z
    s_safe = np.where(s > 0, s, 1.0)
    x = xyz[..., 0] / s_safe
    y = xyz[..., 1] / s_safe
    # Mask zero-luminance pixels
    x = np.where(s > 0, x, 0.0)
    y = np.where(s > 0, y, 0.0)
    return np.stack([x, y], axis=-1)


def uv_per_pixel(xyz: np.ndarray) -> np.ndarray:
    """Compute CIE 1976 u'v' chromaticity from XYZ image.

    u' = 4X / (X + 15Y + 3Z)
    v' = 9Y / (X + 15Y + 3Z)

    Parameters
    ----------
    xyz : np.ndarray, shape (ny, nx, 3)

    Returns
    -------
    np.ndarray, shape (ny, nx, 2)  — (u', v') per pixel
    """
    X = xyz[..., 0]
    Y = xyz[..., 1]
    Z = xyz[..., 2]
    denom = X + 15.0 * Y + 3.0 * Z
    denom_safe = np.where(denom > 0, denom, 1.0)
    u = 4.0 * X / denom_safe
    v = 9.0 * Y / denom_safe
    u = np.where(denom > 0, u, 0.0)
    v = np.where(denom > 0, v, 0.0)
    return np.stack([u, v], axis=-1)


# Robertson (1968) CCT isotherm table: (u, v, reciprocal_mired, slope)
# CCTs from 1000 K to ~50000 K (reciprocal megaKelvins = mired).
# Source: Robertson (1968) as reproduced in Wyszecki & Stiles "Color Science".
_ROBERTSON_TABLE = np.array([
    # u_i,      v_i,      t_i (10^6/K),  d_i (slope)
    [0.18006,  0.26352,  -0.24341,   0],   # boundary row for interpolation
    [0.18066,  0.26589,  -0.24341,   0],
    [0.18133,  0.26846,  -0.23764,   0],
    [0.18208,  0.27119,  -0.20219,   0],
    [0.18293,  0.27407,  -0.13338,   0],
    [0.18388,  0.27709,  -0.04905,   0],
    [0.18494,  0.28021,   0.04343,   0],
    [0.18611,  0.28342,   0.13650,   0],
    [0.18740,  0.28668,   0.22855,   0],
    [0.18880,  0.28997,   0.31803,   0],
    [0.19032,  0.29326,   0.40580,   0],
    [0.19462,  0.30141,   0.59071,   0],
    [0.19962,  0.30921,   0.73437,   0],
    [0.20525,  0.31647,   0.85445,   0],
    [0.21142,  0.32312,   0.95588,   0],
    [0.21807,  0.32909,   1.04370,   0],
    [0.22511,  0.33439,   1.12140,   0],
    [0.23247,  0.33904,   1.19030,   0],
    [0.24010,  0.34308,   1.25560,   0],
    [0.24792,  0.34655,   1.31220,   0],
    [0.25591,  0.34951,   1.36380,   0],
    [0.26400,  0.35200,   1.41310,   0],
    [0.27218,  0.35407,   1.46040,   0],
    [0.28039,  0.35577,   1.50570,   0],
    [0.28863,  0.35714,   1.54990,   0],
    [0.29685,  0.35823,   1.59360,   0],
    [0.30505,  0.35907,   1.63770,   0],
    [0.31320,  0.35968,   1.68440,   0],
    [0.32129,  0.36011,   1.73710,   0],
    [0.32931,  0.36038,   1.80200,   0],
    [0.33724,  0.36051,   1.88710,   0],
], dtype=float)

# Robertson CCT values in Kelvin corresponding to each row
_ROBERTSON_CCT_K = np.array([
    1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350, 1400, 1450, 1500,
    1600, 1700, 1800, 1900, 2000, 2100, 2200, 2300, 2400, 2500,
    2600, 2700, 2800, 2900, 3000, 3100, 3200, 3300, 3400, 3500,
], dtype=float)


def cct_robertson(xy: np.ndarray) -> np.ndarray:
    """Estimate CCT via Robertson's (1968) isotherm method.

    Parameters
    ----------
    xy : np.ndarray, shape (..., 2)
        CIE 1931 (x, y) chromaticity coordinates.

    Returns
    -------
    np.ndarray, shape (...)
        CCT in Kelvin. NaN for dark pixels (Y < 1e-10).
        Values are clamped to [1000, 25000] K.
    """
    x = xy[..., 0]
    y = xy[..., 1]

    # Convert to CIE 1960 UCS (u, v) for Robertson isotherms
    # u = 4x / (-2x + 12y + 3),  v = 6y / (-2x + 12y + 3)
    denom = -2.0 * x + 12.0 * y + 3.0
    denom_safe = np.where(denom != 0, denom, 1.0)
    u = 4.0 * x / denom_safe
    v = 6.0 * y / denom_safe

    orig_shape = u.shape
    u_flat = u.ravel()
    v_flat = v.ravel()
    n_pts = u_flat.shape[0]

    # Robertson table: u_i, v_i, slope_i (t_i is in col 2, slope in col 3)
    # We use 30 entries (skip first sentinel row for computation)
    tbl = _ROBERTSON_TABLE  # shape (31, 4)
    u_r = tbl[:, 0]
    v_r = tbl[:, 1]
    # Compute slopes from adjacent points
    # slope = (v[i+1] - v[i]) / (u[i+1] - u[i])  for each isotherm
    slopes = np.zeros(len(tbl), dtype=float)
    for i in range(len(tbl) - 1):
        du = u_r[i + 1] - u_r[i]
        if abs(du) > 1e-10:
            slopes[i] = (v_r[i + 1] - v_r[i]) / du
        else:
            slopes[i] = 1e6
    slopes[-1] = slopes[-2]

    cct_flat = np.full(n_pts, np.nan)

    for pt in range(n_pts):
        up = u_flat[pt]
        vp = v_flat[pt]
        # Skip dark pixels
        if not (np.isfinite(up) and np.isfinite(vp)):
            continue

        # Compute Robertson distance d_i = (vp - v_i) - slope_i * (up - u_i)
        d = (vp - v_r) - slopes * (up - u_r)

        # Find first sign change
        found = False
        for i in range(len(d) - 1):
            if np.isnan(d[i]) or np.isnan(d[i + 1]):
                continue
            if d[i] * d[i + 1] <= 0:
                # Interpolate between isotherm i and i+1
                di = abs(d[i])
                di1 = abs(d[i + 1])
                total = di + di1
                if total < 1e-12:
                    cct_val = _ROBERTSON_CCT_K[i]
                else:
                    # Interpolate in reciprocal Mired space
                    t_i = 1e6 / _ROBERTSON_CCT_K[i]
                    t_i1 = 1e6 / _ROBERTSON_CCT_K[min(i + 1, len(_ROBERTSON_CCT_K) - 1)]
                    t_interp = t_i + (t_i1 - t_i) * di / total
                    cct_val = 1e6 / t_interp if t_interp > 0 else _ROBERTSON_CCT_K[i]
                cct_flat[pt] = float(np.clip(cct_val, 1000.0, 25000.0))
                found = True
                break

        if not found:
            # Use closest endpoint
            closest = int(np.argmin(np.abs(d)))
            cct_flat[pt] = float(np.clip(_ROBERTSON_CCT_K[min(closest, len(_ROBERTSON_CCT_K) - 1)], 1000.0, 25000.0))

    return cct_flat.reshape(orig_shape)


def compute_color_kpis(
    spectral_grid: np.ndarray,
    wavelengths: np.ndarray,
) -> dict:
    """Compute CIE color uniformity KPIs from a spectral detector grid.

    Parameters
    ----------
    spectral_grid : np.ndarray, shape (ny, nx, n_bins)
    wavelengths : np.ndarray, shape (n_bins,)

    Returns
    -------
    dict with keys:
        delta_ccx, delta_ccy : float   — max-min range of CIE 1931 x, y (full detector)
        delta_uprime, delta_vprime : float  — max-min range of u', v' (full detector)
        cct_avg : float  — luminance-weighted mean CCT (K)
        cct_range : float  — max-min CCT range (K)
        center_1_4, center_1_6, center_1_10 : dict  — same KPIs for center fractions
    """
    xyz = xyz_per_pixel(spectral_grid, wavelengths)   # (ny, nx, 3)
    xy = xy_per_pixel(xyz)                              # (ny, nx, 2)
    uv = uv_per_pixel(xyz)                              # (ny, nx, 2)
    Y = xyz[..., 1]                                     # luminance (ny, nx)

    def _kpis_for_region(xy_r, uv_r, Y_r):
        mask = Y_r > 1e-10
        if not np.any(mask):
            return {
                "delta_ccx": 0.0, "delta_ccy": 0.0,
                "delta_uprime": 0.0, "delta_vprime": 0.0,
                "cct_avg": float("nan"), "cct_range": 0.0,
            }
        x_vals = xy_r[..., 0][mask]
        y_vals = xy_r[..., 1][mask]
        u_vals = uv_r[..., 0][mask]
        v_vals = uv_r[..., 1][mask]
        cct_vals = cct_robertson(np.stack([x_vals, y_vals], axis=-1))
        cct_valid = cct_vals[np.isfinite(cct_vals)]
        Y_masked = Y_r[mask]
        if len(cct_valid) > 0 and Y_masked.sum() > 0:
            w = Y_masked[np.isfinite(cct_vals)]
            w_sum = w.sum()
            cct_avg = float(np.dot(cct_valid, w) / w_sum) if w_sum > 0 else float(np.mean(cct_valid))
            cct_range = float(cct_valid.max() - cct_valid.min())
        else:
            cct_avg = float("nan")
            cct_range = 0.0
        return {
            "delta_ccx": float(x_vals.max() - x_vals.min()),
            "delta_ccy": float(y_vals.max() - y_vals.min()),
            "delta_uprime": float(u_vals.max() - u_vals.min()),
            "delta_vprime": float(v_vals.max() - v_vals.min()),
            "cct_avg": cct_avg,
            "cct_range": cct_range,
        }

    full_kpis = _kpis_for_region(xy, uv, Y)
    result = {
        "delta_ccx": full_kpis["delta_ccx"],
        "delta_ccy": full_kpis["delta_ccy"],
        "delta_uprime": full_kpis["delta_uprime"],
        "delta_vprime": full_kpis["delta_vprime"],
        "cct_avg": full_kpis["cct_avg"],
        "cct_range": full_kpis["cct_range"],
    }

    ny, nx = xy.shape[:2]
    for label, fraction in [("center_1_4", 0.25), ("center_1_6", 1 / 6), ("center_1_10", 0.10)]:
        f_side = float(np.sqrt(fraction))
        cy, cx = ny // 2, nx // 2
        half_y = max(1, int(ny * f_side / 2))
        half_x = max(1, int(nx * f_side / 2))
        xy_crop = xy[cy - half_y: cy + half_y, cx - half_x: cx + half_x]
        uv_crop = uv[cy - half_y: cy + half_y, cx - half_x: cx + half_x]
        Y_crop  = Y[cy - half_y: cy + half_y, cx - half_x: cx + half_x]
        region_kpis = _kpis_for_region(xy_crop, uv_crop, Y_crop)
        result[label] = {
            "delta_ccx":    region_kpis["delta_ccx"],
            "delta_ccy":    region_kpis["delta_ccy"],
            "delta_uprime": region_kpis["delta_uprime"],
            "delta_vprime": region_kpis["delta_vprime"],
        }

    return result
