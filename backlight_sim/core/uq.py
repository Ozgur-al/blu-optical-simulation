"""Batch-means uncertainty quantification utilities (Phase 4, Wave 1).

Pure-numpy module providing frequentist batch-means confidence-interval helpers
used by:
  * the tracer (Wave 2) to populate per-batch detector grids,
  * the UI / HTML report (Wave 3) to render "value ± half_width" strings,
  * the Phase 6 optimizer to evaluate KPI CIs without importing ``backlight_sim.gui``.

The module contains:
  * A hard-coded Student-t critical-value table for two-sided CIs at
    ``conf_level ∈ {0.90, 0.95, 0.99}`` and ``dof ∈ {3..19}``.  Values were
    sourced from ``scipy.stats.t.ppf(1 - (1 - conf) / 2, dof)`` and rounded to
    4 decimal places.  The table keeps scipy out of the runtime dependency
    footprint (see CONTEXT D-04 / research.md "Don't Hand-Roll").
  * :class:`CIEstimate` — an immutable dataclass carrying ``mean``,
    ``half_width``, sample ``std``, ``n_batches`` and ``conf_level``.
  * :func:`batch_mean_ci` — the core CI formula ``mean ± t * s / sqrt(K)``.
  * :func:`per_bin_stderr` — ``(ny, nx)`` per-bin stderr from ``(K, ny, nx)``
    batch grids.
  * :func:`kpi_batches` — applies a scalar-valued KPI function across K
    per-batch grids.

LAYERING RULE: this module MUST NOT import PySide6, pyqtgraph, or any
``backlight_sim.gui.*`` module (enforced by a subprocess test in
``tests/test_uq.py``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np


# ---------------------------------------------------------------------------
# Student-t critical-value table
# ---------------------------------------------------------------------------

# t_{dof, 1 - alpha/2} for two-sided CI where alpha = 1 - conf_level.
# Keys: (conf_level, dof); dof = K - 1. Values rounded to 4 decimal places.
# Sourced from scipy.stats.t.ppf(1 - (1 - conf) / 2, dof).
_T_TABLE: dict[tuple[float, int], float] = {
    (0.90, 3):  2.3534, (0.95, 3):  3.1824, (0.99, 3):  5.8409,
    (0.90, 4):  2.1318, (0.95, 4):  2.7764, (0.99, 4):  4.6041,
    (0.90, 5):  2.0150, (0.95, 5):  2.5706, (0.99, 5):  4.0321,
    (0.90, 6):  1.9432, (0.95, 6):  2.4469, (0.99, 6):  3.7074,
    (0.90, 7):  1.8946, (0.95, 7):  2.3646, (0.99, 7):  3.4995,
    (0.90, 8):  1.8595, (0.95, 8):  2.3060, (0.99, 8):  3.3554,
    (0.90, 9):  1.8331, (0.95, 9):  2.2622, (0.99, 9):  3.2498,
    (0.90, 10): 1.8125, (0.95, 10): 2.2281, (0.99, 10): 3.1693,
    (0.90, 11): 1.7959, (0.95, 11): 2.2010, (0.99, 11): 3.1058,
    (0.90, 12): 1.7823, (0.95, 12): 2.1788, (0.99, 12): 3.0545,
    (0.90, 13): 1.7709, (0.95, 13): 2.1604, (0.99, 13): 3.0123,
    (0.90, 14): 1.7613, (0.95, 14): 2.1448, (0.99, 14): 2.9768,
    (0.90, 15): 1.7531, (0.95, 15): 2.1314, (0.99, 15): 2.9467,
    (0.90, 16): 1.7459, (0.95, 16): 2.1199, (0.99, 16): 2.9208,
    (0.90, 17): 1.7396, (0.95, 17): 2.1098, (0.99, 17): 2.8982,
    (0.90, 18): 1.7341, (0.95, 18): 2.1009, (0.99, 18): 2.8784,
    (0.90, 19): 1.7291, (0.95, 19): 2.0930, (0.99, 19): 2.8609,
}

_SUPPORTED_CONF: tuple[float, ...] = (0.90, 0.95, 0.99)
_MIN_BATCHES: int = 4   # dof floor of 3; K<4 rejected (CIs become uninformative)
_MAX_DOF: int = 19      # beyond dof=19, clamp to the tail value (tight asymptote)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def student_t_critical(conf_level: float, n_batches: int) -> float:
    """Return ``t_{n_batches - 1, 1 - alpha/2}`` for a two-sided CI.

    Raises
    ------
    ValueError
        If ``conf_level`` is not in ``{0.90, 0.95, 0.99}`` or
        ``n_batches < 4``.

    Notes
    -----
    Degrees of freedom (``n_batches - 1``) are clamped to 19; for larger K the
    Student-t distribution is already very close to the normal, and the
    table asymptote at dof=19 is a conservative (slightly wider) CI.
    """
    if conf_level not in _SUPPORTED_CONF:
        raise ValueError(
            f"conf_level must be one of {_SUPPORTED_CONF}, got {conf_level}"
        )
    if n_batches < _MIN_BATCHES:
        raise ValueError(
            f"n_batches must be >= {_MIN_BATCHES}, got {n_batches}"
        )
    dof = min(n_batches - 1, _MAX_DOF)
    return _T_TABLE[(conf_level, dof)]


# ---------------------------------------------------------------------------
# CIEstimate dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CIEstimate:
    """Immutable carrier of a batch-means CI result.

    Attributes
    ----------
    mean:
        Sample mean of the per-batch KPI values.
    half_width:
        ``t * s / sqrt(K)`` — distance from ``mean`` to either CI endpoint.
    std:
        Sample standard deviation (``ddof=1``) of the per-batch values.
    n_batches:
        ``K``; ``0`` signals "no UQ data" (legacy / UQ-off).
    conf_level:
        CI confidence level used to pick the Student-t critical value.
    """

    mean: float
    half_width: float
    std: float
    n_batches: int
    conf_level: float

    # .......................................................................
    # Derived accessors
    # .......................................................................

    @property
    def lower(self) -> float:
        return self.mean - self.half_width

    @property
    def upper(self) -> float:
        return self.mean + self.half_width

    # .......................................................................
    # Formatting
    # .......................................................................

    def format(self, precision: int = 3, unit: str = "") -> str:
        """Render ``"mean ± half_width unit"`` aligned to 2 sig figs of the CI.

        When ``n_batches == 0`` or ``half_width`` is non-finite / non-positive
        the ``±`` token is omitted and the legacy display (plain ``mean``) is
        used — matches pre-Phase-4 behavior on legacy results.
        """
        if self.n_batches == 0 or not np.isfinite(self.half_width):
            return f"{self.mean:.{precision}g}{unit}"
        if self.half_width <= 0:
            return f"{self.mean:.{precision}g}{unit}"

        # Align mean to the same decimal position as 2 sig figs of half_width.
        # Example: half_width=1.23 → decimals=1 → "87.3 ± 1.2".
        decimals = max(0, 1 - int(math.floor(math.log10(abs(self.half_width)))))
        return f"{self.mean:.{decimals}f} ± {self.half_width:.{decimals}f}{unit}"


# ---------------------------------------------------------------------------
# Core CI computation
# ---------------------------------------------------------------------------

def batch_mean_ci(
    values: np.ndarray | list[float],
    conf_level: float = 0.95,
) -> CIEstimate:
    """Compute the mean and a symmetric CI from ``K`` per-batch KPI values.

    Parameters
    ----------
    values:
        ``K`` scalar KPI values, one per batch (K >= 4).  Accepts list or
        numpy array; flattened to 1D internally.
    conf_level:
        One of ``0.90``, ``0.95``, ``0.99``.

    Returns
    -------
    :class:`CIEstimate`
        With ``mean = values.mean()``, ``std = values.std(ddof=1)``,
        ``half_width = t * std / sqrt(K)``.

    Raises
    ------
    ValueError
        If ``len(values) < 4`` or ``conf_level`` is unsupported.
    """
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size < _MIN_BATCHES:
        raise ValueError(
            f"batch_mean_ci requires >= {_MIN_BATCHES} values, got {arr.size}"
        )
    mean = float(arr.mean())
    std = float(arr.std(ddof=1))
    stderr = std / math.sqrt(arr.size)
    t = student_t_critical(conf_level, arr.size)
    return CIEstimate(
        mean=mean,
        half_width=float(t * stderr),
        std=std,
        n_batches=int(arr.size),
        conf_level=float(conf_level),
    )


# ---------------------------------------------------------------------------
# Per-bin stderr
# ---------------------------------------------------------------------------

def per_bin_stderr(grid_batches: np.ndarray) -> np.ndarray:
    """Return the ``(ny, nx)`` per-bin stderr ``std(axis=0, ddof=1) / sqrt(K)``.

    Parameters
    ----------
    grid_batches:
        Array of shape ``(K, ny, nx)`` containing K per-batch detector grids.

    Returns
    -------
    np.ndarray
        ``(ny, nx)`` float array; all zeros when ``K < 2`` (CI undefined).

    Raises
    ------
    ValueError
        If ``grid_batches.ndim != 3``.
    """
    arr = np.asarray(grid_batches, dtype=float)
    if arr.ndim != 3:
        raise ValueError(
            f"grid_batches must be (K, ny, nx), got shape {arr.shape}"
        )
    K = arr.shape[0]
    if K < 2:
        return np.zeros(arr.shape[1:], dtype=float)
    return arr.std(axis=0, ddof=1) / math.sqrt(K)


# ---------------------------------------------------------------------------
# Functional KPI batch evaluator
# ---------------------------------------------------------------------------

def kpi_batches(
    grid_batches: np.ndarray,
    kpi_fn: Callable[[np.ndarray], float],
) -> np.ndarray:
    """Apply ``kpi_fn`` to each of K per-batch grids and return ``(K,)`` array.

    Parameters
    ----------
    grid_batches:
        Array of shape ``(K, ...)`` — K batched grids (any trailing shape).
    kpi_fn:
        Callable taking one grid slice and returning a scalar KPI value.

    Returns
    -------
    np.ndarray
        1D float array of length ``K`` with per-batch KPI values; suitable
        for :func:`batch_mean_ci`.

    Raises
    ------
    ValueError
        If ``grid_batches`` has fewer than 2 dimensions.
    """
    arr = np.asarray(grid_batches)
    if arr.ndim < 2:
        raise ValueError(
            f"grid_batches must have at least 2 dims, got shape {arr.shape}"
        )
    return np.asarray(
        [float(kpi_fn(arr[k])) for k in range(arr.shape[0])],
        dtype=float,
    )


__all__ = [
    "CIEstimate",
    "batch_mean_ci",
    "kpi_batches",
    "per_bin_stderr",
    "student_t_critical",
]
