"""IES (IESNA LM-63) and basic LDT file parsers.

Converts angular intensity data to the internal {theta_deg, intensity} format
used by Project.angular_distributions.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np


def load_ies(path: str | Path) -> dict[str, list[float]]:
    """Parse an IESNA LM-63 format (.ies) file.

    Returns {"theta_deg": [...], "intensity": [...]} with values averaged
    over all horizontal planes (C-planes) to produce a single radial profile.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Find TILT= line which precedes the numeric data
    tilt_idx = None
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("TILT="):
            tilt_idx = i
            break
    if tilt_idx is None:
        raise ValueError("Not a valid IES file: TILT= line not found")

    # Collect all numbers after TILT= line
    nums: list[float] = []
    for line in lines[tilt_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            continue
        for token in stripped.split():
            try:
                nums.append(float(token))
            except ValueError:
                continue

    if len(nums) < 13:
        raise ValueError("IES file has insufficient numeric data")

    # Parse header values (LM-63 standard order)
    n_lamps = int(nums[0])
    lumens_per_lamp = nums[1]
    candela_mult = nums[2]
    n_vert = int(nums[3])
    n_horiz = int(nums[4])
    photometric_type = int(nums[5])
    units_type = int(nums[6])
    width = nums[7]
    length = nums[8]
    height = nums[9]
    ballast_factor = nums[10]
    future_use = nums[11]
    input_watts = nums[12]

    offset = 13
    # Read vertical angles
    vert_angles = np.array(nums[offset: offset + n_vert], dtype=float)
    offset += n_vert

    # Read horizontal angles
    horiz_angles = np.array(nums[offset: offset + n_horiz], dtype=float)
    offset += n_horiz

    # Read candela values: n_horiz planes × n_vert values each
    candela = np.zeros((n_horiz, n_vert), dtype=float)
    for h in range(n_horiz):
        candela[h, :] = nums[offset: offset + n_vert]
        offset += n_vert

    # Apply multiplier
    candela *= candela_mult

    # Average across all horizontal planes to get I(θ)
    avg_intensity = candela.mean(axis=0)

    # Normalize: peak = 1.0
    peak = avg_intensity.max()
    if peak > 0:
        avg_intensity = avg_intensity / peak

    return {
        "theta_deg": vert_angles.tolist(),
        "intensity": avg_intensity.tolist(),
    }


def load_ldt(path: str | Path) -> dict[str, list[float]]:
    """Parse a basic EULUMDAT (.ldt) file.

    Returns {"theta_deg": [...], "intensity": [...]} averaged over C-planes.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    if len(lines) < 42:
        raise ValueError("LDT file too short to be valid EULUMDAT")

    # EULUMDAT format: line indices are fixed
    # Line 26 (0-indexed): number of C-planes (Mc)
    # Line 27: distance between C-planes (Dc)
    # Line 28: number of intensities per C-plane (Ng)
    # Line 29: distance between gamma angles (Dg)
    n_c_planes = int(float(lines[25]))
    dc = float(lines[26])
    n_gamma = int(float(lines[27]))
    dg = float(lines[28])

    # Lines 42 onward: intensity values
    # First come n_gamma values for C-plane 0, then for C-plane 1, etc.
    data_start = 42
    all_values: list[float] = []
    for line in lines[data_start:]:
        try:
            all_values.append(float(line))
        except ValueError:
            continue

    n_needed = n_c_planes * n_gamma
    if len(all_values) < n_needed:
        raise ValueError(f"LDT: expected {n_needed} intensity values, got {len(all_values)}")

    candela = np.array(all_values[:n_needed]).reshape(n_c_planes, n_gamma)

    # Gamma angles (vertical)
    gamma_angles = np.arange(n_gamma) * dg

    # Average over C-planes
    avg_intensity = candela.mean(axis=0)
    peak = avg_intensity.max()
    if peak > 0:
        avg_intensity = avg_intensity / peak

    return {
        "theta_deg": gamma_angles.tolist(),
        "intensity": avg_intensity.tolist(),
    }


def load_ies_or_ldt(path: str | Path) -> dict[str, list[float]]:
    """Auto-detect file type and parse accordingly."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".ldt":
        return load_ldt(p)
    return load_ies(p)


# ---------------------------------------------------------------------------
# IES / CSV export
# ---------------------------------------------------------------------------


def export_ies(
    path: str | Path,
    theta_deg: np.ndarray | list[float],
    candela_grid: np.ndarray,
    total_lm: float,
    n_lamps: int = 1,
) -> None:
    """Write an IESNA LM-63-2002 photometric file from a far-field candela distribution.

    Parameters
    ----------
    path : str or Path
        Output file path (typically .ies extension).
    theta_deg : array-like of shape (n_theta,)
        Vertical (elevation) angle values in degrees, 0..180.
    candela_grid : ndarray of shape (n_theta, n_phi)
        Candela values.  Rows = theta, columns = phi C-planes.
    total_lm : float
        Total luminous flux in lumens.
    n_lamps : int
        Number of lamps (default 1).
    """
    theta = np.asarray(theta_deg, dtype=float)
    grid = np.asarray(candela_grid, dtype=float)
    n_theta, n_phi = grid.shape

    # Phi angles: 0, step, ..., 360 - step
    phi_step = 360.0 / n_phi
    phi_deg = np.arange(n_phi) * phi_step

    lines: list[str] = [
        "IESNA:LM-63-2002",
        "[TEST] BLU Optical Simulation Export",
        "[MANUFAC] blu-sim",
        "[LUMCAT]",
        "[LUMINAIRE]",
        "[LAMP]",
        "TILT=NONE",
        # Photometric parameters line
        (
            f"{n_lamps}  {total_lm:.4f}  1.0  {n_theta}  {n_phi}  1  1"
            "  0.0  0.0  0.0  1.0  1.0  0.0"
        ),
    ]

    # Vertical angles (theta) — one line, space-separated
    lines.append(" ".join(f"{v:.4f}" for v in theta))

    # Horizontal angles (phi) — one line, space-separated
    lines.append(" ".join(f"{v:.4f}" for v in phi_deg))

    # Candela data: one row per C-plane (phi slice), theta values
    for phi_idx in range(n_phi):
        row = grid[:, phi_idx]
        lines.append(" ".join(f"{v:.4f}" for v in row))

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_farfield_csv(
    path: str | Path,
    theta_deg: np.ndarray | list[float],
    phi_deg: np.ndarray | list[float],
    candela_grid: np.ndarray,
) -> None:
    """Write far-field candela data as a long-format CSV.

    Columns: theta_deg, phi_deg, candela — one row per (theta, phi) bin.

    Parameters
    ----------
    path : str or Path
        Output .csv file path.
    theta_deg : array-like of shape (n_theta,)
        Theta angle centers in degrees.
    phi_deg : array-like of shape (n_phi,)
        Phi angle centers in degrees.
    candela_grid : ndarray of shape (n_theta, n_phi)
        Candela values.
    """
    theta = np.asarray(theta_deg, dtype=float)
    phi = np.asarray(phi_deg, dtype=float)
    grid = np.asarray(candela_grid, dtype=float)
    n_theta, n_phi = grid.shape

    rows: list[str] = ["theta_deg,phi_deg,candela"]
    for ti in range(n_theta):
        for pi in range(n_phi):
            rows.append(f"{theta[ti]:.4f},{phi[pi]:.4f},{grid[ti, pi]:.6f}")

    Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8")


def compute_farfield_kpis(
    candela_grid: np.ndarray,
    theta_centers_deg: np.ndarray | list[float],
) -> dict:
    """Compute photometric KPIs from a far-field candela distribution.

    Parameters
    ----------
    candela_grid : ndarray of shape (n_theta, n_phi)
        Candela distribution (rows = theta, columns = phi).
    theta_centers_deg : array-like of shape (n_theta,)
        Theta bin center angles in degrees (0 = north pole, 180 = south pole).

    Returns
    -------
    dict with keys:
        peak_cd : float — maximum candela value
        total_lm : float — total luminous flux (integrate candela * solid_angle)
        beam_angle : float — full angle (degrees) where candela >= 50% of peak
        field_angle : float — full angle (degrees) where candela >= 10% of peak
        asymmetry : float — max ratio of candela at symmetric phi positions
    """
    grid = np.asarray(candela_grid, dtype=float)
    theta_deg = np.asarray(theta_centers_deg, dtype=float)
    n_theta, n_phi = grid.shape

    # Peak candela
    peak_cd = float(grid.max())

    # Total flux: integrate candela * solid_angle over all bins
    theta_rad = np.deg2rad(theta_deg)
    delta_theta = np.pi / n_theta
    delta_phi = 2.0 * np.pi / n_phi
    solid_angles = delta_theta * delta_phi * np.maximum(np.sin(theta_rad), 1e-6)  # (n_theta,)
    total_lm = float((grid * solid_angles[:, None]).sum())

    # Beam angle and field angle — use average candela over all phi for each theta
    avg_cd_per_theta = grid.mean(axis=1)  # (n_theta,)

    if peak_cd > 0:
        norm_cd = avg_cd_per_theta / peak_cd
    else:
        norm_cd = avg_cd_per_theta

    # Beam angle: 2 × half-angle where avg_cd drops to 50% of peak.
    # For axially-symmetric sources peaked at theta=0, this gives full cone angle.
    above_50 = theta_deg[norm_cd >= 0.5]
    if len(above_50) > 0:
        beam_angle = float(above_50[-1] * 2.0)
    else:
        beam_angle = 0.0

    # Field angle: 2 × half-angle where avg_cd drops to 10% of peak
    above_10 = theta_deg[norm_cd >= 0.1]
    if len(above_10) > 0:
        field_angle = float(above_10[-1] * 2.0)
    else:
        field_angle = 0.0

    # Asymmetry: max ratio between opposing C-plane pairs
    # C0 vs C180 (phi=0 vs phi=180 degrees), C90 vs C270
    asymmetry = 1.0
    phi_step = 360.0 / n_phi
    opposite_pairs = [
        (0, n_phi // 2),          # C0 vs C180
        (n_phi // 4, 3 * n_phi // 4),  # C90 vs C270
    ]
    for i0, i1 in opposite_pairs:
        if i0 < n_phi and i1 < n_phi:
            cd0 = grid[:, i0]
            cd1 = grid[:, i1]
            denom = np.maximum(np.minimum(cd0, cd1), 1e-9)
            numer = np.maximum(cd0, cd1)
            ratio = float((numer / denom).max())
            asymmetry = max(asymmetry, ratio)

    return {
        "peak_cd": peak_cd,
        "total_lm": total_lm,
        "beam_angle": beam_angle,
        "field_angle": field_angle,
        "asymmetry": asymmetry,
    }
