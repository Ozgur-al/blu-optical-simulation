"""2D heatmap display with uniformity statistics."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QLabel, QGroupBox,
)

from backlight_sim.core.detectors import DetectorResult

# Uniformity area fractions to evaluate
_FRACTIONS = [("1/4", 0.25), ("1/6", 1 / 6), ("1/10", 0.10)]


def _uniformity_in_center(grid: np.ndarray, fraction: float) -> tuple[float, float]:
    """Return (min/avg, min/max) uniformity in the central *fraction* area."""
    ny, nx = grid.shape
    f_side = float(np.sqrt(fraction))
    cy, cx = ny // 2, nx // 2
    half_y = max(1, int(ny * f_side / 2))
    half_x = max(1, int(nx * f_side / 2))
    roi = grid[cy - half_y: cy + half_y, cx - half_x: cx + half_x]
    if roi.size == 0 or roi.max() == 0:
        return 0.0, 0.0
    avg = float(roi.mean())
    mn  = float(roi.min())
    mx  = float(roi.max())
    return (mn / avg if avg > 0 else 0.0, mn / mx if mx > 0 else 0.0)


class HeatmapPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ---- detector selector ----
        top = QHBoxLayout()
        top.addWidget(QLabel("Detector:"))
        self._selector = QComboBox()
        self._selector.currentTextChanged.connect(self._on_detector_changed)
        top.addWidget(self._selector)
        top.addStretch()
        layout.addLayout(top)

        # ---- heatmap ----
        self._plot = pg.PlotWidget()
        self._plot.setAspectLocked(True)
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._img = pg.ImageItem()
        self._plot.addItem(self._img)
        self._cbar = pg.ColorBarItem(
            values=(0, 1), colorMap=pg.colormap.get("inferno"),
        )
        self._cbar.setImageItem(self._img)
        layout.addWidget(self._plot, stretch=3)

        # ---- stats ----
        stats_box = QGroupBox("Luminance & Uniformity")
        sg = QGridLayout(stats_box)

        def _lbl(text="--"):
            l = QLabel(text)
            l.setStyleSheet("font-family: monospace;")
            return l

        self._lbl_avg  = _lbl(); self._lbl_peak = _lbl(); self._lbl_min = _lbl()
        self._lbl_hits = _lbl()
        sg.addWidget(QLabel("Avg:"),  0, 0); sg.addWidget(self._lbl_avg,  0, 1)
        sg.addWidget(QLabel("Peak:"), 0, 2); sg.addWidget(self._lbl_peak, 0, 3)
        sg.addWidget(QLabel("Min:"),  0, 4); sg.addWidget(self._lbl_min,  0, 5)
        sg.addWidget(QLabel("Hits:"), 0, 6); sg.addWidget(self._lbl_hits, 0, 7)

        # Uniformity rows
        self._uni_labels: dict[str, tuple[QLabel, QLabel]] = {}
        for row_i, (label, _frac) in enumerate(_FRACTIONS, start=1):
            sg.addWidget(QLabel(f"U ({label} area)  min/avg:"), row_i, 0)
            la = _lbl(); sg.addWidget(la, row_i, 1)
            sg.addWidget(QLabel("min/max:"), row_i, 2)
            lm = _lbl(); sg.addWidget(lm, row_i, 3)
            self._uni_labels[label] = (la, lm)

        layout.addWidget(stats_box, stretch=0)

        self._results: dict[str, DetectorResult] = {}

    # ------------------------------------------------------------------

    def update_results(self, results: dict[str, DetectorResult]):
        self._results = results
        self._selector.clear()
        self._selector.addItems(list(results.keys()))
        if results:
            self._show_result(results[next(iter(results))])

    def _on_detector_changed(self, name: str):
        if name in self._results:
            self._show_result(self._results[name])

    def _show_result(self, result: DetectorResult):
        grid = result.grid
        if grid.size == 0:
            return

        self._img.setImage(grid.T)
        vmin, vmax = float(grid.min()), float(grid.max())
        if vmax > vmin:
            self._cbar.setLevels(values=(vmin, vmax))

        avg  = float(grid.mean())
        peak = float(grid.max())
        mn   = float(grid.min())

        self._lbl_avg.setText(f"{avg:.4g}")
        self._lbl_peak.setText(f"{peak:.4g}")
        self._lbl_min.setText(f"{mn:.4g}")
        self._lbl_hits.setText(str(result.total_hits))

        for label, frac in _FRACTIONS:
            u_avg, u_max = _uniformity_in_center(grid, frac)
            la, lm = self._uni_labels[label]
            la.setText(f"{u_avg:.3f}")
            lm.setText(f"{u_max:.3f}")

    def clear(self):
        self._img.clear()
        self._selector.clear()
        self._results.clear()
        for lbl in [self._lbl_avg, self._lbl_peak, self._lbl_min, self._lbl_hits]:
            lbl.setText("--")
        for la, lm in self._uni_labels.values():
            la.setText("--"); lm.setText("--")
