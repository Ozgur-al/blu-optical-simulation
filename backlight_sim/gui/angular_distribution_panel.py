"""Angular distribution import/export, editing, and plotting panel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backlight_sim.io.angular_distributions import load_profile_csv, merge_default_profiles


class AngularDistributionPanel(QWidget):
    distributions_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._loading_table = False

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Distribution:"))
        self._selector = QComboBox()
        self._selector.currentTextChanged.connect(self._on_selection_changed)
        top.addWidget(self._selector, 1)
        self._import_btn = QPushButton("Import CSV/TXT")
        self._import_btn.clicked.connect(self._import_distribution)
        top.addWidget(self._import_btn)
        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._export_distribution)
        top.addWidget(self._export_btn)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_distribution)
        top.addWidget(self._delete_btn)
        layout.addLayout(top)

        self._meta = QLabel("No distribution loaded.")
        self._meta.setStyleSheet("color: gray;")
        layout.addWidget(self._meta)

        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("bottom", "Theta (deg)")
        self._plot.setLabel("left", "Relative Intensity")
        layout.addWidget(self._plot, 1)

        edit_box = QWidget()
        eg = QGridLayout(edit_box)
        eg.setContentsMargins(0, 0, 0, 0)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["theta_deg", "intensity"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        eg.addWidget(self._table, 0, 0, 1, 4)
        self._add_row_btn = QPushButton("Add Row")
        self._add_row_btn.clicked.connect(self._add_row)
        eg.addWidget(self._add_row_btn, 1, 0)
        self._remove_row_btn = QPushButton("Remove Row")
        self._remove_row_btn.clicked.connect(self._remove_row)
        eg.addWidget(self._remove_row_btn, 1, 1)
        self._apply_btn = QPushButton("Apply Table")
        self._apply_btn.clicked.connect(self._apply_table_to_distribution)
        eg.addWidget(self._apply_btn, 1, 2)
        self._duplicate_btn = QPushButton("Duplicate As...")
        self._duplicate_btn.clicked.connect(self._duplicate_distribution)
        eg.addWidget(self._duplicate_btn, 1, 3)
        layout.addWidget(edit_box, 1)

    def set_project(self, project):
        self._project = project
        if self._project is not None:
            merge_default_profiles(self._project)
        self.refresh()

    def refresh(self):
        names = sorted(self._project.angular_distributions.keys()) if self._project else []
        current = self._selector.currentText()
        blocker = QSignalBlocker(self._selector)
        self._selector.clear()
        self._selector.addItems(names)
        if current and current in names:
            self._selector.setCurrentText(current)
        del blocker
        if self._selector.count() > 0:
            self._on_selection_changed(self._selector.currentText())
        else:
            self._plot.clear()
            self._table.setRowCount(0)
            self._meta.setText("No distribution loaded.")

    def _unique_name(self, base: str) -> str:
        if self._project is None:
            return base
        name = base
        idx = 2
        while name in self._project.angular_distributions:
            name = f"{base}_{idx}"
            idx += 1
        return name

    def _table_points(self) -> tuple[np.ndarray, np.ndarray]:
        theta = []
        intensity = []
        for row in range(self._table.rowCount()):
            t_item = self._table.item(row, 0)
            i_item = self._table.item(row, 1)
            if t_item is None or i_item is None:
                continue
            try:
                t = float(t_item.text())
                i = float(i_item.text())
            except ValueError:
                continue
            theta.append(t)
            intensity.append(i)
        if len(theta) < 2:
            raise ValueError("Need at least two valid rows.")
        theta_arr = np.asarray(theta, dtype=float)
        intensity_arr = np.asarray(intensity, dtype=float)
        valid = np.isfinite(theta_arr) & np.isfinite(intensity_arr)
        theta_arr = np.clip(theta_arr[valid], 0.0, 180.0)
        intensity_arr = np.clip(intensity_arr[valid], 0.0, None)
        if theta_arr.size < 2:
            raise ValueError("Need at least two valid numeric rows.")
        order = np.argsort(theta_arr)
        return theta_arr[order], intensity_arr[order]

    def _fill_table(self, theta: np.ndarray, intensity: np.ndarray):
        self._loading_table = True
        self._table.setRowCount(0)
        for t, i in zip(theta, intensity):
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(f"{float(t):.6g}"))
            self._table.setItem(row, 1, QTableWidgetItem(f"{float(i):.6g}"))
        self._loading_table = False

    def _import_distribution(self):
        if self._project is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Angular Distribution",
            "",
            "Data files (*.csv *.txt);;All files (*)",
        )
        if not path:
            return
        try:
            profile = load_profile_csv(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return
        name = self._unique_name(Path(path).stem or "distribution")
        self._project.angular_distributions[name] = profile
        self.refresh()
        self._selector.setCurrentText(name)
        self.distributions_changed.emit()

    def _export_distribution(self):
        if self._project is None:
            return
        name = self._selector.currentText()
        if not name:
            return
        dist = self._project.angular_distributions.get(name)
        if not dist:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Angular Distribution",
            f"{name}.csv",
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return
        theta = np.asarray(dist.get("theta_deg", []), dtype=float)
        intensity = np.asarray(dist.get("intensity", []), dtype=float)
        table = np.column_stack([theta, intensity])
        np.savetxt(path, table, delimiter=",", header="theta_deg,intensity", comments="")

    def _delete_distribution(self):
        if self._project is None:
            return
        name = self._selector.currentText()
        if not name:
            return
        if name in ("isotropic", "lambertian", "batwing"):
            QMessageBox.warning(self, "Protected Profile", "Default profiles cannot be deleted.")
            return
        self._project.angular_distributions.pop(name, None)
        self.refresh()
        self.distributions_changed.emit()

    def _add_row(self):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem("0"))
        self._table.setItem(row, 1, QTableWidgetItem("0"))

    def _remove_row(self):
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._table.removeRow(row)

    def _apply_table_to_distribution(self):
        if self._project is None:
            return
        name = self._selector.currentText()
        if not name:
            return
        try:
            theta, intensity = self._table_points()
        except Exception as exc:
            QMessageBox.critical(self, "Invalid Table", str(exc))
            return
        self._project.angular_distributions[name] = {
            "theta_deg": theta.tolist(),
            "intensity": intensity.tolist(),
        }
        self._plot_distribution(name)
        self.distributions_changed.emit()

    def _duplicate_distribution(self):
        if self._project is None:
            return
        name = self._selector.currentText()
        if not name:
            return
        dist = self._project.angular_distributions.get(name)
        if not dist:
            return
        new_name = self._unique_name(f"{name}_copy")
        self._project.angular_distributions[new_name] = {
            "theta_deg": list(dist.get("theta_deg", [])),
            "intensity": list(dist.get("intensity", [])),
        }
        self.refresh()
        self._selector.setCurrentText(new_name)
        self.distributions_changed.emit()

    def _on_selection_changed(self, name: str):
        if self._loading_table:
            return
        self._plot_distribution(name)

    def _plot_distribution(self, name: str):
        self._plot.clear()
        if self._project is None or not name:
            self._meta.setText("No distribution loaded.")
            self._table.setRowCount(0)
            return
        dist = self._project.angular_distributions.get(name)
        if not dist:
            self._meta.setText("No distribution loaded.")
            self._table.setRowCount(0)
            return
        theta = np.asarray(dist.get("theta_deg", []), dtype=float)
        intensity = np.asarray(dist.get("intensity", []), dtype=float)
        if theta.size == 0 or intensity.size == 0:
            self._meta.setText("No data points.")
            self._table.setRowCount(0)
            return
        self._fill_table(theta, intensity)
        self._plot.plot(theta, intensity, pen=pg.mkPen((255, 160, 40), width=2))
        self._plot.plot(
            theta,
            intensity,
            pen=None,
            symbol="o",
            symbolSize=5,
            symbolBrush=(255, 160, 40),
        )
        self._meta.setText(
            f"{name}: {theta.size} points | theta [{float(theta.min()):.1f}, {float(theta.max()):.1f}] deg"
        )
