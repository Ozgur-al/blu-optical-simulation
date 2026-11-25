"""IES (IESNA LM-63) and basic LDT file parsers.

Converts angular intensity data to the internal {theta_deg, intensity} format
used by Project.angular_distributions.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np


def _azimuthal_average(c_angles_deg: np.ndarray, candela: np.ndarray) -> np.ndarray:
    """Average ``candela`` (n_planes, n_vert) over azimuth, weighting each
    C-plane by the azimuth span it represents (trapezoidal rule).

    The stored planes may cover a symmetric sub-range (single plane, 0-90,
    0-180, 90-270 ...); averaging over that sub-range equals the full-circle
    average for the corresponding symmetry.  When the planes span more than
    180 deg but less than 360 deg (full data without the closing 360 plane)
    the first plane is re-appended at +360 so the wrap interval is weighted
    too.  Duplicate closing planes (0 and 360) are handled naturally by the
    trapezoid end weights.
    """
    ang = np.asarray(c_angles_deg, dtype=float)
    cd = np.asarray(candela, dtype=float)
    n = cd.shape[0]
    if n == 1 or ang.size != n:
        return cd.mean(axis=0)
    span = ang[-1] - ang[0]
    if 180.0 < span < 360.0 - 1e-9:
        ang = np.append(ang, ang[0] + 360.0)
        cd = np.vstack([cd, cd[:1]])
        span = 360.0
    if span <= 0:
        return cd.mean(axis=0)
    d = np.diff(ang)
    w = np.zeros(ang.size, dtype=float)
    w[:-1] += d / 2.0
    w[1:] += d / 2.0
    if w.sum() <= 0:
        return cd.mean(axis=0)
    return (cd * w[:, None]).sum(axis=0) / w.sum()


def _normalize_peak(arr: np.ndarray) -> np.ndarray:
    peak = arr.max() if arr.size else 0.0
    return arr / peak if peak > 0 else arr


def _tokens_to_floats(lines: list[str]) -> list[float]:
    nums: list[float] = []
    for line in lines:
        for token in line.replace(",", " ").split():
            try:
                nums.append(float(token))
            except ValueError:
                continue
    return nums


def load_ies(path: str | Path) -> dict[str, list[float]]:
    """Parse an IESNA LM-63 format (.ies) file.

    Handles ``TILT=NONE``, ``TILT=INCLUDE`` (the tilt block is skipped; tilt
    multipliers only matter for lamp orientation, not the radial profile) and
    ``TILT=<file>`` (treated as NONE).  Returns
    ``{"theta_deg": [...], "intensity": [...]}`` with the C-planes averaged
    over azimuth (span-weighted) to a single peak-normalised radial profile.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    tilt_idx = None
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("TILT="):
            tilt_idx = i
            break
    if tilt_idx is None:
        raise ValueError("Not a valid IES file: TILT= line not found")
    tilt_value = lines[tilt_idx].strip()[5:].strip().upper()

    nums = _tokens_to_floats(lines[tilt_idx + 1:])
    offset = 0
    if tilt_value == "INCLUDE":
        # <lamp-to-luminaire geometry> <N> <N angles> <N multipliers>
        if len(nums) < 2:
            raise ValueError("IES TILT=INCLUDE block is truncated")
        n_tilt = int(nums[1])
        offset = 2 + 2 * n_tilt

    if len(nums) - offset < 13:
        raise ValueError("IES file has insufficient numeric data")

    h = nums[offset: offset + 13]
    candela_mult = h[2]
    n_vert = int(h[3])
    n_horiz = int(h[4])
    if n_vert <= 0 or n_horiz <= 0:
        raise ValueError("IES file declares no vertical/horizontal angles")
    offset += 13

    needed = n_vert + n_horiz + n_vert * n_horiz
    if len(nums) - offset < needed:
        raise ValueError(
            f"IES file has insufficient candela data: need {needed} values, "
            f"got {len(nums) - offset}"
        )

    vert_angles = np.array(nums[offset: offset + n_vert], dtype=float)
    offset += n_vert
    horiz_angles = np.array(nums[offset: offset + n_horiz], dtype=float)
    offset += n_horiz
    candela = np.array(
        nums[offset: offset + n_vert * n_horiz], dtype=float
    ).reshape(n_horiz, n_vert)
    candela *= candela_mult

    avg_intensity = _normalize_peak(_azimuthal_average(horiz_angles, candela))
    return {
        "theta_deg": vert_angles.tolist(),
        "intensity": avg_intensity.tolist(),
    }


def _ldt_float(s: str) -> float:
    return float(s.strip().replace(",", "."))


def load_ldt(path: str | Path) -> dict[str, list[float]]:
    """Parse an EULUMDAT (.ldt) file per the EULUMDAT specification.

    Layout (1-based line numbers): 1 company, 2 Ityp, 3 Isym, 4 Mc, 5 Dc,
    6 Ng, 7 Dg, 8-12 text, 13-21 dimensions, 22 DFF, 23 LORL, 24 conversion
    factor, 25 tilt, 26 n lamp sets, then 6 lines per lamp set, 10 direct
    ratios, Mc C-angles, Ng gamma angles, then intensities (cd/klm) for the
    C-planes stored under the declared symmetry (Isym 0..4).

    Returns ``{"theta_deg": gamma, "intensity": I}`` averaged over azimuth
    (span-weighted) and normalised to peak 1.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    # Keep blank lines: text fields (lines 8-12, lamp type) may be empty.
    lines = [l.strip() for l in text.splitlines()]

    try:
        isym = int(_ldt_float(lines[2]))
        mc = int(_ldt_float(lines[3]))
        n_gamma = int(_ldt_float(lines[5]))
        conv = _ldt_float(lines[23]) if lines[23] else 1.0
        n_sets = int(_ldt_float(lines[25]))
    except (IndexError, ValueError) as exc:
        raise ValueError(f"LDT header is malformed: {exc}") from exc
    if mc <= 0 or n_gamma <= 0:
        raise ValueError("LDT declares no C-planes or gamma angles")
    if isym not in (0, 1, 2, 3, 4):
        raise ValueError(f"LDT: unsupported symmetry indicator Isym={isym}")

    pos = 26 + 6 * n_sets + 10   # 0-based index of the first C angle
    if isym == 0:
        n_store, mc1 = mc, 0
    elif isym == 1:
        n_store, mc1 = 1, 0
    elif isym == 2:
        n_store, mc1 = mc // 2 + 1, 0
    elif isym == 3:
        n_store, mc1 = mc // 2 + 1, (3 * mc) // 4
    else:  # 4
        n_store, mc1 = mc // 4 + 1, 0

    def _read(count: int, start: int, what: str) -> list[float]:
        vals = [_ldt_float(l) for l in lines[start: start + count]]
        if len(vals) < count:
            raise ValueError(f"LDT: expected {count} {what}, got {len(vals)}")
        return vals

    try:
        c_angles = np.array(_read(mc, pos, "C-plane angles"))
        pos += mc
        gamma = np.array(_read(n_gamma, pos, "gamma angles"))
        pos += n_gamma
        # Intensities are normally one per line; tolerate several per line.
        tail = [v for l in lines[pos:] for v in l.replace(";", " ").split()]
        vals = [_ldt_float(v) for v in tail[: n_store * n_gamma]]
    except ValueError as exc:
        raise ValueError(f"LDT data block is malformed: {exc}") from exc
    if len(vals) < n_store * n_gamma:
        raise ValueError(
            f"LDT: expected {n_store * n_gamma} intensity values, got {len(vals)}"
        )
    candela = np.array(vals, dtype=float).reshape(n_store, n_gamma) * conv

    idx = [(mc1 + i) % mc for i in range(n_store)]
    plane_angles = c_angles[idx].astype(float)
    # Unwrap (Isym=3 stores C270 -> C360/C0 -> C90).
    for i in range(1, plane_angles.size):
        while plane_angles[i] < plane_angles[i - 1]:
            plane_angles[i] += 360.0

    avg_intensity = _normalize_peak(_azimuthal_average(plane_angles, candela))
    return {
        "theta_deg": gamma.tolist(),
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

    # LM-63 type C requires vertical angles starting at 0 and ending at 180
    # (full sphere) and horizontal angles 0..360 inclusive.  The simulator's
    # bins are centred ((i + 0.5) * step), so resample onto compliant grids:
    # vertical — add 0/180 end points (pole value = nearest bin);
    # horizontal — periodic interpolation from bin centres onto 0..360.
    v_out = theta.copy()
    if v_out.size == 0 or v_out[0] > 0.0:
        v_out = np.concatenate(([0.0], v_out))
    if v_out[-1] < 180.0:
        v_out = np.concatenate((v_out, [180.0]))
    grid_v = np.empty((v_out.size, n_phi), dtype=float)
    for j in range(n_phi):
        grid_v[:, j] = np.interp(v_out, theta, grid[:, j])

    phi_step = 360.0 / n_phi
    phi_centres = (np.arange(n_phi) + 0.5) * phi_step
    h_out = np.arange(n_phi + 1) * phi_step          # 0 .. 360 inclusive
    h_out[-1] = 360.0
    xp = np.concatenate(([phi_centres[-1] - 360.0], phi_centres,
                         [phi_centres[0] + 360.0]))
    out = np.empty((v_out.size, h_out.size), dtype=float)
    for i in range(v_out.size):
        fp = np.concatenate(([grid_v[i, -1]], grid_v[i], [grid_v[i, 0]]))
        out[i] = np.interp(h_out, xp, fp)

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
            f"{n_lamps}  {total_lm:.4f}  1.0  {v_out.size}  {h_out.size}  1  1"
            "  0.0  0.0  0.0"
        ),
        # Ballast factor, future use, input watts
        "1.0  1.0  0.0",
    ]

    # Vertical angles (theta) — one line, space-separated
    lines.append(" ".join(f"{v:.4f}" for v in v_out))

    # Horizontal angles (phi) — one line, space-separated
    lines.append(" ".join(f"{v:.4f}" for v in h_out))

    # Candela data: one row per C-plane (phi slice), theta values
    for phi_idx in range(h_out.size):
        lines.append(" ".join(f"{v:.4f}" for v in out[:, phi_idx]))

    _atomic_write_text(Path(path), "\n".join(lines) + "\n")


def _atomic_write_text(path: Path, text: str) -> None:
    import os
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                               dir=str(path.parent) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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

    # Beam / field angle measured about the actual beam axis (not an
    # assumed theta=0): the axis is the candela-weighted mean direction of
    # bins at >= 50 % of peak (falls back to the peak bin).  Candela is then
    # averaged in rings of angular distance from that axis and the full
    # angle is 2x the interpolated distance of the outermost 50 % / 10 %
    # crossing of the ring profile (normalised to its maximum).
    beam_angle, field_angle = _beam_field_angles(grid, theta_deg)

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


def _beam_field_angles(grid: np.ndarray, theta_deg: np.ndarray) -> tuple[float, float]:
    n_theta, n_phi = grid.shape
    peak = float(grid.max()) if grid.size else 0.0
    if peak <= 0:
        return 0.0, 0.0
    th = np.deg2rad(np.asarray(theta_deg, dtype=float))
    ph = (np.arange(n_phi) + 0.5) * 2.0 * np.pi / n_phi
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    dirs = np.stack([np.sin(TH) * np.cos(PH), np.sin(TH) * np.sin(PH), np.cos(TH)], axis=-1)

    mask = grid >= 0.5 * peak
    w = (grid * np.sin(TH))[mask]
    axis = (dirs[mask] * w[:, None]).sum(axis=0)
    if np.linalg.norm(axis) < 1e-9 * max(float(w.sum()), 1e-300):
        i, j = np.unravel_index(int(np.argmax(grid)), grid.shape)
        axis = dirs[i, j]
    axis = axis / np.linalg.norm(axis)

    alpha = np.degrees(np.arccos(np.clip(dirs @ axis, -1.0, 1.0)))
    step = 180.0 / n_theta
    edges = np.arange(0.0, 180.0 + step, step)
    idx = np.clip(np.digitize(alpha.ravel(), edges) - 1, 0, len(edges) - 2)
    sums = np.bincount(idx, weights=grid.ravel(), minlength=len(edges) - 1)
    cnts = np.bincount(idx, minlength=len(edges) - 1)
    valid = cnts > 0
    centres = (edges[:-1] + edges[1:]) / 2.0
    prof_a = centres[valid]
    prof = sums[valid] / cnts[valid]
    if prof.size == 0 or prof.max() <= 0:
        return 0.0, 0.0
    prof = prof / prof.max()
    # Anchor the profile at alpha = 0 with the first ring's value.
    prof_a = np.concatenate(([0.0], prof_a))
    prof = np.concatenate(([prof[0]], prof))

    def _half(thr: float) -> float:
        # Outermost crossing (so batwing / ring-peaked beams use the outer
        # edge, as the previous "last theta above threshold" rule did).
        above = np.nonzero(prof >= thr)[0]
        if above.size == 0:
            return 0.0
        k = int(above[-1])
        if k >= prof.size - 1:
            return float(prof_a[-1])
        a0, a1 = prof_a[k], prof_a[k + 1]
        p0, p1 = prof[k], prof[k + 1]
        if p0 == p1:
            return float(a0)
        return float(a0 + (p0 - thr) / (p0 - p1) * (a1 - a0))

    return 2.0 * _half(0.5), 2.0 * _half(0.1)
