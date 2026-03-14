"""BSDF (Bidirectional Scattering Distribution Function) CSV import and validation.

CSV format expected: long-format with 4 required columns:
    theta_in      — incident angle in degrees (polar angle from surface normal)
    theta_out     — scattered angle in degrees (polar angle from surface normal)
    refl_intensity — reflective BSDF intensity for this (theta_in, theta_out) pair
    trans_intensity — transmissive BSDF intensity for this (theta_in, theta_out) pair

Each row represents one (theta_in, theta_out) pair. The function pivots this into a
2D matrix structure suitable for 2D CDF importance sampling.

Profile dict structure returned:
    {
        "theta_in":  [ti_0, ti_1, ..., ti_M-1],        # sorted unique theta_in values
        "theta_out": [to_0, to_1, ..., to_N-1],        # sorted unique theta_out values
        "refl_intensity":  [[...], ...],                # (M, N) nested list
        "trans_intensity": [[...], ...],                # (M, N) nested list
    }
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np


def load_bsdf_csv(path: str | Path) -> dict:
    """Parse a goniophotometer BSDF CSV file (long format) into a profile dict.

    Parameters
    ----------
    path : str or Path
        Path to the CSV file.

    Returns
    -------
    dict
        Profile with keys: theta_in, theta_out, refl_intensity, trans_intensity.

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    path = Path(path)
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        # Check required columns
        required = {"theta_in", "theta_out", "refl_intensity", "trans_intensity"}
        missing = required - set(fieldnames)
        if missing:
            raise ValueError(
                f"BSDF CSV is missing required columns: {sorted(missing)}. "
                f"Expected columns: theta_in, theta_out, refl_intensity, trans_intensity."
            )
        for row in reader:
            rows.append({
                "theta_in": float(row["theta_in"]),
                "theta_out": float(row["theta_out"]),
                "refl_intensity": float(row["refl_intensity"]),
                "trans_intensity": float(row["trans_intensity"]),
            })

    if not rows:
        raise ValueError("BSDF CSV contains no data rows.")

    # Extract unique sorted theta_in and theta_out values
    theta_in_vals = sorted(set(r["theta_in"] for r in rows))
    theta_out_vals = sorted(set(r["theta_out"] for r in rows))

    M = len(theta_in_vals)
    N = len(theta_out_vals)

    # Build index maps
    ti_idx = {v: i for i, v in enumerate(theta_in_vals)}
    to_idx = {v: i for i, v in enumerate(theta_out_vals)}

    refl_matrix = np.zeros((M, N), dtype=float)
    trans_matrix = np.zeros((M, N), dtype=float)

    for row in rows:
        i = ti_idx[row["theta_in"]]
        j = to_idx[row["theta_out"]]
        refl_matrix[i, j] = row["refl_intensity"]
        trans_matrix[i, j] = row["trans_intensity"]

    return {
        "theta_in": theta_in_vals,
        "theta_out": theta_out_vals,
        "refl_intensity": refl_matrix.tolist(),
        "trans_intensity": trans_matrix.tolist(),
    }


def validate_bsdf(profile: dict) -> tuple[bool, str]:
    """Validate that a BSDF profile conserves energy.

    For each theta_in row, the total integrated reflectance + transmittance must
    not exceed 1.0 (within a small tolerance). This ensures no energy is created.

    The check is done by summing the refl_intensity and trans_intensity values
    per row. If any row sum > 1.0 + tolerance, the profile is rejected.

    Note: this is a loose check on raw intensities (not proper solid-angle
    integration). A properly normalized BSDF file would have row sums <= 1.0.

    Parameters
    ----------
    profile : dict
        BSDF profile dict as returned by load_bsdf_csv.

    Returns
    -------
    (valid, message) : tuple[bool, str]
        valid is True if the profile passes energy conservation.
        message describes the issue if invalid.
    """
    theta_in = profile.get("theta_in", [])
    refl = np.asarray(profile.get("refl_intensity", []), dtype=float)
    trans = np.asarray(profile.get("trans_intensity", []), dtype=float)

    if refl.ndim != 2 or trans.ndim != 2:
        return False, "refl_intensity and trans_intensity must be 2D arrays."

    if refl.shape != trans.shape:
        return False, (
            f"refl_intensity shape {refl.shape} != trans_intensity shape {trans.shape}"
        )

    tolerance = 1e-3
    # Sum over theta_out axis (axis=1) for each theta_in row
    total_per_row = refl.sum(axis=1) + trans.sum(axis=1)

    bad_rows = np.where(total_per_row > 1.0 + tolerance)[0]
    if bad_rows.size > 0:
        idx = int(bad_rows[0])
        ti = theta_in[idx] if idx < len(theta_in) else idx
        row_sum = float(total_per_row[idx])
        return False, (
            f"Energy conservation violated at theta_in={ti}°: "
            f"sum(refl+trans)={row_sum:.4f} > 1.0+{tolerance}"
        )

    return True, "OK"
