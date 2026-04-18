"""Pure-numpy KPI helpers consumed by GUI, report, tracer, and Phase 6 optimizer.

Lifted from ``backlight_sim/gui/heatmap_panel.py``
(``_uniformity_in_center``, ``_corner_ratio``, ``_edge_center_ratio``) and
``backlight_sim/gui/parameter_sweep_dialog.py`` (``_kpis``) to satisfy the
CLAUDE.md layering rule: ``core/`` must never import PySide6 / pyqtgraph /
``backlight_sim.gui``.

Bodies are copied verbatim from the pre-lift GUI implementations — parity is
asserted by ``backlight_sim/tests/test_kpi.py`` against locally-replicated
reference copies.

A new :func:`compute_scalar_kpis` aggregator replaces the old
``parameter_sweep_dialog._kpis`` tuple return with a dict so Phase 6 CMA-ES
can select KPI keys by name without tuple-unpack churn.
"""

from __future__ import annotations

import numpy as np

from backlight_sim.core.detectors import DetectorResult, SimulationResult


# ---------------------------------------------------------------------------
# Grid-level helpers (pure numpy)
# ---------------------------------------------------------------------------

def uniformity_in_center(grid: np.ndarray, fraction: float) -> tuple[float, float]:
    """Return ``(min/avg, min/max)`` uniformity in the central *fraction* area.

    The central region is a square covering ``fraction`` of the total grid
    area (side length = ``sqrt(fraction) * grid_size``).  Returns
    ``(0.0, 0.0)`` when the region is empty or all zeros.
    """
    ny, nx = grid.shape
    f_side = float(np.sqrt(fraction))
    cy, cx = ny // 2, nx // 2
    half_y = max(1, int(ny * f_side / 2))
    half_x = max(1, int(nx * f_side / 2))
    roi = grid[cy - half_y: cy + half_y, cx - half_x: cx + half_x]
    if roi.size == 0 or roi.max() == 0:
        return 0.0, 0.0
    avg = float(roi.mean())
    mn = float(roi.min())
    mx = float(roi.max())
    return (mn / avg if avg > 0 else 0.0, mn / mx if mx > 0 else 0.0)


def corner_ratio(grid: np.ndarray, corner_frac: float = 0.1) -> float:
    """Average of the four corner patches divided by the full-grid average.

    Each corner patch is ``corner_frac × grid dimensions`` (clamped to ≥ 1 px).
    Returns ``0.0`` when the grid average is zero.
    """
    ny, nx = grid.shape
    ch = max(1, int(ny * corner_frac))
    cw = max(1, int(nx * corner_frac))
    corners = np.concatenate([
        grid[:ch,   :cw  ].ravel(),
        grid[:ch,  -cw:  ].ravel(),
        grid[-ch:,  :cw  ].ravel(),
        grid[-ch:, -cw:  ].ravel(),
    ])
    full_avg = float(grid.mean())
    corner_avg = float(corners.mean())
    return corner_avg / full_avg if full_avg > 0 else 0.0


def edge_center_ratio(grid: np.ndarray) -> float:
    """Ratio of outer-edge average to center-region average.

    Center = inner 50 % × 50 % region (25 % of total area).
    Edge   = outermost 15 % strip on all four sides.
    Returns ``edge_avg / center_avg``; close to 1.0 is most uniform.  Returns
    ``0.0`` when the center average is zero.
    """
    ny, nx = grid.shape
    cy, cx = ny // 2, nx // 2
    half_y = max(1, int(ny * 0.25))
    half_x = max(1, int(nx * 0.25))
    center = grid[cy - half_y: cy + half_y, cx - half_x: cx + half_x]

    ey = max(1, int(ny * 0.15))
    ex = max(1, int(nx * 0.15))
    edge_mask = np.zeros(grid.shape, dtype=bool)
    edge_mask[:ey, :] = True
    edge_mask[-ey:, :] = True
    edge_mask[:, :ex] = True
    edge_mask[:, -ex:] = True
    edge = grid[edge_mask]

    center_avg = float(center.mean()) if center.size > 0 else 0.0
    edge_avg = float(edge.mean()) if edge.size > 0 else 0.0
    if center_avg == 0:
        return 0.0
    return edge_avg / center_avg


# ---------------------------------------------------------------------------
# Scalar KPI aggregator (replaces gui/parameter_sweep_dialog::_kpis)
# ---------------------------------------------------------------------------

def compute_scalar_kpis(result: SimulationResult) -> dict[str, float]:
    """Return a dict of scalar KPIs used by parameter sweep & Phase 6 optimizer.

    Keys
    ----
    ``efficiency_pct``:
        ``sum(detector_flux) / total_emitted_flux * 100``.  ``0.0`` when
        ``total_emitted_flux <= 0``.
    ``uniformity_1_4_min_avg``:
        First element of :func:`uniformity_in_center` at ``fraction=0.25``
        on the first detector's grid.
    ``hotspot_peak_avg``:
        ``grid.max() / grid.mean()`` on the first detector's grid.
        ``0.0`` when ``grid.mean() <= 0``.

    Returns a zero-filled dict (all 3 keys set to ``0.0``) when ``result`` has
    no detectors — matches legacy ``_kpis`` behavior for back-compat.
    """
    keys = ("efficiency_pct", "uniformity_1_4_min_avg", "hotspot_peak_avg")
    if not result.detectors:
        return {k: 0.0 for k in keys}

    grid = next(iter(result.detectors.values())).grid
    avg = float(grid.mean())

    if result.total_emitted_flux > 0:
        det_total = sum(dr.total_flux for dr in result.detectors.values())
        eff = det_total / result.total_emitted_flux * 100.0
    else:
        eff = 0.0

    u14, _ = uniformity_in_center(grid, 0.25)
    hot = float(grid.max()) / avg if avg > 0 else 0.0

    return {
        "efficiency_pct": eff,
        "uniformity_1_4_min_avg": u14,
        "hotspot_peak_avg": hot,
    }


# ---------------------------------------------------------------------------
# Per-batch source flux (unbiased scaling for rays_per_batch remainder)
# ---------------------------------------------------------------------------


def _per_batch_source_flux(
    result: SimulationResult,
    det: DetectorResult,
) -> np.ndarray | None:
    """Return ``(n_batches,)`` per-batch source flux using rays_per_batch.

    Formula: ``source_flux_per_batch[k] = total_emitted_flux * rays_per_batch[k] / sum(rays_per_batch)``.

    This is UNBIASED even when ``rays_per_source % K != 0`` — Wave 2 distributes
    the remainder by giving the first ``R`` batches an extra ray each, so actual
    per-batch source flux differs by ±1 ray worth.  The naive ``total/K``
    formula biases the per-batch efficiency values, inflating the CI
    half-width estimate.  See threat T-04.03-05 in plan 04-03.

    Returns ``None`` when ``rays_per_batch`` is ``None`` or
    ``total_emitted_flux <= 0`` — caller falls back to legacy aggregate
    efficiency.
    """
    if det.rays_per_batch is None or result.total_emitted_flux <= 0:
        return None
    rpb = np.asarray(det.rays_per_batch, dtype=float)
    rays_total = float(rpb.sum())
    if rays_total <= 0:
        return None
    return result.total_emitted_flux * (rpb / rays_total)


# ---------------------------------------------------------------------------
# Shared CI aggregator — consumed by heatmap_panel, report, batch_export
# ---------------------------------------------------------------------------


def compute_all_kpi_cis(
    result: SimulationResult,
    conf_level: float = 0.95,
):
    """Return ``dict[str, CIEstimate | None]`` for every scalar KPI.

    Keys covered: ``avg``, ``peak``, ``min``, ``cv``, ``hot``, ``ecr``,
    ``corner``, ``uni_1_4_min_avg``, ``uni_1_6_min_avg``, ``uni_1_10_min_avg``,
    ``efficiency_pct``.

    All values are ``None`` when UQ is off (``n_batches < 4`` or
    ``grid_batches is None``).  Efficiency uses
    :func:`_per_batch_source_flux` for unbiased per-batch scaling
    (checker I5 / threat T-04.03-05).
    """
    # Delayed import avoids a potential circular reference between
    # ``backlight_sim.core.uq`` and ``backlight_sim.core.kpi`` — core.uq
    # never imports core.kpi, so this is safe.
    from backlight_sim.core.uq import batch_mean_ci, kpi_batches

    keys_default = (
        "avg", "peak", "min", "cv", "hot", "ecr", "corner",
        "uni_1_4_min_avg", "uni_1_6_min_avg", "uni_1_10_min_avg",
        "efficiency_pct",
    )
    out: dict = {k: None for k in keys_default}
    if not result.detectors:
        return out
    det = next(iter(result.detectors.values()))
    gb = det.grid_batches
    if gb is None or det.n_batches < 4:
        return out

    def _mean(g: np.ndarray) -> float:
        return float(g.mean())

    def _max(g: np.ndarray) -> float:
        return float(g.max())

    def _min(g: np.ndarray) -> float:
        return float(g.min())

    def _cv(g: np.ndarray) -> float:
        m = float(g.mean())
        return float(g.std()) / m * 100.0 if m > 0 else 0.0

    def _hot(g: np.ndarray) -> float:
        m = float(g.mean())
        return float(g.max()) / m if m > 0 else 0.0

    out["avg"] = batch_mean_ci(kpi_batches(gb, _mean), conf_level)
    out["peak"] = batch_mean_ci(kpi_batches(gb, _max), conf_level)
    out["min"] = batch_mean_ci(kpi_batches(gb, _min), conf_level)
    out["cv"] = batch_mean_ci(kpi_batches(gb, _cv), conf_level)
    out["hot"] = batch_mean_ci(kpi_batches(gb, _hot), conf_level)
    out["ecr"] = batch_mean_ci(kpi_batches(gb, edge_center_ratio), conf_level)
    out["corner"] = batch_mean_ci(kpi_batches(gb, corner_ratio), conf_level)

    for label, frac in (("1_4", 0.25), ("1_6", 1.0 / 6.0), ("1_10", 0.1)):
        # Pin `frac` into the lambda default so each iteration binds its own value.
        vals = kpi_batches(gb, lambda g, f=frac: uniformity_in_center(g, f)[0])
        out[f"uni_{label}_min_avg"] = batch_mean_ci(vals, conf_level)

    per_batch_src = _per_batch_source_flux(result, det)
    if per_batch_src is not None and det.flux_batches is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            eff_batches = np.where(
                per_batch_src > 0,
                np.asarray(det.flux_batches, dtype=float) / per_batch_src * 100.0,
                0.0,
            )
        out["efficiency_pct"] = batch_mean_ci(eff_batches, conf_level)

    return out


__all__ = [
    "_per_batch_source_flux",
    "compute_all_kpi_cis",
    "compute_scalar_kpis",
    "corner_ratio",
    "edge_center_ratio",
    "uniformity_in_center",
]
