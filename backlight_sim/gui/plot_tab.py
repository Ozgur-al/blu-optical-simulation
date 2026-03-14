"""Analysis plot tab with section views and distribution plots."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QSpinBox, QPushButton,
)

from backlight_sim.core.detectors import SimulationResult


class PlotTab(QWidget):
    """Dedicated analysis plot tab for section views and distribution charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Plot type:"))
        self._type_cb = QComboBox()
        self._type_cb.setAccessibleName("Plot type")
        self._type_cb.setToolTip("Choose the type of analysis plot to display")
        self._type_cb.addItems([
            "X Section (Y=center)",
            "Y Section (X=center)",
            "X Section (custom Y)",
            "Y Section (custom X)",
            "Flux histogram",
            "Cumulative distribution",
        ])
        self._type_cb.currentIndexChanged.connect(self._refresh)
        ctrl.addWidget(self._type_cb)

        ctrl.addWidget(QLabel("Slice pos:"))
        self._slice_spin = QSpinBox()
        self._slice_spin.setAccessibleName("Slice position")
        self._slice_spin.setRange(0, 999)
        self._slice_spin.setValue(50)
        self._slice_spin.setToolTip("Slice position in grid pixels (for custom section)")
        self._slice_spin.valueChanged.connect(self._refresh)
        ctrl.addWidget(self._slice_spin)

        ctrl.addWidget(QLabel("Detector:"))
        self._det_cb = QComboBox()
        self._det_cb.setAccessibleName("Detector selector")
        self._det_cb.setToolTip("Select which detector results to plot")
        self._det_cb.currentTextChanged.connect(self._on_det_changed)
        ctrl.addWidget(self._det_cb)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Plot
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        layout.addWidget(self._plot, 1)

        self._sim_result: SimulationResult | None = None

    def update_results(self, result: SimulationResult):
        self._sim_result = result
        self._det_cb.clear()
        self._det_cb.addItems(list(result.detectors.keys()))
        self._refresh()

    def _on_det_changed(self, _name: str):
        self._refresh()

    def _refresh(self, _=None):
        self._plot.clear()
        if self._sim_result is None:
            return
        det_name = self._det_cb.currentText()
        if not det_name or det_name not in self._sim_result.detectors:
            return

        grid = self._sim_result.detectors[det_name].grid
        ny, nx = grid.shape
        plot_type = self._type_cb.currentIndex()

        if plot_type == 0:
            # X section at Y=center
            row = ny // 2
            self._plot.setLabel("bottom", "X pixel")
            self._plot.setLabel("left", "Flux")
            self._plot.plot(np.arange(nx), grid[row, :],
                           pen=pg.mkPen('y', width=2))
            self._plot.setTitle(f"X Section at Y={row}")

        elif plot_type == 1:
            # Y section at X=center
            col = nx // 2
            self._plot.setLabel("bottom", "Y pixel")
            self._plot.setLabel("left", "Flux")
            self._plot.plot(np.arange(ny), grid[:, col],
                           pen=pg.mkPen('c', width=2))
            self._plot.setTitle(f"Y Section at X={col}")

        elif plot_type == 2:
            # X section at custom Y
            row = min(self._slice_spin.value(), ny - 1)
            self._plot.setLabel("bottom", "X pixel")
            self._plot.setLabel("left", "Flux")
            self._plot.plot(np.arange(nx), grid[row, :],
                           pen=pg.mkPen('y', width=2))
            self._plot.setTitle(f"X Section at Y={row}")

        elif plot_type == 3:
            # Y section at custom X
            col = min(self._slice_spin.value(), nx - 1)
            self._plot.setLabel("bottom", "Y pixel")
            self._plot.setLabel("left", "Flux")
            self._plot.plot(np.arange(ny), grid[:, col],
                           pen=pg.mkPen('c', width=2))
            self._plot.setTitle(f"Y Section at X={col}")

        elif plot_type == 4:
            # Flux histogram
            vals = grid.ravel()
            y, x = np.histogram(vals[vals > 0], bins=50)
            self._plot.setLabel("bottom", "Flux value")
            self._plot.setLabel("left", "Count")
            self._plot.plot(x, y, stepMode="center",
                           fillLevel=0, fillOutline=True,
                           pen=pg.mkPen('g', width=1),
                           brush=(80, 200, 80, 80))
            self._plot.setTitle("Flux Distribution")

        elif plot_type == 5:
            # Cumulative distribution
            vals = np.sort(grid.ravel())
            cdf = np.arange(1, len(vals) + 1) / len(vals)
            self._plot.setLabel("bottom", "Flux value")
            self._plot.setLabel("left", "Cumulative fraction")
            self._plot.plot(vals, cdf, pen=pg.mkPen('m', width=2))
            self._plot.setTitle("Cumulative Flux Distribution")

    def clear(self):
        self._plot.clear()
        self._det_cb.clear()
        self._sim_result = None
