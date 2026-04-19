"""Ensemble tolerance Monte Carlo service.

Headless (no PySide6 / GUI imports). Consumed by gui/ensemble_dialog.py and tests.
All public functions are implemented in Wave 1; stubs raise NotImplementedError here
so the TDD test suite can be written and collected before implementation.
"""

from __future__ import annotations

import copy
from typing import Iterator

import numpy as np

from backlight_sim.core.project_model import Project


# ---------------------------------------------------------------------------
# Public API (stubs — Wave 0; implemented in Wave 1)
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
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")


def _jitter_cavity(p: Project, rng: np.random.Generator, overrides: dict | None = None) -> None:
    """Mutate *p* in-place: re-invoke build_cavity() with jittered recipe args.

    Called by apply_jitter() when p.cavity_recipe is non-empty.
    Not intended to be called directly from outside the module.
    """
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")


def _count_active_tolerance_params(project: Project) -> int:
    """Return the number of tolerance parameters with sigma > 0 in *project*."""
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")


def _active_tolerance_params(project: Project) -> list[tuple[str, float]]:
    """Return [(param_name, sigma)] for all active (sigma > 0) tolerance parameters."""
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")


def build_oat_sample(project: Project, seed: int) -> list[tuple[Project, str]]:
    """Return [(project_clone, param_label)] for one-at-a-time sensitivity.

    Index 0 = baseline (no jitter, label "baseline").
    Indices 1..k = each active tolerance perturbed by +1σ.
    Total = k+1 runs.

    Seed is masked to signed int32 range (``seed & 0x7FFFFFFF``) per Phase 4 pattern.
    """
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")


def compute_oat_sensitivity(
    baseline_kpis: dict[str, float],
    perturbed_kpis: list[dict[str, float]],
    param_names: list[str],
    param_sigmas: list[float],
) -> dict[str, list[float]]:
    """Return {kpi_name: [normalized_sensitivity_per_param]}.

    Sensitivity index = |ΔKPI| / sigma_param. Zero for params with sigma == 0.
    """
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")


def build_sobol_sample(
    project: Project,
    N: int,
    seed: int,
) -> list[tuple[Project, np.ndarray]]:
    """Generate N Saltelli A/B matrix realizations for Sobol Si estimation.

    N is rounded up to the next power of 2; minimum 32 is enforced.
    Requires scipy.stats.qmc (scipy >= 1.7, verified 1.17.1 in this env).

    Returns:
        List of (jittered_project_clone, param_vector) where param_vector is
        the [0,1]^k uniform draw from the Sobol sequence (before mapping to σ).
    """
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")


def compute_sobol_sensitivity(
    kpi_matrix: np.ndarray,
    param_matrix: np.ndarray,
    N: int,
    k: int,
) -> dict[str, np.ndarray]:
    """Estimate Sobol first-order sensitivity indices via Saltelli (2002) pick-freeze.

    Args:
        kpi_matrix: (N*(k+2), n_kpis) array of KPI values from Saltelli design.
        param_matrix: (N*(k+2), k) parameter sample matrix.
        N: Number of Sobol base samples (power of 2).
        k: Number of active tolerance parameters.

    Returns:
        {kpi_name: Si_array_shape_(k,)} — first-order indices clamped to [0, 1].
    """
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")

def build_mc_sample(
    base_project: "Project",
    N: int,
    seed: int,
) -> "list[Project]":
    """Generate N i.i.d. random jittered project clones for distribution ensemble.

    Each member is an independent draw: apply_jitter(base_project, rng_i) where rng_i
    uses a per-member seed derived from the base seed. This is the primary mode for
    producing the P5/P50/P95 KPI distribution histogram.

    Args:
        base_project: Base project with tolerance sigma fields set (not mutated).
        N: Number of members. Clamped to [1, 500].
        seed: Base seed (masked to int32 range internally).

    Returns:
        List of N deep-copied, jittered Project instances.
    """
    raise NotImplementedError("Implemented in Wave 1 (05-02-PLAN.md)")
