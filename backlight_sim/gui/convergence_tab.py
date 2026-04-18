"""Convergence tab: cumulative KPI vs ray count with shaded CI band.

Renders a pyqtgraph plot showing how a selected KPI evolves as more per-batch
samples are accumulated.  The shaded band is the 95% confidence interval
derived from ``core.uq.batch_mean_ci`` over the per-batch KPI values up to
batch ``k``.

Consumers:
- MainWindow wires it next to PlotTab and calls ``update_from_result(result)``
  after a simulation completes.

Contracts (Wave 2 data model):
- ``DetectorResult.grid_batches`` shape ``(K, ny, nx)`` drives per-batch KPIs.
- ``DetectorResult.rays_per_batch`` list[int] feeds the x-axis cumulative ray
  count — remainder-aware (checker I5).
- ``DetectorResult.flux_batches`` + ``_per_batch_source_flux`` drive the
  efficiency KPI path.

When UQ is off (``n_batches < 4``), the plot is cleared and an "empty" label
is shown — legacy behavior preserved.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from backlight_sim.core.detectors import SimulationResult
from backlight_sim.core.kpi import _per_batch_source_flux, uniformity_in_center
from backlight_sim.core.uq import batch_mean_ci


# KPI selector entries: (display_label, internal_key).
_CONV_KPIS: tuple[tuple[str, str], ...] = (
    ("Uniformity 1/4 (min/avg)", "uniformity_1_4_min_avg"),
    ("Efficiency (%)", "efficiency_pct"),
    ("Hotspot (peak/avg)", "hotspot_peak_avg"),
)


def _per_batch_values_up_to_k(
    result: SimulationResult,
    kpi_key: str,
    k: int,
) -> np.ndarray:
    """Return the per-batch KPI values for batches 0..k-1.

    k >= 1.  Uses rays_per_batch-aware per-batch source flux for efficiency.
    """
    det = next(iter(result.detectors.values()))
    gb = det.grid_batches[:k]

    if kpi_key == "uniformity_1_4_min_avg":
        return np.asarray(
            [uniformity_in_center(gb[i], 0.25)[0] for i in range(k)],
            dtype=float,
        )
    if kpi_key == "efficiency_pct":
        per_batch_src = _per_batch_source_flux(result, det)
        if per_batch_src is None or det.flux_batches is None:
            return np.zeros(k, dtype=float)
        fb = np.asarray(det.flux_batches, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            eff = np.where(
                per_batch_src[:k] > 0,
                fb[:k] / per_batch_src[:k] * 100.0,
                0.0,
            )
        return np.asarray(eff, dtype=float)
    if kpi_key == "hotspot_peak_avg":
        out = np.zeros(k, dtype=float)
        for i in range(k):
            m = float(gb[i].mean())
            out[i] = float(gb[i].max()) / m if m > 0 else 0.0
        return out
    return np.zeros(k, dtype=float)


class ConvergenceTab(QWidget):
    """Convergence-plot tab: cumulative KPI vs ray count with 95% CI band."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Track:"))
        self._kpi_combo = QComboBox()
        self._kpi_combo.setAccessibleName("Convergence KPI")
        for label, _key in _CONV_KPIS:
            self._kpi_combo.addItem(label)
        self._kpi_combo.currentIndexChanged.connect(self._rerender)
        header.addWidget(self._kpi_combo)
        header.addStretch()
        layout.addLayout(header)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "Cumulative rays traced")
        self._plot.setLabel("left", "KPI value")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(self._plot, stretch=1)

        self._empty_label = QLabel(
            "UQ data not available (set uq_batches > 0 and re-run the simulation)."
        )
        self._empty_label.setStyleSheet("color: #888; font-style: italic; padding: 6px;")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        self._last_result: SimulationResult | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_from_result(self, result: SimulationResult) -> None:
        """Refresh the convergence plot from a fresh simulation result."""
        self._last_result = result
        self._rerender()

    def clear(self) -> None:
        self._last_result = None
        self._plot.clear()
        self._empty_label.setVisible(False)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _rerender(self) -> None:
        self._plot.clear()
        result = self._last_result
        if result is None or not result.detectors:
            self._empty_label.setVisible(True)
            return
        det = next(iter(result.detectors.values()))
        if det.grid_batches is None or det.n_batches < 4:
            self._empty_label.setVisible(True)
            return
        self._empty_label.setVisible(False)

        idx = self._kpi_combo.currentIndex()
        if idx < 0 or idx >= len(_CONV_KPIS):
            idx = 0
        kpi_label, kpi_key = _CONV_KPIS[idx]

        K = int(det.n_batches)

        # X axis: cumulative rays per partial-K uses rays_per_batch when
        # available (remainder-aware, checker I5).  Fall back to uniform
        # spacing when the tracer did not populate rays_per_batch.
        if det.rays_per_batch is not None:
            rpb = np.asarray(det.rays_per_batch, dtype=float)
            xs = np.cumsum(rpb)
        else:
            xs = np.arange(1, K + 1, dtype=float)

        means: list[float] = []
        lowers: list[float] = []
        uppers: list[float] = []
        for k in range(1, K + 1):
            per_batch_vals = _per_batch_values_up_to_k(result, kpi_key, k)
            if k >= 4:
                ci = batch_mean_ci(per_batch_vals, conf_level=0.95)
                means.append(ci.mean)
                lowers.append(ci.lower)
                uppers.append(ci.upper)
            else:
                m = float(per_batch_vals.mean())
                means.append(m)
                lowers.append(m)
                uppers.append(m)

        # Center curve first.
        pen = pg.mkPen(color=(80, 160, 255), width=2)
        self._plot.plot(xs, np.asarray(means), pen=pen, name=kpi_label)

        # Shaded CI band via FillBetweenItem(upper, lower).
        upper_curve = pg.PlotDataItem(xs, np.asarray(uppers), pen=None)
        lower_curve = pg.PlotDataItem(xs, np.asarray(lowers), pen=None)
        fill = pg.FillBetweenItem(
            upper_curve,
            lower_curve,
            brush=pg.mkBrush(80, 160, 255, 60),
        )
        self._plot.addItem(upper_curve)
        self._plot.addItem(lower_curve)
        self._plot.addItem(fill)
        self._plot.setLabel("left", kpi_label)


__all__ = ["ConvergenceTab"]
