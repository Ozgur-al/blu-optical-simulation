"""Single-parameter sweep dialog — runs a batch of simulations and shows KPIs."""

from __future__ import annotations

import copy

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QDoubleSpinBox, QSpinBox, QLabel,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox,
)

from backlight_sim.core.project_model import Project
from backlight_sim.core.detectors import SimulationResult
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.gui.heatmap_panel import _uniformity_in_center

# Sweep-able parameters: display_name → (internal_key, default_start, default_end)
_PARAMS: dict[str, tuple[str, float, float]] = {
    "Source flux — all (units)":    ("source_flux",      1.0,   1000.0),
    "Reflector reflectance (0-1)":  ("reflector_refl",   0.5,   0.99),
    "Diffuser transmittance (0-1)": ("diffuser_trans",   0.1,   0.95),
    "Max bounces":                  ("max_bounces",      5.0,   150.0),
    "Rays per source":              ("rays_per_source",  1000.0, 50000.0),
}


def _apply_param(project: Project, key: str, value: float) -> None:
    """Mutate *project* (already a deep-copy) to reflect the sweep parameter."""
    if key == "source_flux":
        for src in project.sources:
            if src.enabled:
                src.flux = float(value)
    elif key == "reflector_refl":
        v = float(np.clip(value, 0.0, 1.0))
        for mat in project.materials.values():
            if mat.surface_type == "reflector":
                mat.reflectance = v
    elif key == "diffuser_trans":
        v = float(np.clip(value, 0.0, 1.0))
        for mat in project.materials.values():
            if mat.surface_type == "diffuser":
                mat.transmittance = v
    elif key == "max_bounces":
        project.settings.max_bounces = max(1, int(round(value)))
    elif key == "rays_per_source":
        project.settings.rays_per_source = max(100, int(round(value)))


def _kpis(result: SimulationResult) -> tuple[float, float, float]:
    """Return (efficiency_%, uniformity_1/4_min_avg, hotspot_peak/avg)."""
    if not result.detectors:
        return 0.0, 0.0, 0.0
    grid = next(iter(result.detectors.values())).grid
    avg = float(grid.mean())
    if result.total_emitted_flux > 0:
        det_total = sum(dr.total_flux for dr in result.detectors.values())
        eff = det_total / result.total_emitted_flux * 100.0
    else:
        eff = 0.0
    u14, _ = _uniformity_in_center(grid, 0.25)
    hot = float(grid.max()) / avg if avg > 0 else 0.0
    return eff, u14, hot


class _SweepThread(QThread):
    step_done    = Signal(int, float, object)   # (step_idx, param_value, SimulationResult)
    sweep_finished = Signal()

    def __init__(self, base_project: Project, param_key: str, values: np.ndarray):
        super().__init__()
        self._base   = base_project
        self._key    = param_key
        self._values = values
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        for i, v in enumerate(self._values):
            if self._cancelled:
                break
            proj = copy.deepcopy(self._base)
            _apply_param(proj, self._key, float(v))
            tracer = RayTracer(proj)
            result = tracer.run()
            self.step_done.emit(i, float(v), result)
        self.sweep_finished.emit()


class ParameterSweepDialog(QDialog):
    """Dialog for running a single-parameter sweep and displaying KPI results."""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Parameter Sweep")
        self.setMinimumWidth(660)
        self.setMinimumHeight(480)
        self._project = project
        self._thread: _SweepThread | None = None

        layout = QVBoxLayout(self)

        # ── Parameter & range ───────────────────────────────────────────
        fl = QFormLayout()
        self._param_cb = QComboBox()
        self._param_cb.addItems(list(_PARAMS.keys()))
        self._param_cb.currentIndexChanged.connect(self._on_param_changed)
        fl.addRow("Parameter:", self._param_cb)

        range_row = QHBoxLayout()
        self._start_spin = QDoubleSpinBox()
        self._start_spin.setRange(-1e9, 1e9)
        self._start_spin.setDecimals(4)
        self._end_spin = QDoubleSpinBox()
        self._end_spin.setRange(-1e9, 1e9)
        self._end_spin.setDecimals(4)
        self._steps_spin = QSpinBox()
        self._steps_spin.setRange(2, 100)
        self._steps_spin.setValue(10)
        range_row.addWidget(QLabel("Start:"))
        range_row.addWidget(self._start_spin)
        range_row.addWidget(QLabel("End:"))
        range_row.addWidget(self._end_spin)
        range_row.addWidget(QLabel("Steps:"))
        range_row.addWidget(self._steps_spin)
        fl.addRow("Range:", range_row)
        layout.addLayout(fl)

        # ── Run / Cancel ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Run Sweep")
        self._run_btn.clicked.connect(self._run_sweep)
        self._cancel_btn = QPushButton("Cancel Sweep")
        self._cancel_btn.clicked.connect(self._cancel_sweep)
        self._cancel_btn.setEnabled(False)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Progress ─────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        # ── Results table ─────────────────────────────────────────────────
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Value", "Efficiency %", "U(1/4) min/avg", "Hotspot (pk/avg)"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        # ── Close ─────────────────────────────────────────────────────────
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

        # Initialize spinbox defaults
        self._on_param_changed(0)

    # ------------------------------------------------------------------

    def _on_param_changed(self, _idx: int):
        name = self._param_cb.currentText()
        _, default_start, default_end = _PARAMS.get(name, ("", 1.0, 100.0))
        self._start_spin.setValue(default_start)
        self._end_spin.setValue(default_end)

    def _run_sweep(self):
        enabled_sources = [s for s in self._project.sources if s.enabled]
        if not enabled_sources:
            QMessageBox.warning(self, "No Active Sources",
                                "Enable at least one light source before sweeping.")
            return
        if not self._project.detectors:
            QMessageBox.warning(self, "No Detectors",
                                "Add at least one detector before sweeping.")
            return

        self._table.setRowCount(0)
        name = self._param_cb.currentText()
        key, _, _ = _PARAMS[name]
        start  = self._start_spin.value()
        end    = self._end_spin.value()
        n      = self._steps_spin.value()
        values = np.linspace(start, end, n)

        self._progress.setMaximum(n)
        self._progress.setValue(0)
        self._run_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

        # Update column header to show the swept parameter
        self._table.setHorizontalHeaderItem(0, QTableWidgetItem(name))

        self._thread = _SweepThread(copy.deepcopy(self._project), key, values)
        self._thread.step_done.connect(self._on_step_done)
        self._thread.sweep_finished.connect(self._on_sweep_finished)
        self._thread.start()

    def _cancel_sweep(self):
        if self._thread:
            self._thread.cancel()
            self._cancel_btn.setEnabled(False)

    def _on_step_done(self, idx: int, value: float, result: SimulationResult):
        self._progress.setValue(idx + 1)
        eff, u14, hot = _kpis(result)
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, text in enumerate([
            f"{value:.5g}",
            f"{eff:.2f}",
            f"{u14:.4f}",
            f"{hot:.4f}",
        ]):
            self._table.setItem(row, col, QTableWidgetItem(text))
        self._table.scrollToBottom()

    def _on_sweep_finished(self):
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(2000)
        super().closeEvent(event)
