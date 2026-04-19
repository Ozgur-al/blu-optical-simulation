"""Ensemble tolerance Monte Carlo service.

Headless (no PySide6 / GUI imports). Consumed by gui/ensemble_dialog.py and tests.
"""

from __future__ import annotations

import copy

import numpy as np

from backlight_sim.core.project_model import Project
from backlight_sim.io.geometry_builder import build_cavity


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _count_active_tolerance_params(project: Project) -> int:
    """Return the number of tolerance parameters with sigma > 0 in *project*."""
    n = 0
    # LED position group (project-level default OR any per-source override)
    has_pos = (
        project.settings.source_position_sigma_mm > 0
        or any(s.position_sigma_mm > 0 for s in project.sources if s.enabled)
    )
    if has_pos:
        n += 1
    # Cavity tolerances
    recipe = project.cavity_recipe
    if recipe.get("depth_sigma_mm", 0.0) > 0:
        n += 1
    if recipe.get("wall_angle_x_sigma_deg", 0.0) > 0:
        n += 1
    if recipe.get("wall_angle_y_sigma_deg", 0.0) > 0:
        n += 1
    return n


def _active_tolerance_params(project: Project) -> list[tuple[str, float]]:
    """Return [(param_name, sigma)] for all active (sigma > 0) tolerance parameters."""
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
    for key, label in [
        ("depth_sigma_mm", "depth_sigma_mm"),
        ("wall_angle_x_sigma_deg", "wall_angle_x_sigma_deg"),
        ("wall_angle_y_sigma_deg", "wall_angle_y_sigma_deg"),
    ]:
        v = recipe.get(key, 0.0)
        if v > 0:
            params.append((label, float(v)))
    return params


def _zero_all_sigmas(p: Project) -> None:
    """Zero all tolerance sigma fields on p (for OAT single-parameter isolation)."""
    p.settings.source_position_sigma_mm = 0.0
    for src in p.sources:
        src.position_sigma_mm = 0.0
    recipe = p.cavity_recipe
    for key in ("depth_sigma_mm", "wall_angle_x_sigma_deg", "wall_angle_y_sigma_deg"):
        if key in recipe:
            recipe[key] = 0.0


def _jitter_cavity(p: Project, rng: np.random.Generator, overrides: dict | None = None) -> None:
    """Mutate *p* in-place: re-invoke build_cavity() with jittered recipe args.

    Called by apply_jitter() when p.cavity_recipe is non-empty.
    """
    recipe = dict(p.cavity_recipe)  # shallow copy; scalars only
    dist_depth = recipe.get("depth_distribution", "gaussian")
    dist_angle = recipe.get("wall_angle_distribution", "gaussian")

    def _draw(sigma: float, dist: str) -> float:
        if dist == "uniform":
            return float(rng.uniform(-sigma * np.sqrt(3), sigma * np.sqrt(3)))
        return float(rng.normal(0.0, sigma))

    if overrides and "depth_sigma_mm" in overrides:
        recipe["depth"] = recipe.get("depth", 0.0) + overrides["depth_sigma_mm"]
    else:
        depth_sigma = recipe.get("depth_sigma_mm", 0.0)
        if depth_sigma > 0:
            recipe["depth"] = recipe.get("depth", 0.0) + _draw(depth_sigma, dist_depth)

    for axis, key_sigma, key_val in [
        ("x", "wall_angle_x_sigma_deg", "wall_angle_x_deg"),
        ("y", "wall_angle_y_sigma_deg", "wall_angle_y_deg"),
    ]:
        if overrides and key_sigma in overrides:
            recipe[key_val] = recipe.get(key_val, 0.0) + overrides[key_sigma]
        else:
            sigma = recipe.get(key_sigma, 0.0)
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
    """Apply exact offset values to p (mutates in-place; caller already holds a deep-copy)."""
    pos_delta = offsets.get("position_sigma_mm", None)
    if pos_delta is not None:
        for src in p.sources:
            if src.enabled:
                # Equal axis distribution: sigma_axis = sigma_3d / sqrt(3) ensures the 3D RMS
                # displacement equals sigma_3d (var(dx)+var(dy)+var(dz) = sigma_3d^2).
                d = pos_delta / np.sqrt(3)
                src.position = src.position + np.array([d, d, d])
    if p.cavity_recipe:
        recipe = p.cavity_recipe
        if "depth_sigma_mm" in offsets:
            recipe["depth"] = recipe.get("depth", 0.0) + offsets["depth_sigma_mm"]
        if "wall_angle_x_sigma_deg" in offsets:
            recipe["wall_angle_x_deg"] = recipe.get("wall_angle_x_deg", 0.0) + offsets["wall_angle_x_sigma_deg"]
        if "wall_angle_y_sigma_deg" in offsets:
            recipe["wall_angle_y_deg"] = recipe.get("wall_angle_y_deg", 0.0) + offsets["wall_angle_y_sigma_deg"]
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_jitter(
    project: Project,
    rng: np.random.Generator,
    param_overrides: dict | None = None,
) -> Project:
    """Return a deep-copy of *project* with all tolerance jitters applied.

    Position jitter is written to ``src.position`` in-place on the deep-copy
    so that ``_serialize_project()`` picks up jittered coordinates
    (pre-serialization pattern; mirrors flux_tolerance in tracer.py).

    Args:
        project: Base project (not mutated).
        rng: Seeded RNG — caller controls seed for reproducibility.
        param_overrides: Optional {param_name: value} dict used by OAT to fix
            individual parameters to +1σ offsets. None = draw all from distributions.

    Returns:
        Deep-copied project with jittered source positions and/or cavity geometry.
    """
    p = copy.deepcopy(project)
    sigma_default = p.settings.source_position_sigma_mm
    dist = p.settings.source_position_distribution

    for src in p.sources:
        if not src.enabled:
            continue
        sigma = src.position_sigma_mm if src.position_sigma_mm > 0 else sigma_default
        # param_overrides can override sigma for OAT single-param perturbation
        if param_overrides and "position_sigma_mm" in param_overrides:
            sigma = float(param_overrides["position_sigma_mm"])
        if sigma > 0:
            if dist == "uniform":
                dx, dy, dz = rng.uniform(-sigma * np.sqrt(3), sigma * np.sqrt(3), 3)
            else:  # gaussian (default)
                dx, dy, dz = rng.normal(0.0, sigma, 3)
            src.position = src.position + np.array([dx, dy, dz])

    # D-01b: re-draw flux_tolerance per member (explicit in clone)
    for src in p.sources:
        if src.enabled and src.flux_tolerance > 0:
            jitter = rng.uniform(-src.flux_tolerance / 100.0, src.flux_tolerance / 100.0)
            src.flux = src.flux * (1.0 + jitter)

    if p.cavity_recipe:
        _jitter_cavity(p, rng, overrides=param_overrides)

    return p


def build_oat_sample(project: Project, seed: int) -> list[tuple[Project, str]]:
    """Return [(project_clone, param_label)] for one-at-a-time sensitivity.

    Index 0 = baseline (no jitter, label "baseline").
    Indices 1..k = each active tolerance perturbed by +1σ.
    Total = k+1 runs.

    Seed is masked to signed int32 range (``seed & 0x7FFFFFFF``) per Phase 4 pattern.
    """
    rng = np.random.default_rng(seed & 0x7FFFFFFF)
    results: list[tuple[Project, str]] = [(copy.deepcopy(project), "baseline")]
    for param_name, sigma in _active_tolerance_params(project):
        # Temporarily zero all sigmas; set only the target param to +1sigma
        p_temp = copy.deepcopy(project)
        _zero_all_sigmas(p_temp)
        # Set just the one param we're perturbing
        if param_name == "position_sigma_mm":
            p_temp.settings.source_position_sigma_mm = sigma
        elif param_name in ("depth_sigma_mm", "wall_angle_x_sigma_deg", "wall_angle_y_sigma_deg"):
            p_temp.cavity_recipe[param_name] = sigma
        perturbed = apply_jitter(p_temp, rng)
        results.append((perturbed, param_name))
    return results


def compute_oat_sensitivity(
    baseline_kpis: dict[str, float],
    perturbed_kpis: list[dict[str, float]],
    param_names: list[str],
    param_sigmas: list[float],
) -> dict[str, list[float]]:
    """Return {kpi_name: [normalized_sensitivity_per_param]}.

    Sensitivity index = |ΔKPI| / sigma_param. Zero for params with sigma == 0.
    """
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
    """Generate N Saltelli A/B matrix realizations for Sobol Si estimation.

    N is rounded up to the next power of 2; minimum 32 is enforced.
    Requires scipy.stats.qmc (scipy >= 1.7, verified 1.17.1 in this env).

    Seed is masked to signed int32 range (``seed & 0x7FFFFFFF``) per Phase 4 pattern.

    Returns:
        List of (jittered_project_clone, param_vector) where param_vector is
        the [0,1]^k uniform draw from the Sobol sequence (before mapping to σ).
    """
    from scipy.stats import qmc  # scipy >= 1.7 required; verified 1.17.1 in env
    k = _count_active_tolerance_params(project)
    if k == 0:
        return []
    # Enforce minimum 32, round up to next power of 2
    N_pow2 = int(2 ** np.ceil(np.log2(max(N, 32))))
    params = _active_tolerance_params(project)
    sampler = qmc.Sobol(d=k, scramble=True, seed=seed & 0x7FFFFFFF)
    raw = sampler.random(N_pow2)  # (N_pow2, k) in [0, 1]
    results: list[tuple[Project, np.ndarray]] = []
    for i in range(N_pow2):
        u = raw[i]  # (k,) in [0, 1]
        p = copy.deepcopy(project)
        offsets: dict[str, float] = {}
        for j, (param_name, sigma) in enumerate(params):
            from scipy.stats import norm
            delta = float(norm.ppf(np.clip(u[j], 1e-6, 1 - 1e-6)) * sigma)
            offsets[param_name] = delta
        _apply_prescribed_offsets(p, offsets)
        results.append((p, u))
    return results


def compute_sobol_sensitivity(
    kpi_matrix: np.ndarray,
    param_matrix: np.ndarray,
    N: int,
    k: int,
) -> dict[str, np.ndarray]:
    """Estimate Sobol first-order sensitivity indices via Saltelli (2002) pick-freeze.

    Expects kpi_matrix shaped (N*(k+2), n_kpis) from the Saltelli design produced
    by build_sobol_sample. The design order is: N rows from matrix A, then N rows
    from matrix B, then k * N rows from AB_i matrices (one per param).

    First-order Si = (1/N) * sum_j(f_B_j * (f_ABi_j - f_A_j)) / Var(f)
    Indices are clamped to [0, 1] to remove negative artefacts at small N.

    Args:
        kpi_matrix: (N*(k+2), n_kpis) float array.
        param_matrix: (N*(k+2), k) parameter sample matrix (unused; for future extension).
        N: Number of Sobol base samples (power of 2).
        k: Number of active tolerance parameters.

    Returns:
        {kpi_name_index: Si_array_shape_(k,)} keyed by column index as string,
        with first-order indices clamped to [0, 1].
    """
    n_kpis = kpi_matrix.shape[1] if kpi_matrix.ndim == 2 else 1
    if kpi_matrix.ndim == 1:
        kpi_matrix = kpi_matrix[:, np.newaxis]

    # Saltelli (2002) layout: rows 0..N-1 = f_A, N..2N-1 = f_B,
    # 2N..2N+N-1 = f_AB0, 2N+N..2N+2N-1 = f_AB1, ...
    f_A = kpi_matrix[:N]           # (N, n_kpis)
    f_B = kpi_matrix[N: 2 * N]    # (N, n_kpis)

    results = {}
    for kpi_col in range(n_kpis):
        fa = f_A[:, kpi_col]   # (N,)
        fb = f_B[:, kpi_col]   # (N,)
        var_y = float(np.var(np.concatenate([fa, fb])))
        si_vals = np.zeros(k, dtype=float)
        if var_y > 0:
            for i in range(k):
                f_ABi = kpi_matrix[(2 + i) * N: (3 + i) * N, kpi_col]  # (N,)
                # Saltelli (2002) eq. 4
                si_vals[i] = float(np.mean(fb * (f_ABi - fa)) / var_y)
        # Clamp to [0, 1] — negative values are statistical artefacts at small N
        results[str(kpi_col)] = np.clip(si_vals, 0.0, 1.0)
    return results


def build_mc_sample(
    base_project: Project,
    N: int,
    seed: int,
) -> list[Project]:
    """Generate N i.i.d. random jittered project clones for distribution ensemble.

    Each of the N members draws all tolerance parameters independently from their
    distributions using a per-member RNG derived from the base seed. This is the
    primary mode for producing the P5/P50/P95 KPI distribution histogram.

    Flux_tolerance is re-drawn per member (D-01b): handled inside apply_jitter().

    Args:
        base_project: Base project with tolerance sigma fields set (not mutated).
        N: Number of members. Clamped to [1, 500].
        seed: Base seed (int32-masked internally).

    Returns:
        List of N deep-copied, jittered Project instances.
    """
    N = min(max(1, N), 500)  # clamp [1, 500]
    base_seed = seed & 0x7FFFFFFF
    members: list[Project] = []
    for i in range(N):
        member_seed = (base_seed + i * 6364136223846793005) & 0x7FFFFFFF
        rng = np.random.default_rng(member_seed)
        member = apply_jitter(base_project, rng)
        members.append(member)
    return members
