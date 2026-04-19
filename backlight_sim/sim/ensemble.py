"""Ensemble tolerance Monte Carlo service.

Headless (no PySide6 / GUI imports). Consumed by gui/ensemble_dialog.py and tests.
"""

from __future__ import annotations

import copy
from statistics import NormalDist

import numpy as np

from backlight_sim.core.project_model import Project
from backlight_sim.io.geometry_builder import build_cavity


_STANDARD_NORMAL = NormalDist()
_CAVITY_SIGMA_KEYS = (
    "depth_sigma_mm",
    "wall_angle_x_sigma_deg",
    "wall_angle_y_sigma_deg",
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _count_active_tolerance_params(project: Project) -> int:
    """Return the number of tolerance parameters with sigma > 0 in *project*."""
    n = 0
    has_pos = (
        project.settings.source_position_sigma_mm > 0
        or any(s.position_sigma_mm > 0 for s in project.sources if s.enabled)
    )
    if has_pos:
        n += 1
    recipe = project.cavity_recipe
    if recipe.get("depth_sigma_mm", 0.0) > 0:
        n += 1
    if recipe.get("wall_angle_x_sigma_deg", 0.0) > 0:
        n += 1
    if recipe.get("wall_angle_y_sigma_deg", 0.0) > 0:
        n += 1
    return n


def _active_tolerance_params(project: Project) -> list[tuple[str, float]]:
    """Return ``[(param_name, sigma)]`` for all active tolerance parameters."""
    params: list[tuple[str, float]] = []
    sigma_default = project.settings.source_position_sigma_mm
    per_src_max = max(
        (s.position_sigma_mm for s in project.sources if s.enabled and s.position_sigma_mm > 0),
        default=0.0,
    )
    effective_pos_sigma = max(sigma_default, per_src_max)
    if effective_pos_sigma > 0:
        params.append(("position_sigma_mm", effective_pos_sigma))
    recipe = project.cavity_recipe
    for key in _CAVITY_SIGMA_KEYS:
        value = float(recipe.get(key, 0.0))
        if value > 0:
            params.append((key, value))
    return params


def _jitter_cavity(
    p: Project,
    rng: np.random.Generator,
    overrides: dict[str, float] | None = None,
) -> None:
    """Mutate *p* in-place by re-invoking ``build_cavity`` with jittered args."""
    recipe = dict(p.cavity_recipe)
    dist_depth = recipe.get("depth_distribution", "gaussian")
    dist_angle = recipe.get("wall_angle_distribution", "gaussian")

    def _draw(sigma: float, dist: str) -> float:
        if dist == "uniform":
            return float(rng.uniform(-sigma * np.sqrt(3.0), sigma * np.sqrt(3.0)))
        return float(rng.normal(0.0, sigma))

    if overrides and "depth_sigma_mm" in overrides:
        recipe["depth"] = recipe.get("depth", 0.0) + float(overrides["depth_sigma_mm"])
    else:
        depth_sigma = float(recipe.get("depth_sigma_mm", 0.0))
        if depth_sigma > 0:
            recipe["depth"] = recipe.get("depth", 0.0) + _draw(depth_sigma, dist_depth)

    for key_sigma, key_val in (
        ("wall_angle_x_sigma_deg", "wall_angle_x_deg"),
        ("wall_angle_y_sigma_deg", "wall_angle_y_deg"),
    ):
        if overrides and key_sigma in overrides:
            recipe[key_val] = recipe.get(key_val, 0.0) + float(overrides[key_sigma])
        else:
            sigma = float(recipe.get(key_sigma, 0.0))
            if sigma > 0:
                recipe[key_val] = recipe.get(key_val, 0.0) + _draw(sigma, dist_angle)

    build_cavity(
        p,
        width=recipe["width"],
        height=recipe["height"],
        depth=recipe["depth"],
        wall_angle_x_deg=recipe.get("wall_angle_x_deg", 0.0),
        wall_angle_y_deg=recipe.get("wall_angle_y_deg", 0.0),
        floor_material=recipe.get("floor_material", "default_reflector"),
        wall_material=recipe.get("wall_material", "default_reflector"),
        replace_existing=True,
    )


def _apply_prescribed_offsets(p: Project, offsets: dict[str, float]) -> None:
    """Apply exact offset values to *p* in place."""
    pos_delta = offsets.get("position_sigma_mm")
    if pos_delta is not None:
        d = float(pos_delta) / np.sqrt(3.0)
        for src in p.sources:
            if src.enabled:
                src.position = src.position + np.array([d, d, d], dtype=float)

    cavity_overrides = {
        key: float(value)
        for key, value in offsets.items()
        if key in _CAVITY_SIGMA_KEYS
    }
    if p.cavity_recipe and cavity_overrides:
        _jitter_cavity(
            p,
            np.random.default_rng(0),
            overrides=cavity_overrides,
        )


def _project_with_prescribed_offsets(
    project: Project,
    offsets: dict[str, float],
) -> Project:
    """Return a deep copy of *project* with deterministic offsets applied."""
    p = copy.deepcopy(project)
    _apply_prescribed_offsets(p, offsets)
    return p


def _unit_to_normal_offset(u: float, sigma: float) -> float:
    """Map a unit-hypercube draw onto a zero-mean normal offset with stddev ``sigma``."""
    if sigma <= 0:
        return 0.0
    clipped = min(max(float(u), 1e-6), 1.0 - 1e-6)
    return float(_STANDARD_NORMAL.inv_cdf(clipped) * sigma)


def _saltelli_base_matrices(
    k: int,
    n_samples: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return Saltelli base matrices ``A`` and ``B`` in ``[0, 1]``.

    Uses SciPy's Sobol generator when available; otherwise falls back to a
    reproducible pseudorandom design so the feature still works in lighter
    environments.
    """
    try:
        from scipy.stats import qmc
    except ImportError:
        rng = np.random.default_rng(seed & 0x7FFFFFFF)
        raw = rng.random((n_samples, 2 * k))
    else:
        sampler = qmc.Sobol(d=2 * k, scramble=True, seed=seed & 0x7FFFFFFF)
        m = int(np.log2(n_samples))
        raw = sampler.random_base2(m)
    return raw[:, :k], raw[:, k:]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_jitter(
    project: Project,
    rng: np.random.Generator,
    param_overrides: dict | None = None,
) -> Project:
    """Return a deep copy of *project* with tolerance jitters applied.

    ``param_overrides`` can pin selected parameters to exact offsets while all
    other active tolerances still draw from their configured distributions.
    """
    p = copy.deepcopy(project)
    sigma_default = p.settings.source_position_sigma_mm
    dist = p.settings.source_position_distribution
    position_override = None
    if param_overrides and "position_sigma_mm" in param_overrides:
        position_override = float(param_overrides["position_sigma_mm"])

    for src in p.sources:
        if not src.enabled:
            continue
        if position_override is not None:
            d = position_override / np.sqrt(3.0)
            src.position = src.position + np.array([d, d, d], dtype=float)
            continue

        sigma = src.position_sigma_mm if src.position_sigma_mm > 0 else sigma_default
        if sigma <= 0:
            continue
        if dist == "uniform":
            dx, dy, dz = rng.uniform(-sigma * np.sqrt(3.0), sigma * np.sqrt(3.0), 3)
        else:
            dx, dy, dz = rng.normal(0.0, sigma, 3)
        src.position = src.position + np.array([dx, dy, dz], dtype=float)

    for src in p.sources:
        if src.enabled and src.flux_tolerance > 0:
            jitter = rng.uniform(-src.flux_tolerance / 100.0, src.flux_tolerance / 100.0)
            src.flux = src.flux * (1.0 + jitter)

    if p.cavity_recipe:
        cavity_overrides = None
        if param_overrides:
            cavity_overrides = {
                key: float(value)
                for key, value in param_overrides.items()
                if key in _CAVITY_SIGMA_KEYS
            }
        _jitter_cavity(p, rng, overrides=cavity_overrides or None)

    return p


def build_oat_sample(project: Project, seed: int) -> list[tuple[Project, str]]:
    """Return deterministic one-at-a-time samples.

    Index 0 is the unperturbed baseline. Indices 1..k apply exact ``+1 sigma``
    offsets for each active tolerance parameter.
    """
    _ = seed & 0x7FFFFFFF  # retained for API stability; OAT perturbations are deterministic
    results: list[tuple[Project, str]] = [(copy.deepcopy(project), "baseline")]
    for param_name, sigma in _active_tolerance_params(project):
        perturbed = _project_with_prescribed_offsets(project, {param_name: float(sigma)})
        results.append((perturbed, param_name))
    return results


def compute_oat_sensitivity(
    baseline_kpis: dict[str, float],
    perturbed_kpis: list[dict[str, float]],
    param_names: list[str],
    param_sigmas: list[float],
) -> dict[str, list[float]]:
    """Return ``{kpi_name: [normalized_sensitivity_per_param]}``."""
    _ = param_names
    results: dict[str, list[float]] = {}
    for kpi_key, base_val in baseline_kpis.items():
        sens = []
        for pert_kpis, sigma in zip(perturbed_kpis, param_sigmas):
            delta = abs(pert_kpis.get(kpi_key, base_val) - base_val)
            sens.append(delta / sigma if sigma > 0 else 0.0)
        results[kpi_key] = sens
    return results


def build_sobol_sample(
    project: Project,
    N: int,
    seed: int,
) -> list[tuple[Project, np.ndarray]]:
    """Generate a Saltelli A/B/AB_i design for Sobol first-order indices."""
    k = _count_active_tolerance_params(project)
    if k == 0:
        return []

    n_pow2 = int(2 ** np.ceil(np.log2(max(N, 32))))
    params = _active_tolerance_params(project)
    A, B = _saltelli_base_matrices(k, n_pow2, seed)
    matrices = [A, B]
    for i in range(k):
        AB_i = A.copy()
        AB_i[:, i] = B[:, i]
        matrices.append(AB_i)

    results: list[tuple[Project, np.ndarray]] = []
    for matrix in matrices:
        for u in matrix:
            offsets = {
                param_name: _unit_to_normal_offset(u[j], sigma)
                for j, (param_name, sigma) in enumerate(params)
            }
            p = _project_with_prescribed_offsets(project, offsets)
            results.append((p, np.asarray(u, dtype=float).copy()))
    return results


def compute_sobol_sensitivity(
    kpi_matrix: np.ndarray,
    param_matrix: np.ndarray,
    N: int,
    k: int,
) -> dict[str, np.ndarray]:
    """Estimate first-order Sobol indices from a Saltelli design."""
    _ = param_matrix
    n_kpis = kpi_matrix.shape[1] if kpi_matrix.ndim == 2 else 1
    if kpi_matrix.ndim == 1:
        kpi_matrix = kpi_matrix[:, np.newaxis]

    required_rows = N * (k + 2)
    if N <= 0 or k < 0 or kpi_matrix.shape[0] < required_rows:
        return {str(idx): np.zeros(k, dtype=float) for idx in range(n_kpis)}
    kpi_matrix = kpi_matrix[:required_rows]

    f_A = kpi_matrix[:N]
    f_B = kpi_matrix[N: 2 * N]

    results: dict[str, np.ndarray] = {}
    for kpi_col in range(n_kpis):
        fa = f_A[:, kpi_col]
        fb = f_B[:, kpi_col]
        var_y = float(np.var(np.concatenate([fa, fb])))
        si_vals = np.zeros(k, dtype=float)
        if var_y > 0:
            for i in range(k):
                f_ABi = kpi_matrix[(2 + i) * N: (3 + i) * N, kpi_col]
                si_vals[i] = float(np.mean(fb * (f_ABi - fa)) / var_y)
        results[str(kpi_col)] = np.clip(si_vals, 0.0, 1.0)
    return results


def build_mc_sample(
    base_project: Project,
    N: int,
    seed: int,
) -> list[Project]:
    """Generate ``N`` i.i.d. random jittered project clones for distribution mode."""
    N = min(max(1, N), 500)
    base_rng = np.random.default_rng(seed & 0x7FFFFFFF)
    child_rngs = base_rng.spawn(N)
    members: list[Project] = []
    for rng in child_rngs:
        members.append(apply_jitter(base_project, rng))
    return members
