"""Default angular distribution profiles and CSV helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np


DEFAULT_PROFILE_POINTS: dict[str, tuple[list[float], list[float]]] = {
    "isotropic": (
        [0, 10, 20, 30, 40, 50, 60, 70, 80, 90],
        [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    ),
    "lambertian": (
        [0, 10, 20, 30, 40, 50, 60, 70, 80, 90],
        [1.0, 0.985, 0.94, 0.866, 0.766, 0.643, 0.5, 0.342, 0.174, 0.0],
    ),
    "batwing": (
        [0, 10, 20, 30, 40, 50, 60, 70, 80, 90],
        [0.3, 0.38, 0.54, 0.72, 0.88, 1.0, 0.92, 0.68, 0.35, 0.0],
    ),
}


def default_profile_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "angular_distributions"


def _write_csv(path: Path, theta: list[float], intensity: list[float]) -> None:
    arr = np.column_stack([np.asarray(theta, dtype=float), np.asarray(intensity, dtype=float)])
    np.savetxt(path, arr, delimiter=",", header="theta_deg,intensity", comments="")


def ensure_default_profile_csvs() -> Path:
    folder = default_profile_dir()
    folder.mkdir(parents=True, exist_ok=True)
    for name, (theta, intensity) in DEFAULT_PROFILE_POINTS.items():
        path = folder / f"{name}.csv"
        if not path.exists():
            _write_csv(path, theta, intensity)
    return folder


def load_profile_csv(path: str | Path) -> dict[str, list[float]]:
    data = np.genfromtxt(path, delimiter=",", comments="#", dtype=float)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] < 2:
        raise ValueError(f"Invalid profile CSV: {path}")
    theta = data[:, 0]
    intensity = data[:, 1]
    valid = np.isfinite(theta) & np.isfinite(intensity)
    theta = np.clip(theta[valid], 0.0, 180.0)
    intensity = np.clip(intensity[valid], 0.0, None)
    order = np.argsort(theta)
    theta = theta[order]
    intensity = intensity[order]
    return {"theta_deg": theta.tolist(), "intensity": intensity.tolist()}


def load_default_profiles() -> dict[str, dict[str, list[float]]]:
    folder = ensure_default_profile_csvs()
    out: dict[str, dict[str, list[float]]] = {}
    for path in sorted(folder.glob("*.csv")):
        out[path.stem] = load_profile_csv(path)
    return out


def merge_default_profiles(project) -> None:
    defaults = load_default_profiles()
    for name, profile in defaults.items():
        if name not in project.angular_distributions:
            project.angular_distributions[name] = profile
