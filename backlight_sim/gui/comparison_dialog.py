"""Side-by-side project comparison dialog — runs simulations off the GUI thread."""

from __future__ import annotations

import copy

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QProgressBar,
)

from backlight_sim.core.project_model import Project
from backlight_sim.core.detectors import SimulationResult
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.gui.heatmap_panel import _uniformity_in_center, _edge_center_ratio


class _ComparisonThread(QThread):
    """Run two quick simulations off the GUI thread."""
    finished = Signal(object, object)  # (result_a, result_b) or (error_str, None)

    def __init__(self, current: Project, variant: Project):
        super().__init__()
        self._current = copy.deepcopy(current)
        self._variant = copy.deepcopy(variant)
        for p in (self._current, self._variant):
            p.settings.rays_per_source = 1000
            p.settings.max_bounces = 20
            p.settings.record_ray_paths = 0

    def run(self):
        try:
            result_a = RayTracer(self._current).run()
            result_b = RayTracer(self._variant).run()
            self.finished.emit(result_a, result_b)
        except Exception as exc:
            self.finished.emit(str(exc), None)


def _project_kpis(project: Project, result: SimulationResult) -> dict[str, str]:
    """Extract a dict of KPI name -> formatted value."""
    kpis = {}
    kpis["Sources"] = str(len([s for s in project.sources if s.enabled]))
    kpis["Surfaces"] = str(len(project.surfaces))

    if not result.detectors:
        return kpis

    grid = next(iter(result.detectors.values())).grid
    if grid.size == 0:
        return kpis

    avg = float(grid.mean())
    peak = float(grid.max())
    std = float(grid.std())

    kpis["Avg flux"] = f"{avg:.4g}"
    kpis["Peak flux"] = f"{peak:.4g}"
    kpis["Std Dev"] = f"{std:.4g}"
    kpis["Hotspot (pk/avg)"] = f"{peak / avg:.3f}" if avg > 0 else "--"
    kpis["Edge/Center"] = f"{_edge_center_ratio(grid):.3f}"

    u14, _ = _uniformity_in_center(grid, 0.25)
    kpis["U(1/4) min/avg"] = f"{u14:.3f}"

    if result.total_emitted_flux > 0:
        det_flux = sum(dr.total_flux for dr in result.detectors.values())
        kpis["Efficiency %"] = f"{det_flux / result.total_emitted_flux * 100:.1f}"
        esc_pct = result.escaped_flux / result.total_emitted_flux * 100
        kpis["Escaped %"] = f"{esc_pct:.1f}"
        kpis["Absorbed %"] = f"{max(0, 100 - det_flux / result.total_emitted_flux * 100 - esc_pct):.1f}"

    return kpis


class ComparisonDialog(QDialog):
    """Compare current project against a saved variant."""

    def __init__(self, current: Project, variant_name: str,
                 variant: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Compare: Current vs {variant_name}")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._current = current
        self._variant_name = variant_name
        self._thread = None

        layout = QVBoxLayout(self)
        self._status_lbl = QLabel("Running quick simulations for comparison...")
        layout.addWidget(self._status_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        layout.addWidget(self._progress)

        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        # Run simulations off the GUI thread
        self._thread = _ComparisonThread(current, variant)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, result_a, result_b):
        self._progress.hide()

        if result_b is None:
            # result_a is an error string
            self._status_lbl.setText(f"Comparison failed: {result_a}")
            return

        kpis_a = _project_kpis(self._current, result_a)
        kpis_b = _project_kpis(self._current, result_b)  # variant uses same KPI function

        all_keys = list(dict.fromkeys(list(kpis_a.keys()) + list(kpis_b.keys())))
        self._table.setColumnCount(3)
        self._table.setRowCount(len(all_keys))
        self._table.setHorizontalHeaderLabels(["KPI", "Current", self._variant_name])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for row, key in enumerate(all_keys):
            self._table.setItem(row, 0, QTableWidgetItem(key))
            self._table.setItem(row, 1, QTableWidgetItem(kpis_a.get(key, "--")))
            self._table.setItem(row, 2, QTableWidgetItem(kpis_b.get(key, "--")))

        self._status_lbl.setText(
            f"Quick comparison ({self._current.name} vs {self._variant_name})")

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.wait(3000)
        super().closeEvent(event)
