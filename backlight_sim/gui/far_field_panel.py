"""Far-field photometric panel — polar plot with C-plane overlays, KPI sidebar, IES/CSV export."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from backlight_sim.io.ies_parser import (
    compute_farfield_kpis,
    export_farfield_csv,
    export_ies,
)


# C-plane definitions: (label, phi_deg, color)
_C_PLANES = [
    ("C0",   0,   (0.2, 0.4, 1.0, 1.0)),
    ("C45",  45,  (0.8, 0.6, 0.0, 1.0)),
    ("C90",  90,  (0.8, 0.4, 0.0, 1.0)),
    ("C135", 135, (0.0, 0.7, 0.3, 1.0)),
    ("C180", 180, (0.4, 0.7, 1.0, 1.0)),
    ("C225", 225, (1.0, 0.8, 0.0, 1.0)),
    ("C270", 270, (1.0, 0.5, 0.1, 1.0)),
    ("C315", 315, (0.3, 0.9, 0.4, 1.0)),
]


class FarFieldPanel(QWidget):
    """Displays far-field polar plot with multi-slice C-plane overlay and KPI sidebar.

    Call ``show_result(sd, result)`` after a far-field simulation completes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sd = None
        self._result = None

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # ---- Left: polar plot + C-plane checkboxes ----
        left_widget = QWidget()
        left_vbox = QVBoxLayout(left_widget)
        left_vbox.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget(title="Far-field Polar Plot")
        self._plot.setAspectLocked(True)
        self._plot.setLabel("bottom", "cd (X)")
        self._plot.setLabel("left", "cd (Z)")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._curve_items: dict[str, pg.PlotDataItem] = {}
        left_vbox.addWidget(self._plot, 1)

        # C-plane checkboxes
        cplane_row = QHBoxLayout()
        self._cplane_checks: dict[str, QCheckBox] = {}
        for label, phi_deg, color in _C_PLANES:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.toggled.connect(self._on_cplane_toggled)
            self._cplane_checks[label] = cb
            cplane_row.addWidget(cb)
        cplane_row.addStretch()
        left_vbox.addLayout(cplane_row)

        main_layout.addWidget(left_widget, 1)

        # ---- Right: KPI sidebar ----
        right_widget = QWidget()
        right_widget.setMinimumWidth(180)
        right_widget.setMaximumWidth(240)
        right_vbox = QVBoxLayout(right_widget)
        right_vbox.setContentsMargins(4, 4, 4, 4)

        kpi_group = QGroupBox("KPIs")
        kpi_form = QFormLayout(kpi_group)
        self._kpi_labels: dict[str, QLabel] = {}
        for key in ("peak_cd", "total_lm", "beam_angle", "field_angle", "asymmetry"):
            lbl = QLabel("—")
            self._kpi_labels[key] = lbl
            title = key.replace("_", " ").title()
            kpi_form.addRow(f"{title}:", lbl)
        right_vbox.addWidget(kpi_group)
        right_vbox.addStretch()

        # Export buttons
        export_group = QGroupBox("Export")
        export_vbox = QVBoxLayout(export_group)
        self._export_ies_btn = QPushButton("Export IES")
        self._export_csv_btn = QPushButton("Export CSV")
        self._export_ies_btn.clicked.connect(self._do_export_ies)
        self._export_csv_btn.clicked.connect(self._do_export_csv)
        export_vbox.addWidget(self._export_ies_btn)
        export_vbox.addWidget(self._export_csv_btn)
        right_vbox.addWidget(export_group)

        main_layout.addWidget(right_widget)

        # Pre-create curve objects for each C-plane
        for label, phi_deg, color in _C_PLANES:
            pen = pg.mkPen(color=color, width=2)
            curve = self._plot.plot(pen=pen, name=label)
            self._curve_items[label] = curve

        # Add polar reference circles
        self._add_polar_guide_circles()

        self._update_buttons()

    def _add_polar_guide_circles(self):
        """Draw concentric reference circles on the polar plot."""
        for r in [0.25, 0.5, 0.75, 1.0]:
            theta = np.linspace(0, 2 * np.pi, 200)
            x = r * np.sin(theta)
            y = r * np.cos(theta)
            self._plot.plot(x, y, pen=pg.mkPen(color=(80, 80, 80), width=1, style=Qt.PenStyle.DashLine))

    def show_result(self, sd, result):
        """Update the panel with new far-field simulation results.

        Parameters
        ----------
        sd : SphereDetector
            The sphere detector (used for geometry reference).
        result : SphereDetectorResult
            The simulation result with candela_grid populated.
        """
        self._sd = sd
        self._result = result
        self._refresh_all()

    def _refresh_all(self):
        if self._result is None or self._result.candela_grid is None:
            return

        grid = np.asarray(self._result.candela_grid, dtype=float)
        n_theta, n_phi = grid.shape
        peak = grid.max()
        if peak <= 0:
            return

        # Normalized grid for plotting (radius = candela / peak)
        norm_grid = grid / peak

        # Theta angle centers (0..180 degrees)
        theta_centers = (np.arange(n_theta) + 0.5) * 180.0 / n_theta
        theta_rad = np.deg2rad(theta_centers)

        # Phi angle centers
        phi_centers = (np.arange(n_phi) + 0.5) * 360.0 / n_phi

        # Update curves for each C-plane
        for label, phi_deg, color in _C_PLANES:
            curve = self._curve_items[label]
            # Find nearest phi index
            phi_idx = int(np.argmin(np.abs(phi_centers - phi_deg)))
            r = norm_grid[:, phi_idx]

            # Polar: x = I * sin(theta), y = I * cos(theta)
            # Also mirror to negative theta (symmetric about vertical axis)
            x_pos = r * np.sin(theta_rad)
            y_pos = r * np.cos(theta_rad)
            x_neg = -x_pos[::-1]
            y_neg = y_pos[::-1]
            x = np.concatenate([x_neg, x_pos])
            y = np.concatenate([y_neg, y_pos])

            visible = self._cplane_checks[label].isChecked()
            curve.setData(x, y)
            curve.setVisible(visible)

        # Update KPI sidebar
        kpis = compute_farfield_kpis(grid, theta_centers)
        self._kpi_labels["peak_cd"].setText(f"{kpis['peak_cd']:.1f} cd")
        self._kpi_labels["total_lm"].setText(f"{kpis['total_lm']:.1f} lm")
        self._kpi_labels["beam_angle"].setText(f"{kpis['beam_angle']:.1f} deg")
        self._kpi_labels["field_angle"].setText(f"{kpis['field_angle']:.1f} deg")
        self._kpi_labels["asymmetry"].setText(f"{kpis['asymmetry']:.2f}")

        self._update_buttons()

    def _on_cplane_toggled(self, _checked: bool):
        if self._result is None:
            return
        for label, _phi, _color in _C_PLANES:
            curve = self._curve_items[label]
            curve.setVisible(self._cplane_checks[label].isChecked())

    def _update_buttons(self):
        has_result = (self._result is not None and
                      getattr(self._result, "candela_grid", None) is not None)
        self._export_ies_btn.setEnabled(has_result)
        self._export_csv_btn.setEnabled(has_result)

    def _do_export_ies(self):
        if self._result is None or self._result.candela_grid is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export IES", "far_field.ies", "IES files (*.ies);;All files (*)"
        )
        if not path:
            return
        grid = np.asarray(self._result.candela_grid, dtype=float)
        n_theta, n_phi = grid.shape
        theta_centers = (np.arange(n_theta) + 0.5) * 180.0 / n_theta
        total_lm = float(compute_farfield_kpis(grid, theta_centers)["total_lm"])
        try:
            export_ies(path, theta_centers, grid, total_lm)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Exported", f"IES file saved:\n{path}")
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", str(exc))

    def _do_export_csv(self):
        if self._result is None or self._result.candela_grid is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Far-field CSV", "far_field.csv",
            "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return
        grid = np.asarray(self._result.candela_grid, dtype=float)
        n_theta, n_phi = grid.shape
        theta_centers = (np.arange(n_theta) + 0.5) * 180.0 / n_theta
        phi_centers = (np.arange(n_phi) + 0.5) * 360.0 / n_phi
        try:
            export_farfield_csv(path, theta_centers, phi_centers, grid)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Exported", f"CSV file saved:\n{path}")
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", str(exc))
