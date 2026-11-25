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

    Emits total_known(n) once the sample design is built.
    Emits step_done(idx, result, project_clone) after each successful member and
    member_failed(idx, message) for each member whose trace raised.
    Emits sweep_finished() when all members complete, fail, or cancel is called.
    """
    total_known = Signal(int)                 # number of members in the design
    step_done = Signal(int, object, object)   # (member_idx, SimulationResult, Project clone)
    member_failed = Signal(int, str)          # (member_idx, error message)
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
        self._tracer = None

    def cancel(self) -> None:
        self._cancelled = True
        tracer = self._tracer
        if tracer is not None:
            tracer.cancel()   # stop the in-flight trace, not just the next member

    def run(self) -> None:
        from backlight_sim.sim.ensemble import build_mc_sample, build_oat_sample, build_sobol_sample
        from backlight_sim.sim.tracer import RayTracer

        try:
            if self._mode == "mc":
                # Distribution mode: N i.i.d. draws — provides histogram + P5/P50/P95
                projects = build_mc_sample(self._base, self._n, self._seed)
                samples = [(p, None) for p in projects]
            elif self._mode == "sobol":
                samples = build_sobol_sample(self._base, self._n, self._seed)
            else:
                # "oat" -- sensitivity mode, k+1 runs
                samples = build_oat_sample(self._base, self._seed)
            self.total_known.emit(len(samples))

            for i, (proj, _param_info) in enumerate(samples):
                if self._cancelled:
                    break
                self._tracer = RayTracer(proj)
                try:
                    result = self._tracer.run()
                except Exception as exc:
                    # Report (do not hide) failed members; keep the thread alive.
                    self.member_failed.emit(i, f"{type(exc).__name__}: {exc}")
                    continue
                if self._cancelled:
                    break   # cancelled mid-trace: partial result is not a valid member
                self.step_done.emit(i, result, proj)
        except Exception as exc:
            self.member_failed.emit(-1, f"{type(exc).__name__}: {exc}")
        finally:
            self._tracer = None
            self.sweep_finished.emit()


# ---------------------------------------------------------------------------
# KPI registry
# ---------------------------------------------------------------------------

# KPI keys available from compute_scalar_kpis (Phase 4) with their direction:
# True = higher is better (worst case = minimum), False = lower is better
# (worst case = maximum).  Only keys that compute_scalar_kpis actually returns
# are listed — offering others would silently plot zeros.
_KPI_KEYS = [
    ("uniformity_1_4_min_avg", "Uniformity 1/4 (min/avg)", True),
    ("efficiency_pct",         "Efficiency (%)",           True),
    ("hotspot_peak_avg",       "Hotspot (peak/avg)",       False),
]
# Map from display name -> key
_KPI_LABEL_TO_KEY = {label: key for key, label, _hib in _KPI_KEYS}
_KPI_KEY_TO_LABEL = {key: label for key, label, _hib in _KPI_KEYS}
_KPI_HIGHER_IS_BETTER = {key: hib for key, _label, hib in _KPI_KEYS}


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
        self._failures: list[str] = []
        # Distribution tab state (parallel lists, successful members only, in order)
        self._dist_kpi_values: list[float] = []
        self._dist_all_kpis: list[dict[str, float]] = []
        self._dist_member_projects: list[Project] = []
        self._worst_project: Project | None = None
        self._worst_val: float | None = None
        # Sensitivity tab state: member index -> KPI dict (None = member failed)
        self._sens_kpis_by_idx: dict[int, dict[str, float] | None] = {}
        self._sens_expected = 0
        self._sens_run_mode: str | None = None   # mode of the data in _sens_kpis_by_idx

        self.setWindowTitle("Tolerance Ensemble")
        self.resize(1000, 680)
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
        for _key, label, _hib in _KPI_KEYS:
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
        # Hidden until real percentiles exist; empty plot gets a sane 0..1 range.
        for line in (self._p5_line, self._p50_line, self._p95_line):
            line.hide()
        self._dist_plot.setXRange(0.0, 1.0)
        self._dist_plot.setYRange(0.0, 10.0)
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
        for _key, label, _hib in _KPI_KEYS:
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
        self._sens_status = QLabel("")
        layout.addWidget(self._sens_status)
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
        self._worst_val = None
        self._load_worst_btn.setEnabled(False)
        self._load_worst_btn.setText("Load worst case as variant")
        self._failures = []
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
        self._thread.total_known.connect(self._progress.setMaximum)
        self._thread.step_done.connect(self._on_dist_step_done)
        self._thread.member_failed.connect(self._on_member_failed)
        self._thread.sweep_finished.connect(self._on_dist_finished)
        self._thread.start()

    def _on_member_failed(self, idx: int, message: str) -> None:
        if idx >= 0:
            self._progress.setValue(idx + 1)
            self._failures.append(f"member {idx}: {message}")
        else:
            self._failures.append(f"sample design: {message}")
        # Failed sensitivity members stay absent from _sens_kpis_by_idx, so the
        # OAT/Sobol tables refuse to compute from a misaligned design (WR-02).

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
        if self._worst_project is not None:
            self._load_worst_btn.setEnabled(True)
        self._report_failures()

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
        self._sens_kpis_by_idx = {}
        self._sens_expected = 0
        self._sens_run_mode = mode
        self._failures = []
        self._sens_table.setRowCount(0)
        self._sens_status.setText("")
        self._progress.setValue(0)
        self._progress.setMaximum(0)   # busy until the design size is known
        self._set_running(True)
        seed = self._project.settings.random_seed & 0x7FFFFFFF
        self._thread = _EnsembleThread(
            base_project=copy.deepcopy(self._project),
            n_members=n,
            mode=mode,
            seed=seed,
        )
        self._thread.total_known.connect(self._on_sens_total_known)
        self._thread.step_done.connect(self._on_sens_step_done)
        self._thread.member_failed.connect(self._on_member_failed)
        self._thread.sweep_finished.connect(self._on_sens_finished)
        self._thread.start()

    def _on_sens_total_known(self, total: int) -> None:
        self._sens_expected = total
        self._progress.setMaximum(max(total, 1))

    def _on_sens_step_done(self, idx: int, result, proj: Project) -> None:
        self._progress.setValue(idx + 1)
        self._sens_kpis_by_idx[idx] = compute_scalar_kpis(result)

    def _on_sens_finished(self) -> None:
        self._set_running(False)
        if self._progress.maximum() == 0:
            self._progress.setMaximum(1)
        self._update_sens_table()
        self._report_failures()

    def _on_sens_mode_changed(self) -> None:
        sobol = "Sobol" in self._sens_mode_combo.currentText()
        self._sobol_n_spin.setEnabled(sobol and not self._is_running())

    def _on_sens_kpi_changed(self) -> None:
        if self._sens_kpis_by_idx and not self._is_running():
            self._update_sens_table()

    def _update_sens_table(self) -> None:
        """Dispatch on the mode the data was produced with (not the current combo)."""
        if self._sens_run_mode == "sobol":
            self._update_sobol_sensitivity_table()
        elif self._sens_run_mode == "oat":
            self._update_oat_sensitivity_table()

    def _complete_sens_kpis(self, expected: int) -> list[dict[str, float]] | None:
        """Return KPI dicts for indices 0..expected-1, or None if any is missing."""
        if expected <= 0:
            return None
        out = []
        for i in range(expected):
            k = self._sens_kpis_by_idx.get(i)
            if k is None:
                return None
            out.append(k)
        return out

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
        self._dist_plot.enableAutoRange()
        if len(kpi_values) >= 5:
            p5, p50, p95 = np.percentile(kpi_values, [5, 50, 95])
            self._p5_line.setValue(p5)
            self._p50_line.setValue(p50)
            self._p95_line.setValue(p95)
            for line in (self._p5_line, self._p50_line, self._p95_line):
                line.show()
            self._percentile_label.setText(f"P5: {p5:.4f} | P50: {p50:.4f} | P95: {p95:.4f}")

    # ------------------------------------------------------------------
    # Sensitivity table (Sensitivity Analysis tab)
    # ------------------------------------------------------------------

    def _fill_sens_table(self, rows: list[tuple[str, float]]) -> None:
        self._sens_table.setSortingEnabled(False)
        self._sens_table.setRowCount(len(rows))
        for row_idx, (pname, sv) in enumerate(rows):
            self._sens_table.setItem(row_idx, 0, QTableWidgetItem(pname))
            self._sens_table.setItem(row_idx, 1, QTableWidgetItem(f"{sv:.4f}"))
        self._sens_table.setSortingEnabled(True)

    def _update_oat_sensitivity_table(self) -> None:
        """Populate sensitivity table using OAT indices. index 0=baseline, 1..k=perturbed."""
        from backlight_sim.sim.ensemble import compute_oat_sensitivity, _active_tolerance_params
        params = _active_tolerance_params(self._project)
        if not params:
            self._sens_table.setRowCount(0)
            self._sens_status.setText("No active tolerance parameters (all sigmas are 0).")
            return
        kpis = self._complete_sens_kpis(len(params) + 1)
        if kpis is None:
            self._sens_table.setRowCount(0)
            self._sens_status.setText(
                "OAT run incomplete (cancelled or member failures) — sensitivity not computed."
            )
            return
        selected_key = _KPI_LABEL_TO_KEY[self._sens_kpi_combo.currentText()]
        sensitivity = compute_oat_sensitivity(
            kpis[0],
            kpis[1:],
            [p[0] for p in params],
            [p[1] for p in params],
        )
        sens_vals = sensitivity.get(selected_key, [0.0] * len(params))
        rows = sorted(zip([p[0] for p in params], sens_vals), key=lambda x: -x[1])
        self._fill_sens_table(rows)
        self._sens_status.setText("OAT: |ΔKPI| / σ per parameter.")

    def _update_sobol_sensitivity_table(self) -> None:
        """Populate sensitivity table using Sobol first-order Si indices."""
        from backlight_sim.sim.ensemble import compute_sobol_sensitivity, _active_tolerance_params
        params = _active_tolerance_params(self._project)
        if not params:
            self._sens_table.setRowCount(0)
            self._sens_status.setText("No active tolerance parameters (all sigmas are 0).")
            return
        k = len(params)
        all_kpis = self._complete_sens_kpis(self._sens_expected)
        if all_kpis is None:
            self._sens_table.setRowCount(0)
            self._sens_status.setText(
                "Sobol run incomplete (cancelled or member failures) — the Saltelli "
                "design needs every run, so indices were not computed."
            )
            return
        n_runs = len(all_kpis)
        # Expected Saltelli layout: N*(k+2) runs
        selected_key = _KPI_LABEL_TO_KEY[self._sens_kpi_combo.currentText()]
        kpi_col = np.array([kpis.get(selected_key, 0.0) for kpis in all_kpis])
        # N = n_runs / (k+2)
        N = n_runs // (k + 2)
        if N < 1:
            return
        kpi_matrix = kpi_col[:, np.newaxis]   # (n_runs, 1)
        param_matrix = np.zeros((n_runs, k))  # placeholder
        si_dict = compute_sobol_sensitivity(kpi_matrix, param_matrix, N, k)
        si_vals = si_dict.get("0", np.zeros(k))
        rows = sorted(zip([p[0] for p in params], si_vals), key=lambda x: -x[1])
        self._fill_sens_table(rows)
        self._sens_status.setText(f"Sobol first-order Si (N={N}, {n_runs} runs).")

    # ------------------------------------------------------------------
    # Worst-case drill-down (Distribution tab)
    # ------------------------------------------------------------------

    def _update_worst_case(self, selected_key: str) -> None:
        if not self._dist_all_kpis:
            return
        vals = [k.get(selected_key, np.nan) for k in self._dist_all_kpis]
        if all(np.isnan(v) for v in vals):
            return
        # Worst = minimum for higher-is-better KPIs, maximum for lower-is-better.
        if _KPI_HIGHER_IS_BETTER.get(selected_key, True):
            worst_idx = int(np.nanargmin(vals))
        else:
            worst_idx = int(np.nanargmax(vals))
        if worst_idx < len(self._dist_member_projects):
            self._worst_project = self._dist_member_projects[worst_idx]
            self._worst_val = float(vals[worst_idx])
            self._load_worst_btn.setText(
                f"Load worst case as variant ({selected_key}={self._worst_val:.4f})"
            )

    def _load_worst_case(self) -> None:
        if self._worst_project is None or self._worst_val is None:
            return
        selected_key = _KPI_LABEL_TO_KEY[self._dist_kpi_combo.currentText()]
        name = f"Ensemble worst ({selected_key}={self._worst_val:.4f})"
        self.save_variant.emit(name, self._worst_project)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _check_project_ready(self) -> bool:
        if not [s for s in self._project.sources if s.enabled]:
            QMessageBox.warning(self, "No Active Sources",
                                "Enable at least one source before running.")
            return False
        if not self._project.detectors:
            QMessageBox.warning(self, "No Detectors",
                                "Add at least one detector — ensemble KPIs are "
                                "computed on the first detector.")
            return False
        return True

    def _report_failures(self) -> None:
        if not self._failures or not self.isVisible():
            return
        QMessageBox.warning(
            self, "Ensemble Members Failed",
            f"{len(self._failures)} member(s) failed and were skipped:\n"
            + "\n".join(self._failures[:10]),
        )

    def _is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _set_running(self, running: bool) -> None:
        self._dist_run_btn.setEnabled(not running)
        self._sens_run_btn.setEnabled(not running)
        # Lock inputs that define/interpret the running design (WR-03).
        self._sens_mode_combo.setEnabled(not running)
        self._dist_n_spin.setEnabled(not running)
        self._sobol_n_spin.setEnabled(
            not running and "Sobol" in self._sens_mode_combo.currentText()
        )
        self._cancel_btn.setEnabled(running)

    def _cancel_ensemble(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.cancel()

    def done(self, result: int) -> None:
        # Close / Esc / window-X all route through done(): always stop the worker.
        from backlight_sim.gui.thread_utils import stop_thread
        stop_thread(self._thread)
        super().done(result)
