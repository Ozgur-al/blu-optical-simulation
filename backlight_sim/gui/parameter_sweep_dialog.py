"""Single-parameter sweep dialog — runs a batch of simulations and shows KPIs."""

from __future__ import annotations

import copy

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QComboBox, QDoubleSpinBox, QSpinBox, QLabel, QWidget,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QLineEdit, QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from backlight_sim.core.project_model import Project
from backlight_sim.core.detectors import SimulationResult
from backlight_sim.core.kpi import (
    compute_scalar_kpis,
    uniformity_in_center as _uniformity_in_center,
)
from backlight_sim.sim.tracer import RayTracer

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


class _MultiSweepThread(QThread):
    step_done      = Signal(int, float, float, object)  # (idx, val1, val2, result)
    sweep_finished = Signal()

    def __init__(self, base_project: Project, key1: str, key2: str,
                 grid: list[tuple[float, float]]):
        super().__init__()
        self._base = base_project
        self._key1 = key1
        self._key2 = key2
        self._grid = grid
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        for i, (v1, v2) in enumerate(self._grid):
            if self._cancelled:
                break
            proj = copy.deepcopy(self._base)
            _apply_param(proj, self._key1, float(v1))
            _apply_param(proj, self._key2, float(v2))
            tracer = RayTracer(proj)
            result = tracer.run()
            self.step_done.emit(i, float(v1), float(v2), result)
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

        # ── Multi-parameter sweep option ──────────────────────────────────
        multi_row = QHBoxLayout()
        self._multi_check = QCheckBox("2-parameter sweep")
        self._multi_check.setToolTip("Sweep two parameters simultaneously (grid)")
        self._multi_check.toggled.connect(self._on_multi_toggled)
        multi_row.addWidget(self._multi_check)
        self._param2_cb = QComboBox()
        self._param2_cb.addItems(list(_PARAMS.keys()))
        self._param2_cb.setCurrentIndex(1)
        self._param2_cb.setEnabled(False)
        multi_row.addWidget(QLabel("Param 2:"))
        multi_row.addWidget(self._param2_cb)
        self._start2_spin = QDoubleSpinBox()
        self._start2_spin.setRange(-1e9, 1e9)
        self._start2_spin.setDecimals(4)
        self._start2_spin.setEnabled(False)
        self._end2_spin = QDoubleSpinBox()
        self._end2_spin.setRange(-1e9, 1e9)
        self._end2_spin.setDecimals(4)
        self._end2_spin.setEnabled(False)
        self._steps2_spin = QSpinBox()
        self._steps2_spin.setRange(2, 20)
        self._steps2_spin.setValue(5)
        self._steps2_spin.setEnabled(False)
        multi_row.addWidget(QLabel("Start:"))
        multi_row.addWidget(self._start2_spin)
        multi_row.addWidget(QLabel("End:"))
        multi_row.addWidget(self._end2_spin)
        multi_row.addWidget(QLabel("Steps:"))
        multi_row.addWidget(self._steps2_spin)
        layout.addLayout(multi_row)

        # ── Filter row ────────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Type to filter results...")
        self._filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_edit)
        self._pareto_btn = QPushButton("Highlight Pareto")
        self._pareto_btn.setToolTip("Highlight Pareto-optimal rows (max efficiency, max uniformity, min hotspot)")
        self._pareto_btn.clicked.connect(self._highlight_pareto)
        filter_row.addWidget(self._pareto_btn)
        layout.addLayout(filter_row)

        # ── Table + plot in a horizontal splitter ─────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Value", "Efficiency %", "U(1/4) min/avg", "Hotspot (pk/avg)"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        splitter.addWidget(self._table)

        # KPI vs parameter plot
        plot_widget = QVBoxLayout()
        kpi_row = QHBoxLayout()
        kpi_row.addWidget(QLabel("Plot:"))
        self._plot_kpi_cb = QComboBox()
        self._plot_kpi_cb.addItems(["Efficiency %", "U(1/4) min/avg", "Hotspot"])
        self._plot_kpi_cb.currentIndexChanged.connect(self._refresh_plot)
        kpi_row.addWidget(self._plot_kpi_cb)
        kpi_row.addStretch()
        pw = pg.PlotWidget()
        pw.showGrid(x=True, y=True, alpha=0.25)
        pw.setLabel("bottom", "Parameter value")
        pw.setLabel("left", "KPI")
        self._plot_widget = pw
        plot_container = QWidget()
        pvl = QVBoxLayout(plot_container)
        pvl.setContentsMargins(0, 0, 0, 0)
        pvl.addLayout(kpi_row)
        pvl.addWidget(pw)
        splitter.addWidget(plot_container)
        layout.addWidget(splitter, stretch=1)

        # Accumulated sweep data for plot refresh
        self._sweep_values: list[float] = []
        self._sweep_values2: list[float] = []  # second param for multi-sweep
        self._sweep_kpis: list[tuple[float, float, float]] = []
        # Persistent plot curve — updated incrementally instead of full clear+redraw
        self._plot_curve = None

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

    def _on_multi_toggled(self, checked: bool):
        self._param2_cb.setEnabled(checked)
        self._start2_spin.setEnabled(checked)
        self._end2_spin.setEnabled(checked)
        self._steps2_spin.setEnabled(checked)
        if checked:
            name2 = self._param2_cb.currentText()
            _, s, e = _PARAMS.get(name2, ("", 1.0, 100.0))
            self._start2_spin.setValue(s)
            self._end2_spin.setValue(e)

    def _apply_filter(self, text: str):
        text = text.strip().lower()
        for row in range(self._table.rowCount()):
            show = True
            if text:
                show = any(
                    text in (self._table.item(row, col).text().lower() if self._table.item(row, col) else "")
                    for col in range(self._table.columnCount())
                )
            self._table.setRowHidden(row, not show)

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

        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._sweep_values.clear()
        self._sweep_values2.clear()
        self._sweep_kpis.clear()
        self._plot_widget.clear()
        self._plot_curve = None  # reset persistent curve for new sweep
        name = self._param_cb.currentText()
        key, _, _ = _PARAMS[name]
        start  = self._start_spin.value()
        end    = self._end_spin.value()
        n      = self._steps_spin.value()
        values = np.linspace(start, end, n)

        if self._multi_check.isChecked():
            name2 = self._param2_cb.currentText()
            key2, _, _ = _PARAMS[name2]
            values2 = np.linspace(self._start2_spin.value(), self._end2_spin.value(),
                                   self._steps2_spin.value())
            # Build grid of (value1, value2) pairs
            grid_values = []
            for v1 in values:
                for v2 in values2:
                    grid_values.append((v1, v2))
            total = len(grid_values)
            self._table.setColumnCount(5)
            self._table.setHorizontalHeaderLabels(
                [name, name2, "Efficiency %", "U(1/4) min/avg", "Hotspot (pk/avg)"]
            )
            self._progress.setMaximum(total)
            self._progress.setValue(0)
            self._run_btn.setEnabled(False)
            self._cancel_btn.setEnabled(True)
            self._thread = _MultiSweepThread(
                copy.deepcopy(self._project), key, key2, grid_values)
            self._thread.step_done.connect(self._on_multi_step_done)
            self._thread.sweep_finished.connect(self._on_sweep_finished)
            self._thread.start()
            return

        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            [name, "Efficiency %", "U(1/4) min/avg", "Hotspot (pk/avg)"])
        self._progress.setMaximum(n)
        self._progress.setValue(0)
        self._run_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

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
        k = compute_scalar_kpis(result)
        eff, u14, hot = k["efficiency_pct"], k["uniformity_1_4_min_avg"], k["hotspot_peak_avg"]
        self._sweep_values.append(value)
        self._sweep_kpis.append((eff, u14, hot))
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
        self._refresh_plot()

    def _refresh_plot(self, _=None):
        """Update the KPI vs parameter value plot from cached sweep data.

        Uses setData() on a persistent curve to avoid O(n) clear+redraw on
        every step, keeping the per-step cost at O(1).
        """
        if not self._sweep_values:
            return
        xs = np.array(self._sweep_values)
        idx = self._plot_kpi_cb.currentIndex()   # 0=eff, 1=u14, 2=hot
        ys = np.array([k[idx] for k in self._sweep_kpis])
        self._plot_widget.setLabel("left", self._plot_kpi_cb.currentText())
        if self._plot_curve is None:
            self._plot_curve = self._plot_widget.plot(
                xs, ys,
                pen=pg.mkPen((80, 160, 255), width=2),
                symbol="o", symbolSize=6, symbolBrush=(80, 160, 255),
            )
        else:
            self._plot_curve.setData(xs, ys)

    def _on_multi_step_done(self, idx: int, v1: float, v2: float, result: SimulationResult):
        self._progress.setValue(idx + 1)
        k = compute_scalar_kpis(result)
        eff, u14, hot = k["efficiency_pct"], k["uniformity_1_4_min_avg"], k["hotspot_peak_avg"]
        self._sweep_values.append(v1)
        self._sweep_values2.append(v2)
        self._sweep_kpis.append((eff, u14, hot))
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col, text in enumerate([
            f"{v1:.5g}", f"{v2:.5g}",
            f"{eff:.2f}", f"{u14:.4f}", f"{hot:.4f}",
        ]):
            self._table.setItem(row, col, QTableWidgetItem(text))
        self._table.scrollToBottom()
        self._refresh_plot()

    def _compute_pareto_indices(self) -> list[int]:
        """Return indices of Pareto-optimal points.

        Objectives: maximize efficiency, maximize uniformity, minimize hotspot.
        A point is dominated if another point is ≥ in all objectives and > in at least one.
        """
        if not self._sweep_kpis:
            return []
        n = len(self._sweep_kpis)
        # Convert to "all maximize" by negating hotspot
        pts = np.array([(eff, u14, -hot) for eff, u14, hot in self._sweep_kpis])
        dominated = np.zeros(n, dtype=bool)
        for i in range(n):
            if dominated[i]:
                continue
            for j in range(n):
                if i == j or dominated[j]:
                    continue
                # j dominates i if j >= i in all and j > i in at least one
                if np.all(pts[j] >= pts[i]) and np.any(pts[j] > pts[i]):
                    dominated[i] = True
                    break
        return [i for i in range(n) if not dominated[i]]

    def _highlight_pareto(self):
        """Highlight Pareto-optimal rows in gold and mark them on the plot."""
        pareto_idx = self._compute_pareto_indices()
        if not pareto_idx:
            return
        gold = QBrush(QColor(255, 215, 0, 80))
        white = QBrush(QColor(255, 255, 255, 0))
        for row in range(self._table.rowCount()):
            brush = gold if row in pareto_idx else white
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item:
                    item.setBackground(brush)
        # Overlay Pareto points on plot
        if self._sweep_values:
            xs = np.array(self._sweep_values)
            kpi_idx = self._plot_kpi_cb.currentIndex()
            ys = np.array([self._sweep_kpis[i][kpi_idx] for i in range(len(self._sweep_kpis))])
            px = xs[pareto_idx]
            py = ys[pareto_idx]
            self._plot_widget.plot(
                px, py, pen=None,
                symbol="star", symbolSize=14,
                symbolBrush=(255, 215, 0), symbolPen=pg.mkPen('k', width=1),
            )

    def _on_sweep_finished(self):
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._table.setSortingEnabled(True)
        # Auto-highlight Pareto if multi-param sweep
        if self._multi_check.isChecked() and self._sweep_kpis:
            self._highlight_pareto()

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(2000)
        super().closeEvent(event)
