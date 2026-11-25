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
    # NOTE: must not be named "finished" -- that would shadow QThread.finished,
    # which thread_utils.stop_thread relies on.
    comparison_done = Signal(object, object)  # (result_a, result_b) or (error_str, None)

    def __init__(self, current: Project, variant: Project):
        super().__init__()
        self._current = copy.deepcopy(current)
        self._variant = copy.deepcopy(variant)
        for p in (self._current, self._variant):
            p.settings.rays_per_source = 1000
            p.settings.max_bounces = 20
            p.settings.record_ray_paths = 0
        self._cancelled = False
        self._tracer: RayTracer | None = None

    def cancel(self):
        self._cancelled = True
        tracer = self._tracer
        if tracer is not None:
            tracer.cancel()

    def run(self):
        try:
            results = []
            for proj in (self._current, self._variant):
                if self._cancelled:
                    return
                self._tracer = RayTracer(proj)
                results.append(self._tracer.run())
            if not self._cancelled:
                self.comparison_done.emit(results[0], results[1])
        except Exception as exc:
            self.comparison_done.emit(str(exc), None)
        finally:
            self._tracer = None


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
        self._variant = variant
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
        self._thread.comparison_done.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, result_a, result_b):
        self._progress.hide()

        if result_b is None:
            # result_a is an error string
            self._status_lbl.setText(f"Comparison failed: {result_a}")
            return

        kpis_a = _project_kpis(self._current, result_a)
        kpis_b = _project_kpis(self._variant, result_b)

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

    def done(self, result: int):
        # Close button / Esc / window-X all route through done(): stop the worker.
        from backlight_sim.gui.thread_utils import stop_thread
        stop_thread(self._thread)
        super().done(result)
