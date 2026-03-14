"""Angular distribution import/export, editing, and plotting panel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
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

        # View mode selector
        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("View:"))
        self._view_mode = QComboBox()
        self._view_mode.addItems(["Cartesian", "Polar", "Mirrored 2D", "3D Lobe"])
        self._view_mode.currentIndexChanged.connect(self._on_view_mode_changed)
        view_row.addWidget(self._view_mode)
        view_row.addStretch()
        layout.addLayout(view_row)

        # Stacked plots for different view modes
        self._plot_stack = QStackedWidget()

        # 0: Cartesian (theta vs I)
        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.25)
        self._plot.setLabel("bottom", "Theta (deg)")
        self._plot.setLabel("left", "Relative Intensity")
        self._plot_stack.addWidget(self._plot)

        # 1: Polar plot
        self._polar_plot = pg.PlotWidget()
        self._polar_plot.setAspectLocked(True)
        self._polar_plot.showGrid(x=True, y=True, alpha=0.15)
        self._polar_plot.setLabel("bottom", "X")
        self._polar_plot.setLabel("left", "Y")
        self._plot_stack.addWidget(self._polar_plot)

        # 2: Mirrored 2D (shows -90 to +90)
        self._mirror_plot = pg.PlotWidget()
        self._mirror_plot.showGrid(x=True, y=True, alpha=0.25)
        self._mirror_plot.setLabel("bottom", "Theta (deg)")
        self._mirror_plot.setLabel("left", "Relative Intensity")
        self._plot_stack.addWidget(self._mirror_plot)

        # 3: 3D lobe (using pyqtgraph.opengl)
        try:
            import pyqtgraph.opengl as gl
            self._lobe_view = gl.GLViewWidget()
            self._lobe_view.setBackgroundColor(30, 30, 40)
            self._lobe_view.setCameraPosition(distance=3, elevation=30, azimuth=45)
            self._plot_stack.addWidget(self._lobe_view)
            self._has_gl = True
        except Exception as exc:
            self._lobe_view = QLabel(f"OpenGL not available: {exc}")
            self._plot_stack.addWidget(self._lobe_view)
            self._has_gl = False
        self._lobe_item = None

        layout.addWidget(self._plot_stack, 1)

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

        # Normalization buttons
        norm_peak_btn = QPushButton("Norm: Peak=1")
        norm_peak_btn.setToolTip("Scale intensities so the maximum value equals 1.0")
        norm_peak_btn.clicked.connect(lambda: self._normalize("peak"))
        eg.addWidget(norm_peak_btn, 2, 0)
        norm_flux_btn = QPushButton("Norm: Flux=1")
        norm_flux_btn.setToolTip("Scale so ∫I(θ)·sin(θ)dθ = 1  (unit solid-angle flux)")
        norm_flux_btn.clicked.connect(lambda: self._normalize("flux"))
        eg.addWidget(norm_flux_btn, 2, 1)
        norm_range_btn = QPushButton("Norm: [0,1]")
        norm_range_btn.setToolTip("Min-max rescale intensities to [0, 1]")
        norm_range_btn.clicked.connect(lambda: self._normalize("range"))
        eg.addWidget(norm_range_btn, 2, 2)

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
            "All supported (*.csv *.txt *.ies *.ldt);;CSV/TXT (*.csv *.txt);;IES files (*.ies);;LDT files (*.ldt);;All files (*)",
        )
        if not path:
            return
        try:
            ext = Path(path).suffix.lower()
            if ext in (".ies", ".ldt"):
                from backlight_sim.io.ies_parser import load_ies_or_ldt
                profile = load_ies_or_ldt(path)
            else:
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

    def _normalize(self, mode: str):
        """Normalize the currently selected distribution in-place."""
        if self._project is None:
            return
        name = self._selector.currentText()
        if not name:
            return
        dist = self._project.angular_distributions.get(name)
        if not dist:
            return
        theta = np.asarray(dist.get("theta_deg", []), dtype=float)
        intensity = np.asarray(dist.get("intensity", []), dtype=float)
        if intensity.size == 0:
            return

        if mode == "peak":
            peak = float(intensity.max())
            if peak > 0:
                intensity = intensity / peak
        elif mode == "flux":
            # ∫I(θ)·sin(θ)·dθ  (trapezoid rule)
            theta_rad = np.radians(theta)
            total = float(np.trapezoid(intensity * np.sin(theta_rad), theta_rad))
            if total > 0:
                intensity = intensity / total
        elif mode == "range":
            mn, mx = float(intensity.min()), float(intensity.max())
            if mx > mn:
                intensity = (intensity - mn) / (mx - mn)

        self._project.angular_distributions[name] = {
            "theta_deg": theta.tolist(),
            "intensity": intensity.tolist(),
        }
        self._plot_distribution(name)
        self.distributions_changed.emit()

    def _on_view_mode_changed(self, idx: int):
        self._plot_stack.setCurrentIndex(idx)
        name = self._selector.currentText()
        if name:
            self._plot_distribution(name)

    def _on_selection_changed(self, name: str):
        if self._loading_table:
            return
        self._plot_distribution(name)

    def _plot_distribution(self, name: str):
        self._plot.clear()
        self._polar_plot.clear()
        self._mirror_plot.clear()
        if self._has_gl and self._lobe_item is not None:
            self._lobe_view.removeItem(self._lobe_item)
            self._lobe_item = None

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
        self._meta.setText(
            f"{name}: {theta.size} points | theta [{float(theta.min()):.1f}, {float(theta.max()):.1f}] deg"
        )

        mode = self._view_mode.currentIndex()
        pen = pg.mkPen((255, 160, 40), width=2)
        sym_opts = dict(pen=None, symbol="o", symbolSize=5, symbolBrush=(255, 160, 40))

        if mode == 0:
            # Cartesian
            self._plot.plot(theta, intensity, pen=pen)
            self._plot.plot(theta, intensity, **sym_opts)

        elif mode == 1:
            # Polar: convert (theta, I) to (x, y) in polar coords
            theta_rad = np.radians(theta)
            x = intensity * np.sin(theta_rad)
            y = intensity * np.cos(theta_rad)
            self._polar_plot.plot(x, y, pen=pen)
            self._polar_plot.plot(x, y, **sym_opts)
            # Draw reference circles
            for r in [0.25, 0.5, 0.75, 1.0]:
                circ_t = np.linspace(0, np.pi, 100)
                cx = r * np.sin(circ_t)
                cy = r * np.cos(circ_t)
                self._polar_plot.plot(cx, cy, pen=pg.mkPen((100, 100, 100, 80), width=1))
            # Axis lines
            self._polar_plot.plot([0, 0], [0, 1.1], pen=pg.mkPen((100, 100, 100, 120), width=1))
            self._polar_plot.plot([-1.1, 1.1], [0, 0], pen=pg.mkPen((100, 100, 100, 120), width=1))

        elif mode == 2:
            # Mirrored 2D: show -theta to +theta
            mirrored_theta = np.concatenate([-theta[::-1], theta])
            mirrored_i = np.concatenate([intensity[::-1], intensity])
            self._mirror_plot.plot(mirrored_theta, mirrored_i, pen=pen)
            self._mirror_plot.plot(mirrored_theta, mirrored_i, **sym_opts)
            self._mirror_plot.setLabel("bottom", "Theta (deg) — mirrored")

        elif mode == 3 and self._has_gl:
            # 3D lobe: revolution of I(theta) around Z axis
            import pyqtgraph.opengl as gl
            n_phi = 72
            theta_rad = np.radians(theta)
            phi = np.linspace(0, 2 * np.pi, n_phi)
            # Build mesh vertices
            verts = []
            faces = []
            for i, (t, inten) in enumerate(zip(theta_rad, intensity)):
                r = float(inten)
                z = r * np.cos(t)
                for j, p in enumerate(phi):
                    x = r * np.sin(t) * np.cos(p)
                    y = r * np.sin(t) * np.sin(p)
                    verts.append([x, y, z])

            verts = np.array(verts, dtype=np.float32)
            n_t = len(theta)
            for i in range(n_t - 1):
                for j in range(n_phi - 1):
                    v0 = i * n_phi + j
                    v1 = i * n_phi + j + 1
                    v2 = (i + 1) * n_phi + j
                    v3 = (i + 1) * n_phi + j + 1
                    faces.append([v0, v1, v2])
                    faces.append([v1, v3, v2])

            if verts.size > 0 and len(faces) > 0:
                faces = np.array(faces, dtype=np.uint32)
                # Color based on intensity (height)
                colors = np.zeros((len(faces), 4), dtype=np.float32)
                for fi, face in enumerate(faces):
                    avg_z = verts[face, 2].mean()
                    t = max(0, min(1, avg_z / max(intensity.max(), 1e-9)))
                    colors[fi] = [1.0 * t + 0.2, 0.6 * t + 0.1, 0.1, 0.85]

                mesh = gl.GLMeshItem(
                    vertexes=verts, faces=faces, faceColors=colors,
                    smooth=True, drawEdges=False, shader="shaded",
                )
                self._lobe_view.addItem(mesh)
                self._lobe_item = mesh
