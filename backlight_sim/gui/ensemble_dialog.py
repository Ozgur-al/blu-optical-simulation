"""Ensemble tolerance Monte Carlo dialog.

Runs N realizations of the current project sampled from tolerance distributions and
displays KPI distributions (histogram, P5/P50/P95) and sensitivity ranking.
"""
from __future__ import annotations

import copy

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QSpinBox, QLabel, QWidget,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox,
)

from backlight_sim.core.project_model import Project
from backlight_sim.core.kpi import compute_scalar_kpis


# ---------------------------------------------------------------------------
# Background QThread
# ---------------------------------------------------------------------------

class _EnsembleThread(QThread):
    """Runs N ensemble realizations in a background thread.

    mode field determines what the thread executes:
      "mc"    -- N i.i.d. draws via build_mc_sample (Distribution tab)
      "oat"   -- k+1 OAT runs via build_oat_sample (Sensitivity tab)
      "sobol" -- N*(k+2) Sobol runs via build_sobol_sample (Sensitivity tab)

    Emits step_done(idx, result, project_clone) after each member.
    Emits sweep_finished() when all members complete or cancel is called.
    """
    step_done = Signal(int, object, object)   # (member_idx, SimulationResult, Project clone)
    sweep_finished = Signal()

    def __init__(
        self,
        base_project: Project,
        n_members: int,
        mode: str,      # "mc" | "oat" | "sobol"
        seed: int,
    ) -> None:
        super().__init__()
        self._base = base_project
        self._n = min(max(1, n_members), 500)   # DoS clamp [1, 500]
        self._mode = mode
        self._seed = seed & 0x7FFFFFFF          # int32 mask (Phase 4 pattern)
        self._cancelled = False
        self._member_projects: list[Project] = []   # for worst-case drill-down

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        from backlight_sim.sim.ensemble import build_mc_sample, build_oat_sample, build_sobol_sample
        from backlight_sim.sim.tracer import RayTracer

        if self._mode == "mc":
            # Distribution mode: N i.i.d. draws — provides histogram + P5/P50/P95
            projects = build_mc_sample(self._base, self._n, self._seed)
            samples = [(p, None) for p in projects]
        elif self._mode == "sobol":
            samples = build_sobol_sample(self._base, self._n, self._seed)
        else:
            # "oat" -- sensitivity mode, k+1 runs
            samples = build_oat_sample(self._base, self._seed)

        for i, (proj, _param_info) in enumerate(samples):
            if self._cancelled:
                break
            try:
                result = RayTracer(proj).run()
            except Exception:
                continue    # skip failed members; do not crash the thread
            self._member_projects.append(proj)
            self.step_done.emit(i, result, proj)

        self.sweep_finished.emit()


# ---------------------------------------------------------------------------
# KPI registry
# ---------------------------------------------------------------------------

# KPI keys available from compute_scalar_kpis (Phase 4)
_KPI_KEYS = [
    ("uniformity_1_4_min_avg", "Uniformity 1/4 (min/avg)"),
    ("efficiency_pct",         "Efficiency (%)"),
    ("hotspot_peak_avg",       "Hotspot (peak/avg)"),
    ("avg_flux",               "Avg flux"),
    ("cv_pct",                 "CV (%)"),
]
# Map from display name -> key
_KPI_LABEL_TO_KEY = {label: key for key, label in _KPI_KEYS}
_KPI_KEY_TO_LABEL = {key: label for key, label in _KPI_KEYS}


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class EnsembleDialog(QDialog):
    """Tolerance ensemble dialog with two independent tabs.

    Tab 1 -- Distribution: runs N i.i.d. draws (mode="mc") via build_mc_sample.
      Shows live histogram + P5/P50/P95. Sensitivity NOT computed in this mode.

    Tab 2 -- Sensitivity Analysis: runs OAT (k+1 runs, mode="oat") or
      Sobol (N*(k+2) runs, mode="sobol"). Shows sensitivity table only.
    """

    save_variant = Signal(str, object)   # (name, Project) -- worst-case drill-down

    def __init__(self, project: Project, parent=None) -> None:
        super().__init__(parent)
        self._project = project
        self._thread: _EnsembleThread | None = None
        # Distribution tab state
        self._dist_kpi_values: list[float] = []
        self._dist_all_kpis: list[dict[str, float]] = []
        self._dist_member_projects: list[Project] = []
        self._worst_project: Project | None = None
        # Sensitivity tab state
        self._sens_all_kpis: list[dict[str, float]] = []

        self.setWindowTitle("Tolerance Ensemble")
        self.resize(950, 650)
        self._build_ui()

    def _build_ui(self) -> None:
        from PySide6.QtWidgets import QTabWidget
        root = QVBoxLayout(self)

        # Progress bar + cancel (shared between tabs)
        prog_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setValue(0)
        prog_row.addWidget(self._progress)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_ensemble)
        prog_row.addWidget(self._cancel_btn)
        root.addLayout(prog_row)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_distribution_tab(), "Distribution")
        self._tabs.addTab(self._build_sensitivity_tab(), "Sensitivity Analysis")
        root.addWidget(self._tabs)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_distribution_tab(self) -> QWidget:
        """Tab 1: N i.i.d. draws -> histogram + P5/P50/P95."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Control row
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("N members:"))
        self._dist_n_spin = QSpinBox()
        self._dist_n_spin.setRange(1, 500)   # DoS clamp
        self._dist_n_spin.setValue(50)        # default N=50
        ctrl.addWidget(self._dist_n_spin)
        ctrl.addStretch()
        ctrl.addWidget(QLabel("Show KPI:"))
        self._dist_kpi_combo = QComboBox()
        for _key, label in _KPI_KEYS:
            self._dist_kpi_combo.addItem(label)
        self._dist_kpi_combo.currentIndexChanged.connect(self._on_dist_kpi_changed)
        ctrl.addWidget(self._dist_kpi_combo)
        self._dist_run_btn = QPushButton("Run Distribution")
        self._dist_run_btn.clicked.connect(self._run_distribution)
        ctrl.addWidget(self._dist_run_btn)
        layout.addLayout(ctrl)

        # Histogram plot
        self._dist_plot = pg.PlotWidget()
        self._dist_plot.setLabel("bottom", "KPI Value")
        self._dist_plot.setLabel("left", "Count")
        self._hist_item = pg.BarGraphItem(
            x=[0.5], height=[0], width=0.05,
            brush=pg.mkBrush(80, 160, 255, 180)
        )
        self._dist_plot.addItem(self._hist_item)
        self._p5_line  = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("r", width=1),
                                         label="P5",  labelOpts={"color": "r"})
        self._p50_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("w", width=2),
                                         label="P50", labelOpts={"color": "w"})
        self._p95_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("g", width=1),
                                         label="P95", labelOpts={"color": "g"})
        self._dist_plot.addItem(self._p5_line)
        self._dist_plot.addItem(self._p50_line)
        self._dist_plot.addItem(self._p95_line)
        layout.addWidget(self._dist_plot)

        self._percentile_label = QLabel("P5: -- | P50: -- | P95: --")
        layout.addWidget(self._percentile_label)

        self._load_worst_btn = QPushButton("Load worst case as variant")
        self._load_worst_btn.setEnabled(False)
        self._load_worst_btn.clicked.connect(self._load_worst_case)
        layout.addWidget(self._load_worst_btn)
        return tab

    def _build_sensitivity_tab(self) -> QWidget:
        """Tab 2: OAT (k+1 runs) or Sobol (N*(k+2) runs) -> sensitivity table."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Control row
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Mode:"))
        self._sens_mode_combo = QComboBox()
        self._sens_mode_combo.addItems(["Fast (OAT)", "Full (Sobol, N>=32)"])
        self._sens_mode_combo.currentIndexChanged.connect(self._on_sens_mode_changed)
        ctrl.addWidget(self._sens_mode_combo)

        ctrl.addWidget(QLabel("N (Sobol only):"))
        self._sobol_n_spin = QSpinBox()
        self._sobol_n_spin.setRange(32, 500)   # minimum 32 for Sobol
        self._sobol_n_spin.setValue(64)
        self._sobol_n_spin.setEnabled(False)   # disabled until Sobol mode selected
        self._sobol_n_spin.setToolTip(
            "N must be >= 32 for reliable Sobol estimates.\n"
            "N is rounded up to the next power of 2 automatically."
        )
        ctrl.addWidget(self._sobol_n_spin)

        ctrl.addStretch()
        ctrl.addWidget(QLabel("Show KPI:"))
        self._sens_kpi_combo = QComboBox()
        for _key, label in _KPI_KEYS:
            self._sens_kpi_combo.addItem(label)
        self._sens_kpi_combo.currentIndexChanged.connect(self._on_sens_kpi_changed)
        ctrl.addWidget(self._sens_kpi_combo)

        self._sens_run_btn = QPushButton("Run Sensitivity")
        self._sens_run_btn.clicked.connect(self._run_sensitivity)
        ctrl.addWidget(self._sens_run_btn)
        layout.addLayout(ctrl)

        # Sensitivity table
        layout.addWidget(QLabel("Sensitivity index (|ΔKPI| / σ_param for OAT; Si for Sobol):"))
        self._sens_table = QTableWidget(0, 2)
        self._sens_table.setHorizontalHeaderLabels(["Parameter", "Sensitivity"])
        self._sens_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._sens_table.setSortingEnabled(True)
        layout.addWidget(self._sens_table)
        return tab

    # ------------------------------------------------------------------
    # Distribution tab: run / step / finish
    # ------------------------------------------------------------------

    def _run_distribution(self) -> None:
        if not self._check_project_ready():
            return
        n = self._dist_n_spin.value()
        self._dist_kpi_values.clear()
        self._dist_all_kpis.clear()
        self._dist_member_projects.clear()
        self._worst_project = None
        self._load_worst_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.setMaximum(n)
        self._set_running(True)
        seed = self._project.settings.random_seed & 0x7FFFFFFF
        self._thread = _EnsembleThread(
            base_project=copy.deepcopy(self._project),
            n_members=n,
            mode="mc",
            seed=seed,
        )
        self._thread.step_done.connect(self._on_dist_step_done)
        self._thread.sweep_finished.connect(self._on_dist_finished)
        self._thread.start()

    def _on_dist_step_done(self, idx: int, result, proj: Project) -> None:
        self._progress.setValue(idx + 1)
        self._dist_member_projects.append(proj)
        kpis = compute_scalar_kpis(result)
        self._dist_all_kpis.append(kpis)
        selected_key = _KPI_LABEL_TO_KEY[self._dist_kpi_combo.currentText()]
        self._dist_kpi_values.append(kpis.get(selected_key, 0.0))
        self._update_histogram(self._dist_kpi_values)
        self._update_worst_case(selected_key)

    def _on_dist_finished(self) -> None:
        self._set_running(False)
        if self._thread:
            self._dist_member_projects = self._thread._member_projects
        if self._worst_project is not None:
            self._load_worst_btn.setEnabled(True)

    def _on_dist_kpi_changed(self) -> None:
        if not self._dist_all_kpis:
            return
        selected_key = _KPI_LABEL_TO_KEY[self._dist_kpi_combo.currentText()]
        self._dist_kpi_values = [k.get(selected_key, 0.0) for k in self._dist_all_kpis]
        self._update_histogram(self._dist_kpi_values)
        self._update_worst_case(selected_key)

    # ------------------------------------------------------------------
    # Sensitivity tab: run / step / finish
    # ------------------------------------------------------------------

    def _run_sensitivity(self) -> None:
        if not self._check_project_ready():
            return
        mode_text = self._sens_mode_combo.currentText()
        mode = "sobol" if "Sobol" in mode_text else "oat"
        n = self._sobol_n_spin.value() if mode == "sobol" else 1  # OAT ignores n
        if mode == "sobol" and n < 32:
            QMessageBox.warning(self, "Sobol Minimum",
                                "Sobol mode requires N >= 32. N will be rounded up automatically.")
        self._sens_all_kpis.clear()
        self._progress.setValue(0)
        self._set_running(True)
        seed = self._project.settings.random_seed & 0x7FFFFFFF
        self._thread = _EnsembleThread(
            base_project=copy.deepcopy(self._project),
            n_members=n,
            mode=mode,
            seed=seed,
        )
        self._thread.step_done.connect(self._on_sens_step_done)
        self._thread.sweep_finished.connect(self._on_sens_finished)
        self._thread.start()

    def _on_sens_step_done(self, idx: int, result, proj: Project) -> None:
        self._progress.setValue(idx + 1)
        kpis = compute_scalar_kpis(result)
        self._sens_all_kpis.append(kpis)

    def _on_sens_finished(self) -> None:
        self._set_running(False)
        mode_text = self._sens_mode_combo.currentText()
        if "Sobol" in mode_text:
            self._update_sobol_sensitivity_table()
        else:
            self._update_oat_sensitivity_table()

    def _on_sens_mode_changed(self) -> None:
        sobol = "Sobol" in self._sens_mode_combo.currentText()
        self._sobol_n_spin.setEnabled(sobol)

    def _on_sens_kpi_changed(self) -> None:
        if self._sens_all_kpis:
            self._update_oat_sensitivity_table()

    # ------------------------------------------------------------------
    # Histogram (Distribution tab)
    # ------------------------------------------------------------------

    def _update_histogram(self, kpi_values: list[float]) -> None:
        """Live-update BarGraphItem with dynamic bin edges (pitfall 6 avoidance)."""
        if len(kpi_values) < 2:
            return
        counts, edges = np.histogram(kpi_values, bins=min(20, len(kpi_values)))
        centers = (edges[:-1] + edges[1:]) / 2
        width = float(edges[1] - edges[0]) if len(edges) > 1 else 0.05
        self._hist_item.setOpts(x=centers, height=counts.astype(float), width=width)
        if len(kpi_values) >= 5:
            p5, p50, p95 = np.percentile(kpi_values, [5, 50, 95])
            self._p5_line.setValue(p5)
            self._p50_line.setValue(p50)
            self._p95_line.setValue(p95)
            self._percentile_label.setText(f"P5: {p5:.4f} | P50: {p50:.4f} | P95: {p95:.4f}")

    # ------------------------------------------------------------------
    # Sensitivity table (Sensitivity Analysis tab)
    # ------------------------------------------------------------------

    def _update_oat_sensitivity_table(self) -> None:
        """Populate sensitivity table using OAT indices. index 0=baseline, 1..k=perturbed."""
        from backlight_sim.sim.ensemble import compute_oat_sensitivity, _active_tolerance_params
        if len(self._sens_all_kpis) < 2:
            return
        params = _active_tolerance_params(self._project)
        if not params:
            return
        baseline_kpis = self._sens_all_kpis[0]
        perturbed_kpis = self._sens_all_kpis[1:len(params) + 1]
        if len(perturbed_kpis) < len(params):
            return
        selected_key = _KPI_LABEL_TO_KEY[self._sens_kpi_combo.currentText()]
        sensitivity = compute_oat_sensitivity(
            baseline_kpis,
            perturbed_kpis,
            [p[0] for p in params],
            [p[1] for p in params],
        )
        sens_vals = sensitivity.get(selected_key, [0.0] * len(params))
        rows = sorted(zip([p[0] for p in params], sens_vals), key=lambda x: -x[1])
        self._sens_table.setRowCount(len(rows))
        for row_idx, (pname, sv) in enumerate(rows):
            self._sens_table.setItem(row_idx, 0, QTableWidgetItem(pname))
            self._sens_table.setItem(row_idx, 1, QTableWidgetItem(f"{sv:.4f}"))

    def _update_sobol_sensitivity_table(self) -> None:
        """Populate sensitivity table using Sobol first-order Si indices."""
        from backlight_sim.sim.ensemble import compute_sobol_sensitivity, _active_tolerance_params
        params = _active_tolerance_params(self._project)
        if not params or not self._sens_all_kpis:
            return
        k = len(params)
        n_runs = len(self._sens_all_kpis)
        # Expected Saltelli layout: N*(k+2) runs
        selected_key = _KPI_LABEL_TO_KEY[self._sens_kpi_combo.currentText()]
        kpi_col = np.array([kpis.get(selected_key, 0.0) for kpis in self._sens_all_kpis])
        # N = n_runs / (k+2)
        N = n_runs // (k + 2)
        if N < 1:
            return
        kpi_matrix = kpi_col[:, np.newaxis]   # (n_runs, 1)
        param_matrix = np.zeros((n_runs, k))  # placeholder
        si_dict = compute_sobol_sensitivity(kpi_matrix, param_matrix, N, k)
        si_vals = si_dict.get("0", np.zeros(k))
        rows = sorted(zip([p[0] for p in params], si_vals), key=lambda x: -x[1])
        self._sens_table.setRowCount(len(rows))
        for row_idx, (pname, sv) in enumerate(rows):
            self._sens_table.setItem(row_idx, 0, QTableWidgetItem(pname))
            self._sens_table.setItem(row_idx, 1, QTableWidgetItem(f"{sv:.4f}"))

    # ------------------------------------------------------------------
    # Worst-case drill-down (Distribution tab)
    # ------------------------------------------------------------------

    def _update_worst_case(self, selected_key: str) -> None:
        if not self._dist_all_kpis:
            return
        worst_idx = int(np.argmin([k.get(selected_key, float("inf"))
                                   for k in self._dist_all_kpis]))
        if worst_idx < len(self._dist_member_projects):
            self._worst_project = self._dist_member_projects[worst_idx]
            worst_val = self._dist_all_kpis[worst_idx].get(selected_key, 0.0)
            self._load_worst_btn.setText(
                f"Load worst case as variant ({selected_key}={worst_val:.4f})"
            )

    def _load_worst_case(self) -> None:
        if self._worst_project is None:
            return
        selected_key = _KPI_LABEL_TO_KEY[self._dist_kpi_combo.currentText()]
        worst_val = min(k.get(selected_key, float("inf")) for k in self._dist_all_kpis)
        name = f"Ensemble worst ({selected_key}={worst_val:.4f})"
        self.save_variant.emit(name, self._worst_project)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _check_project_ready(self) -> bool:
        if not [s for s in self._project.sources if s.enabled]:
            QMessageBox.warning(self, "No Active Sources",
                                "Enable at least one source before running.")
            return False
        return True

    def _set_running(self, running: bool) -> None:
        self._dist_run_btn.setEnabled(not running)
        self._sens_run_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)

    def _cancel_ensemble(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.cancel()

    def closeEvent(self, event) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(2000)
        super().closeEvent(event)
